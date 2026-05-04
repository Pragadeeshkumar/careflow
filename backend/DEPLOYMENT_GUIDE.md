# CareFlow Backend - Deployment & Troubleshooting

## 🚀 Deployment Checklist

### Pre-Deployment

- [ ] All environment variables set in `.env`
- [ ] PostgreSQL database created and migrated
- [ ] Redis server configured and running
- [ ] Razorpay API keys obtained and tested
- [ ] Gemini API key configured
- [ ] Firebase FCM credentials set up
- [ ] SSL certificates ready (for HTTPS)
- [ ] Load balancer configured (optional)

### Production Configuration

```bash
# .env for production
DEBUG=False
TESTING=False
DATABASE_URL=postgresql://user:pass@prod-db:5432/hospital_db
REDIS_URL=redis://redis-server:6379/0
JWT_SECRET_KEY=use-strong-random-key-here
SECRET_KEY=another-strong-random-key

# API Keys (never commit these!)
GEMINI_API_KEY=sk-xxxxx
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=xxxxx
```

### Database Migration

```bash
# In production environment
flask db upgrade
# This runs all pending Alembic migrations
```

### Running with Gunicorn (Production)

```bash
# Install Gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn --workers 4 --threads 2 --worker-class sync --bind 0.0.0.0:5000 run:app

# Or with gevent for async
pip install gevent gevent-websocket
gunicorn --workers 2 --worker-class gevent --worker-connections 1000 --bind 0.0.0.0:5000 run:app
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "run:app"]
```

```bash
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: hospital_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  backend:
    build: .
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres:5432/hospital_db
      REDIS_URL: redis://redis:6379/0
    ports:
      - "5000:5000"
    volumes:
      - ./.env:/app/.env

  celery_worker:
    build: .
    depends_on:
      - redis
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://postgres:password@postgres:5432/hospital_db
    command: celery -A app.celery_tasks worker --loglevel=info

  celery_beat:
    build: .
    depends_on:
      - redis
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://postgres:password@postgres:5432/hospital_db
    command: celery -A app.celery_tasks beat --loglevel=info

volumes:
  postgres_data:
```

```bash
# Deploy with Docker Compose
docker-compose up -d
```

---

## 🐛 Troubleshooting

### Issue: Redis Connection Error
```
Error: Connection refused [127.0.0.1:6379]
```

**Solutions**:
```bash
# Check if Redis is running
redis-cli ping
# Should return "PONG"

# Start Redis if not running
redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:7
```

### Issue: Database Connection Failed
```
Error: could not translate host name "localhost" to address
```

**Solutions**:
```bash
# Check PostgreSQL is running
psql postgres

# Create database if not exists
createdb hospital_db

# Set correct DATABASE_URL in .env
DATABASE_URL=postgresql://user:password@localhost:5432/hospital_db

# Run migrations
flask db upgrade
```

### Issue: JWT Token Invalid
```
Error: Invalid token or token expired
```

**Solutions**:
```python
# Check token is being sent correctly
headers = {"Authorization": f"Bearer {token}"}

# Token should come from /api/auth/login response

# Verify JWT_SECRET_KEY is set in .env
JWT_SECRET_KEY=your-secret-key

# Check token expiration time
JWT_ACCESS_TOKEN_EXPIRES_MINUTES=60

# Refresh token if expired
curl -X POST http://localhost:5000/api/auth/refresh \
  -H "Authorization: Bearer REFRESH_TOKEN"
```

### Issue: Queue Position Not Updating
```
Patient position doesn't change in real-time
```

**Solutions**:
```bash
# Check Redis keys exist
redis-cli
KEYS queue:*
# Should show queue:priority, queue:linear, queue:state, queue:position

# Clear and rebuild if corrupted
FLUSHDB  # WARNING: Clears all Redis data

# Restart Celery workers (they rebuild on start)
celery -A app.celery_tasks worker --loglevel=info
```

### Issue: Notifications Not Sending
```
FCM notifications not arriving on mobile
```

**Solutions**:
```bash
# Verify FCM token is set
curl -X GET http://localhost:5000/api/patient/profile \
  -H "Authorization: Bearer TOKEN" \
  | grep fcm_token

# Should show fcm_token with valid value

# Test notification manually
curl -X POST http://localhost:5000/api/patient/location \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 19.0760, "longitude": 72.8777}'
  # If in queue and close, should trigger geofence alert

# Check Celery logs for notification task
celery -A app.celery_tasks worker --loglevel=debug
```

### Issue: Razorpay Verification Fails
```
Error: Payment verification failed
```

**Solutions**:
```python
# Verify signature manually
import hmac
import hashlib

order_id = "order_abc123"
payment_id = "pay_xyz789"
signature = "abc123def456"
key_secret = os.getenv("RAZORPAY_KEY_SECRET")

message = f"{order_id}|{payment_id}"
expected = hmac.new(
    key_secret.encode(),
    message.encode(),
    hashlib.sha256
).hexdigest()

assert expected == signature  # Should match
```

### Issue: WebSocket Connection Fails
```
Error: WebSocket connection failed
```

**Solutions**:
```javascript
// Check Socket.IO initialization
const socket = io('http://localhost:5000', {
  auth: {
    token: accessToken
  }
});

socket.on('connect', () => {
  console.log('Connected');
});

socket.on('connect_error', (error) => {
  console.log('Connection error:', error);
});

// Enable debug logging
localStorage.debug = '*';
```

