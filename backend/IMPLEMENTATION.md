# CareFlow Backend Implementation Guide

## Overview
Complete hospital queue management system with priority queueing, real-time updates, AI triage, and geofence monitoring.

---

## Architecture Summary

### Technology Stack
- **Backend**: Flask 3.0 + SQLAlchemy + Redis + Celery
- **Database**: PostgreSQL with Alembic migrations
- **Real-time**: Socket.IO + WebSocket
- **AI**: Gemini API for triage & chatbot
- **Payments**: Razorpay integration
- **Notifications**: Firebase Cloud Messaging (FCM)
- **Task Queue**: Celery with Redis broker
- **Authentication**: JWT with role-based claims

### Core Components

#### 1. Queue Engine (`services/queue_engine.py`)
```python
QueueEngine class with methods:
- enqueue_patient(appointment_id, is_priority, priority_score)
- get_next_patient() → appointment_id
- mark_called(appointment_id)
- mark_completed(appointment_id)
- get_position(appointment_id) → int
- get_queue_ahead(appointment_id) → int
- cancel_token(appointment_id)
```

**Data Structure**: 
- Priority Queue: Redis Sorted Set `queue:priority` (negate score for ordering)
- Linear Queue: Redis List `queue:linear` (FIFO)
- Position Cache: Redis Hash `queue:position` (O(1) lookups)
- State Store: Redis Hash `queue:state` (JSON per appointment)

**Complexity**: 
- Insert: O(log N)
- Position lookup: O(1)
- Next call: O(1)

---

## API Endpoints

### Authentication (`/api/auth/`)
```
POST   /register        Create new user (patient/doctor/receptionist)
POST   /login           Login and get JWT tokens
POST   /refresh         Refresh access token
GET    /me              Get current user info
POST   /logout          Logout
```

**Request Example**:
```json
{
  "email": "patient@example.com",
  "password": "secure_password",
  "full_name": "John Doe",
  "phone": "+91999999999",
  "role": "patient",
  "date_of_birth": "1990-01-15",
  "blood_group": "O+"
}
```

**Response**:
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "user": { "id": "uuid", "role": "patient", ... }
}
```

---

### Patient Routes (`/api/patient/`)
```
POST   /book                        Create appointment
GET    /history                     Get all appointments
GET    /appointments/<apt_id>       Get appointment details
GET    /queue/status                Get current queue position
GET    /profile                     Get patient profile
PUT    /profile                     Update profile
POST   /location                    Send GPS coordinates
GET    /health-summary              Get health history
```

**Patient Queue Status Response**:
```json
{
  "in_queue": true,
  "token_number": 42,
  "position": 3,
  "people_ahead": 2,
  "status": "waiting",
  "doctor": {
    "id": "doc-uuid",
    "name": "Dr. Smith",
    "specialisation": "Cardiology"
  }
}
```

---

### Doctor Routes (`/api/doctor/`)
```
GET    /queue                       View all queued patients
POST   /call_next                   Call next patient
POST   /complete/<apt_id>           Mark appointment complete
POST   /escalate/<apt_id>           Escalate to priority queue
GET    /profile                     Get doctor profile
GET    /patients/<doctor_id>        Get assigned patients
```

**Queue View Response**:
```json
{
  "total_queued": 15,
  "queue": [
    {
      "position": 1,
      "token_number": 42,
      "patient": { "id": "...", "name": "...", "phone": "..." },
      "symptoms": "Chest pain",
      "triage_score": 8,
      "is_priority": true
    },
    ...
  ]
}
```

---

### Receptionist Routes (`/api/receptionist/`)
```
GET    /appointments                Get appointments for date
POST   /issue_token/<apt_id>        Issue queue token
POST   /confirm_payment/<apt_id>    Confirm manual payment
POST   /cancel/<apt_id>             Cancel appointment
POST   /no_show/<apt_id>            Mark patient as no-show
GET    /queue/status                Get live queue status
GET    /appointments/<apt_id>/details Get appointment details
```

**Issue Token Request**:
```json
{
  "is_priority": false,
  "priority_score": 5
}
```

---

### Queue Routes (`/api/queue/`)
```
GET    /status/<apt_id>             Get position for appointment
GET    /state                       Full queue state (doctor/receptionist only)
GET    /today                       Today's queue
GET    /position/<apt_id>           Current position
GET    /stats                       Queue statistics (public)
GET    /compare-wait                Estimated wait times
```

---

### Payment Routes (`/api/payment/`)
```
POST   /create-order                Create Razorpay order
POST   /verify                      Verify payment signature
POST   /webhook                     Razorpay webhook (server-side)
GET    /history                     Payment history
GET    /<payment_id>                Payment details
```

**Create Order Response**:
```json
{
  "order_id": "order_9A33XWu170g0xg",
  "amount": 200,
  "currency": "INR",
  "key_id": "rzp_test_XXXXXX"
}
```

---

### Triage Routes (`/api/triage/`)
```
POST   /analyze                     Analyze symptoms & get priority score
GET    /symptoms-guide              Get emergency symptoms list
GET    /previous-scores/<patient_id> Get past triage scores
```

**Analyze Symptoms Request**:
```json
{
  "appointment_id": "apt-uuid",
  "symptoms": "Severe chest pain and shortness of breath"
}
```

**Response**:
```json
{
  "analysis": {
    "priority_score": 8,
    "summary": "Possible cardiac issue - urgent consultation needed",
    "recommendation": "Immediate doctor consultation",
    "emergency": true
  },
  "appointment_id": "apt-uuid"
}
```

---

### Chat Routes (`/api/chat/`)
```
POST   /message                     Send message to chatbot (streaming)
GET    /history                     Get conversation history
DELETE /clear-history               Clear history
GET    /faq                         Get FAQs (public)
```

**Message Request**:
```json
{
  "message": "What should I do about this chest pain?",
  "stream": true
}
```

**Streaming Response** (Server-Sent Events):
```
data: {"chunk": "Chest pain can be "}
data: {"chunk": "serious. I recommend "}
data: {"chunk": "consulting a doctor..."}
data: {"complete": true}
```

---

## WebSocket Events

### Client → Server
```javascript
// Connect with JWT
socket.emit('connect', { token: accessToken })

