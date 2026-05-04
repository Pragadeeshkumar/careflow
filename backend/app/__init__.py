from flask import Flask, jsonify
from app.config import get_config
from app.extensions import db, migrate, jwt, socketio, cors, init_redis


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(get_config())

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    socketio.init_app(app, message_queue=app.config["SOCKETIO_MESSAGE_QUEUE"])
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    init_redis(app)

    with app.app_context():
        from app.models import User, Appointment, QueueToken, Payment

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.patient import patient_bp
    from app.routes.doctor import doctor_bp
    from app.routes.receptionist import receptionist_bp
    from app.routes.queue import queue_bp
    from app.routes.payment import init_razorpay, payment_bp
    from app.routes.chat import chat_bp, init_chatbot_model   # ✅ IMPORTANT
    from app.routes.triage import triage_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(patient_bp, url_prefix="/api/patient")
    app.register_blueprint(doctor_bp, url_prefix="/api/doctor")
    app.register_blueprint(receptionist_bp, url_prefix="/api/receptionist")
    app.register_blueprint(queue_bp, url_prefix="/api/queue")
    app.register_blueprint(payment_bp, url_prefix="/api/payment")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(triage_bp, url_prefix="/api/triage")

    # Razorpay
    init_razorpay(app)

    # ✅ CRITICAL: INIT CHATBOT
    init_chatbot_model(app)

    # Socket events
    from app.sockets import events

    from app.routes.web import web_bp
    app.register_blueprint(web_bp, url_prefix="/")

    @jwt.expired_token_loader
    def expired_token(_h, _d):
        return jsonify({"error": "Token expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token(_r):
        return jsonify({"error": "Invalid token"}), 401

    @jwt.unauthorized_loader
    def missing_token(_r):
        return jsonify({"error": "Authorization required"}), 401

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app