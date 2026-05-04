from flask import Blueprint, render_template

web_bp = Blueprint("web", __name__)

@web_bp.route("/")
def login():
    return render_template("login.html")

@web_bp.route("/register")
def register():
    return render_template("register.html")

@web_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@web_bp.route("/book")
def book():
    return render_template("book.html")

@web_bp.route("/payment")
def payment():
    return render_template("payment.html")

@web_bp.route("/queue")
def queue():
    return render_template("queue.html")

@web_bp.route("/doctor-dashboard")
def doctor_dashboard():
    return render_template("doctor_dashboard.html")

@web_bp.route("/receptionist-dashboard")
def receptionist_dashboard():
    return render_template("receptionist_dashboard.html")