// Subscribe to appointment queue
socket.emit('subscribe_queue', { 
  appointment_id: 'apt-uuid',
  role: 'patient' 
})

// Get current position
socket.emit('get_queue_position', { 
  appointment_id: 'apt-uuid' 
})

// Doctor/receptionist request full queue
socket.emit('request_full_queue')
```

### Server → Client (Broadcasts)
```javascript
// Patient position update
socket.on('queue_position_update', (data) => {
  // { appointment_id, position, people_ahead }
})

// Patient called
socket.on('you_are_called', (data) => {
  // { appointment_id, token_number, message }
})

// Queue changed
socket.on('queue_state_changed', (data) => {
  // { queue: [...], total, timestamp }
})

// New token in queue
socket.on('new_token_in_queue', (data) => {
  // { appointment_id, token_number, position }
})
```

---

## Background Tasks (Celery)

### Scheduled Tasks
```
monitor_geofence()           Every 30 seconds
check_countdown_notifications() Every 15 seconds
send_appointment_reminders() Every 5 minutes
cleanup_expired_tokens()     Daily at 23:59
sync_queue_to_cache()        Every 60 seconds
```

### Running Celery Worker
```bash
# Terminal 1: Celery worker
celery -A app.celery_tasks worker --loglevel=info

# Terminal 2: Celery beat (scheduler)
celery -A app.celery_tasks beat --loglevel=info
```

---

## Notification Triggers

### Countdown Notifications (Position 4→3→2→1)
- Triggered automatically when patient approaches
- Sent via FCM push notification
- "You are #3 in the queue. Get ready!"

### Called Notification
- Sent when doctor calls patient
- "Token #42 Called! Please proceed to the consultation room."

### Geofence Alert
- Sent when patient leaves 200m radius while ≤4 positions away
- "Don't Leave! You'll lose your place in the queue."

### Payment Confirmation
- Sent after successful payment
- "Your booking fee of ₹200 has been received. You are now in the queue."

### Appointment Reminder
- Sent 30 minutes before appointment
- "Your appointment is in 30 minutes..."

---

## Database Schema

### Users Table
```sql
id (UUID PK)
role (patient/doctor/receptionist)
email (unique)
phone (unique)
full_name
password_hash
date_of_birth (patient only)
blood_group (patient only)
fcm_token (patient only)
last_lat, last_lng, last_location_at
specialisation (doctor only)
license_number (doctor only)
is_active
created_at, updated_at
```

### Appointments Table
```sql
id (UUID PK)
patient_id (FK users)
doctor_id (FK users)
scheduled_date
scheduled_time
symptoms (text)
triage_score (0-10)
triage_summary
status (pending_payment/confirmed/in_queue/in_progress/completed/cancelled/no_show)
notes
booking_fee (₹200 default)
created_at, updated_at
```

### QueueTokens Table
```sql
id (UUID PK)
patient_id, appointment_id (FK), doctor_id (FK)
token_number (daily counter)
queue_date
queue_type (linear/priority)
priority_score (for sorting)
status (waiting/called/in_progress/completed/skipped/cancelled)
issued_at, called_at, completed_at
alerts_sent (comma-separated: "4,3,2")
```

### Payments Table
```sql
id (UUID PK)
patient_id, appointment_id (FK)
razorpay_order_id, razorpay_payment_id, razorpay_signature
amount, currency (INR)
status (created/paid/failed/refunded)
created_at, paid_at
```

---

## Setup & Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/hospital_db

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ACCESS_TOKEN_EXPIRES_MINUTES=60

# Redis
REDIS_URL=redis://localhost:6379/0

# Gemini AI
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-1.5-flash

# Razorpay
RAZORPAY_KEY_ID=your-key-id
RAZORPAY_KEY_SECRET=your-key-secret

# Firebase FCM
FIREBASE_CREDENTIALS=path/to/firebase-credentials.json
```