### Issue: Geofence Alert Not Triggering
```
Geofence violation detected but no notification
```

**Solutions**:
```bash
# Check Celery beat is running
ps aux | grep celery

# Should see both worker and beat processes

# Verify geofence task is scheduled
celery -A app.celery_tasks inspect scheduled

# Check geofence service configuration
# In geofence_service.py: HOSPITAL_LAT, HOSPITAL_LNG, HOSPITAL_RADIUS_METERS

# Manually test geofence check
curl -X POST http://localhost:5000/api/patient/location \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 19.0805, "longitude": 72.8761}'
  # Outside 200m radius should trigger
```

### Issue: High Memory Usage
```
Memory usage keeps increasing
```

**Solutions**:
```bash
# Monitor memory
watch -n 1 'redis-cli INFO memory'

# Clear expired keys manually
redis-cli FLUSHALL ASYNC

# Reduce queue history limit in app/sockets/events.py
# Change: redis_conn.ltrim(key, 0, 99)  # Keep last 100
# To:     redis_conn.ltrim(key, 0, 19)  # Keep last 20

# Restart Redis
redis-cli SHUTDOWN
redis-server
```

### Issue: Slow Queue Operations
```
Getting queue takes > 5 seconds
```

**Solutions**:
```bash
# Check Redis performance
redis-cli --latency

# Profile queue operations
curl -X GET "http://localhost:5000/api/queue/state?limit=10" \
  -H "Authorization: Bearer TOKEN"
# Add ?limit=10 to reduce results

# Verify Redis has enough memory
redis-cli INFO memory | grep used_memory_human

# Add database indexes
# Already done in models, verify with:
psql hospital_db -c "CREATE INDEX IF NOT EXISTS idx_queue_tokens_status ON queue_tokens(status);"
```

---

## 📊 Performance Tuning

### Database
```sql
-- Add indexes for common queries
CREATE INDEX idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_queue_tokens_status ON queue_tokens(status);
CREATE INDEX idx_queue_tokens_date ON queue_tokens(queue_date);
CREATE INDEX idx_payments_status ON payments(status);

-- Enable query logging
SET log_statement = 'all';
SET log_duration = true;
```

### Redis
```bash
# Optimize memory
# In redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persist data
save 900 1        # Save if 1 key changed in 900 sec
save 300 10       # Save if 10 keys changed in 300 sec
```

### Flask
```python
# Cache expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def get_hospital_boundary():
    return GeofenceService.get_hospital_boundary()
```

---

## 📈 Monitoring & Logging

### Application Logs
```bash
# Write logs to file
export LOG_FILE=logs/app.log
python run.py > $LOG_FILE 2>&1 &

# Monitor logs in real-time
tail -f logs/app.log | grep ERROR

# Count errors
grep ERROR logs/app.log | wc -l
```

### Database Monitoring
```bash
# Check slow queries
psql hospital_db

hospital_db=# SELECT query, calls, mean_exec_time 
               FROM pg_stat_statements 
               ORDER BY mean_exec_time DESC LIMIT 10;

hospital_db=# SELECT datname, numbackends 
               FROM pg_stat_database;
```

### Redis Monitoring
```bash
# Real-time stats
redis-cli info stats

# Monitor commands
redis-cli MONITOR

# Memory breakdown
redis-cli INFO memory

# Key space stats
redis-cli INFO keyspace
```

---

## 🔒 Security Hardening

### API Security
```python
# Add rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app, key_func=get_remote_address)

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    ...
```

### HTTPS
```bash
# Generate self-signed certificate for testing
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Run with HTTPS
gunicorn --certfile cert.pem --keyfile key.pem --bind 0.0.0.0:443 run:app
```

### SQL Injection Prevention
```python
# Use parameterized queries (SQLAlchemy ORM does this automatically)
# ✅ Safe
user = User.query.filter_by(email=email).first()

# ❌ Unsafe (never do this)
user = db.session.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

---

## 🧪 Health Checks

```bash
# Application health
curl http://localhost:5000/health

# Database health
curl http://localhost:5000/health/db

# Redis health
curl http://localhost:5000/health/redis

# Queue health
curl http://localhost:5000/api/queue/stats
```

---

## 📞 Emergency Recovery

### Database Backup
```bash
# Backup
pg_dump hospital_db > backup.sql

# Restore
psql hospital_db < backup.sql
```

### Redis Backup
```bash
# Backup (Redis does this automatically)
# File: dump.rdb

# Manual backup
redis-cli BGSAVE

# Restore
redis-server --appendonly yes
```

### Queue Reset (Emergency)
```bash
# Clear all queues (causes data loss!)
redis-cli
FLUSHDB
# Celery will rebuild on startup

# Or specific queues
DEL queue:priority queue:linear queue:position queue:state
```

---

## 📞 Support Resources

- **API Docs**: See `IMPLEMENTATION.md`
- **Architecture**: See `COMPLETION_SUMMARY.md`
- **Config**: Check `app/config.py`
- **Models**: Check `app/models/`
- **Services**: Check `app/services/`
- **Routes**: Check `app/routes/`

---

**Last Updated**: May 3, 2026
