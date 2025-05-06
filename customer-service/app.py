#!/usr/bin/env python3
# Customer Service Microservice
# RESTful API using Flask

from flask import Flask, request, jsonify
import requests
import os
import uuid
import hashlib
import logging
import re
from datetime import datetime
import jwt
from flask_cors import CORS
from functools import wraps
from flask import send_from_directory
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
DB_NAME = os.environ.get('DB_NAME', '/data/customer.sqlite')
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key')  # In production, use a secure secret
JWT_EXPIRATION = int(os.environ.get('JWT_EXPIRATION', 8640000))  # 24 hours in seconds


EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')


# Initialize database tables for customers
def initialize_customer_table():
    """Initialize the customers table in the database"""
    try:
        # Check if the customers table exists
        connect_response = requests.post(
            f"{DB_SERVICE_URL}/connect",
            json={"db_name": DB_NAME}  # Use the environment variable
        )
        
        logger.info(f"Database connection: {connect_response.json()}")

        tables_response = requests.get(f"{DB_SERVICE_URL}/tables")
        tables = tables_response.json().get('tables', [])
        if 'customers' not in tables:
            # Create customers table with email_verified field
            customer_schema = {
                "customer_id": "TEXT PRIMARY KEY",
                "email": "TEXT UNIQUE NOT NULL",
                "password_hash": "TEXT NOT NULL",
                "first_name": "TEXT",
                "last_name": "TEXT",
                "phone": "TEXT",
                "address": "TEXT",
                "email_verified": "BOOLEAN DEFAULT 0",  # Add verification status
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "last_login": "TIMESTAMP"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "customers", "columns": customer_schema}
            )
            
            logger.info(f"Customers table initialization: {response.json()}")
            
        # Create customer_sessions table
        if 'customer_sessions' not in tables:
            session_schema = {
                "session_id": "TEXT PRIMARY KEY",
                "customer_id": "TEXT NOT NULL",
                "token": "TEXT NOT NULL",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "expires_at": "TIMESTAMP NOT NULL",
                "FOREIGN KEY (customer_id)": "REFERENCES customers(customer_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "customer_sessions", "columns": session_schema}
            )
            
            logger.info(f"Customer sessions table initialization: {response.json()}")
        
    except Exception as e:
        logger.error(f"Error initializing customer tables: {str(e)}")
        return {"status": "error", "message": f"Error initializing customer tables: {str(e)}"}

# Initialize tables when the service starts
initialize_customer_table()

# Helper functions
def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, email):
        return True
    return False

