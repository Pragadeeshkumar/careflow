from app import create_app
from app.extensions import db
from app.models import User, UserRole


STAFF_USERS = [
    {
        "full_name": "Dr. CareFlow",
        "email": "doctor@careflow.test",
        "password": "doctor123",
        "role": UserRole.DOCTOR,
        "specialisation": "General Medicine",
        "license_number": "CF-DOC-001",
    },
    {
        "full_name": "CareFlow Reception",
        "email": "receptionist@careflow.test",
        "password": "reception123",
        "role": UserRole.RECEPTIONIST,
    },
]


app = create_app()


with app.app_context():
    for staff in STAFF_USERS:
        user = User.query.filter_by(email=staff["email"]).first()

        if not user:
            user = User(
                full_name=staff["full_name"],
                email=staff["email"],
                role=staff["role"],
            )
            db.session.add(user)

        user.full_name = staff["full_name"]
        user.role = staff["role"]
        user.phone = staff.get("phone")
        user.specialisation = staff.get("specialisation")
        user.license_number = staff.get("license_number")
        user.is_active = True
        user.set_password(staff["password"])

        print(f"Ready: {staff['role']} | {staff['email']} | password: {staff['password']}")

    db.session.commit()
