import requests
import time

BASE_URL = "http://192.168.0.105:5000/api"

PASSWORD = "test123"

# 🔥 PUT YOUR REAL EXPO TOKEN HERE
TEST_PUSH_TOKEN = "ExponentPushToken[c1MW6YKxbYluf7U76FV8Xw]"

# 🔥 EXISTING DOCTOR ACCOUNT
DOCTOR_EMAIL = "doctor@careflow.test"
DOCTOR_PASSWORD = "doctor123"


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
# LOGIN (PATIENT)
# -------------------------
def login(email):
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": PASSWORD
    })
    return res.json()["access_token"]


# -------------------------
# LOGIN (DOCTOR)
# -------------------------
def login_doctor():
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": DOCTOR_EMAIL,
        "password": DOCTOR_PASSWORD
    })

    if res.status_code != 200:
        print("❌ Doctor login failed:", res.text)
        exit()

    print("👨‍⚕️ Doctor logged in")
    return res.json()["access_token"]


# -------------------------
# SET PUSH TOKEN
# -------------------------
def set_push_token(token, push_token):
    res = requests.post(
        f"{BASE_URL}/patient/notifications/token",
        headers={"Authorization": f"Bearer {token}"},
        json={"fcm_token": push_token}
    )

    print("🔑 Push token set:", res.status_code)


# -------------------------
# CREATE APPOINTMENT
# -------------------------
def create_appointment(token):
    res = requests.post(
        f"{BASE_URL}/patient/book",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "doctor_id": "de12b019-7859-4d71-8fd8-26e86a603498",
            "scheduled_date": "2026-05-10",
            "scheduled_time": "10:00",
            "symptoms": "queue test"
        }
    )

    if res.status_code != 201:
        print("❌ Appointment error:", res.text)
        return None

    return res.json()["appointment"]["id"]


# -------------------------
# ENQUEUE (BYPASS PAYMENT)
# -------------------------
def enqueue(token, appointment_id):
    res = requests.post(
        f"{BASE_URL}/payment/dev/force-enqueue",
        headers={"Authorization": f"Bearer {token}"},
        json={"appointment_id": appointment_id}
    )

    print("🚀 Enqueued:", res.status_code)


# -------------------------
# CALL NEXT (DOCTOR)
# -------------------------
def call_next(doctor_token):
    res = requests.post(
        f"{BASE_URL}/doctor/call_next",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    print("📢 CALL:", res.status_code)

    if res.status_code != 200:
        print("❌ ERROR:", res.text)


# -------------------------
# MAIN TEST FLOW
# -------------------------
def main():
    users = []
    tokens = []
    appointments = []

    print("\n🔥 Creating users...\n")
    for i in range(1, 6):
        email = create_user(i)
        users.append(email)

    print("\n🔐 Logging in users...\n")
    for email in users:
        token = login(email)
        tokens.append(token)

    # 🔥 SET PUSH TOKEN FOR LAST USER (TARGET USER)
    print("\n🔑 Setting push token...\n")
    set_push_token(tokens[-1], TEST_PUSH_TOKEN)

    print("\n📅 Creating appointments...\n")
    for token in tokens:
        apt = create_appointment(token)
        if apt:
            appointments.append(apt)
        time.sleep(1)

    print("\n🚀 Enqueuing users...\n")
    for i in range(len(appointments)):
        enqueue(tokens[i], appointments[i])
        time.sleep(1)

    # 🔥 LOGIN DOCTOR (FIXES 403)
    doctor_token = login_doctor()

    print("\n📢 Calling patients...\n")

    # Call 4 times → triggers notifications
    for _ in range(4):
        call_next(doctor_token)
        time.sleep(3)

    print("\n✅ TEST COMPLETE\n")


if __name__ == "__main__":
    main()