def generate_token(customer_id):
    """Generate a JWT for a customer"""
    expiration = datetime.now().timestamp() + JWT_EXPIRATION
    payload = {
        'customer_id': customer_id,
        'exp': expiration
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token, expiration

def token_required(f):
    """Decorator for endpoints that require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check if the token is in the headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Token is missing'}), 401
        
        try:
            # Decode the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            customer_id = payload['customer_id']
            
            # Verify the token is in the database
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/customer_sessions/data",
                params={"condition": "customer_id = ? AND token = ?", "params": f"{customer_id},{token}"}
            )
            
            session_data = response.json().get('data', [])
            if not session_data:
                return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401
            
            # Add the customer_id to the kwargs
            kwargs['customer_id'] = customer_id
            
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'error', 'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'status': 'error', 'message': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

# Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        services_status = {}
            # Check if DB service is accessible
        try:
            db_response = requests.get(f"{DB_SERVICE_URL}/health", timeout=3)
            services_status['db_service'] = "up" if db_response.status_code == 200 else "down"
        except Exception as e:
            logger.error(f"DB service check error: {str(e)}")
            services_status['db_service'] = "down"
            # Check Email service
        try:
            email_response = requests.get(f"{EMAIL_SERVICE_URL}/api/health", timeout=3)  # Make sure to use /api/health
            services_status['email_service'] = "up" if email_response.status_code == 200 else "down"
        except Exception as e:
            logger.error(f"Email service check error: {str(e)}")
            services_status['email_service'] = "down"   

        return jsonify({
                "status": "up",
                "service": "Customer API",
                "services": services_status,
                "version": "1.0.0"
            })
    except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
            return jsonify({
                "status": "error",
                "service": "Customer API",
                "message": f"Error connecting to DB service: {str(e)}",
                "version": "1.0.0"
            }), 500



@app.route('/api/customers/register', methods=['POST'])
def register_customer():
    """Register a new customer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            return jsonify({"status": "error", "message": "Invalid email format"}), 400
        
        # Check if email already exists
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "email = ?", "params": data['email']}
        )
        
        if response.json().get('data'):
            return jsonify({"status": "error", "message": "Email already registered"}), 409
        
        # Create customer data
        customer_data = {
            "customer_id": str(uuid.uuid4()),
            "email": data['email'],
            "password_hash": hash_password(data['password']),
            "first_name": data['first_name'],
            "last_name": data['last_name'],
            "phone": data.get('phone', ''),
            "address": data.get('address', ''),
            "email_verified": False,  # Initialize as not verified
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Insert customer data
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/customers/data",
            json=customer_data
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to register customer"}), 500
        
        # Send verification email
        EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
        EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
        
        try:
            email_response = requests.post(
                f"{EMAIL_SERVICE_URL}/send/verification",
                json={"email": customer_data['email']},
                headers={"X-API-Key": EMAIL_SERVICE_API_KEY}
            )
            
            if email_response.status_code != 200:
                logger.warning(f"Failed to send verification email: {email_response.json()}")
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
        
        # Generate token
        token, expiration = generate_token(customer_data['customer_id'])
        
        # Store session
        session_data = {
            "session_id": str(uuid.uuid4()),
            "customer_id": customer_data['customer_id'],
            "token": token,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/customer_sessions/data",
            json=session_data
        )
        
        # Return customer info with token
        return jsonify({
            "status": "success",
            "message": "Customer registered successfully. Please check your email to verify your account.",
            "customer": {
                "customer_id": customer_data['customer_id'],
                "email": customer_data['email'],
                "first_name": customer_data['first_name'],
                "last_name": customer_data['last_name'],
                "email_verified": False
            },
            "token": token,
            "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        logger.error(f"Error registering customer: {str(e)}")
        return jsonify({"status": "error", "message": f"Error registering customer: {str(e)}"}), 500

@app.route('/api/customers/verify-email', methods=['POST'])
def verify_customer_email():
    """Verify a customer's email using the verification code"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'email' not in data or 'code' not in data:
            return jsonify({"status": "error", "message": "Email and verification code are required"}), 400
        
        # Check if email exists first
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "email = ?", "params": data['email']}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Email not found"}), 404
        
        customer = customers[0]
        
        # Check if already verified
        if customer.get('email_verified', False):
            return jsonify({"status": "success", "message": "Email already verified"}), 200
        
        # Verify the code with the email service
        EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
        EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
        
        try:
            verify_response = requests.post(
                f"{EMAIL_SERVICE_URL}/verify/code",
                json={"email": data['email'], "code": data['code']},
                headers={"X-API-Key": EMAIL_SERVICE_API_KEY}
            )
            
            verification_result = verify_response.json()
            
            if verify_response.status_code != 200 or not verification_result.get('verified', False):
                return jsonify({
                    "status": "error", 
                    "message": verification_result.get('message', 'Invalid verification code')
                }), 400
                
            # Update the customer's email_verified status
            update_data = {
                "email_verified": True,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            response = requests.put(
                f"{DB_SERVICE_URL}/tables/customers/data",
                json={"values": update_data, "condition": "email = ?", "params": [data['email']]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return jsonify({"status": "error", "message": "Failed to verify email"}), 500
            
            # Send welcome email
            try:
                welcome_response = requests.post(
                    f"{EMAIL_SERVICE_URL}/send/welcome",
                    json={
                        "email": customer['email'],
                        "name": f"{customer['first_name']} {customer['last_name']}"
                    },
                    headers={"X-API-Key": EMAIL_SERVICE_API_KEY}
                )
            except Exception as e:
                logger.error(f"Error sending welcome email: {str(e)}")
            
            # Generate a token for automatic login after verification
            token, expiration = generate_token(customer['customer_id'])
            
            # Store session
            session_data = {
                "session_id": str(uuid.uuid4()),
                "customer_id": customer['customer_id'],
                "token": token,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
            }
            
            session_response = requests.post(
                f"{DB_SERVICE_URL}/tables/customer_sessions/data",
                json=session_data
            )
            
            # Return success with token for auto-login
            return jsonify({
                "status": "success",
                "message": "Email verified successfully. You can now log in.",
                "token": token,
                "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
            })
            
        except Exception as e:
            logger.error(f"Error verifying code with email service: {str(e)}")
            return jsonify({"status": "error", "message": f"Error verifying code: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error verifying customer email: {str(e)}")
        return jsonify({"status": "error", "message": f"Error verifying customer email: {str(e)}"}), 500


        
def email_verified_required(f):
    """Decorator for endpoints that require verified email"""
    @wraps(f)
    def decorated(*args, **kwargs):
        customer_id = kwargs.get('customer_id')
        
        # Get customer data
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Check if email is verified
        if not customer.get('email_verified', False):
            return jsonify({
                "status": "error", 
                "message": "Email not verified. Please verify your email to access this feature."
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated

@app.route('/api/customers/resend-verification', methods=['POST'])
def resend_verification_email():
    """Resend verification email"""
    try:
        data = request.get_json()
        
        if 'email' not in data:
            return jsonify({"status": "error", "message": "Email is required"}), 400
        
        # Check if email exists and is not already verified
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "email = ?", "params": data['email']}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Email not registered"}), 404
        
        customer = customers[0]
        
        # Check if already verified
        if customer.get('email_verified', False):
            return jsonify({"status": "error", "message": "Email already verified"}), 400
        
        # Send verification email
        try:
            email_response = requests.post(
                f"{EMAIL_SERVICE_URL}/send/verification",
                json={"email": data['email']},
                headers={"X-API-Key": EMAIL_SERVICE_API_KEY}
            )
            
            if email_response.status_code != 200:
                logger.warning(f"Failed to send verification email: {email_response.json()}")
                return jsonify({"status": "error", "message": "Failed to send verification email"}), 500
                
            return jsonify({
                "status": "success",
                "message": "Verification email sent successfully"
            })
            
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            return jsonify({"status": "error", "message": f"Error sending verification email: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error resending verification email: {str(e)}")
        return jsonify({"status": "error", "message": f"Error resending verification email: {str(e)}"}), 500

        
@app.route('/api/customers/login', methods=['POST'])
def login_customer():
    """Login a customer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'email' not in data or 'password' not in data:
            return jsonify({"status": "error", "message": "Email and password are required"}), 400
        
        # Hash the password
        password_hash = hash_password(data['password'])
        
        # Find the customer
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "email = ?", "params": data['email']}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Email not registered"}), 404
        
        customer = customers[0]
        
        # Verify password
        if customer['password_hash'] != password_hash:
            return jsonify({"status": "error", "message": "Invalid password"}), 401
        if not customer.get('email_verified', False):
            # Automatically resend verification email
            try:
                EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
                EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
                
                email_response = requests.post(
                    f"{EMAIL_SERVICE_URL}/send/verification",
                    json={"email": customer['email']},
                    headers={"X-API-Key": EMAIL_SERVICE_API_KEY}
                )
            except Exception as e:
                logger.error(f"Error sending verification email: {str(e)}")
            
            return jsonify({
                "status": "error", 
                "message": "Email not verified. Please check your inbox for a verification email.",
                "verification_required": True,
                "email": customer['email']
            }), 403
        # Generate token
        token, expiration = generate_token(customer['customer_id'])
        
        # Store session
        session_data = {
            "session_id": str(uuid.uuid4()),
            "customer_id": customer['customer_id'],
            "token": token,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/customer_sessions/data",
            json=session_data
        )
        
        # Update last login
        update_data = {
            "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/customers/data",
            json={"values": update_data, "condition": "customer_id = ?", "params": [customer['customer_id']]}
        )
        
        # Return customer info with token
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "customer": {
                "customer_id": customer['customer_id'],
                "email": customer['email'],
                "first_name": customer['first_name'],
                "last_name": customer['last_name']
            },
            "token": token,
            "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        logger.error(f"Error logging in customer: {str(e)}")
        return jsonify({"status": "error", "message": f"Error logging in customer: {str(e)}"}), 500

@app.route('/api/customers/logout', methods=['POST'])
@token_required
def logout_customer(customer_id):
    """Logout a customer by invalidating their session"""
    try:
        # Get the token from the Authorization header
        auth_header = request.headers['Authorization']
        token = auth_header.split(' ')[1]
        
        # Delete the session from the database
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/customer_sessions/data",
            json={"condition": "customer_id = ? AND token = ?", "params": [customer_id, token]}
        )
        
        return jsonify({
            "status": "success",
            "message": "Logout successful"
        })
        
    except Exception as e:
        logger.error(f"Error logging out customer: {str(e)}")
        return jsonify({"status": "error", "message": f"Error logging out customer: {str(e)}"}), 500

@app.route('/api/customers/profile', methods=['GET'])
@token_required
def get_customer_profile(customer_id):
    """Get a customer's profile"""
    try:
        # Get customer data
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Remove sensitive info
        customer.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "message": "Profile retrieved successfully",
            "customer": customer
        })
        
    except Exception as e:
        logger.error(f"Error getting customer profile: {str(e)}")
        return jsonify({"status": "error", "message": f"Error getting customer profile: {str(e)}"}), 500

