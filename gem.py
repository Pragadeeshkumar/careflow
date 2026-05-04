import requests
import time

BASE = "http://192.168.0.105:5000/api"

PATIENT_EMAIL = "praga@example.com"
PATIENT_PASSWORD = "praga@123"

# 👇 MUST match your doctor list
DOCTOR_ID = "de12b019-7859-4d71-8fd8-26e86a603498"

# 👇 EXISTING DOCTOR ACCOUNT (IMPORTANT)
DOCTOR_EMAIL = "doctor@test.com"
DOCTOR_PASSWORD = "test123"


# -------------------------
# LOGIN
# -------------------------
def login(email, password):
    res = requests.post(f"{BASE}/auth/login", json={
        "email": email,
        "password": password
    })

    if res.status_code != 200:
        print("❌ Login failed:", res.text)
        return None

    return res.json()["access_token"]


# -------------------------
# CREATE APPOINTMENT
# -------------------------
def create_appointment(token):
    res = requests.post(
        f"{BASE}/patient/book",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "doctor_id": DOCTOR_ID,
            "scheduled_date": "2026-05-10",
            "scheduled_time": "10:00",
            "symptoms": "full pipeline test"
        }
    )

    print("\n📅 BOOK STATUS:", res.status_code)

    if res.status_code != 201:
        print("❌ Booking failed:", res.text)
        return None

    data = res.json()
    appointment_id = data["appointment"]["id"]

    print("✅ Appointment created:", appointment_id)
    return appointment_id


# -------------------------
# BYPASS PAYMENT → ENQUEUE
# -------------------------
def bypass_enqueue(token, appointment_id):
    res = requests.post(
        f"{BASE}/payment/dev/force-enqueue",
        headers={"Authorization": f"Bearer {token}"},
        json={"appointment_id": appointment_id}
    )

    print("\n🚀 ENQUEUE STATUS:", res.status_code)
    print("🚀 RESPONSE:", res.text)


# -------------------------
# CALL NEXT (DOCTOR)
# -------------------------
def call_next(doctor_token):
    res = requests.post(
        f"{BASE}/doctor/call_next",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    print("\n📢 CALL STATUS:", res.status_code)
    print("📢 RAW:", res.text)

    try:
        print("📢 JSON:", res.json())
    except:
        print("❌ Not JSON response")


# -------------------------
# MAIN FLOW
# -------------------------
def main():
    print("\n🔐 Logging in patient...\n")
    patient_token = login(PATIENT_EMAIL, PATIENT_PASSWORD)

    if not patient_token:
        return

    print("\n👨‍⚕️ Logging in doctor...\n")
    doctor_token = login(DOCTOR_EMAIL, DOCTOR_PASSWORD)

    if not doctor_token:
        print("❌ Doctor login failed")
        return

    print("\n📅 Creating appointment...\n")
    appointment_id = create_appointment(patient_token)

    if not appointment_id:
        return

    time.sleep(1)

    print("\n🚀 Bypassing payment...\n")
    bypass_enqueue(patient_token, appointment_id)

    time.sleep(2)

    # print("\n📢 Calling patient...\n")
    # call_next(doctor_token)

    print("\n✅ FULL PIPELINE DONE\n")


if __name__ == "__main__":
    main()