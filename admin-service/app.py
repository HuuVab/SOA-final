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

# Initialize tables when the service starts
initialize_admin_tables()

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

# Rest of the API routes remain the same...
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

# The rest of your routes would go here...

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

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5011))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')