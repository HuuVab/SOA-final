#!/usr/bin/env python3
# Admin Service - Centralized administration for all microservices
# RESTful API using Flask

from flask import Flask, request, jsonify, Response
import requests
import os
import uuid
import hashlib
import logging
import jwt
from datetime import datetime, timedelta
from flask_cors import CORS
from functools import wraps
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
DB_SERVICE_URL = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
JWT_SECRET = os.environ.get('ADMIN_JWT_SECRET', 'admin-secret-key')  # Use a different secret for admin tokens
JWT_EXPIRATION = int(os.environ.get('ADMIN_JWT_EXPIRATION', 3600))  # 1 hour in seconds

# Service URLs - all the services the admin can interact with
SERVICE_URLS = {
    'customer': os.environ.get('CUSTOMER_SERVICE_URL', 'http://localhost:5000/api'),
    'cart': os.environ.get('CART_SERVICE_URL', 'http://localhost:5008/api'),
    'database': DB_SERVICE_URL,
    'email': os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002'),
    'media': os.environ.get('MEDIA_SERVICE_URL', 'http://localhost:5007/api'),
    'order': os.environ.get('ORDER_SERVICE_URL', 'http://localhost:5010/api'),
    'payment': os.environ.get('PAYMENT_SERVICE_URL', 'http://localhost:5009/api'),
    'promotion': os.environ.get('PROMOTION_SERVICE_URL', 'http://localhost:5006/api'),
    'storage': os.environ.get('STORAGE_SERVICE_URL', 'http://localhost:5005/api'),
}

# Initialize database tables for admin users
def initialize_admin_tables():
    """Initialize the admin users table in the database"""
    try:
        # Connect to database
        connect_response = requests.post(
            f"{DB_SERVICE_URL}/connect",
            json={"db_name": "/data/admin.sqlite"}
        )
        
        logger.info(f"Database connection: {connect_response.json()}")

        tables_response = requests.get(f"{DB_SERVICE_URL}/tables")
        tables = tables_response.json().get('tables', [])
        
        # Create admin_users table if it doesn't exist
        if 'admin_users' not in tables:
            admin_schema = {
                "user_id": "TEXT PRIMARY KEY",
                "username": "TEXT UNIQUE NOT NULL",
                "email": "TEXT UNIQUE NOT NULL",
                "password_hash": "TEXT NOT NULL",
                "first_name": "TEXT",
                "last_name": "TEXT",
                "is_active": "BOOLEAN DEFAULT 1",
                "is_superadmin": "BOOLEAN DEFAULT 0",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "last_login": "TIMESTAMP"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "admin_users", "columns": admin_schema}
            )
            
            logger.info(f"Admin users table initialization: {response.json()}")
            
        # Create admin_sessions table if it doesn't exist
        if 'admin_sessions' not in tables:
            session_schema = {
                "session_id": "TEXT PRIMARY KEY",
                "user_id": "TEXT NOT NULL",
                "token": "TEXT NOT NULL",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "expires_at": "TIMESTAMP NOT NULL",
                "ip_address": "TEXT",
                "user_agent": "TEXT",
                "FOREIGN KEY (user_id)": "REFERENCES admin_users(user_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "admin_sessions", "columns": session_schema}
            )
            
            logger.info(f"Admin sessions table initialization: {response.json()}")
        
        # Create admin_audit_log table if it doesn't exist
        if 'admin_audit_log' not in tables:
            audit_schema = {
                "log_id": "TEXT PRIMARY KEY",
                "user_id": "TEXT NOT NULL",
                "action": "TEXT NOT NULL",
                "service": "TEXT NOT NULL",
                "resource": "TEXT",
                "details": "TEXT",
                "ip_address": "TEXT",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (user_id)": "REFERENCES admin_users(user_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "admin_audit_log", "columns": audit_schema}
            )
            
            logger.info(f"Admin audit log table initialization: {response.json()}")
        
        # Create a default superadmin if none exists
        check_admin_response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            params={"condition": "is_superadmin = ?", "params": "1"}
        )
        
        if not check_admin_response.json().get('data', []):
            # Create a default superadmin
            default_admin = {
                "user_id": str(uuid.uuid4()),
                "username": "admin",
                "email": "admin@example.com",
                "password_hash": hash_password("admin123"),  # Change this in production!
                "first_name": "Admin",
                "last_name": "User",
                "is_active": True,
                "is_superadmin": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables/admin_users/data",
                json=default_admin
            )
            
            logger.info(f"Default superadmin creation: {response.json()}")
        
        return {"status": "success", "message": "Admin tables initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing admin tables: {str(e)}")
        return {"status": "error", "message": f"Error initializing admin tables: {str(e)}"}

# Initialize tables when the service starts
initialize_admin_tables()

# Helper functions
def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_admin_token(user_id, is_superadmin=False):
    """Generate a JWT for an admin user"""
    expiration = datetime.now() + timedelta(seconds=JWT_EXPIRATION)
    payload = {
        'user_id': user_id,
        'exp': int(expiration.timestamp()),
        'iat': int(datetime.now().timestamp()),
        'admin': True,
        'superadmin': is_superadmin
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token, expiration

def admin_required(f):
    """Decorator for endpoints that require admin authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check if the token is in the headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Admin token is missing'}), 401
        
        try:
            # Decode the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            
            # Check if admin flag is present
            if not payload.get('admin', False):
                return jsonify({'status': 'error', 'message': 'Not an admin token'}), 403
            
            user_id = payload['user_id']
            
            # Verify the token is in the database
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_sessions/data",
                params={"condition": "user_id = ? AND token = ?", "params": f"{user_id},{token}"}
            )
            
            session_data = response.json().get('data', [])
            if not session_data:
                return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401
            
            # Get admin user data
            user_response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_users/data",
                params={"condition": "user_id = ?", "params": user_id}
            )
            
            users = user_response.json().get('data', [])
            if not users or not users[0].get('is_active', False):
                return jsonify({'status': 'error', 'message': 'Admin account inactive or deleted'}), 401
            
            # Add the user_id to the kwargs
            kwargs['user_id'] = user_id
            kwargs['is_superadmin'] = payload.get('superadmin', False)
            
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'error', 'message': 'Admin token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'status': 'error', 'message': 'Invalid admin token'}), 401
        
        return f(*args, **kwargs)
    return decorated

def superadmin_required(f):
    """Decorator for endpoints that require superadmin privileges"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check if the token is in the headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Admin token is missing'}), 401
        
        try:
            # Decode the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            
            # Check if superadmin flag is present
            if not payload.get('superadmin', False):
                return jsonify({'status': 'error', 'message': 'Superadmin privileges required'}), 403
            
            user_id = payload['user_id']
            
            # Verify the token is in the database
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_sessions/data",
                params={"condition": "user_id = ? AND token = ?", "params": f"{user_id},{token}"}
            )
            
            session_data = response.json().get('data', [])
            if not session_data:
                return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401
            
            # Get admin user data and verify superadmin status
            user_response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_users/data",
                params={"condition": "user_id = ? AND is_superadmin = ?", "params": f"{user_id},1"}
            )
            
            users = user_response.json().get('data', [])
            if not users or not users[0].get('is_active', False):
                return jsonify({'status': 'error', 'message': 'Superadmin account inactive or privilege revoked'}), 403
            
            # Add the user_id to the kwargs
            kwargs['user_id'] = user_id
            
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'error', 'message': 'Admin token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'status': 'error', 'message': 'Invalid admin token'}), 401
        
        return f(*args, **kwargs)
    return decorated