@app.route('/api/customers/profile', methods=['PUT'])
@token_required
def update_customer_profile(customer_id):
    """Update a customer's profile"""
    try:
        data = request.get_json()
        
        # Prevent updating sensitive fields
        forbidden_fields = ['customer_id', 'email', 'password_hash', 'created_at']
        for field in forbidden_fields:
            if field in data:
                data.pop(field)
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update customer data
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/customers/data",
            json={"values": data, "condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to update profile"}), 500
        
        # Get updated profile
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        customer = customers[0]
        customer.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "message": "Profile updated successfully",
            "customer": customer
        })
        
    except Exception as e:
        logger.error(f"Error updating customer profile: {str(e)}")
        return jsonify({"status": "error", "message": f"Error updating customer profile: {str(e)}"}), 500

@app.route('/api/customers/password', methods=['PUT'])
@token_required
def change_password(customer_id):
    """Change a customer's password"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'current_password' not in data or 'new_password' not in data:
            return jsonify({"status": "error", "message": "Current and new password are required"}), 400
        
        # Get customer data
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Verify current password
        current_password_hash = hash_password(data['current_password'])
        if customer['password_hash'] != current_password_hash:
            return jsonify({"status": "error", "message": "Current password is incorrect"}), 401
        
        # Update password
        new_password_hash = hash_password(data['new_password'])
        update_data = {
            "password_hash": new_password_hash,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/customers/data",
            json={"values": update_data, "condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to change password"}), 500
        
        # Invalidate all sessions
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/customer_sessions/data",
            json={"condition": "customer_id = ?", "params": [customer_id]}
        )
        
        # Generate new token
        token, expiration = generate_token(customer_id)
        
        # Store new session
        session_data = {
            "session_id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "token": token,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/customer_sessions/data",
            json=session_data
        )
        
        return jsonify({
            "status": "success",
            "message": "Password changed successfully",
            "token": token,
            "expires_at": datetime.fromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        return jsonify({"status": "error", "message": f"Error changing password: {str(e)}"}), 500

@app.route('/api/customers/<email>/exists', methods=['GET'])
def check_email_exists(email):
    """Check if an email is already registered"""
    try:
        # Validate email format
        if not validate_email(email):
            return jsonify({"status": "error", "message": "Invalid email format"}), 400
        
        # Check if email exists
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "email = ?", "params": email}
        )
        
        exists = len(response.json().get('data', [])) > 0
        
        return jsonify({
            "status": "success",
            "exists": exists
        })
        
    except Exception as e:
        logger.error(f"Error checking email existence: {str(e)}")
        return jsonify({"status": "error", "message": f"Error checking email existence: {str(e)}"}), 500

@app.route('/api/customers/orders', methods=['GET'])
@token_required
def get_customer_orders(customer_id):
    """Get a customer's orders"""
    try:
        # Get orders from the database service
        response = requests.get(
            f"{DB_SERVICE_URL}/customers/{customer_id}/orders"
        )
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to retrieve orders"}), 500
        
        return jsonify(response.json())
        
    except Exception as e:
        logger.error(f"Error getting customer orders: {str(e)}")
        return jsonify({"status": "error", "message": f"Error getting customer orders: {str(e)}"}), 500

