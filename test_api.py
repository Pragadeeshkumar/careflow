import requests
import time

BASE_URL = "http://192.168.0.105:5000/api"
PASSWORD = "test123"

DOCTOR_ID = "de12b019-7859-4d71-8fd8-26e86a603498"  # Dr CareFlow


# -------------------------
# CREATE USER
# -------------------------
def create_user(i):
    email = f"user{i}@test.com"

    requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": PASSWORD,
        "full_name": f"User {i}",
        "role": "patient"
    })

    return email


# -------------------------
# CREATE DOCTOR (IMPORTANT)
# -------------------------
def create_doctor():
    email = "doctor@test.com"

    requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": PASSWORD,
        "full_name": "Dr CareFlow",
        "role": "doctor",
        "specialisation": "General Medicine"
    })

    return email


# -------------------------
# LOGIN
# -------------------------
def login(email):
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": PASSWORD
    })
    return res.json()["access_token"]


# -------------------------
# CREATE APPOINTMENT
# -------------------------
def create_appointment(token):
    res = requests.post(
        f"{BASE_URL}/patient/book",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "doctor_id": DOCTOR_ID,
            "scheduled_date": "2026-05-10",
            "scheduled_time": "10:00",
            "symptoms": "test queue"
        }
    )

    if res.status_code != 201:
        print("❌ Appointment error:", res.text)
        return None

    return res.json()["appointment"]["id"]


# -------------------------
# ENQUEUE
# -------------------------
def enqueue(token, appointment_id):
    res = requests.post(
        f"{BASE_URL}/payment/dev/force-enqueue",
        headers={"Authorization": f"Bearer {token}"},
        json={"appointment_id": appointment_id}
    )

    print("🚀", res.json())


# -------------------------
# CALL NEXT (DOCTOR)
# -------------------------
# def call_next(doctor_token):
#     res = requests.post(
#         f"{BASE_URL}/doctor/call_next",
#         headers={"Authorization": f"Bearer {doctor_token}"}
#     )

#     print("STATUS:", res.status_code)
#     print("RAW:", res.text)   # 👈 IMPORTANT

#     try:
#         print("📢", res.json())
#     except:
#         print("❌ Not JSON response")


# -------------------------
# MAIN
# -------------------------
def main():
    users = []
    tokens = []
    appointments = []

    print("\n👨‍⚕️ Creating doctor...\n")
    doctor_email = create_doctor()
    doctor_token = login(doctor_email)

    print("\n🔥 Creating patients...\n")

    for i in range(1, 6):
        email = create_user(i)
        users.append(email)

    print("\n🔐 Logging in patients...\n")

    for email in users:
        tokens.append(login(email))

    print("\n📅 Booking appointments...\n")

    for token in tokens:
        apt = create_appointment(token)
        if apt:
            appointments.append(apt)
        time.sleep(0.5)

    print("\n🚀 Enqueue...\n")

    for i in range(len(appointments)):
        enqueue(tokens[i], appointments[i])
        time.sleep(0.5)

    print("\n⏳ Waiting for queue...\n")
    time.sleep(3)

    print("\n📢 Calling patients...\n")

    # for _ in range(3):
    #     call_next(doctor_token)
    #     time.sleep(2)

    print("\n✅ DONE\n")


if __name__ == "__main__":
    main()