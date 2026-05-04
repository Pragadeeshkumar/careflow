import uuid
from datetime import datetime, timezone
from app.extensions import db


class QueueType:
    LINEAR = "linear"      # normal FIFO
    PRIORITY = "priority"  # emergency / high triage score


class TokenStatus:
    WAITING = "waiting"
    CALLED = "called"        # doctor called this token
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"      # patient not present when called
    CANCELLED = "cancelled"


class QueueToken(db.Model):
    __tablename__ = "queue_tokens"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # ── Links ─────────────────────────────────────────────
    patient_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    appointment_id = db.Column(db.String(36), db.ForeignKey("appointments.id"), nullable=False, unique=True)
    doctor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)

    # ── Token identity ────────────────────────────────────
    token_number = db.Column(db.Integer, nullable=False)   # e.g. 42 — shown to patient
    queue_date = db.Column(db.Date, nullable=False, index=True)  # tokens reset each day
    queue_type = db.Column(db.String(20), default=QueueType.LINEAR, nullable=False)

    # ── Priority (for priority queue sorting) ─────────────
    # Lower number = served first.
    # Linear queue: priority_score = 1000 + token_number (pure FIFO)
    # Priority queue: priority_score = triage_score * -10 (higher triage → lower score → served first)
    priority_score = db.Column(db.Integer, default=1000, nullable=False)

    # ── Status + timing ───────────────────────────────────
    status = db.Column(db.String(20), default=TokenStatus.WAITING, nullable=False)
    issued_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    called_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # ── Notification tracking ─────────────────────────────
    # Records which countdown alerts have been sent (e.g. "4,3,2")
    alerts_sent = db.Column(db.String(20), default="", nullable=False)

    # ── Relationships ─────────────────────────────────────
    patient = db.relationship("User", back_populates="queue_tokens", foreign_keys=[patient_id])
    appointment = db.relationship("Appointment", back_populates="queue_token")

    def alerts_sent_list(self) -> list[int]:
        if not self.alerts_sent:
            return []
        return [int(x) for x in self.alerts_sent.split(",") if x]

    def mark_alert_sent(self, count: int):
        sent = self.alerts_sent_list()
        if count not in sent:
            sent.append(count)
            self.alerts_sent = ",".join(str(x) for x in sent)

    def to_dict(self, position: int = None):
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "token_number": self.token_number,
            "queue_type": self.queue_type,
            "status": self.status,
            "priority_score": self.priority_score,
            "queue_date": self.queue_date.isoformat(),
            "issued_at": self.issued_at.isoformat(),
            "called_at": self.called_at.isoformat() if self.called_at else None,
            "position": position,  # live position injected by queue engine
        }

    def __repr__(self):
        return f"<QueueToken #{self.token_number} {self.status}>"