@app.route('/api/customers/validate-token', methods=['POST'])
def validate_token():
    """Validate a JWT token"""
    try:
        data = request.get_json()
        
        if 'token' not in data:
            return jsonify({"status": "error", "message": "Token is required"}), 400
        
        token = data['token']
        
        try:
            # Decode the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            customer_id = payload['customer_id']
            
            # Verify the token is in the database
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/customer_sessions/data",
                params={"condition": "customer_id = ? AND token = ?", "params": f"{customer_id},{token}"}
            )
            
            session_data = response.json().get('data', [])
            if not session_data:
                return jsonify({'status': 'error', 'message': 'Invalid or expired token', 'valid': False}), 401
            
            # Get customer data
            response = requests.get(
                f"{DB_SERVICE_URL}/tables/customers/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            customers = response.json().get('data', [])
            if not customers:
                return jsonify({'status': 'error', 'message': 'Customer not found', 'valid': False}), 404
            
            customer = customers[0]
            customer.pop('password_hash', None)
            
            # Check if email is verified
            if not customer.get('email_verified', False):
                return jsonify({
                    'status': 'error',
                    'message': 'Email not verified. Please verify your email to continue.',
                    'valid': False,
                    'verification_required': True,
                    'email': customer['email']
                }), 403
            
            return jsonify({
                'status': 'success',
                'message': 'Token is valid',
                'valid': True,
                'customer': customer
            })
            
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'error', 'message': 'Token has expired', 'valid': False}), 401
        except jwt.InvalidTokenError:
            return jsonify({'status': 'error', 'message': 'Invalid token', 'valid': False}), 401
        
    except Exception as e:
        logger.error(f"Error validating token: {str(e)}")
        return jsonify({"status": "error", "message": f"Error validating token: {str(e)}", "valid": False}), 500


