from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Appointment, Payment, PaymentStatus, User, UserRole
from app.routes.auth import role_required
import razorpay
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)

payment_bp = Blueprint("payment", __name__)

# Initialize Razorpay client (set in app context)
razorpay_client = None


def init_razorpay(app):
    """Initialize Razorpay with API keys."""
    global razorpay_client
    key_id = app.config.get("RAZORPAY_KEY_ID")
    key_secret = app.config.get("RAZORPAY_KEY_SECRET")
    
    if not key_id or not key_secret:
        logger.warning("Razorpay keys not configured")
        return None
    
    razorpay_client = razorpay.Client(auth=(key_id, key_secret))
    return razorpay_client


@payment_bp.route("/create-order", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def create_order():
    """
    Create a Razorpay payment order for an appointment.
    
    JSON body:
    {
        "appointment_id": "apt-uuid"
    }
    """
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    
    appointment_id = data.get("appointment_id")
    if not appointment_id:
        return jsonify({"error": "appointment_id required"}), 400
    
    # Get appointment
    apt = Appointment.query.filter_by(id=appointment_id, patient_id=patient_id).first()
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404
    
    # Get or create payment record
    payment = Payment.query.filter_by(appointment_id=appointment_id).first()
    if not payment:
        return jsonify({"error": "Payment record not found"}), 404
    
    if payment.status == PaymentStatus.PAID:
        return jsonify({"error": "Appointment already paid"}), 400
    
    # Create Razorpay order
    if not razorpay_client:
        return jsonify({"error": "Payment service unavailable"}), 503
    
    try:
        payment.amount = 1.00
        order_data = {
            "amount": 100,  # ₹1 in paise
            "currency": payment.currency,
            "receipt": f"apt_{appointment_id}",
            "notes": {
                "appointment_id": appointment_id,
                "patient_id": patient_id,
                "patient_email": apt.patient.email,
                "doctor_id": apt.doctor_id or "N/A",
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        # Save order ID and updated amount to payment
        payment.razorpay_order_id = order["id"]
        payment.status = PaymentStatus.CREATED
        db.session.commit()
        
        logger.info(f"Razorpay order created: {order['id']} for appointment {appointment_id}")
        
        return jsonify({
            "order_id": order["id"],
            "amount": float(payment.amount),
            "currency": payment.currency,
            "appointment_id": appointment_id,
            "key_id": razorpay_client.auth[0],  # Public key for client
        }), 201
    
    except Exception as e:
        logger.error(f"Razorpay order creation error: {e}")
        return jsonify({"error": "Failed to create payment order"}), 500
@payment_bp.route("/dev/force-enqueue", methods=["POST"])
@jwt_required()
def force_enqueue():
    """
    DEV ONLY: bypass payment and directly put patient in queue
    """
    from app.models import QueueToken
    from datetime import date
    from app.services.queue_engine import QueueEngine

    patient_id = get_jwt_identity()
    data = request.get_json() or {}

    appointment_id = data.get("appointment_id")
    if not appointment_id:
        return jsonify({"error": "appointment_id required"}), 400

    apt = Appointment.query.filter_by(id=appointment_id, patient_id=patient_id).first()
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404

    # ✅ mark appointment confirmed
    apt.status = "confirmed"

    # ✅ create token
    last_token = db.session.query(db.func.max(QueueToken.token_number)).scalar()
    next_token = (last_token or 0) + 1

    token = QueueToken(
        appointment_id=appointment_id,
        patient_id=patient_id,
        doctor_id=apt.doctor_id,
        token_number=next_token,
        queue_date=date.today(),
    )

    db.session.add(token)
    db.session.commit()

    # ✅ ADD TO REDIS QUEUE
    QueueEngine.enqueue_patient(
        appointment_id=appointment_id,
        patient_id=patient_id,
        is_priority=False
    )

    return jsonify({
        "message": "Added to queue (DEV bypass)",
        "token_number": next_token
    }), 200
@payment_bp.route("/verify", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def verify_payment():
    """
    Verify payment signature from Razorpay.
    
    JSON body:
    {
        "razorpay_order_id": "order_xxx",
        "razorpay_payment_id": "pay_xxx",
        "razorpay_signature": "signature_xxx"
    }
    """
    from app.models import QueueToken
    from datetime import date

    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    
    order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")
    signature = data.get("razorpay_signature")
    
    logger.info(f"Payment verification attempt - patient: {patient_id}, order: {order_id}")
    
    if not all([order_id, payment_id, signature]):
        logger.warning(f"Missing payment details for patient {patient_id}")
        return jsonify({"error": "Missing payment details"}), 400
    
    # Get payment record
    payment = Payment.query.filter_by(razorpay_order_id=order_id).first()
    if not payment:
        logger.warning(f"Payment not found for order {order_id}")
        return jsonify({"error": "Payment record not found"}), 404
    
    if payment.appointment.patient_id != patient_id:
        logger.warning(f"Unauthorized payment verification - patient {patient_id} vs {payment.appointment.patient_id}")
        return jsonify({"error": "Unauthorized"}), 403
    
    # Verify signature
    if not verify_razorpay_signature(order_id, payment_id, signature):
        logger.warning(f"Invalid Razorpay signature for order {order_id}")
        return jsonify({"error": "Payment verification failed"}), 400
    
    logger.info(f"Payment signature verified for order {order_id}")
    
    # Update payment status
    payment.razorpay_payment_id = payment_id
    payment.razorpay_signature = signature
    payment.status = PaymentStatus.PAID
    
    # Update appointment status
    apt = payment.appointment
    apt.status = "confirmed"
    logger.info(f"Appointment {apt.id} marked confirmed")

    # 🔥 CREATE QUEUE TOKEN (NEW LOGIC)
    existing = QueueToken.query.filter_by(
        appointment_id=payment.appointment_id
    ).first()

    if not existing:
        last_token = db.session.query(db.func.max(QueueToken.token_number)).scalar()
        next_token = (last_token or 0) + 1

        token = QueueToken(
            appointment_id=payment.appointment_id,
            patient_id=payment.patient_id,
            doctor_id=apt.doctor_id,
            token_number=next_token,
            queue_date=date.today(),
        )

        db.session.add(token)
        logger.info(f"Queue token created: #{next_token} for appointment {apt.id}")
    else:
        logger.info(f"Queue token already exists for appointment {apt.id}")
    
    # Commit everything together
    db.session.commit()
    
    logger.info(f"Payment verified: {payment_id} for appointment {payment.appointment_id}")
    
    return jsonify({
        "message": "Payment verified successfully",
        "payment_id": payment_id,
        "appointment_id": payment.appointment_id,
    }), 200


@payment_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    Razorpay webhook for payment events.
    This is called by Razorpay servers (not by client).
    """
    event_data = request.get_json()
    
    if not event_data:
        return jsonify({"error": "No data"}), 400
    
    event = event_data.get("event")
    
    try:
        if event == "payment.authorized":
            handle_payment_authorized(event_data["payload"]["payment"]["entity"])
        elif event == "payment.failed":
            handle_payment_failed(event_data["payload"]["payment"]["entity"])
        elif event == "order.paid":
            handle_order_paid(event_data["payload"]["order"]["entity"])
        
        return jsonify({"status": "processed"}), 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500


def handle_payment_authorized(payment_entity):
    """Handle successful payment authorization."""
    razorpay_payment_id = payment_entity.get("id")
    razorpay_order_id = payment_entity.get("order_id")
    
    payment = Payment.query.filter_by(razorpay_order_id=razorpay_order_id).first()
    if payment:
        payment.razorpay_payment_id = razorpay_payment_id
        payment.status = PaymentStatus.PAID
        
        apt = payment.appointment
        apt.status = "confirmed"
        
        db.session.commit()
        
        logger.info(f"Payment authorized via webhook: {razorpay_payment_id}")


def handle_payment_failed(payment_entity):
    """Handle failed payment."""
    razorpay_order_id = payment_entity.get("order_id")
    reason = payment_entity.get("description", "Unknown")
    
    payment = Payment.query.filter_by(razorpay_order_id=razorpay_order_id).first()
    if payment:
        payment.status = PaymentStatus.FAILED
        db.session.commit()
        
        logger.warning(f"Payment failed: {razorpay_order_id} - {reason}")


def handle_order_paid(order_entity):
    """Handle order paid event."""
    razorpay_order_id = order_entity.get("id")
    
    payment = Payment.query.filter_by(razorpay_order_id=razorpay_order_id).first()
    if payment and payment.status != PaymentStatus.PAID:
        payment.status = PaymentStatus.PAID
        payment.appointment.status = "confirmed"
        db.session.commit()
        
        logger.info(f"Order marked paid: {razorpay_order_id}")


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature."""
    if not razorpay_client:
        return False
    
    try:
        key_secret = razorpay_client.auth[1]
        message = f"{order_id}|{payment_id}"
        expected_signature = hmac.new(
            key_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return expected_signature == signature
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


@payment_bp.route("/history", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_payment_history():
    """Get patient's payment history."""
    patient_id = get_jwt_identity()
    
    payments = Payment.query.filter_by(patient_id=patient_id).order_by(
        Payment.created_at.desc()
    ).limit(50).all()
    
    return jsonify({
        "total": len(payments),
        "payments": [p.to_dict() for p in payments],
    }), 200


@payment_bp.route("/<payment_id>", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_payment(payment_id):
    """Get payment details."""
    patient_id = get_jwt_identity()
    
    payment = Payment.query.filter_by(id=payment_id, patient_id=patient_id).first()
    if not payment:
        return jsonify({"error": "Payment not found"}), 404
    
    result = payment.to_dict()
    result["appointment"] = payment.appointment.to_dict() if payment.appointment else None
    
    return jsonify(result), 200
