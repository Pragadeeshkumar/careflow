from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_cors import CORS
import redis as redis_client

# Initialised without app — bound in create_app()
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
cors = CORS()

# Redis connection — set up in create_app() after config is loaded
redis_conn: redis_client.Redis = None  # type: ignore


def init_redis(app):
    global redis_conn
    redis_conn = redis_client.from_url(
        app.config["REDIS_URL"], decode_responses=True
    )
    return redis_conn