@app.route('/api/customers/all', methods=['GET'])
def get_all_customers():
    """Get all customers - Admin endpoint, no authentication required"""
    try:
        # Get all customers from the database
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"columns": "customer_id,email,first_name,last_name,phone,address,email_verified,created_at,updated_at,last_login"}
        )
        
        customers = response.json().get('data', [])
        
        return jsonify({
            "status": "success",
            "message": f"Retrieved {len(customers)} customers",
            "customers": customers
        })
        
    except Exception as e:
        logger.error(f"Error getting all customers: {str(e)}")
        return jsonify({"status": "error", "message": f"Error getting all customers: {str(e)}"}), 500

@app.route('/api/customers/<customer_id>/update', methods=['PUT'])
def admin_update_customer(customer_id):
    """Update a customer without authentication - Admin endpoint"""
    try:
        data = request.get_json()
        
        # Check if customer exists
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        # Prevent updating sensitive fields
        forbidden_fields = ['customer_id', 'password_hash', 'created_at']
        for field in forbidden_fields:
            if field in data:
                data.pop(field)
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update customer data
        response = requests.put(
            f"{DB_SERVICE_URL}/tables/customers/data",
            json={"values": data, "condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to update customer"}), 500
        
        # Get updated profile
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        customer = customers[0]
        customer.pop('password_hash', None)
        
        return jsonify({
            "status": "success",
            "message": "Customer updated successfully",
            "customer": customer
        })
        
    except Exception as e:
        logger.error(f"Error updating customer: {str(e)}")
        return jsonify({"status": "error", "message": f"Error updating customer: {str(e)}"}), 500

@app.route('/api/customers/<customer_id>/delete', methods=['DELETE'])
def admin_delete_customer(customer_id):
    """Delete a customer account - Admin endpoint"""
    try:
        # Get customer data first
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/customers/data",
            params={"condition": "customer_id = ?", "params": customer_id}
        )
        
        customers = response.json().get('data', [])
        if not customers:
            return jsonify({"status": "error", "message": "Customer not found"}), 404
        
        customer = customers[0]
        
        # Send account deletion notification email
        EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
        EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
        
        try:
            email_body = f"""
Dear {customer['first_name']} {customer['last_name']},

Your account has been deleted from our system.

Account details:
- Email: {customer['email']}
- Customer ID: {customer['customer_id']}
- Deletion time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

If you didn't request this deletion, please contact our support team immediately.

Best regards,
Customer Service Team
"""
            
            email_response = requests.post(
                f"{EMAIL_SERVICE_URL}/api/send-email",
                json={
                    "recipient_email": customer['email'],
                    "subject": "Account Deletion Confirmation",
                    "message": email_body
                },
                headers={"X-API-Key": EMAIL_SERVICE_API_KEY}
            )
            
            if email_response.status_code != 200:
                logger.warning(f"Failed to send deletion email: {email_response.json()}")
                
        except Exception as e:
            logger.error(f"Error sending deletion email: {str(e)}")
        
        # Delete all sessions for this customer
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/customer_sessions/data",
            json={"condition": "customer_id = ?", "params": [customer_id]}
        )
        
        # Delete the customer
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/customers/data",
            json={"condition": "customer_id = ?", "params": [customer_id]}
        )
        
        if response.status_code != 200 or response.json().get('status') != 'success':
            return jsonify({"status": "error", "message": "Failed to delete customer"}), 500
        
        return jsonify({
            "status": "success",
            "message": f"Customer {customer['email']} deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"Error deleting customer: {str(e)}")
        return jsonify({"status": "error", "message": f"Error deleting customer: {str(e)}"}), 500

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')
# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')