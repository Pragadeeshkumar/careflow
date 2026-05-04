import uuid
from datetime import datetime, timezone
from app.extensions import db


class PaymentStatus:
    CREATED = "created"      # Razorpay order created
    PAID = "paid"            # webhook confirmed
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Links ─────────────────────────────────────────────
    patient_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    appointment_id = db.Column(db.String(36), db.ForeignKey("appointments.id"), nullable=False, unique=True)

    # ── Razorpay identifiers ──────────────────────────────
    razorpay_order_id = db.Column(db.String(100), unique=True, nullable=True)
    razorpay_payment_id = db.Column(db.String(100), unique=True, nullable=True)
    razorpay_signature = db.Column(db.String(255), nullable=True)

    # ── Amount ────────────────────────────────────────────
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(5), default="INR", nullable=False)

    # ── Status ────────────────────────────────────────────
    status = db.Column(db.String(20), default=PaymentStatus.CREATED, nullable=False)

    # ── Meta ──────────────────────────────────────────────
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────
    patient = db.relationship("User", back_populates="payments")
    appointment = db.relationship("Appointment", back_populates="payment")

    def to_dict(self):
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "razorpay_order_id": self.razorpay_order_id,
            "amount": float(self.amount),
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }

    def __repr__(self):
        return f"<Payment {self.razorpay_order_id} {self.status}>"
