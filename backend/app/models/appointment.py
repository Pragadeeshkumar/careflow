import uuid
from datetime import datetime, timezone
from app.extensions import db


class AppointmentStatus:
    PENDING_PAYMENT = "pending_payment"  # booked but not paid
    CONFIRMED = "confirmed"              # paid, waiting for queue
    IN_QUEUE = "in_queue"               # has a queue token
    IN_PROGRESS = "in_progress"         # doctor called them
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

    ALL = [
        PENDING_PAYMENT, CONFIRMED, IN_QUEUE,
        IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW,
    ]


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Participants ──────────────────────────────────────
    patient_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    doctor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)

    # ── Scheduling ────────────────────────────────────────
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.Time, nullable=False)

    # ── AI triage ─────────────────────────────────────────
    symptoms = db.Column(db.Text, nullable=True)          # raw patient input
    triage_score = db.Column(db.Integer, default=0)       # 0=normal, 1-10 = priority (10=highest)
    triage_summary = db.Column(db.Text, nullable=True)    # Gemini summary

    # ── Status ────────────────────────────────────────────
    status = db.Column(db.String(30), default=AppointmentStatus.PENDING_PAYMENT, nullable=False)
    notes = db.Column(db.Text, nullable=True)             # doctor notes post-consult

    # ── Booking fee ───────────────────────────────────────
    booking_fee = db.Column(db.Numeric(10, 2), default=1.00)

    # ── Meta ──────────────────────────────────────────────
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────
    patient = db.relationship("User", back_populates="appointments", foreign_keys=[patient_id])
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    queue_token = db.relationship("QueueToken", back_populates="appointment", uselist=False)
    payment = db.relationship("Payment", back_populates="appointment", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "scheduled_date": self.scheduled_date.isoformat(),
            "scheduled_time": self.scheduled_time.strftime("%H:%M"),
            "symptoms": self.symptoms,
            "triage_score": self.triage_score,
            "triage_summary": self.triage_summary,
            "status": self.status,
            "notes": self.notes,
            "booking_fee": float(self.booking_fee),
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<Appointment {self.id} status={self.status}>"
