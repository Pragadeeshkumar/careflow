from app import create_app
from app.extensions import db, redis_conn
from app.models import User, Appointment, QueueToken, Payment
import redis

redis_conn = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)
EMAIL = "praga@example.com"

app = create_app()

with app.app_context():
    user = User.query.filter_by(email=EMAIL).first()

    if not user:
        print("❌ User not found")
        exit()

    user_id = user.id
    print("🔍 Clearing history for:", user.email)

    # 1. Get all appointments
    appointments = Appointment.query.filter_by(patient_id=user_id).all()
    appointment_ids = [a.id for a in appointments]

    # 2. Delete queue tokens
    QueueToken.query.filter(QueueToken.appointment_id.in_(appointment_ids)).delete(synchronize_session=False)

    # 3. Delete payments
    Payment.query.filter(Payment.appointment_id.in_(appointment_ids)).delete(synchronize_session=False)

    # 4. Delete appointments
    Appointment.query.filter_by(patient_id=user_id).delete()

    db.session.commit()

    # 5. Clear Redis queue + states
    for app_id in appointment_ids:
        redis_conn.hdel("queue_state", app_id)
        redis_conn.hdel("queue_position", app_id)
        redis_conn.lrem("linear_queue", 0, app_id)
        redis_conn.zrem("priority_queue", app_id)

    print("✅ All history cleared for user")