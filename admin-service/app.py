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

@app.route('/api/images/<image_id>', methods=['GET'])
@admin_required
def get_image(user_id, is_superadmin, image_id):
    """Get an image by ID (admin shortcut)"""
    log_admin_action(user_id, "view_image", "storage", f"images/{image_id}", f"Retrieved image {image_id}")
    return proxy_request(user_id, is_superadmin, 'storage', f'images/{image_id}')

@app.route('/api/images/<image_id>', methods=['PUT'])
@admin_required
def update_image(user_id, is_superadmin, image_id):
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
def delete_image(user_id, is_superadmin, image_id):
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



# Order management shortcuts
@app.route('/api/orders', methods=['GET'])
@admin_required
def get_all_orders(user_id, is_superadmin):
    """Get all orders (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'order', 'admin/orders')

@app.route('/api/orders/<order_id>', methods=['GET'])
@admin_required
def get_order(user_id, is_superadmin, order_id):
    """Get a specific order (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'order', f'admin/orders/{order_id}')

@app.route('/api/orders/<order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(user_id, is_superadmin, order_id):
    """Update order status (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'order', f'admin/orders/{order_id}/status')

# Customer management shortcuts
@app.route('/api/customers', methods=['GET'])
@admin_required
def get_all_customers(user_id, is_superadmin):
    """Get all customers (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'customer', 'admin/customers')

@app.route('/api/customers/<customer_id>', methods=['GET'])
@admin_required
def get_customer(user_id, is_superadmin, customer_id):
    """Get a specific customer (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'customer', f'admin/customers/{customer_id}')

# Promotion management shortcuts
@app.route('/api/promotions', methods=['GET'])
@admin_required
def get_all_promotions(user_id, is_superadmin):
    """Get all promotions (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'promotion', 'promotions')

@app.route('/api/promotions', methods=['POST'])
@admin_required
def create_promotion(user_id, is_superadmin):
    """Create a new promotion (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'promotion', 'promotions')

@app.route('/api/promotions/<promotion_id>', methods=['PUT'])
@admin_required
def update_promotion(user_id, is_superadmin, promotion_id):
    """Update a promotion (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'promotion', f'promotions/{promotion_id}')

# Media management shortcuts
@app.route('/api/media', methods=['GET'])
@admin_required
def get_all_media(user_id, is_superadmin):
    """Get all media items (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'media', 'media')

@app.route('/api/media/<media_id>', methods=['GET'])
@admin_required
def get_media(user_id, is_superadmin, media_id):
    """Get a specific media item (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'media', f'media/{media_id}')

@app.route('/api/media', methods=['POST'])
@admin_required
def upload_media(user_id, is_superadmin):
    """Upload a new media item (admin shortcut)"""
    return proxy_request(user_id, is_superadmin, 'media', 'media')

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5011))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')