from app import create_app
from app.extensions import db
from app.models import User, UserRole

app = create_app()

with app.app_context():
    # check if doctor already exists
    existing = User.query.filter_by(email="doctor@example.com").first()
    
    if existing:
        print("Doctor already exists:", existing.id)
    else:
        doctor = User(
            full_name="Dr. Strange",
            email="doctor@example.com",
            role=UserRole.DOCTOR,
            specialisation="General"
        )
        doctor.set_password("doctor123")

        db.session.add(doctor)
        db.session.commit()

        print("Doctor created successfully!")
        print("Doctor ID:", doctor.id)