### Initialize Database
```bash
cd backend
python run.py --migrate  # Run migrations
```

### Run Development Server
```bash
python run.py
# Server at http://localhost:5000
```

---

## Key Features Implemented

✅ **Queue Architecture**
- Dual queue system (linear FIFO + priority)
- O(log N) Redis sorted set operations
- Real-time position tracking with instant lookups

✅ **Authentication**
- JWT tokens with role claims
- Role-based route protection decorators
- Three user types: patient, doctor, receptionist

✅ **Patient Features**
- Appointment booking with payment
- Real-time queue position
- GPS location tracking
- Geofence alerts when leaving
- Health history
- Appointment management

✅ **Doctor Features**
- View live queue
- Call next patient
- Mark complete & add notes
- Escalate cases to priority
- View patient history

✅ **Receptionist Features**
- Manage appointments
- Issue queue tokens
- Confirm payments
- Mark no-shows
- View all queues

✅ **AI/ML**
- Symptom analysis with Gemini (emergency detection + scoring)
- Medical chatbot with streaming responses
- Safety guardrails for emergency guidance

✅ **Notifications**
- Firebase FCM push notifications
- Countdown alerts (4→3→2→1)
- Geofence violations
- Payment confirmation
- Appointment reminders

✅ **Real-time Updates**
- WebSocket connections for live queue
- Server-Sent Events for streaming chat
- Broadcast events for queue changes
- Position updates pushed to clients

✅ **Integration**
- Razorpay payment gateway
- Google Gemini AI API
- Firebase Cloud Messaging
- Celery background tasks

---

## Next Steps

1. **Database Migrations**: Set up Alembic for schema versioning
2. **Web Portal**: Create doctor/receptionist dashboards with HTML/Bootstrap
3. **React Native App**: Build mobile client with Expo
4. **Testing**: Write unit tests for queue engine, services, routes
5. **Deployment**: Containerize with Docker, deploy to cloud
6. **Monitoring**: Set up logging, error tracking, analytics

---

## Testing the API

### Using cURL
```bash
# Register patient
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"pat@ex.com","password":"pass123","full_name":"John","role":"patient"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pat@ex.com","password":"pass123"}'

# Get queue status
curl -X GET http://localhost:5000/api/queue/stats \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

## Troubleshooting

**Geofence not triggering**: Check Redis connection and patient.fcm_token is set

**Notifications not working**: Verify GEMINI_API_KEY and Firebase setup

**Queue position not updating**: Check Redis keys exist: `queue:priority`, `queue:linear`, `queue:position`

**WebSocket connection fails**: Ensure Socket.IO initialized in create_app()

**Payment verification fails**: Check Razorpay signature secret in .env
