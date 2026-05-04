from app import create_app
from app.extensions import db
from app.models import Payment, PaymentStatus, QueueToken
from datetime import datetime, timezone

app = create_app()

with app.app_context():
    payment = Payment.query.order_by(Payment.created_at.desc()).first()

    if not payment:
        print("No payments found.")
        exit()

    # mark as paid
    payment.status = PaymentStatus.PAID
    db.session.commit()
    print("Payment marked as PAID:", payment.id)

    # check existing queue token
    existing = QueueToken.query.filter_by(
        appointment_id=payment.appointment_id
    ).first()

    if existing:
        print("Queue token already exists:", existing.id)
    else:
        appointment = payment.appointment

        # get next token number
        last_token = db.session.query(db.func.max(QueueToken.token_number)).scalar()
        next_token = (last_token or 0) + 1

        token = QueueToken(
            appointment_id=payment.appointment_id,
            patient_id=payment.patient_id,
            doctor_id=appointment.doctor_id,   # ✅ REQUIRED
            token_number=next_token,
            queue_date=datetime.now(timezone.utc).date(),  # ✅ REQUIRED
        )

        db.session.add(token)
        db.session.commit()

        print("Queue token created!")
        print("Token number:", next_token)