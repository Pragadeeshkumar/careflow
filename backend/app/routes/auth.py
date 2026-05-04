from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from app.models.user import User, UserRole
from app.extensions import db
import logging
from functools import wraps

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


# ── Role-based access decorators ──────────────────────────
def role_required(required_role: str):
    """Decorator to require specific role."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") != required_role:
                return jsonify({"error": f"Role '{required_role}' required"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def roles_required(*allowed_roles):
    """Decorator to allow multiple roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            if claims.get("role") not in allowed_roles:
                return jsonify({"error": f"Unauthorized role. Allowed: {list(allowed_roles)}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Auth Routes ───────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user (patient, doctor, or receptionist).
    
    JSON body:
    {
        "email": "user@example.com",
        "password": "secure_password",
        "full_name": "John Doe",
        "phone": "+91999999999",
        "role": "patient",  # or "doctor" or "receptionist"
        "specialisation": "Cardiology",  # doctor only
        "date_of_birth": "1990-01-15",   # patient only
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    email = data.get("email")
    password = data.get("password")
    role = data.get("role", UserRole.PATIENT)
    full_name = data.get("full_name")

    if not all([email, password, full_name]):
        return jsonify({"error": "Missing required fields: email, password, full_name"}), 400

    if role not in UserRole.ALL:
        return jsonify({"error": f"Invalid role. Must be one of: {UserRole.ALL}"}), 400

    # Check existing user
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 409

    if data.get("phone"):
        existing_phone = User.query.filter_by(phone=data["phone"]).first()
        if existing_phone:
            return jsonify({"error": "Phone number already registered"}), 409

    # Create user
    user = User(
        email=email,
        role=role,
        full_name=full_name,
        phone=data.get("phone")
    )
    user.set_password(password)

    # Role-specific fields
    if role == UserRole.DOCTOR:
        user.specialisation = data.get("specialisation")
        user.license_number = data.get("license_number")
    elif role == UserRole.PATIENT:
        user.date_of_birth = data.get("date_of_birth")
        user.blood_group = data.get("blood_group")

    db.session.add(user)
    db.session.commit()

    logger.info(f"New {role} registered: {user.email}")

    # Generate tokens
    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role}
    )
    refresh_token = create_refresh_token(
        identity=user.id,
        additional_claims={"role": user.role}
    )

    return jsonify({
        "message": "Registration successful",
        "user": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login user and return JWT tokens with role claims.
    
    JSON body:
    {
        "email": "user@example.com",
        "password": "secure_password"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    email = data.get("email")
    password = data.get("password")

    if not all([email, password]):
        return jsonify({"error": "Missing email or password"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.is_active:
        return jsonify({"error": "User account is disabled"}), 403

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role}
    )
    refresh_token = create_refresh_token(
        identity=user.id,
        additional_claims={"role": user.role}
    )

    logger.info(f"Login successful: {user.email} ({user.role})")

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict()
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token."""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.is_active:
        return jsonify({"error": "User not found or inactive"}), 401

    access_token = create_access_token(
        identity=current_user_id,
        additional_claims={"role": user.role}
    )
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """Get current authenticated user info."""
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "user": user.to_dict(),
        "role": claims.get("role"),
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logout user (token blacklisting in production)."""
    current_user_id = get_jwt_identity()
    logger.info(f"User logged out: {current_user_id}")
    return jsonify({"message": "Logout successful"}), 200