def log_admin_action(user_id, action, service, resource=None, details=None):
    """Log an admin action to the audit log"""
    try:
        log_id = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_data = {
            "log_id": log_id,
            "user_id": user_id,
            "action": action,
            "service": service,
            "resource": resource,
            "details": details,
            "ip_address": request.remote_addr,
            "created_at": now
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/admin_audit_log/data",
            json=log_data
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to log admin action: {response.json()}")
    except Exception as e:
        logger.error(f"Error logging admin action: {str(e)}")

# Authentication routes
@app.route('/api/auth/login', methods=['POST'])
def admin_login():
    """Login as an admin user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'username' not in data or 'password' not in data:
            return jsonify({"status": "error", "message": "Username and password are required"}), 400
        
        username = data['username']
        password = data['password']
        
        # Hash the password
        password_hash = hash_password(password)
        
        # Find the admin user
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            params={"condition": "username = ?", "params": username}
        )
        
        users = response.json().get('data', [])
        if not users:
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401
        
        user = users[0]
        
        # Verify password
        if user['password_hash'] != password_hash:
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401
        
        # Check if user is active
        if not user.get('is_active', False):
            return jsonify({"status": "error", "message": "Account is inactive"}), 403
        
        # Generate token
        token, expiration = generate_admin_token(user['user_id'], user.get('is_superadmin', False))
        
        # Store session
        session_data = {
            "session_id": str(uuid.uuid4()),
            "user_id": user['user_id'],
            "token": token,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expiration.strftime("%Y-%m-%d %H:%M:%S"),
            "ip_address": request.remote_addr,
            "user_agent": request.user_agent.string if request.user_agent else None
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/admin_sessions/data",
            json=session_data
        )
        
        # Update last login
        update_data = {
            "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            json={"values": update_data, "condition": "user_id = ?", "params": [user['user_id']]}
        )
        
        # Log the login action
        log_admin_action(user['user_id'], "login", "admin", None, f"Admin login from {request.remote_addr}")
        
        # Return user info with token
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": {
                "user_id": user['user_id'],
                "username": user['username'],
                "email": user['email'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "is_superadmin": user.get('is_superadmin', False)
            },
            "token": token,
            "expires_at": expiration.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        logger.error(f"Error logging in admin: {str(e)}")
        return jsonify({"status": "error", "message": f"Error logging in: {str(e)}"}), 500

@app.route('/api/auth/logout', methods=['POST'])
@admin_required
def admin_logout(user_id, is_superadmin):
    """Logout an admin user by invalidating their session"""
    try:
        # Get the token from the Authorization header
        auth_header = request.headers['Authorization']
        token = auth_header.split(' ')[1]
        
        # Delete the session from the database
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/admin_sessions/data",
            json={"condition": "user_id = ? AND token = ?", "params": [user_id, token]}
        )
        
        # Log the logout action
        log_admin_action(user_id, "logout", "admin")
        
        return jsonify({
            "status": "success",
            "message": "Logout successful"
        })
        
    except Exception as e:
        logger.error(f"Error logging out admin: {str(e)}")
        return jsonify({"status": "error", "message": f"Error logging out: {str(e)}"}), 500

@app.route('/api/auth/validate-token', methods=['POST'])
def validate_admin_token():
    """Validate an admin JWT token"""
    try:
        data = request.get_json()
        
        if 'token' not in data:
            return jsonify({"status": "error", "message": "Token is required"}), 400
        
        token = data['token']
        
        try:
            # Decode the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user_id = payload['user_id']
            is_admin = payload.get('admin', False)
            is_superadmin = payload.get('superadmin', False)
            
            if not is_admin:
                return jsonify({'status': 'error', 'message': 'Not an admin token', 'valid': False}), 403
            
            # Verify the token is in the database
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_sessions/data",
                params={"condition": "user_id = ? AND token = ?", "params": f"{user_id},{token}"}
            )
            
            session_data = response.json().get('data', [])
            if not session_data:
                return jsonify({'status': 'error', 'message': 'Invalid or expired token', 'valid': False}), 401
            
            # Get admin user data
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_users/data",
                params={"condition": "user_id = ?", "params": user_id}
            )
            
            users = response.json().get('data', [])
            if not users:
                return jsonify({'status': 'error', 'message': 'Admin user not found', 'valid': False}), 404
            
            user = users[0]
            
            # Check if user is active
            if not user.get('is_active', False):
                return jsonify({'status': 'error', 'message': 'Admin account inactive', 'valid': False}), 403
            
            # Return user info
            return jsonify({
                'status': 'success',
                'message': 'Token is valid',
                'valid': True,
                'user': {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'email': user['email'],
                    'first_name': user['first_name'],
                    'last_name': user['last_name'],
                    'is_superadmin': user.get('is_superadmin', False)
                }
            })
            
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'error', 'message': 'Token has expired', 'valid': False}), 401
        except jwt.InvalidTokenError:
            return jsonify({'status': 'error', 'message': 'Invalid token', 'valid': False}), 401
        
    except Exception as e:
        logger.error(f"Error validating token: {str(e)}")
        return jsonify({"status": "error", "message": f"Error validating token: {str(e)}", "valid": False}), 500

# Admin management routes (superadmin only)
@app.route('/api/admins', methods=['GET'])
@superadmin_required
def get_all_admins(user_id):
    """Get all admin users (superadmin only)"""
    try:
        # Get all admin users
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data"
        )
        
        users = response.json().get('data', [])
        
        # Remove password hashes
        for user in users:
            user.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "admins": users
        })
        
    except Exception as e:
        logger.error(f"Error getting admin users: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admins', methods=['POST'])
@superadmin_required
def create_admin(user_id):
    """Create a new admin user (superadmin only)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
        
        # Check if username or email already exists
        check_response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            params={"condition": "username = ? OR email = ?", "params": f"{data['username']},{data['email']}"}
        )
        
        existing_users = check_response.json().get('data', [])
        if existing_users:
            existing_user = existing_users[0]
            if existing_user['username'] == data['username']:
                return jsonify({"status": "error", "message": "Username already exists"}), 409
            else:
                return jsonify({"status": "error", "message": "Email already exists"}), 409
        
        # Create new admin user
        new_admin = {
            "user_id": str(uuid.uuid4()),
            "username": data['username'],
            "email": data['email'],
            "password_hash": hash_password(data['password']),
            "first_name": data['first_name'],
            "last_name": data['last_name'],
            "is_active": data.get('is_active', True),
            "is_superadmin": data.get('is_superadmin', False),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            json=new_admin
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to create admin user"}), 500
        
        # Log the action
        log_admin_action(
            user_id, 
            "create_admin", 
            "admin", 
            new_admin['user_id'], 
            f"Created admin user: {new_admin['username']}, superadmin: {new_admin['is_superadmin']}"
        )
        
        # Remove password hash from response
        new_admin.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "message": "Admin user created successfully",
            "admin": new_admin
        })
        
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admins/<target_user_id>', methods=['PUT'])
@superadmin_required
def update_admin(user_id, target_user_id):
    """Update an admin user (superadmin only)"""
    try:
        data = request.get_json()
        
        # Check if target user exists
        check_response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            params={"condition": "user_id = ?", "params": target_user_id}
        )
        
        existing_users = check_response.json().get('data', [])
        if not existing_users:
            return jsonify({"status": "error", "message": "Admin user not found"}), 404
        
        existing_user = existing_users[0]
        
        # Prevent self-demotion
        if user_id == target_user_id and 'is_superadmin' in data and not data['is_superadmin']:
            return jsonify({"status": "error", "message": "You cannot remove your own superadmin privileges"}), 403
        
        # Check if updating to an existing username or email
        if 'username' in data or 'email' in data:
            username_condition = f"username = '{data.get('username')}'" if 'username' in data else None
            email_condition = f"email = '{data.get('email')}'" if 'email' in data else None
            
            condition = " OR ".join(filter(None, [username_condition, email_condition]))
            condition += f" AND user_id != '{target_user_id}'"
            
            check_response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_users/data",
                params={"condition": condition}
            )
            
            existing = check_response.json().get('data', [])
            if existing:
                if 'username' in data and existing[0]['username'] == data['username']:
                    return jsonify({"status": "error", "message": "Username already exists"}), 409
                else:
                    return jsonify({"status": "error", "message": "Email already exists"}), 409
        
        # Prepare update data
        update_data = {}
        allowed_fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_superadmin']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Update password if provided
        if 'password' in data and data['password']:
            update_data['password_hash'] = hash_password(data['password'])
        
        update_data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update user
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            json={"values": update_data, "condition": "user_id = ?", "params": [target_user_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to update admin user"}), 500
        
        # If user's active status is changed to inactive, invalidate all sessions
        if 'is_active' in update_data and not update_data['is_active']:
            requests.delete(
                f"{DB_SERVICE_URL}/tables/admin_sessions/data",
                json={"condition": "user_id = ?", "params": [target_user_id]}
            )
        
        # Log the action
        changes = ", ".join([f"{k}: {v}" for k, v in update_data.items() if k != 'password_hash'])
        log_admin_action(
            user_id,
            "update_admin",
            "admin",
            target_user_id,
            f"Updated admin user: {existing_user['username']}, changes: {changes}"
        )
        
        return jsonify({
            "status": "success",
            "message": "Admin user updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error updating admin user: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admins/<target_user_id>', methods=['DELETE'])
@superadmin_required
def delete_admin(user_id, target_user_id):
    """Delete an admin user (superadmin only)"""
    try:
        # Prevent self-deletion
        if user_id == target_user_id:
            return jsonify({"status": "error", "message": "You cannot delete your own account"}), 403
        
        # Check if target user exists
        check_response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            params={"condition": "user_id = ?", "params": target_user_id}
        )
        
        existing_users = check_response.json().get('data', [])
        if not existing_users:
            return jsonify({"status": "error", "message": "Admin user not found"}), 404
        
        existing_user = existing_users[0]
        
        # Delete user sessions first
        requests.delete(
            f"{DB_SERVICE_URL}/tables/admin_sessions/data",
            json={"condition": "user_id = ?", "params": [target_user_id]}
        )
        
        # Delete user
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            json={"condition": "user_id = ?", "params": [target_user_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to delete admin user"}), 500
        
        # Log the action
        log_admin_action(
            user_id,
            "delete_admin",
            "admin",
            target_user_id,
            f"Deleted admin user: {existing_user['username']}"
        )
        
        return jsonify({
            "status": "success",
            "message": "Admin user deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"Error deleting admin user: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Admin profile routes
@app.route('/api/profile', methods=['GET'])
@admin_required
def get_admin_profile(user_id, is_superadmin):
    """Get the admin user's profile"""
    try:
        # Get user data
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            params={"condition": "user_id = ?", "params": user_id}
        )
        
        users = response.json().get('data', [])
        if not users:
            return jsonify({"status": "error", "message": "Admin user not found"}), 404
        
        user = users[0]
        
        # Remove password hash
        user.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "admin": user
        })
        
    except Exception as e:
        logger.error(f"Error getting admin profile: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/profile', methods=['PUT'])
@admin_required
def update_admin_profile(user_id, is_superadmin):
    """Update the admin user's profile"""
    try:
        data = request.get_json()
        
        # Prevent modifying privileged fields
        forbidden_fields = ['user_id', 'is_superadmin', 'is_active', 'created_at']
        for field in forbidden_fields:
            if field in data:
                data.pop(field)
        
        # Check if updating to an existing username or email
        if 'username' in data or 'email' in data:
            username_condition = f"username = '{data.get('username')}'" if 'username' in data else None
            email_condition = f"email = '{data.get('email')}'" if 'email' in data else None
            
            condition = " OR ".join(filter(None, [username_condition, email_condition]))
            condition += f" AND user_id != '{user_id}'"
            
            check_response = requests.get(
                f"{DB_SERVICE_URL}/tables/admin_users/data",
                params={"condition": condition}
            )
            
            existing = check_response.json().get('data', [])
            if existing:
                if 'username' in data and existing[0]['username'] == data['username']:
                    return jsonify({"status": "error", "message": "Username already exists"}), 409
                else:
                    return jsonify({"status": "error", "message": "Email already exists"}), 409
        
        # Prepare update data
        update_data = {}
        allowed_fields = ['username', 'email', 'first_name', 'last_name']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Update password if provided
        if 'password' in data and data['password']:
            # Verify current password if provided
            if 'current_password' in data:
                # Get current password hash
                response = requests.get(
                    f"{DB_SERVICE_URL}/tables/admin_users/data",
                    params={"condition": "user_id = ?", "params": user_id}
                )
                
                users = response.json().get('data', [])
                if not users:
                    return jsonify({"status": "error", "message": "Admin user not found"}), 404
                
                current_hash = users[0]['password_hash']
                
                # Verify current password
                if hash_password(data['current_password']) != current_hash:
                    return jsonify({"status": "error", "message": "Current password is incorrect"}), 400
            
            update_data['password_hash'] = hash_password(data['password'])
        
        update_data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update user
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/admin_users/data",
            json={"values": update_data, "condition": "user_id = ?", "params": [user_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to update profile"}), 500
        
        # Log the action
        changes = ", ".join([f"{k}: {v}" for k, v in update_data.items() if k != 'password_hash'])
        log_admin_action(
            user_id,
            "update_profile",
            "admin",
            user_id,
            f"Updated own profile: {changes}"
        )
        
        return jsonify({
            "status": "success",
            "message": "Profile updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error updating admin profile: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Audit log routes
@app.route('/api/audit-logs', methods=['GET'])
@superadmin_required
def get_audit_logs(user_id):
    """Get admin audit logs (superadmin only)"""
    try:
        # Get query parameters for filtering
        user_filter = request.args.get('user_id')
        action_filter = request.args.get('action')
        service_filter = request.args.get('service')
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        
        conditions = []
        params = []
        
        if user_filter:
            conditions.append("user_id = ?")
            params.append(user_filter)
        
        if action_filter:
            conditions.append("action = ?")
            params.append(action_filter)
        
        if service_filter:
            conditions.append("service = ?")
            params.append(service_filter)
        
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)
        
        # Construct condition string if filters are applied
        condition = " AND ".join(conditions) if conditions else None
        params_str = ",".join(params) if params else None
        
        # Get logs with optional filtering
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/admin_audit_log/data",
            params={
                "condition": condition, 
                "params": params_str, 
                "order_by": "created_at DESC"
            }
        )
        
        logs = response.json().get('data', [])
        
        # Enrich logs with admin usernames
        admin_ids = list(set(log['user_id'] for log in logs))
        
        if admin_ids:
            admins_data = {}
            
            for admin_id in admin_ids:
                admin_response = requests.get(
                    f"{DB_SERVICE_URL}/tables/admin_users/data",
                    params={"condition": "user_id = ?", "params": admin_id}
                )
                
                admin_users = admin_response.json().get('data', [])
                if admin_users:
                    admins_data[admin_id] = {
                        'username': admin_users[0]['username'],
                        'email': admin_users[0]['email']
                    }
            
            for log in logs:
                if log['user_id'] in admins_data:
                    log['admin_user'] = admins_data[log['user_id']]
        
        return jsonify({
            "status": "success",
            "logs": logs
        })
        
    except Exception as e:
        logger.error(f"Error getting audit logs: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Health check
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_response = requests.get(f"{DB_SERVICE_URL}/health")
        db_status = db_response.status_code == 200
        
        # Check service connections
        service_status = {}
        for service_name, service_url in SERVICE_URLS.items():
            try:
                response = requests.get(f"{service_url}/health", timeout=2)
                service_status[service_name] = response.status_code == 200
            except:
                service_status[service_name] = False
        
        return jsonify({
            "status": "up",
            "service": "Admin API",
            "db_status": db_status,
            "services": service_status,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            "status": "error",
            "service": "Admin API",
            "message": str(e),
            "version": "1.0.0"
        }), 500

# Service proxy endpoints
@app.route('/api/proxy/<service>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@admin_required
def proxy_request(user_id, is_superadmin, service, endpoint):
    """
    Proxy requests to other services with admin authentication
    
    This endpoint allows admins to interact with all other services through a single API,
    enforcing admin authentication and logging all admin actions.
    """
    try:
        # Check if service exists
        if service not in SERVICE_URLS:
            return jsonify({"status": "error", "message": f"Service '{service}' not found"}), 404
        
        # Get the target service URL
        service_url = SERVICE_URLS[service]
        
        # Construct full URL
        full_url = f"{service_url}/{endpoint}"
        
        # Prepare headers, maintaining original headers except Host
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        # Get the request method
        method = request.method
        
        # Get query parameters
        params = request.args.to_dict()
        
        # Get request data (if any)
        data = request.get_data() if request.is_json else None
        
        # Log action type based on method and endpoint
        action = f"{method.lower()}_{endpoint}"
        
        # Make the proxied request
        response = requests.request(
            method=method,
            url=full_url,
            headers=headers,
            params=params,
            data=data,
            timeout=30  # Increased timeout for potentially slow operations
        )
        
        # Log the admin action
        log_admin_action(
            user_id,
            action,
            service,
            endpoint,
            f"Proxied {method} request to {service}/{endpoint}, status: {response.status_code}"
        )
        
        # Return the proxied response
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        logger.error(f"Error proxying request: {str(e)}")
        return jsonify({"status": "error", "message": f"Error proxying request: {str(e)}"}), 500

# Service-specific admin shortcuts
# These endpoints provide convenient shortcuts for common admin operations
# Storage Service Admin Endpoints

@app.route('/api/products', methods=['GET'])
@admin_required
def get_all_products(user_id, is_superadmin):
    """Get all products (admin shortcut)"""
    log_admin_action(user_id, "view_all_products", "storage", "products", "Retrieved all products")
    return proxy_request(user_id, is_superadmin, 'storage', 'products')

@app.route('/api/products/<product_id>', methods=['GET'])
@admin_required
def get_product(user_id, is_superadmin, product_id):
    """Get a specific product (admin shortcut)"""
    log_admin_action(user_id, "view_product", "storage", f"products/{product_id}", f"Retrieved product {product_id}")
    return proxy_request(user_id, is_superadmin, 'storage', f'products/{product_id}')

@app.route('/api/products', methods=['POST'])
@admin_required
def create_product(user_id, is_superadmin):
    """Create a new product (admin shortcut)"""
    data = request.get_json()
    log_admin_action(
        user_id, 
        "create_product", 
        "storage", 
        "products", 
        f"Created new product: {data.get('name', 'Unnamed')}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', 'products')

@app.route('/api/products/<product_id>', methods=['PUT'])
@admin_required
def update_product(user_id, is_superadmin, product_id):
    """Update a product (admin shortcut)"""
    data = request.get_json()
    log_admin_action(
        user_id, 
        "update_product", 
        "storage", 
        f"products/{product_id}", 
        f"Updated product {product_id}: {', '.join([f'{k}={v}' for k, v in data.items() if k != 'description'])}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'products/{product_id}')

@app.route('/api/products/<product_id>', methods=['DELETE'])
@admin_required
def delete_product(user_id, is_superadmin, product_id):
    """Delete a product (admin shortcut)"""
    log_admin_action(user_id, "delete_product", "storage", f"products/{product_id}", f"Deleted product {product_id}")
    return proxy_request(user_id, is_superadmin, 'storage', f'products/{product_id}')

@app.route('/api/products/search', methods=['GET'])
@admin_required
def search_products(user_id, is_superadmin):
    """Search for products (admin shortcut)"""
    query = request.args.get('q', '')
    log_admin_action(user_id, "search_products", "storage", "products/search", f"Searched for products with query: {query}")
    return proxy_request(user_id, is_superadmin, 'storage', f'products/search')

@app.route('/api/products/category/<category>', methods=['GET'])
@admin_required
def get_products_by_category(user_id, is_superadmin, category):
    """Get products by category (admin shortcut)"""
    log_admin_action(
        user_id, 
        "view_products_by_category", 
        "storage", 
        f"products/category/{category}", 
        f"Retrieved products in category: {category}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'products/category/{category}')

@app.route('/api/products/manufacturer/<manufacturer>', methods=['GET'])
@admin_required
def get_products_by_manufacturer(user_id, is_superadmin, manufacturer):
    """Get products by manufacturer (admin shortcut)"""
    log_admin_action(
        user_id, 
        "view_products_by_manufacturer", 
        "storage", 
        f"products/manufacturer/{manufacturer}", 
        f"Retrieved products by manufacturer: {manufacturer}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'products/manufacturer/{manufacturer}')

@app.route('/api/categories', methods=['GET'])
@admin_required
def get_categories(user_id, is_superadmin):
    """Get all product categories (admin shortcut)"""
    log_admin_action(user_id, "view_categories", "storage", "categories", "Retrieved all product categories")
    return proxy_request(user_id, is_superadmin, 'storage', 'categories')

@app.route('/api/manufacturers', methods=['GET'])
@admin_required
def get_manufacturers(user_id, is_superadmin):
    """Get all manufacturers (admin shortcut)"""
    log_admin_action(user_id, "view_manufacturers", "storage", "manufacturers", "Retrieved all manufacturers")
    return proxy_request(user_id, is_superadmin, 'storage', 'manufacturers')

# Product Image Management Endpoints

@app.route('/api/products/<product_id>/images', methods=['GET'])
@admin_required
def get_product_images(user_id, is_superadmin, product_id):
    """Get all images for a product (admin shortcut)"""
    log_admin_action(
        user_id, 
        "view_product_images", 
        "storage", 
        f"products/{product_id}/images", 
        f"Retrieved images for product {product_id}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'products/{product_id}/images')

@app.route('/api/products/<product_id>/images/upload', methods=['POST'])
@admin_required
def upload_product_image(user_id, is_superadmin, product_id):
    """Upload an image for a product (admin shortcut)"""
    log_admin_action(
        user_id, 
        "upload_product_image", 
        "storage", 
        f"products/{product_id}/images/upload", 
        f"Uploaded image for product {product_id}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'products/{product_id}/images/upload')

@app.route('/api/products/<product_id>/images/upload/multiple', methods=['POST'])
@admin_required
def upload_multiple_product_images(user_id, is_superadmin, product_id):
    """Upload multiple images for a product (admin shortcut)"""
    file_count = len(request.files.getlist('files[]'))
    log_admin_action(
        user_id, 
        "upload_multiple_product_images", 
        "storage", 
        f"products/{product_id}/images/upload/multiple", 
        f"Uploaded {file_count} images for product {product_id}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'products/{product_id}/images/upload/multiple')

@app.route('/api/product-images/<image_id>', methods=['GET'])
@admin_required
def get_product_image(user_id, is_superadmin, image_id):
    """Get a product image by ID (admin shortcut)"""
    log_admin_action(user_id, "view_product_image", "storage", f"images/{image_id}", f"Retrieved product image {image_id}")
    return proxy_request(user_id, is_superadmin, 'storage', f'images/{image_id}')

@app.route('/api/images/<image_id>', methods=['PUT'])
@admin_required
def update_product_image(user_id, is_superadmin, image_id):
    """Update an image (admin shortcut)"""
    data = request.get_json()
    log_admin_action(
        user_id, 
        "update_image", 
        "storage", 
        f"images/{image_id}", 
        f"Updated image {image_id}: {data}"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'images/{image_id}')

@app.route('/api/images/<image_id>', methods=['DELETE'])
@admin_required
def delete_product_image(user_id, is_superadmin, image_id):
    """Delete an image (admin shortcut)"""
    log_admin_action(user_id, "delete_image", "storage", f"images/{image_id}", f"Deleted image {image_id}")
    return proxy_request(user_id, is_superadmin, 'storage', f'images/{image_id}')

@app.route('/api/images/<image_id>/set-primary', methods=['PUT'])
@admin_required
def set_primary_image(user_id, is_superadmin, image_id):
    """Set an image as the primary image for its product (admin shortcut)"""
    log_admin_action(
        user_id, 
        "set_primary_image", 
        "storage", 
        f"images/{image_id}/set-primary", 
        f"Set image {image_id} as primary"
    )
    return proxy_request(user_id, is_superadmin, 'storage', f'images/{image_id}/set-primary')

@app.route('/api/storage/serve/<path:filepath>', methods=['GET'])
def serve_storage_file(filepath):
    """Serve storage files (pass-through proxy)"""
    # Note: This doesn't require admin privileges since files are typically served directly
    # to customers as well. However, we'll log the access.
    user_id = "anonymous"
    if 'Authorization' in request.headers:
        try:
            token = request.headers['Authorization'].split(' ')[1]
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user_id = payload.get('user_id', 'anonymous')
        except:
            pass
    
    log_admin_action(user_id, "access_file", "storage", f"storage/serve/{filepath}", f"Accessed file {filepath}")
    return proxy_request(None, False, 'storage', f'storage/serve/{filepath}')



# Order Service Admin Endpoints
# Add these to your admin-service/app.py file

@app.route('/api/orders', methods=['GET'])
@admin_required
def get_all_orders(user_id, is_superadmin):
    """Get all orders with optional filtering (admin shortcut)"""
    # Pass through all filter parameters
    status = request.args.get('status')
    customer_id = request.args.get('customer_id')
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    
    # Log the admin action with filter details
    filter_details = []
    if status:
        filter_details.append(f"status={status}")
    if customer_id:
        filter_details.append(f"customer_id={customer_id}")
    if date_from:
        filter_details.append(f"from={date_from}")
    if date_to:
        filter_details.append(f"to={date_to}")
    
    filter_str = ", ".join(filter_details) if filter_details else "no filters"
    log_admin_action(
        user_id, 
        "view_all_orders", 
        "order", 
        "admin/orders", 
        f"Retrieved all orders with filters: {filter_str}"
    )
    
    # Use the proxy request but preserve query parameters
    return proxy_request(user_id, is_superadmin, 'order', 'admin/orders')

@app.route('/api/orders/<order_id>', methods=['GET'])
@admin_required
def get_order_details(user_id, is_superadmin, order_id):
    """Get details for a specific order (admin shortcut)"""
    log_admin_action(
        user_id, 
        "view_order_details", 
        "order", 
        f"admin/orders/{order_id}", 
        f"Viewed details for order {order_id}"
    )
    return proxy_request(user_id, is_superadmin, 'order', f'admin/orders/{order_id}')

@app.route('/api/orders/<order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(user_id, is_superadmin, order_id):
    """Update an order's status (admin shortcut)"""
    data = request.get_json()
    
    status = data.get('status', 'unknown')
    tracking_info = ""
    if data.get('tracking_number'):
        tracking_info = f", tracking={data.get('tracking_number')}"
    if data.get('carrier'):
        tracking_info += f", carrier={data.get('carrier')}"
    
    log_admin_action(
        user_id, 
        "update_order_status", 
        "order", 
        f"admin/orders/{order_id}/status", 
        f"Updated order {order_id} status to '{status}'{tracking_info}"
    )
    return proxy_request(user_id, is_superadmin, 'order', f'admin/orders/{order_id}/status')

# Additional convenience endpoints

@app.route('/api/orders/by-status/<status>', methods=['GET'])
@admin_required
def get_orders_by_status(user_id, is_superadmin, status):
    """Get orders filtered by status (convenience method)"""
    log_admin_action(
        user_id, 
        "view_orders_by_status", 
        "order", 
        f"admin/orders?status={status}", 
        f"Retrieved orders with status '{status}'"
    )
    return proxy_request(user_id, is_superadmin, 'order', f'admin/orders?status={status}')

@app.route('/api/orders/by-customer/<customer_id>', methods=['GET'])
@admin_required
def get_orders_by_customer(user_id, is_superadmin, customer_id):
    """Get orders for a specific customer (convenience method)"""
    log_admin_action(
        user_id, 
        "view_customer_orders", 
        "order", 
        f"admin/orders?customer_id={customer_id}", 
        f"Retrieved orders for customer {customer_id}"
    )
    return proxy_request(user_id, is_superadmin, 'order', f'admin/orders?customer_id={customer_id}')

@app.route('/api/orders/statistics', methods=['GET'])
@admin_required
def get_order_statistics(user_id, is_superadmin):
    """Get order statistics (count by status, revenue, etc.)"""
    try:
        # Forward request to order service
        base_url = SERVICE_URLS.get('order', '')
        
        # Get orders data first
        orders_response = requests.get(
            f"{base_url}/admin/orders",
            headers={"Authorization": request.headers.get('Authorization')}
        )
        
        if orders_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": "Failed to retrieve orders data"
            }), orders_response.status_code
            
        orders_data = orders_response.json().get('orders', [])
        
        # Calculate statistics
        status_counts = {}
        total_revenue = 0
        recent_orders = 0
        now = datetime.now()
        
        for order in orders_data:
            # Count by status
            status = order.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Total revenue
            total_revenue += float(order.get('total_amount', 0))
            
            # Recent orders (last 30 days)
            try:
                created_at = datetime.strptime(order.get('created_at', ''), "%Y-%m-%d %H:%M:%S")
                if (now - created_at).days <= 30:
                    recent_orders += 1
            except:
                pass
        
        statistics = {
            "total_orders": len(orders_data),
            "status_counts": status_counts,
            "total_revenue": round(total_revenue, 2),
            "recent_orders": recent_orders
        }
        
        log_admin_action(
            user_id, 
            "view_order_statistics", 
            "order", 
            "statistics", 
            "Retrieved order statistics"
        )
        
        return jsonify({
            "status": "success",
            "statistics": statistics
        })
    except Exception as e:
        logger.error(f"Error getting order statistics: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/dashboard/recent-orders', methods=['GET'])
@admin_required
def get_recent_orders(user_id, is_superadmin):
    """Get recent orders for dashboard (convenience method)"""
    # Get limit from query params or default to 10
    limit = request.args.get('limit', 10)
    
    log_admin_action(
        user_id, 
        "view_recent_orders", 
        "order", 
        "dashboard/recent-orders", 
        f"Retrieved {limit} recent orders for dashboard"
    )
    
    # First get all orders 
    response = proxy_request(user_id, is_superadmin, 'order', 'admin/orders')
    
    # If response is a tuple (response, status_code), extract the response
    if isinstance(response, tuple):
        response_data = response[0]
    else:
        response_data = response
    
    try:
        # Parse the response data
        if hasattr(response_data, 'get_data'):
            data = json.loads(response_data.get_data(as_text=True))
        else:
            data = response_data
        
        # Extract orders
        orders = data.get('orders', [])
        
        # Sort by created_at (most recent first)
        orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Limit to the requested number
        recent_orders = orders[:int(limit)]
        
        # Return the recent orders
        return jsonify({
            "status": "success", 
            "orders": recent_orders
        })
    except Exception as e:
        logger.error(f"Error processing recent orders: {str(e)}")
        # Just return the original response if there was an error
        return response

@app.route('/api/dashboard/order-summary', methods=['GET'])
@admin_required
def get_order_summary(user_id, is_superadmin):
    """Get order summary for dashboard"""
    try:
        # Forward request to order service to get all orders
        base_url = SERVICE_URLS.get('order', '')
        
        orders_response = requests.get(
            f"{base_url}/admin/orders",
            headers={"Authorization": request.headers.get('Authorization')}
        )
        
        if orders_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": "Failed to retrieve orders data"
            }), orders_response.status_code
            
        orders_data = orders_response.json().get('orders', [])
        
        # Calculate summary data
        processing_count = sum(1 for order in orders_data if order.get('status') == 'processing')
        shipped_count = sum(1 for order in orders_data if order.get('status') == 'shipped')
        delivered_count = sum(1 for order in orders_data if order.get('status') == 'delivered')
        cancelled_count = sum(1 for order in orders_data if order.get('status') == 'cancelled')
        
        # Calculate total revenue
        total_revenue = sum(float(order.get('total_amount', 0)) for order in orders_data)
        
        # Count orders from last 30 days
        now = datetime.now()
        recent_count = 0
        recent_revenue = 0
        
        for order in orders_data:
            try:
                created_at = datetime.strptime(order.get('created_at', ''), "%Y-%m-%d %H:%M:%S")
                if (now - created_at).days <= 30:
                    recent_count += 1
                    recent_revenue += float(order.get('total_amount', 0))
            except:
                pass
        
        summary = {
            "total_orders": len(orders_data),
            "processing_orders": processing_count,
            "shipped_orders": shipped_count,
            "delivered_orders": delivered_count,
            "cancelled_orders": cancelled_count,
            "total_revenue": round(total_revenue, 2),
            "recent_orders": recent_count,
            "recent_revenue": round(recent_revenue, 2)
        }
        
        log_admin_action(
            user_id, 
            "view_order_summary", 
            "order", 
            "dashboard/order-summary", 
            "Retrieved order summary for dashboard"
        )
        
        return jsonify({
            "status": "success",
            "summary": summary
        })
    except Exception as e:
        logger.error(f"Error getting order summary: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Customer management shortcuts
# Customer Service Admin Endpoints

@app.route('/api/customers', methods=['GET'])
@admin_required
def get_all_customers(user_id, is_superadmin):
    """Get all customers with optional filtering (admin only)"""
    try:
        # Pass through query parameters for filtering
        email = request.args.get('email')
        name = request.args.get('name')
        verified = request.args.get('verified')
        
        # Format base query for database service
        condition = None
        params = []
        filter_desc = []
        
        # Build the condition and params for the database query
        if email:
            condition = "email LIKE ?"
            params.append(f"%{email}%")
            filter_desc.append(f"email contains '{email}'")
        
        if name:
            name_condition = "(first_name LIKE ? OR last_name LIKE ?)"
            if condition:
                condition += f" AND {name_condition}"
            else:
                condition = name_condition
            params.extend([f"%{name}%", f"%{name}%"])
            filter_desc.append(f"name contains '{name}'")
        
        if verified is not None:
            verified_value = 1 if verified.lower() == 'true' else 0
            if condition:
                condition += " AND email_verified = ?"
            else:
                condition = "email_verified = ?"
            params.append(str(verified_value))
            filter_desc.append(f"verified is {verified}")
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_all_customers", 
            "customer", 
            "customers",
            f"Retrieved all customers" + (f" with filters: {', '.join(filter_desc)}" if filter_desc else "")
        )
        
        # Make request to database service
        db_service_url = SERVICE_URLS.get('database')
        
        query_params = {}
        if condition:
            query_params["condition"] = condition
            query_params["params"] = ",".join(params)
        
        response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params=query_params
        )
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve customers"}), 500
            
        customers = response.json().get('data', [])
        
        # Remove sensitive information
        for customer in customers:
            customer.pop('password_hash', None)
        
        return jsonify({
            "status": "success", 
            "message": f"Retrieved {len(customers)} customers",
            "customers": customers
        })
    except Exception as e:
        logger.error(f"Error getting all customers: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>', methods=['GET'])
@admin_required
def get_customer_details(user_id, is_superadmin, customer_id):
    """Get detailed information about a specific customer (admin only)"""
    try:
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_customer_details", 
            "customer", 
            f"customers/{customer_id}", 
            f"Viewed details for customer {customer_id}"
        )
        
        # Get customer data from database
        db_service_url = SERVICE_URLS.get('database')
        
        response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve customer data"}), 500
            
        customers = response.json().get('data', [])
        
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Remove sensitive information
        customer.pop('password_hash', None)
        
        # Get customer's sessions
        sessions_response = requests.get(
            f"{db_service_url}/tables/customer_sessions/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        sessions = []
        if sessions_response.status_code == 200:
            sessions = sessions_response.json().get('data', [])
        
        # Get customer's orders if order service is available
        orders = []
        try:
            order_service_url = SERVICE_URLS.get('order')
            if order_service_url:
                orders_response = requests.get(
                    f"{order_service_url}/admin/orders?customer_id={customer_id}",
                    headers={"Authorization": request.headers.get('Authorization')}
                )
                
                if orders_response.status_code == 200:
                    orders = orders_response.json().get('orders', [])
        except Exception as e:
            logger.error(f"Error retrieving customer orders: {str(e)}")
        
        return jsonify({
            "status": "success",
            "customer": customer,
            "sessions": sessions,
            "orders": orders
        })
    except Exception as e:
        logger.error(f"Error getting customer details: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>', methods=['PUT'])
@admin_required
def update_customer(user_id, is_superadmin, customer_id):
    """Update customer information (admin only)"""
    try:
        data = request.get_json()
        
        # Prevent updating certain sensitive fields
        forbidden_fields = ['password_hash', 'customer_id', 'created_at']
        for field in forbidden_fields:
            if field in data:
                data.pop(field)
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log the admin action with details of what's being updated
        log_details = f"Updated customer {customer_id} fields: {', '.join(data.keys())}"
        log_admin_action(
            user_id, 
            "update_customer", 
            "customer", 
            f"customers/{customer_id}", 
            log_details
        )
        
        # Make update request to database service
        db_service_url = SERVICE_URLS.get('database')
        
        response = requests.put(
            f"{db_service_url}/tables/customers/data",
            json={"values": data, "condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to update customer"}), 500
        
        # Get updated customer data
        updated_response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = updated_response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found after update"}), 404
        
        customer = customers[0]
        customer.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "message": "Customer updated successfully",
            "customer": customer
        })
    except Exception as e:
        logger.error(f"Error updating customer: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(user_id, is_superadmin, customer_id):
    """Reset a customer's password (admin only)"""
    try:
        data = request.get_json()
        
        if 'new_password' not in data:
            return jsonify({"status": "error", "message": "New password is required"}), 400
        
        # Get customer data to ensure they exist
        db_service_url = SERVICE_URLS.get('database')
        
        response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Hash the new password
        new_password_hash = hash_password(data['new_password'])
        
        # Update password in database
        update_data = {
            "password_hash": new_password_hash,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.put(
            f"{db_service_url}/tables/customers/data",
            json={"values": update_data, "condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to reset password"}), 500
        
        # Invalidate all sessions
        requests.delete(
            f"{db_service_url}/tables/customer_sessions/data",
            json={"condition": "customer_id = ?", "params": [customer_id]}
        )
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "reset_password", 
            "customer", 
            f"customers/{customer_id}/reset-password", 
            f"Reset password for customer {customer_id} ({customer['email']})"
        )
        
        # Optionally, send a notification email
        try:
            email_service_url = SERVICE_URLS.get('email')
            email_service_api_key = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
            
            if email_service_url:
                requests.post(
                    f"{email_service_url}/send/notification",
                    json={
                        "email": customer['email'],
                        "subject": "Your password has been reset",
                        "message": (
                            f"Dear {customer['first_name']},\n\n"
                            "Your password has been reset by an administrator. "
                            "If you did not request this change, please contact our support team immediately.\n\n"
                            "Thank you,\nThe E-commerce Team"
                        )
                    },
                    headers={"X-API-Key": email_service_api_key}
                )
        except Exception as e:
            logger.error(f"Error sending password reset notification: {str(e)}")
        
        return jsonify({
            "status": "success",
            "message": "Password reset successfully"
        })
    except Exception as e:
        logger.error(f"Error resetting customer password: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>/verify-email', methods=['POST'])
@admin_required
def admin_verify_email(user_id, is_superadmin, customer_id):
    """Manually verify a customer's email (admin only)"""
    try:
        # Get customer data to ensure they exist
        db_service_url = SERVICE_URLS.get('database')
        
        response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Check if already verified
        if customer.get('email_verified', False):
            return jsonify({"status": "success", "message": "Email already verified"}), 200
        
        # Update verification status
        update_data = {
            "email_verified": True,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.put(
            f"{db_service_url}/tables/customers/data",
            json={"values": update_data, "condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to verify email"}), 500
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "verify_email", 
            "customer", 
            f"customers/{customer_id}/verify-email", 
            f"Manually verified email for customer {customer_id} ({customer['email']})"
        )
        
        # Optionally, send a welcome email
        try:
            email_service_url = SERVICE_URLS.get('email')
            email_service_api_key = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
            
            if email_service_url:
                requests.post(
                    f"{email_service_url}/send/welcome",
                    json={
                        "email": customer['email'],
                        "name": f"{customer['first_name']} {customer['last_name']}"
                    },
                    headers={"X-API-Key": email_service_api_key}
                )
        except Exception as e:
            logger.error(f"Error sending welcome email: {str(e)}")
        
        return jsonify({
            "status": "success",
            "message": "Email verified successfully"
        })
    except Exception as e:
        logger.error(f"Error verifying customer email: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>/sessions', methods=['GET'])
@admin_required
def get_customer_sessions(user_id, is_superadmin, customer_id):
    """Get all sessions for a specific customer (admin only)"""
    try:
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_customer_sessions", 
            "customer", 
            f"customers/{customer_id}/sessions", 
            f"Viewed sessions for customer {customer_id}"
        )
        
        # Get customer data to ensure they exist
        db_service_url = SERVICE_URLS.get('database')
        
        customer_response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = customer_response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        # Get sessions
        sessions_response = requests.get(
            f"{db_service_url}/tables/customer_sessions/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        if sessions_response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve sessions"}), 500
            
        sessions = sessions_response.json().get('data', [])
        
        return jsonify({
            "status": "success",
            "customer_id": customer_id,
            "email": customers[0]['email'],
            "sessions": sessions
        })
    except Exception as e:
        logger.error(f"Error getting customer sessions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>/sessions', methods=['DELETE'])
@admin_required
def invalidate_customer_sessions(user_id, is_superadmin, customer_id):
    """Invalidate all sessions for a specific customer (admin only)"""
    try:
        # Get customer data to ensure they exist
        db_service_url = SERVICE_URLS.get('database')
        
        customer_response = requests.get(
            f"{db_service_url}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = customer_response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        # Delete all sessions
        response = requests.delete(
            f"{db_service_url}/tables/customer_sessions/data",
            json={"condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to invalidate sessions"}), 500
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "invalidate_sessions", 
            "customer", 
            f"customers/{customer_id}/sessions", 
            f"Invalidated all sessions for customer {customer_id} ({customers[0]['email']})"
        )
        
        return jsonify({
            "status": "success",
            "message": "All sessions invalidated successfully"
        })
    except Exception as e:
        logger.error(f"Error invalidating customer sessions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/dashboard/customer-stats', methods=['GET'])
@admin_required
def get_customer_stats(user_id, is_superadmin):
    """Get customer statistics for dashboard (admin only)"""
    try:
        # Get all customers
        db_service_url = SERVICE_URLS.get('database')
        
        response = requests.get(
            f"{db_service_url}/tables/customers/data"
        )
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve customers"}), 500
            
        customers = response.json().get('data', [])
        
        # Calculate statistics
        total_customers = len(customers)
        verified_customers = sum(1 for c in customers if c.get('email_verified'))
        unverified_customers = total_customers - verified_customers
        
        # Calculate customers by registration date
        now = datetime.now()
        recent_customers = sum(1 for c in customers if (
            now - datetime.strptime(c.get('created_at', '2000-01-01'), "%Y-%m-%d %H:%M:%S")
        ).days <= 30)
        
        # Get active customers (with recent logins)
        active_customers = sum(1 for c in customers if (
            c.get('last_login') and 
            (now - datetime.strptime(c.get('last_login', '2000-01-01'), "%Y-%m-%d %H:%M:%S")).days <= 30
        ))
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_customer_stats", 
            "customer", 
            "dashboard/customer-stats", 
            "Viewed customer statistics for dashboard"
        )
        
        return jsonify({
            "status": "success",
            "stats": {
                "total_customers": total_customers,
                "verified_customers": verified_customers,
                "unverified_customers": unverified_customers,
                "recent_signups": recent_customers,
                "active_customers": active_customers
            }
        })
    except Exception as e:
        logger.error(f"Error getting customer statistics: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Media Service Admin Endpoints
# Article Management Endpoints

@app.route('/api/articles', methods=['GET'])
@admin_required
def get_all_articles(user_id, is_superadmin):
    """Get all articles with optional filtering (admin shortcut)"""
    # Pass through query parameters
    type = request.args.get('type')
    status = request.args.get('status')
    limit = request.args.get('limit', '10')
    offset = request.args.get('offset', '0')
    
    # Log the admin action with filter details
    filter_desc = []
    if type:
        filter_desc.append(f"type={type}")
    if status:
        filter_desc.append(f"status={status}")
    filter_str = ", ".join(filter_desc) if filter_desc else "no filters"
    
    log_admin_action(
        user_id, 
        "view_all_articles", 
        "media", 
        "articles", 
        f"Retrieved all articles with filters: {filter_str}, limit={limit}, offset={offset}"
    )
    
    # Use the proxy request but preserve query parameters
    return proxy_request(user_id, is_superadmin, 'media', 'articles')

@app.route('/api/articles/<article_id>', methods=['GET'])
@admin_required
def get_article_details(user_id, is_superadmin, article_id):
    """Get details for a specific article (admin shortcut)"""
    log_admin_action(
        user_id, 
        "view_article", 
        "media", 
        f"articles/{article_id}", 
        f"Viewed article {article_id}"
    )
    return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}')

@app.route('/api/articles', methods=['POST'])
@admin_required
def create_article(user_id, is_superadmin):
    """Create a new article (admin shortcut)"""
    try:
        data = request.get_json()
        
        # Log the admin action
        article_type = data.get('type', 'unknown')
        title = data.get('title', 'Untitled')
        
        log_admin_action(
            user_id, 
            "create_article", 
            "media", 
            "articles", 
            f"Created new {article_type}: {title}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', 'articles')
    except Exception as e:
        logger.error(f"Error creating article: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>', methods=['PUT'])
@admin_required
def update_article(user_id, is_superadmin, article_id):
    """Update an article (admin shortcut)"""
    try:
        data = request.get_json()
        
        # Log the admin action with key details
        update_fields = ", ".join(data.keys())
        
        log_admin_action(
            user_id, 
            "update_article", 
            "media", 
            f"articles/{article_id}", 
            f"Updated article {article_id}, fields: {update_fields}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}')
    except Exception as e:
        logger.error(f"Error updating article: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>', methods=['DELETE'])
@admin_required
def delete_article(user_id, is_superadmin, article_id):
    """Delete an article (admin shortcut)"""
    # Get article details first for logging
    try:
        article_response = requests.get(
            f"{SERVICE_URLS.get('media', '')}/articles/{article_id}"
        )
        
        article_title = "Unknown"
        if article_response.status_code == 200:
            article_data = article_response.json().get('data', {})
            article_title = article_data.get('title', 'Unknown')
        
        log_admin_action(
            user_id, 
            "delete_article", 
            "media", 
            f"articles/{article_id}", 
            f"Deleted article {article_id}: {article_title}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}')
    except Exception as e:
        logger.error(f"Error deleting article: {str(e)}")
        # Still try to delete even if we couldn't get the title
        log_admin_action(
            user_id, 
            "delete_article", 
            "media", 
            f"articles/{article_id}", 
            f"Deleted article {article_id}"
        )
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}')

@app.route('/api/articles/<article_id>/publish', methods=['PUT'])
@admin_required
def publish_article(user_id, is_superadmin, article_id):
    """Publish an article (admin shortcut)"""
    try:
        # Get article details first for logging
        article_response = requests.get(
            f"{SERVICE_URLS.get('media', '')}/articles/{article_id}"
        )
        
        article_title = "Unknown"
        if article_response.status_code == 200:
            article_data = article_response.json().get('data', {})
            article_title = article_data.get('title', 'Unknown')
        
        log_admin_action(
            user_id, 
            "publish_article", 
            "media", 
            f"articles/{article_id}/publish", 
            f"Published article {article_id}: {article_title}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/publish')
    except Exception as e:
        logger.error(f"Error publishing article: {str(e)}")
        # Still try to publish even if we couldn't get the title
        log_admin_action(
            user_id, 
            "publish_article", 
            "media", 
            f"articles/{article_id}/publish", 
            f"Published article {article_id}"
        )
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/publish')

@app.route('/api/articles/<article_id>/archive', methods=['PUT'])
@admin_required
def archive_article(user_id, is_superadmin, article_id):
    """Archive an article (admin shortcut)"""
    try:
        # Get article details first for logging
        article_response = requests.get(
            f"{SERVICE_URLS.get('media', '')}/articles/{article_id}"
        )
        
        article_title = "Unknown"
        if article_response.status_code == 200:
            article_data = article_response.json().get('data', {})
            article_title = article_data.get('title', 'Unknown')
        
        log_admin_action(
            user_id, 
            "archive_article", 
            "media", 
            f"articles/{article_id}/archive", 
            f"Archived article {article_id}: {article_title}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/archive')
    except Exception as e:
        logger.error(f"Error archiving article: {str(e)}")
        # Still try to archive even if we couldn't get the title
        log_admin_action(
            user_id, 
            "archive_article", 
            "media", 
            f"articles/{article_id}/archive", 
            f"Archived article {article_id}"
        )
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/archive')

@app.route('/api/articles/search', methods=['GET'])
@admin_required
def search_articles(user_id, is_superadmin):
    """Search for articles (admin shortcut)"""
    try:
        query = request.args.get('q', '')
        limit = request.args.get('limit', '10')
        offset = request.args.get('offset', '0')
        
        log_admin_action(
            user_id, 
            "search_articles", 
            "media", 
            "articles/search", 
            f"Searched for articles with query: '{query}', limit={limit}, offset={offset}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', 'articles/search')
    except Exception as e:
        logger.error(f"Error searching articles: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/featured', methods=['GET'])
@admin_required
def get_featured_articles(user_id, is_superadmin):
    """Get featured articles (admin shortcut)"""
    try:
        limit = request.args.get('limit', '5')
        
        log_admin_action(
            user_id, 
            "view_featured_articles", 
            "media", 
            "articles/featured", 
            f"Retrieved featured articles, limit={limit}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', 'articles/featured')
    except Exception as e:
        logger.error(f"Error getting featured articles: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Image Management Endpoints

@app.route('/api/articles/<article_id>/images', methods=['GET'])
@admin_required
def get_article_images(user_id, is_superadmin, article_id):
    """Get all images for an article (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_article_images", 
            "media", 
            f"articles/{article_id}/images", 
            f"Retrieved images for article {article_id}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/images')
    except Exception as e:
        logger.error(f"Error getting article images: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/media-images/<image_id>', methods=['GET'])
@admin_required
def get_media_image(user_id, is_superadmin, image_id):
    """Get a media/article image by ID (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_media_image", 
            "media", 
            f"images/{image_id}", 
            f"Retrieved media image {image_id}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'images/{image_id}')
    except Exception as e:
        logger.error(f"Error getting media image: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/images/upload', methods=['POST'])
@admin_required
def upload_article_image(user_id, is_superadmin, article_id):
    """Upload an image for an article (admin shortcut)"""
    try:
        # Check for file in request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part in request"}), 400
            
        file = request.files['file']
        filename = file.filename if file.filename else "unknown"
        
        log_admin_action(
            user_id, 
            "upload_article_image", 
            "media", 
            f"articles/{article_id}/images/upload", 
            f"Uploaded image '{filename}' for article {article_id}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/images/upload')
    except Exception as e:
        logger.error(f"Error uploading article image: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/images/upload/multiple', methods=['POST'])
@admin_required
def upload_multiple_article_images(user_id, is_superadmin, article_id):
    """Upload multiple images for an article (admin shortcut)"""
    try:
        # Check for files in request
        if 'files[]' not in request.files:
            return jsonify({"status": "error", "message": "No files part in request"}), 400
            
        files = request.files.getlist('files[]')
        file_count = len(files)
        
        log_admin_action(
            user_id, 
            "upload_multiple_article_images", 
            "media", 
            f"articles/{article_id}/images/upload/multiple", 
            f"Uploaded {file_count} images for article {article_id}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/images/upload/multiple')
    except Exception as e:
        logger.error(f"Error uploading multiple article images: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['PUT'])
@admin_required
def update_media_image(user_id, is_superadmin, image_id):
    """Update image metadata (admin shortcut)"""
    try:
        data = request.get_json()
        update_fields = ", ".join(data.keys())
        
        log_admin_action(
            user_id, 
            "update_image", 
            "media", 
            f"images/{image_id}", 
            f"Updated image {image_id}, fields: {update_fields}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'images/{image_id}')
    except Exception as e:
        logger.error(f"Error updating image: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['DELETE'])
@admin_required
def delete_media_image(user_id, is_superadmin, image_id):
    """Delete an image (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "delete_image", 
            "media", 
            f"images/{image_id}", 
            f"Deleted image {image_id}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'images/{image_id}')
    except Exception as e:
        logger.error(f"Error deleting image: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Tag Management Endpoints

@app.route('/api/tags', methods=['GET'])
@admin_required
def get_all_tags(user_id, is_superadmin):
    """Get all tags (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_all_tags", 
            "media", 
            "tags", 
            "Retrieved all article tags"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', 'tags')
    except Exception as e:
        logger.error(f"Error getting all tags: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tags/<tag_slug>/articles', methods=['GET'])
@admin_required
def get_articles_by_tag(user_id, is_superadmin, tag_slug):
    """Get articles by tag (admin shortcut)"""
    try:
        limit = request.args.get('limit', '10')
        offset = request.args.get('offset', '0')
        
        log_admin_action(
            user_id, 
            "view_articles_by_tag", 
            "media", 
            f"tags/{tag_slug}/articles", 
            f"Retrieved articles with tag '{tag_slug}', limit={limit}, offset={offset}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'tags/{tag_slug}/articles')
    except Exception as e:
        logger.error(f"Error getting articles by tag: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/tags', methods=['GET'])
@admin_required
def get_article_tags(user_id, is_superadmin, article_id):
    """Get tags for an article (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_article_tags", 
            "media", 
            f"articles/{article_id}/tags", 
            f"Retrieved tags for article {article_id}"
        )
        
        return proxy_request(user_id, is_superadmin, 'media', f'articles/{article_id}/tags')
    except Exception as e:
        logger.error(f"Error getting article tags: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Dashboard and Statistics

@app.route('/api/dashboard/media-stats', methods=['GET'])
@admin_required
def get_media_stats(user_id, is_superadmin):
    """Get media statistics for dashboard (admin only)"""
    try:
        # Get articles with status counts
        media_service_url = SERVICE_URLS.get('media', '')
        
        # Get articles
        articles_response = requests.get(f"{media_service_url}/articles?limit=1000")
        articles = []
        if articles_response.status_code == 200:
            articles = articles_response.json().get('data', [])
        
        # Calculate statistics
        total_articles = len(articles)
        published_count = sum(1 for a in articles if a.get('status') == 'published')
        draft_count = sum(1 for a in articles if a.get('status') == 'draft')
        archived_count = sum(1 for a in articles if a.get('status') == 'archived')
        
        article_count = sum(1 for a in articles if a.get('type') == 'article')
        news_count = sum(1 for a in articles if a.get('type') == 'news')
        
        # Get view counts
        total_views = sum(int(a.get('view_count', 0)) for a in articles)
        
        # Get featured articles count
        featured_count = sum(1 for a in articles if a.get('featured') == 1)
        
        # Get tags
        tags_response = requests.get(f"{media_service_url}/tags")
        tags_count = 0
        if tags_response.status_code == 200:
            tags = tags_response.json().get('data', [])
            tags_count = len(tags)
        
        # Calculate recent activity (last 30 days)
        now = datetime.now()
        recent_articles = sum(1 for a in articles if (
            a.get('created_at') and 
            (now - datetime.strptime(a.get('created_at'), "%Y-%m-%d %H:%M:%S")).days <= 30
        ))
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_media_stats", 
            "media", 
            "dashboard/media-stats", 
            "Retrieved media statistics for dashboard"
        )
        
        return jsonify({
            "status": "success",
            "stats": {
                "total_articles": total_articles,
                "published_articles": published_count,
                "draft_articles": draft_count,
                "archived_articles": archived_count,
                "articles_count": article_count,
                "news_count": news_count,
                "total_views": total_views,
                "featured_count": featured_count,
                "tags_count": tags_count,
                "recent_activity": recent_articles
            }
        })
    except Exception as e:
        logger.error(f"Error getting media statistics: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/dashboard/recent-articles', methods=['GET'])
@admin_required
def get_recent_articles(user_id, is_superadmin):
    """Get recent articles for dashboard (admin only)"""
    try:
        limit = int(request.args.get('limit', 5))
        
        # Get recent articles
        media_service_url = SERVICE_URLS.get('media', '')
        
        articles_response = requests.get(
            f"{media_service_url}/articles?limit=100"
        )
        
        articles = []
        if articles_response.status_code == 200:
            articles = articles_response.json().get('data', [])
        
        # Sort by created_at (most recent first)
        articles.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Limit to the requested number
        recent_articles = articles[:limit]
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_recent_articles", 
            "media", 
            "dashboard/recent-articles", 
            f"Retrieved {limit} recent articles for dashboard"
        )
        
        return jsonify({
            "status": "success",
            "articles": recent_articles
        })
    except Exception as e:
        logger.error(f"Error getting recent articles: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/dashboard/popular-articles', methods=['GET'])
@admin_required
def get_popular_articles(user_id, is_superadmin):
    """Get most viewed articles for dashboard (admin only)"""
    try:
        limit = int(request.args.get('limit', 5))
        
        # Get articles
        media_service_url = SERVICE_URLS.get('media', '')
        
        articles_response = requests.get(
            f"{media_service_url}/articles?limit=100"
        )
        
        articles = []
        if articles_response.status_code == 200:
            articles = articles_response.json().get('data', [])
        
        # Sort by view_count (most viewed first)
        articles.sort(key=lambda x: int(x.get('view_count', 0)), reverse=True)
        
        # Limit to the requested number
        popular_articles = articles[:limit]
        
        # Log the admin action
        log_admin_action(
            user_id, 
            "view_popular_articles", 
            "media", 
            "dashboard/popular-articles", 
            f"Retrieved {limit} popular articles for dashboard"
        )
        
        return jsonify({
            "status": "success",
            "articles": popular_articles
        })
    except Exception as e:
        logger.error(f"Error getting popular articles: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Promotion Service Admin Endpoints

@app.route('/api/promotions', methods=['GET'])
@admin_required
def get_all_promotions(user_id, is_superadmin):
    """Get all promotions (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_all_promotions", 
            "promotion", 
            "promotions", 
            "Retrieved all promotions"
        )
        return proxy_request(user_id, is_superadmin, 'promotion', 'promotions')
    except Exception as e:
        logger.error(f"Error getting all promotions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>', methods=['GET'])
@admin_required
def get_promotion(user_id, is_superadmin, promotion_id):
    """Get a specific promotion (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_promotion", 
            "promotion", 
            f"promotions/{promotion_id}", 
            f"Viewed promotion {promotion_id}"
        )
        return proxy_request(user_id, is_superadmin, 'promotion', f'promotions/{promotion_id}')
    except Exception as e:
        logger.error(f"Error getting promotion {promotion_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions', methods=['POST'])
@admin_required
def create_promotion(user_id, is_superadmin):
    """Create a new promotion (admin shortcut)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "Promotion data is required"}), 400
            
        # Build descriptive log message
        product_id = data.get('product_id', 'unknown')
        name = data.get('name', 'unnamed')
        discount_type = data.get('discount_type', 'unknown')
        discount_value = data.get('discount_value', '0')
        
        log_admin_action(
            user_id, 
            "create_promotion", 
            "promotion", 
            "promotions", 
            f"Created new promotion '{name}' for product {product_id} with {discount_type} discount of {discount_value}"
        )
        
        return proxy_request(user_id, is_superadmin, 'promotion', 'promotions')
    except Exception as e:
        logger.error(f"Error creating promotion: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>', methods=['PUT'])
@admin_required
def update_promotion(user_id, is_superadmin, promotion_id):
    """Update a promotion (admin shortcut)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
            
        # Build descriptive log message based on what's being updated
        update_details = []
        
        if 'name' in data:
            update_details.append(f"name='{data['name']}'")
        if 'discount_type' in data:
            update_details.append(f"discount_type='{data['discount_type']}'")
        if 'discount_value' in data:
            update_details.append(f"discount_value={data['discount_value']}")
        if 'is_active' in data:
            status = "activated" if data['is_active'] == 1 else "deactivated"
            update_details.append(f"{status}")
        if 'start_date' in data:
            update_details.append(f"start_date='{data['start_date']}'")
        if 'end_date' in data:
            update_details.append(f"end_date='{data['end_date']}'")
            
        update_str = ", ".join(update_details) if update_details else "fields"
        
        log_admin_action(
            user_id, 
            "update_promotion", 
            "promotion", 
            f"promotions/{promotion_id}", 
            f"Updated promotion {promotion_id}: {update_str}"
        )
        
        return proxy_request(user_id, is_superadmin, 'promotion', f'promotions/{promotion_id}')
    except Exception as e:
        logger.error(f"Error updating promotion {promotion_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>', methods=['DELETE'])
@admin_required
def delete_promotion(user_id, is_superadmin, promotion_id):
    """Delete a promotion (admin shortcut)"""
    try:
        # Optionally, get promotion details first for better logging
        promotion_service_url = SERVICE_URLS.get('promotion', '')
        promotion_response = requests.get(f"{promotion_service_url}/promotions/{promotion_id}")
        
        if promotion_response.status_code == 200:
            promotion_data = promotion_response.json().get('data', {})
            promotion_name = promotion_data.get('name', 'unknown')
            product_id = promotion_data.get('product_id', 'unknown')
            
            log_admin_action(
                user_id, 
                "delete_promotion", 
                "promotion", 
                f"promotions/{promotion_id}", 
                f"Deleted promotion {promotion_id} '{promotion_name}' for product {product_id}"
            )
        else:
            # Simpler log if we can't get promotion details
            log_admin_action(
                user_id, 
                "delete_promotion", 
                "promotion", 
                f"promotions/{promotion_id}", 
                f"Deleted promotion {promotion_id}"
            )
        
        return proxy_request(user_id, is_superadmin, 'promotion', f'promotions/{promotion_id}')
    except Exception as e:
        logger.error(f"Error deleting promotion {promotion_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>/promotions', methods=['GET'])
@admin_required
def get_product_promotions(user_id, is_superadmin, product_id):
    """Get all promotions for a product (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_product_promotions", 
            "promotion", 
            f"products/{product_id}/promotions", 
            f"Retrieved promotions for product {product_id}"
        )
        return proxy_request(user_id, is_superadmin, 'promotion', f'products/{product_id}/promotions')
    except Exception as e:
        logger.error(f"Error getting promotions for product {product_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/active', methods=['GET'])
@admin_required
def get_active_promotions(user_id, is_superadmin):
    """Get active promotions (admin shortcut)"""
    try:
        log_admin_action(
            user_id, 
            "view_active_promotions", 
            "promotion", 
            "promotions/active", 
            "Retrieved active promotions"
        )
        return proxy_request(user_id, is_superadmin, 'promotion', 'promotions/active')
    except Exception as e:
        logger.error(f"Error getting active promotions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Additional admin-specific endpoints

@app.route('/api/promotions/<promotion_id>/activate', methods=['PUT'])
@admin_required
def activate_promotion(user_id, is_superadmin, promotion_id):
    """Activate a promotion (admin convenience function)"""
    try:
        log_admin_action(
            user_id, 
            "activate_promotion", 
            "promotion", 
            f"promotions/{promotion_id}", 
            f"Activated promotion {promotion_id}"
        )
        
        # This is just a convenience method that updates is_active to 1
        update_data = {"is_active": 1}
        
        # Use the existing update endpoint's proxy functionality
        return proxy_request(
            user_id, 
            is_superadmin, 
            'promotion', 
            f'promotions/{promotion_id}', 
            method='PUT', 
            json=update_data
        )
    except Exception as e:
        logger.error(f"Error activating promotion {promotion_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>/deactivate', methods=['PUT'])
@admin_required
def deactivate_promotion(user_id, is_superadmin, promotion_id):
    """Deactivate a promotion (admin convenience function)"""
    try:
        log_admin_action(
            user_id, 
            "deactivate_promotion", 
            "promotion", 
            f"promotions/{promotion_id}", 
            f"Deactivated promotion {promotion_id}"
        )
        
        # This is just a convenience method that updates is_active to 0
        update_data = {"is_active": 0}
        
        # Use the existing update endpoint's proxy functionality
        return proxy_request(
            user_id, 
            is_superadmin, 
            'promotion', 
            f'promotions/{promotion_id}', 
            method='PUT', 
            json=update_data
        )
    except Exception as e:
        logger.error(f"Error deactivating promotion {promotion_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/bulk/deactivate', methods=['POST'])
@admin_required
def bulk_deactivate_promotions(user_id, is_superadmin):
    """Deactivate multiple promotions at once (admin bulk operation)"""
    try:
        data = request.get_json()
        
        if not data or 'promotion_ids' not in data:
            return jsonify({"status": "error", "message": "Promotion IDs are required"}), 400
            
        promotion_ids = data['promotion_ids']
        
        if not isinstance(promotion_ids, list) or not promotion_ids:
            return jsonify({"status": "error", "message": "Valid list of promotion IDs is required"}), 400
            
        promotion_service_url = SERVICE_URLS.get('promotion', '')
        results = []
        
        for promotion_id in promotion_ids:
            try:
                # Deactivate each promotion
                response = requests.put(
                    f"{promotion_service_url}/promotions/{promotion_id}",
                    json={"is_active": 0}
                )
                
                status = "success" if response.status_code == 200 else "error"
                results.append({
                    "promotion_id": promotion_id,
                    "status": status,
                    "message": "Deactivated" if status == "success" else "Failed to deactivate"
                })
            except Exception as e:
                results.append({
                    "promotion_id": promotion_id,
                    "status": "error",
                    "message": str(e)
                })
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        
        log_admin_action(
            user_id, 
            "bulk_deactivate_promotions", 
            "promotion", 
            "promotions/bulk/deactivate", 
            f"Bulk deactivated {success_count} of {len(promotion_ids)} promotions"
        )
        
        return jsonify({
            "status": "success",
            "message": f"Deactivated {success_count} of {len(promotion_ids)} promotions",
            "results": results
        })
    except Exception as e:
        logger.error(f"Error bulk deactivating promotions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/dashboard/promotion-stats', methods=['GET'])
@admin_required
def get_promotion_stats(user_id, is_superadmin):
    """Get promotion statistics for dashboard (admin only)"""
    try:
        # Get all promotions
        promotion_service_url = SERVICE_URLS.get('promotion', '')
        response = requests.get(f"{promotion_service_url}/promotions")
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve promotions"}), 500
            
        promotions = response.json().get('data', [])
        
        # Get active promotions
        active_response = requests.get(f"{promotion_service_url}/promotions/active")
        active_promotions = []
        
        if active_response.status_code == 200:
            active_promotions = active_response.json().get('data', [])
            
        # Calculate statistics
        total_promotions = len(promotions)
        active_count = len(active_promotions)
        inactive_count = total_promotions - active_count
        
        # Count by discount type
        percentage_discounts = sum(1 for p in promotions if p.get('discount_type') == 'percentage')
        fixed_amount_discounts = sum(1 for p in promotions if p.get('discount_type') == 'fixed_amount')
        
        # Calculate average discount values
        avg_percentage = 0
        avg_fixed_amount = 0
        
        if percentage_discounts > 0:
            percentage_values = [float(p.get('discount_value', 0)) for p in promotions 
                                if p.get('discount_type') == 'percentage']
            avg_percentage = sum(percentage_values) / len(percentage_values)
            
        if fixed_amount_discounts > 0:
            fixed_values = [float(p.get('discount_value', 0)) for p in promotions 
                           if p.get('discount_type') == 'fixed_amount']
            avg_fixed_amount = sum(fixed_values) / len(fixed_values)
        
        # Count promotions expiring soon (within 7 days)
        now = datetime.now()
        seven_days_later = now + timedelta(days=7)
        expiring_soon = sum(1 for p in promotions if 
                            p.get('end_date') and 
                            now <= datetime.strptime(p.get('end_date'), "%Y-%m-%d %H:%M:%S") <= seven_days_later)
        
        log_admin_action(
            user_id, 
            "view_promotion_stats", 
            "promotion", 
            "dashboard/promotion-stats", 
            "Retrieved promotion statistics for dashboard"
        )
        
        return jsonify({
            "status": "success",
            "stats": {
                "total_promotions": total_promotions,
                "active_promotions": active_count,
                "inactive_promotions": inactive_count,
                "percentage_discounts": percentage_discounts,
                "fixed_amount_discounts": fixed_amount_discounts,
                "avg_percentage_discount": round(avg_percentage, 2),
                "avg_fixed_amount_discount": round(avg_fixed_amount, 2),
                "expiring_soon": expiring_soon
            }
        })
    except Exception as e:
        logger.error(f"Error getting promotion statistics: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/dashboard/expiring-promotions', methods=['GET'])
@admin_required
def get_expiring_promotions(user_id, is_superadmin):
    """Get promotions expiring within the next 7 days (admin only)"""
    try:
        days = int(request.args.get('days', 7))
        
        # Get all promotions
        promotion_service_url = SERVICE_URLS.get('promotion', '')
        response = requests.get(f"{promotion_service_url}/promotions")
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve promotions"}), 500
            
        all_promotions = response.json().get('data', [])
        
        # Calculate date ranges
        now = datetime.now()
        future_date = now + timedelta(days=days)
        
        # Filter promotions that are expiring within the specified days
        expiring_promotions = []
        for promotion in all_promotions:
            if promotion.get('end_date'):
                try:
                    end_date = datetime.strptime(promotion['end_date'], "%Y-%m-%d %H:%M:%S")
                    if now <= end_date <= future_date:
                        # Get the product details for this promotion
                        product_response = requests.get(
                            f"{promotion_service_url}/products/{promotion['product_id']}/promotions"
                        )
                        
                        if product_response.status_code == 200:
                            product = product_response.json().get('product', {})
                            promotion['product'] = product
                            
                        expiring_promotions.append(promotion)
                except Exception as e:
                    continue
        
        log_admin_action(
            user_id, 
            "view_expiring_promotions", 
            "promotion", 
            "dashboard/expiring-promotions", 
            f"Retrieved promotions expiring within {days} days"
        )
        
        return jsonify({
            "status": "success",
            "message": f"Found {len(expiring_promotions)} promotions expiring within {days} days",
            "promotions": expiring_promotions
        })
    except Exception as e:
        logger.error(f"Error getting expiring promotions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Database Service Admin Endpoints
# Add these to your admin-service/app.py file

@app.route('/api/db-admin/health', methods=['GET'])
@admin_required
def get_db_health(user_id, is_superadmin):
    """Get database service health status (admin only)"""
    try:
        log_admin_action(
            user_id, 
            "check_db_health", 
            "database", 
            "health", 
            "Checked database service health status"
        )
        return proxy_request(user_id, is_superadmin, 'database', 'health')
    except Exception as e:
        logger.error(f"Error getting database health: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/tables', methods=['GET'])
@admin_required
def list_all_tables(user_id, is_superadmin):
    """List all tables in the database (admin only)"""
    try:
        log_admin_action(
            user_id, 
            "list_tables", 
            "database", 
            "tables", 
            "Listed all database tables"
        )
        return proxy_request(user_id, is_superadmin, 'database', 'tables')
    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/tables/<table_name>/schema', methods=['GET'])
@admin_required
def get_table_schema(user_id, is_superadmin, table_name):
    """Get schema for a specific table (admin only)"""
    try:
        log_admin_action(
            user_id, 
            "view_table_schema", 
            "database", 
            f"tables/{table_name}/schema", 
            f"Viewed schema for table '{table_name}'"
        )
        return proxy_request(user_id, is_superadmin, 'database', f'tables/{table_name}/schema')
    except Exception as e:
        logger.error(f"Error getting table schema: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/tables/<table_name>/data', methods=['GET'])
@admin_required
def view_table_data(user_id, is_superadmin, table_name):
    """View data in a specific table with optional filtering (admin only)"""
    try:
        # Pass through any query parameters
        # This allows for filtering: ?condition=column=value&params=value
        
        # Log with appropriate details
        condition = request.args.get('condition', 'all records')
        log_admin_action(
            user_id, 
            "view_table_data", 
            "database", 
            f"tables/{table_name}/data", 
            f"Viewed data in table '{table_name}' with filter: {condition}"
        )
        return proxy_request(user_id, is_superadmin, 'database', f'tables/{table_name}/data')
    except Exception as e:
        logger.error(f"Error viewing table data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/tables', methods=['POST'])
@admin_required
def create_table(user_id, is_superadmin):
    """Create a new table in the database (admin only)"""
    try:
        # This requires superadmin privileges
        if not is_superadmin:
            return jsonify({
                "status": "error",
                "message": "Superadmin privileges required to create database tables"
            }), 403
            
        data = request.get_json()
        
        if not data or 'table_name' not in data or 'columns' not in data:
            return jsonify({
                "status": "error", 
                "message": "Table name and columns are required"
            }), 400
            
        table_name = data['table_name']
        columns = data['columns']
        
        # Log the action with detailed information
        column_names = ", ".join(columns.keys())
        log_admin_action(
            user_id, 
            "create_table", 
            "database", 
            "tables", 
            f"Created new table '{table_name}' with columns: {column_names}"
        )
        
        return proxy_request(user_id, is_superadmin, 'database', 'tables')
    except Exception as e:
        logger.error(f"Error creating table: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/tables/<table_name>', methods=['DELETE'])
@admin_required
def drop_table(user_id, is_superadmin, table_name):
    """Drop a table from the database (admin only, superadmin required)"""
    try:
        # This requires superadmin privileges
        if not is_superadmin:
            return jsonify({
                "status": "error",
                "message": "Superadmin privileges required to drop database tables"
            }), 403
            
        log_admin_action(
            user_id, 
            "drop_table", 
            "database", 
            f"tables/{table_name}", 
            f"Dropped table '{table_name}' from database"
        )
        
        return proxy_request(user_id, is_superadmin, 'database', f'tables/{table_name}')
    except Exception as e:
        logger.error(f"Error dropping table: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/execute', methods=['POST'])
@admin_required
def execute_sql_query(user_id, is_superadmin):
    """Execute a custom SQL query (admin only, superadmin required)"""
    try:
        # This requires superadmin privileges
        if not is_superadmin:
            return jsonify({
                "status": "error",
                "message": "Superadmin privileges required to execute custom SQL queries"
            }), 403
            
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({"status": "error", "message": "Query is required"}), 400
            
        query = data['query']
        
        # Add some basic safety checks for destructive queries
        lower_query = query.lower().strip()
        if lower_query.startswith(('drop ', 'delete ', 'truncate ')):
            # For destructive queries, add extra warning in the logs
            log_admin_action(
                user_id, 
                "execute_destructive_query", 
                "database", 
                "execute", 
                f"WARNING: Executed destructive SQL query: {query[:100]}..."
            )
        else:
            # For normal queries
            log_admin_action(
                user_id, 
                "execute_query", 
                "database", 
                "execute", 
                f"Executed SQL query: {query[:100]}..." if len(query) > 100 else f"Executed SQL query: {query}"
            )
        
        return proxy_request(user_id, is_superadmin, 'database', 'execute')
    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/backup', methods=['POST'])
@admin_required
def backup_database(user_id, is_superadmin):
    """Create a database backup (admin only)"""
    try:
        data = request.get_json()
        backup_dir = data.get('backup_dir', 'backups') if data else 'backups'
        
        log_admin_action(
            user_id, 
            "backup_database", 
            "database", 
            "backup", 
            f"Created database backup in directory: {backup_dir}"
        )
        
        return proxy_request(user_id, is_superadmin, 'database', 'backup')
    except Exception as e:
        logger.error(f"Error backing up database: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/connect', methods=['POST'])
@admin_required
def connect_to_database(user_id, is_superadmin):
    """Connect to a specific database (admin only, superadmin required)"""
    try:
        # This requires superadmin privileges
        if not is_superadmin:
            return jsonify({
                "status": "error",
                "message": "Superadmin privileges required to change database connections"
            }), 403
            
        data = request.get_json()
        
        if not data or 'db_name' not in data:
            return jsonify({
                "status": "error", 
                "message": "Database name is required"
            }), 400
            
        db_name = data['db_name']
        
        log_admin_action(
            user_id, 
            "connect_database", 
            "database", 
            "connect", 
            f"Connected to database: {db_name}"
        )
        
        return proxy_request(user_id, is_superadmin, 'database', 'connect')
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/stats/general', methods=['GET'])
@admin_required
def get_database_stats(user_id, is_superadmin):
    """Get general database statistics (admin only)"""
    try:
        # Get stats through multiple queries to the database service
        db_service_url = SERVICE_URLS.get('database', '')
        
        # Check database health
        health_response = requests.get(f"{db_service_url}/health")
        health_status = "healthy" if health_response.status_code == 200 else "unhealthy"
        
        # Get list of tables
        tables_response = requests.get(f"{db_service_url}/tables")
        tables = []
        table_counts = {}
        
        if tables_response.status_code == 200:
            tables_data = tables_response.json()
            tables = tables_data.get('tables', [])
            
            # Get record counts for each table
            for table in tables:
                count_query = f"SELECT COUNT(*) as count FROM {table}"
                count_response = requests.post(
                    f"{db_service_url}/execute",
                    json={"query": count_query}
                )
                
                if count_response.status_code == 200:
                    count_data = count_response.json()
                    if count_data.get('status') == 'success' and count_data.get('data'):
                        table_counts[table] = count_data['data'][0]['count']
                    else:
                        table_counts[table] = "error"
                else:
                    table_counts[table] = "error"
        
        # Get database size (approximation)
        size_query = "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
        size_response = requests.post(
            f"{db_service_url}/execute",
            json={"query": size_query}
        )
        
        db_size = "unknown"
        if size_response.status_code == 200:
            size_data = size_response.json()
            if size_data.get('status') == 'success' and size_data.get('data'):
                size_bytes = size_data['data'][0]['size']
                # Convert to MB
                db_size = f"{size_bytes / (1024 * 1024):.2f} MB"
        
        log_admin_action(
            user_id, 
            "view_database_stats", 
            "database", 
            "stats/general", 
            "Viewed general database statistics"
        )
        
        return jsonify({
            "status": "success",
            "database_status": health_status,
            "table_count": len(tables),
            "tables": tables,
            "record_counts": table_counts,
            "database_size": db_size,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logger.error(f"Error getting database statistics: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/export/<table_name>', methods=['GET'])
@admin_required
def export_table_data(user_id, is_superadmin, table_name):
    """Export data from a table as JSON (admin only)"""
    try:
        # Get all data from the table
        db_service_url = SERVICE_URLS.get('database', '')
        response = requests.get(f"{db_service_url}/tables/{table_name}/data")
        
        if response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"Error retrieving data from table {table_name}"
            }), response.status_code
            
        data = response.json()
        
        log_admin_action(
            user_id, 
            "export_table_data", 
            "database", 
            f"export/{table_name}", 
            f"Exported data from table '{table_name}'"
        )
        
        # Add export metadata
        result = {
            "export_metadata": {
                "table": table_name,
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "exported_by": user_id,
                "record_count": len(data.get('data', []))
            },
            "data": data.get('data', [])
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error exporting table data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/import/<table_name>', methods=['POST'])
@admin_required
def import_table_data(user_id, is_superadmin, table_name):
    """Import data into a table (admin only, superadmin required)"""
    try:
        # This requires superadmin privileges
        if not is_superadmin:
            return jsonify({
                "status": "error",
                "message": "Superadmin privileges required to import data"
            }), 403
            
        data = request.get_json()
        
        if not data or 'records' not in data:
            return jsonify({
                "status": "error", 
                "message": "Records to import are required"
            }), 400
            
        records = data['records']
        
        if not isinstance(records, list) or len(records) == 0:
            return jsonify({
                "status": "error", 
                "message": "Records must be a non-empty array"
            }), 400
            
        # Verify table exists
        db_service_url = SERVICE_URLS.get('database', '')
        tables_response = requests.get(f"{db_service_url}/tables")
        
        if tables_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": "Failed to verify table existence"
            }), 500
            
        tables = tables_response.json().get('tables', [])
        
        if table_name not in tables:
            return jsonify({
                "status": "error", 
                "message": f"Table '{table_name}' does not exist"
            }), 404
            
        # Get table schema to validate records
        schema_response = requests.get(f"{db_service_url}/tables/{table_name}/schema")
        
        if schema_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": "Failed to retrieve table schema"
            }), 500
            
        schema = schema_response.json().get('schema', [])
        column_names = [col['name'] for col in schema]
        
        # Insert each record
        results = []
        success_count = 0
        
        for record in records:
            # Filter out keys that don't match columns
            filtered_record = {k: v for k, v in record.items() if k in column_names}
            
            insert_response = requests.post(
                f"{db_service_url}/tables/{table_name}/data",
                json=filtered_record
            )
            
            status = "success" if insert_response.status_code == 200 else "error"
            
            if status == "success":
                success_count += 1
                
            results.append({
                "status": status,
                "message": insert_response.json().get('message') if insert_response.status_code == 200 else insert_response.text
            })
        
        log_admin_action(
            user_id, 
            "import_table_data", 
            "database", 
            f"import/{table_name}", 
            f"Imported {success_count} of {len(records)} records into table '{table_name}'"
        )
        
        return jsonify({
            "status": "success",
            "message": f"Imported {success_count} of {len(records)} records successfully",
            "results": results
        })
    except Exception as e:
        logger.error(f"Error importing table data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/db-admin/maintenance', methods=['POST'])
@admin_required
def run_maintenance(user_id, is_superadmin):
    """Run database maintenance operations (admin only, superadmin required)"""
    try:
        # This requires superadmin privileges
        if not is_superadmin:
            return jsonify({
                "status": "error",
                "message": "Superadmin privileges required to run maintenance operations"
            }), 403
            
        db_service_url = SERVICE_URLS.get('database', '')
        
        # Run vacuum to optimize the database
        vacuum_response = requests.post(
            f"{db_service_url}/execute",
            json={"query": "VACUUM"}
        )
        
        # Run integrity check
        integrity_response = requests.post(
            f"{db_service_url}/execute",
            json={"query": "PRAGMA integrity_check"}
        )
        
        integrity_result = "OK"
        if integrity_response.status_code == 200:
            integrity_data = integrity_response.json()
            if integrity_data.get('status') == 'success' and integrity_data.get('data'):
                integrity_result = integrity_data['data'][0]['integrity_check']
        
        log_admin_action(
            user_id, 
            "run_maintenance", 
            "database", 
            "maintenance", 
            "Ran database maintenance operations (VACUUM and integrity check)"
        )
        
        return jsonify({
            "status": "success",
            "message": "Database maintenance completed",
            "vacuum_result": vacuum_response.json() if vacuum_response.status_code == 200 else {"status": "error"},
            "integrity_check": integrity_result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logger.error(f"Error running database maintenance: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5011))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')