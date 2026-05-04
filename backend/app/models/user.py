import uuid
from datetime import datetime, timezone
import bcrypt
from app.extensions import db


class UserRole:
    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"

    ALL = [PATIENT, DOCTOR, RECEPTIONIST]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role = db.Column(db.String(20), nullable=False)  # UserRole constant

    # ── Identity ──────────────────────────────────────────
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # ── Patient-only fields ───────────────────────────────
    date_of_birth = db.Column(db.Date, nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    # FCM token for push notifications
    fcm_token = db.Column(db.String(255), nullable=True)
    # Last known GPS coordinates (updated by mobile app)
    last_lat = db.Column(db.Float, nullable=True)
    last_lng = db.Column(db.Float, nullable=True)
    last_location_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # ── Doctor-only fields ────────────────────────────────
    specialisation = db.Column(db.String(120), nullable=True)
    license_number = db.Column(db.String(60), nullable=True)

    # ── Meta ──────────────────────────────────────────────
    is_active = db.Column(db.Boolean, default=True, nullable=False)
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
    appointments = db.relationship(
        "Appointment", back_populates="patient",
        foreign_keys="Appointment.patient_id", lazy="dynamic"
    )
    queue_tokens = db.relationship(
        "QueueToken", back_populates="patient",
        foreign_keys="QueueToken.patient_id", lazy="dynamic"
    )
    payments = db.relationship(
        "Payment", back_populates="patient", lazy="dynamic"
    )

    # ── Password helpers ──────────────────────────────────
    def set_password(self, plain: str):
        self.password_hash = bcrypt.hashpw(
            plain.encode(), bcrypt.gensalt()
        ).decode()

    def check_password(self, plain: str) -> bool:
        return bcrypt.checkpw(
            plain.encode(), self.password_hash.encode()
        )

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "blood_group": self.blood_group,
            "specialisation": self.specialisation,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<User {self.role}:{self.email}>"
