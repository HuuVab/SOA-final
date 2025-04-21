"""
User Authentication Microservice
--------------------------------
Handles user registration, authentication, profile management, and multiple addresses/phone numbers/payment methods.
"""

from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import jwt
import datetime
import os
import requests
import uuid
from functools import wraps
from bson.objectid import ObjectId

# Initialize Flask app
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')
mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
jwt_expiration = int(os.environ.get('JWT_EXPIRATION', 3600))  # 1 hour by default
email_service_url = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
email_service_api_key = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')
auth_service_base_url = os.environ.get('AUTH_SERVICE_BASE_URL', 'http://localhost:5000')

# Connect to MongoDB
client = MongoClient(mongo_uri)
db = client['ecommerce']
customers_collection = db['customers']
verification_tokens_collection = db['verification_tokens']

# Create indexes for email (for uniqueness and faster queries)
customers_collection.create_index("email", unique=True)
verification_tokens_collection.create_index("token", unique=True)
verification_tokens_collection.create_index("expires_at", expireAfterSeconds=0)

# JWT token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = customers_collection.find_one({'_id': ObjectId(data['user_id'])})
            if not current_user:
                return jsonify({'message': 'User not found!'}), 401
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

def send_verification_email(email, token):
    """Send verification email using email service"""
    verification_url = f"{auth_service_base_url}/verify-email/{token}"
    
    try:
        response = requests.post(
            f"{email_service_url}/send/verification",
            json={
                'email': email,
                'verification_url': verification_url
            },
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': email_service_api_key
            }
        )
        
        if response.status_code == 200:
            app.logger.info(f"Verification email sent to {email}")
            return True
        else:
            app.logger.error(f"Failed to send verification email: {response.text}")
            return False
    except Exception as e:
        app.logger.error(f"Error sending verification email: {str(e)}")
        return False

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if required fields are present
    if not all(key in data for key in ['email', 'password', 'name']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    # Check if user already exists
    if customers_collection.find_one({'email': data['email']}):
        return jsonify({'message': 'User already exists!'}), 409
    
    # Hash the password
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    # Prepare user object with empty arrays for addresses, phones, and payment methods
    new_user = {
        'email': data['email'],
        'password': hashed_password,
        'name': data['name'],
        'created_at': datetime.datetime.utcnow(),
        'is_active': False,  # User is inactive until email is verified
        'email_verified': False,
        'role': 'customer',  # Default role
        'addresses': [],     # Array for multiple addresses
        'phones': [],        # Array for multiple phone numbers
        'payment_methods': [] # Array for multiple payment methods
    }
    
    # Insert user into database
    result = customers_collection.insert_one(new_user)
    user_id = str(result.inserted_id)
    
    # Generate verification token
    verification_token = str(uuid.uuid4())
    
    # Store verification token with expiration (24 hours)
    verification_tokens_collection.insert_one({
        'token': verification_token,
        'user_id': user_id,
        'email': data['email'],
        'expires_at': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    })
    
    # Send verification email
    email_sent = send_verification_email(data['email'], verification_token)
    
    response = {
        'message': 'User registered successfully!',
        'user_id': user_id,
    }
    
    if email_sent:
        response['email_verification'] = 'Verification email sent. Please check your inbox.'
    else:
        response['email_verification'] = 'Failed to send verification email. Please try again later.'
    
    return jsonify(response), 201

@app.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    # Find the verification token
    token_doc = verification_tokens_collection.find_one({'token': token})
    
    if not token_doc:
        return jsonify({'message': 'Invalid or expired verification token!'}), 400
    
    # Update user's email_verified status
    result = customers_collection.update_one(
        {'_id': ObjectId(token_doc['user_id'])},
        {'$set': {'email_verified': True, 'is_active': True}}
    )
    
    if result.modified_count == 0:
        return jsonify({'message': 'User not found!'}), 404
    
    # Delete the used token
    verification_tokens_collection.delete_one({'token': token})
    
    # Send welcome email
    try:
        user = customers_collection.find_one({'_id': ObjectId(token_doc['user_id'])})
        if user:
            requests.post(
                f"{email_service_url}/send/welcome",
                json={
                    'email': user['email'],
                    'name': user['name']
                },
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': email_service_api_key
                }
            )
    except Exception as e:
        app.logger.error(f"Error sending welcome email: {str(e)}")
    
    return jsonify({'message': 'Email verified successfully! You can now log in.'}), 200

@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = request.get_json()
    
    if 'email' not in data:
        return jsonify({'message': 'Email is required!'}), 400
    
    # Find user by email
    user = customers_collection.find_one({'email': data['email']})
    
    if not user:
        # Don't reveal if user exists or not for security
        return jsonify({'message': 'If your email is registered, a verification link will be sent.'}), 200
    
    if user.get('email_verified', False):
        return jsonify({'message': 'Your email is already verified.'}), 200
    
    # Delete any existing tokens for this user
    verification_tokens_collection.delete_many({'email': data['email']})
    
    # Generate new verification token
    verification_token = str(uuid.uuid4())
    
    # Store verification token with expiration (24 hours)
    verification_tokens_collection.insert_one({
        'token': verification_token,
        'user_id': str(user['_id']),
        'email': data['email'],
        'expires_at': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    })
    
    # Send verification email
    email_sent = send_verification_email(data['email'], verification_token)
    
    if email_sent:
        return jsonify({'message': 'Verification email sent. Please check your inbox.'}), 200
    else:
        return jsonify({'message': 'Failed to send verification email. Please try again later.'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'password']):
        return jsonify({'message': 'Missing email or password!'}), 400
    
    user = customers_collection.find_one({'email': data['email']})
    
    if not user or not bcrypt.check_password_hash(user['password'], data['password']):
        return jsonify({'message': 'Invalid credentials!'}), 401
    
    # Check if email is verified
    if not user.get('email_verified', False):
        return jsonify({'message': 'Please verify your email before logging in.'}), 403
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': str(user['_id']),
        'email': user['email'],
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=jwt_expiration)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        'token': token,
        'expires_in': jwt_expiration
    }), 200

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    
    if 'email' not in data:
        return jsonify({'message': 'Email is required!'}), 400
    
    # Find user by email
    user = customers_collection.find_one({'email': data['email']})
    
    if not user:
        # Don't reveal if user exists or not for security
        return jsonify({'message': 'If your email is registered, a password reset link will be sent.'}), 200
    
    # Generate password reset token
    reset_token = str(uuid.uuid4())
    
    # Store reset token with expiration (1 hour)
    reset_tokens_collection = db['password_reset_tokens']
    reset_tokens_collection.create_index("expires_at", expireAfterSeconds=0)
    
    reset_tokens_collection.insert_one({
        'token': reset_token,
        'user_id': str(user['_id']),
        'email': data['email'],
        'expires_at': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    })
    
    # Create reset URL
    reset_url = f"{auth_service_base_url}/reset-password/{reset_token}"
    
    try:
        response = requests.post(
            f"{email_service_url}/send/password-reset",
            json={
                'email': data['email'],
                'reset_url': reset_url
            },
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': email_service_api_key
            }
        )
        
        if response.status_code == 200:
            return jsonify({'message': 'If your email is registered, a password reset link will be sent.'}), 200
        else:
            app.logger.error(f"Failed to send password reset email: {response.text}")
            return jsonify({'message': 'Failed to send password reset email. Please try again later.'}), 500
    except Exception as e:
        app.logger.error(f"Error sending password reset email: {str(e)}")
        return jsonify({'message': 'Failed to send password reset email. Please try again later.'}), 500

@app.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    data = request.get_json()
    
    if 'new_password' not in data:
        return jsonify({'message': 'New password is required!'}), 400
    
    # Find the reset token
    reset_tokens_collection = db['password_reset_tokens']
    token_doc = reset_tokens_collection.find_one({'token': token})
    
    if not token_doc:
        return jsonify({'message': 'Invalid or expired reset token!'}), 400
    
    # Hash the new password
    hashed_password = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')
    
    # Update user's password
    result = customers_collection.update_one(
        {'_id': ObjectId(token_doc['user_id'])},
        {'$set': {'password': hashed_password}}
    )
    
    if result.modified_count == 0:
        return jsonify({'message': 'User not found!'}), 404
    
    # Delete the used token
    reset_tokens_collection.delete_one({'token': token})
    
    return jsonify({'message': 'Password reset successfully! You can now log in with your new password.'}), 200

@app.route('/customer/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    # Remove sensitive information
    user_data = {
        'id': str(current_user['_id']),
        'email': current_user['email'],
        'name': current_user['name'],
        'role': current_user['role'],
        'created_at': current_user['created_at'],
        'addresses': current_user.get('addresses', []),
        'phones': current_user.get('phones', []),
        'payment_methods': current_user.get('payment_methods', [])
    }
    
    return jsonify(user_data), 200

@app.route('/customer/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json()
    
    # Fields that can be updated
    allowed_fields = ['name']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # Update user in database
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Profile updated successfully!'}), 200

@app.route('/customer/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.get_json()
    
    if not all(key in data for key in ['current_password', 'new_password']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    # Verify current password
    if not bcrypt.check_password_hash(current_user['password'], data['current_password']):
        return jsonify({'message': 'Current password is incorrect!'}), 401
    
    # Hash the new password
    hashed_password = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')
    
    # Update password in database
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'password': hashed_password}}
    )
    
    return jsonify({'message': 'Password changed successfully!'}), 200

# Address management endpoints
@app.route('/customer/addresses', methods=['GET'])
@token_required
def get_addresses(current_user):
    addresses = current_user.get('addresses', [])
    return jsonify(addresses), 200

@app.route('/customer/addresses', methods=['POST'])
@token_required
def add_address(current_user):
    data = request.get_json()
    
    # Validate address data
    required_fields = ['label', 'street', 'city', 'state', 'zipcode', 'country']
    if not all(key in data for key in required_fields):
        return jsonify({'message': 'Missing required address fields!'}), 400
    
    # Check if max address limit is reached
    addresses = current_user.get('addresses', [])
    if len(addresses) >= 3:
        return jsonify({'message': 'Maximum number of addresses (3) reached!'}), 400
    
    # Generate a unique ID for the address
    address_id = str(ObjectId())
    
    # Create new address object
    new_address = {
        'id': address_id,
        'label': data['label'],
        'street': data['street'],
        'city': data['city'],
        'state': data['state'],
        'zipcode': data['zipcode'],
        'country': data['country'],
        'is_primary': data.get('is_primary', False)
    }
    
    # If this is the first address or is_primary is True, ensure it's the only primary
    if new_address['is_primary'] or len(addresses) == 0:
        new_address['is_primary'] = True
        customers_collection.update_many(
            {'_id': current_user['_id'], 'addresses.is_primary': True},
            {'$set': {'addresses.$.is_primary': False}}
        )
    
    # Add the new address
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$push': {'addresses': new_address}}
    )
    
    return jsonify({
        'message': 'Address added successfully!',
        'address_id': address_id
    }), 201

@app.route('/customer/addresses/<address_id>', methods=['PUT'])
@token_required
def update_address(current_user, address_id):
    data = request.get_json()
    
    # Find the address index
    addresses = current_user.get('addresses', [])
    address_index = next((i for i, addr in enumerate(addresses) if addr.get('id') == address_id), None)
    
    if address_index is None:
        return jsonify({'message': 'Address not found!'}), 404
    
    # Fields that can be updated
    allowed_fields = ['label', 'street', 'city', 'state', 'zipcode', 'country', 'is_primary']
    update_data = {f'addresses.{address_index}.{k}': v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # If setting as primary, ensure it's the only primary
    if data.get('is_primary', False):
        customers_collection.update_many(
            {'_id': current_user['_id'], 'addresses.is_primary': True},
            {'$set': {'addresses.$.is_primary': False}}
        )
        update_data[f'addresses.{address_index}.is_primary'] = True
    
    # Update the address
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Address updated successfully!'}), 200

@app.route('/customer/addresses/<address_id>', methods=['DELETE'])
@token_required
def delete_address(current_user, address_id):
    # Check if address exists
    addresses = current_user.get('addresses', [])
    address = next((addr for addr in addresses if addr.get('id') == address_id), None)
    
    if not address:
        return jsonify({'message': 'Address not found!'}), 404
    
    # Delete the address
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$pull': {'addresses': {'id': address_id}}}
    )
    
    # If the deleted address was primary and there are other addresses, make one primary
    if address.get('is_primary', False) and len(addresses) > 1:
        remaining_addresses = [addr for addr in addresses if addr.get('id') != address_id]
        if remaining_addresses:
            customers_collection.update_one(
                {'_id': current_user['_id'], 'addresses.id': remaining_addresses[0]['id']},
                {'$set': {'addresses.$.is_primary': True}}
            )
    
    return jsonify({'message': 'Address deleted successfully!'}), 200

# Phone management endpoints
@app.route('/customer/phones', methods=['GET'])
@token_required
def get_phones(current_user):
    phones = current_user.get('phones', [])
    return jsonify(phones), 200

@app.route('/customer/phones', methods=['POST'])
@token_required
def add_phone(current_user):
    data = request.get_json()
    
    # Validate phone data
    if 'number' not in data:
        return jsonify({'message': 'Phone number is required!'}), 400
    
    # Check if max phone limit is reached
    phones = current_user.get('phones', [])
    if len(phones) >= 3:
        return jsonify({'message': 'Maximum number of phone numbers (3) reached!'}), 400
    
    # Generate a unique ID for the phone
    phone_id = str(ObjectId())
    
    # Create new phone object
    new_phone = {
        'id': phone_id,
        'number': data['number'],
        'label': data.get('label', 'Mobile'),
        'is_primary': data.get('is_primary', False)
    }
    
    # If this is the first phone or is_primary is True, ensure it's the only primary
    if new_phone['is_primary'] or len(phones) == 0:
        new_phone['is_primary'] = True
        customers_collection.update_many(
            {'_id': current_user['_id'], 'phones.is_primary': True},
            {'$set': {'phones.$.is_primary': False}}
        )
    
    # Add the new phone
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$push': {'phones': new_phone}}
    )
    
    return jsonify({
        'message': 'Phone number added successfully!',
        'phone_id': phone_id
    }), 201

@app.route('/customer/phones/<phone_id>', methods=['PUT'])
@token_required
def update_phone(current_user, phone_id):
    data = request.get_json()
    
    # Find the phone index
    phones = current_user.get('phones', [])
    phone_index = next((i for i, ph in enumerate(phones) if ph.get('id') == phone_id), None)
    
    if phone_index is None:
        return jsonify({'message': 'Phone number not found!'}), 404
    
    # Fields that can be updated
    allowed_fields = ['number', 'label', 'is_primary']
    update_data = {f'phones.{phone_index}.{k}': v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # If setting as primary, ensure it's the only primary
    if data.get('is_primary', False):
        customers_collection.update_many(
            {'_id': current_user['_id'], 'phones.is_primary': True},
            {'$set': {'phones.$.is_primary': False}}
        )
        update_data[f'phones.{phone_index}.is_primary'] = True
    
    # Update the phone
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Phone number updated successfully!'}), 200

@app.route('/customer/phones/<phone_id>', methods=['DELETE'])
@token_required
def delete_phone(current_user, phone_id):
    # Check if phone exists
    phones = current_user.get('phones', [])
    phone = next((ph for ph in phones if ph.get('id') == phone_id), None)
    
    if not phone:
        return jsonify({'message': 'Phone number not found!'}), 404
    
    # Delete the phone
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$pull': {'phones': {'id': phone_id}}}
    )
    
    # If the deleted phone was primary and there are other phones, make one primary
    if phone.get('is_primary', False) and len(phones) > 1:
        remaining_phones = [ph for ph in phones if ph.get('id') != phone_id]
        if remaining_phones:
            customers_collection.update_one(
                {'_id': current_user['_id'], 'phones.id': remaining_phones[0]['id']},
                {'$set': {'phones.$.is_primary': True}}
            )
    
    return jsonify({'message': 'Phone number deleted successfully!'}), 200

# Payment method management endpoints
@app.route('/customer/payment-methods', methods=['GET'])
@token_required
def get_payment_methods(current_user):
    payment_methods = current_user.get('payment_methods', [])
    # Don't return full card numbers in response
    for method in payment_methods:
        if 'card_number' in method:
            method['card_number'] = '*' * (len(method['card_number']) - 4) + method['card_number'][-4:]
    
    return jsonify(payment_methods), 200

@app.route('/customer/payment-methods', methods=['POST'])
@token_required
def add_payment_method(current_user):
    data = request.get_json()
    
    # Validate payment method data
    if data.get('type') == 'card':
        required_fields = ['type', 'card_number', 'cardholder_name', 'expiry_month', 'expiry_year', 'cvv']
    else:
        return jsonify({'message': 'Invalid payment method type!'}), 400
        
    if not all(key in data for key in required_fields):
        return jsonify({'message': 'Missing required payment method fields!'}), 400
    
    # Check if max payment method limit is reached
    payment_methods = current_user.get('payment_methods', [])
    if len(payment_methods) >= 3:
        return jsonify({'message': 'Maximum number of payment methods (3) reached!'}), 400
    
    # Generate a unique ID for the payment method
    payment_id = str(ObjectId())
    
    # Create new payment method object
    new_payment = {
        'id': payment_id,
        'type': data['type'],
        'label': data.get('label', 'Credit Card'),
        'is_primary': data.get('is_primary', False)
    }
    
    # Add type-specific fields
    if data['type'] == 'card':
        # In a production environment, you would tokenize or encrypt card data
        # This is simplified for example purposes
        new_payment.update({
            'card_number': data['card_number'],
            'cardholder_name': data['cardholder_name'],
            'expiry_month': data['expiry_month'],
            'expiry_year': data['expiry_year'],
            # Don't store CVV in the database for PCI compliance
        })
    
    # If this is the first payment method or is_primary is True, ensure it's the only primary
    if new_payment['is_primary'] or len(payment_methods) == 0:
        new_payment['is_primary'] = True
        customers_collection.update_many(
            {'_id': current_user['_id'], 'payment_methods.is_primary': True},
            {'$set': {'payment_methods.$.is_primary': False}}
        )
    
    # Add the new payment method
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$push': {'payment_methods': new_payment}}
    )
    
    return jsonify({
        'message': 'Payment method added successfully!',
        'payment_id': payment_id
    }), 201

@app.route('/customer/payment-methods/<payment_id>', methods=['PUT'])
@token_required
def update_payment_method(current_user, payment_id):
    data = request.get_json()
    
    # Find the payment method index
    payment_methods = current_user.get('payment_methods', [])
    payment_index = next((i for i, pm in enumerate(payment_methods) if pm.get('id') == payment_id), None)
    
    if payment_index is None:
        return jsonify({'message': 'Payment method not found!'}), 404
    
    # Fields that can be updated
    allowed_fields = ['label', 'is_primary']
    # Add type-specific fields
    if payment_methods[payment_index]['type'] == 'card':
        allowed_fields.extend(['cardholder_name', 'expiry_month', 'expiry_year'])
    
    update_data = {f'payment_methods.{payment_index}.{k}': v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # If setting as primary, ensure it's the only primary
    if data.get('is_primary', False):
        customers_collection.update_many(
            {'_id': current_user['_id'], 'payment_methods.is_primary': True},
            {'$set': {'payment_methods.$.is_primary': False}}
        )
        update_data[f'payment_methods.{payment_index}.is_primary'] = True
    
    # Update the payment method
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Payment method updated successfully!'}), 200

@app.route('/customer/payment-methods/<payment_id>', methods=['DELETE'])
@token_required
def delete_payment_method(current_user, payment_id):
    # Check if payment method exists
    payment_methods = current_user.get('payment_methods', [])
    payment = next((pm for pm in payment_methods if pm.get('id') == payment_id), None)
    
    if not payment:
        return jsonify({'message': 'Payment method not found!'}), 404
    
    # Delete the payment method
    customers_collection.update_one(
        {'_id': current_user['_id']},
        {'$pull': {'payment_methods': {'id': payment_id}}}
    )
    
    # If the deleted payment method was primary and there are others, make one primary
    if payment.get('is_primary', False) and len(payment_methods) > 1:
        remaining_methods = [pm for pm in payment_methods if pm.get('id') != payment_id]
        if remaining_methods:
            customers_collection.update_one(
                {'_id': current_user['_id'], 'payment_methods.id': remaining_methods[0]['id']},
                {'$set': {'payment_methods.$.is_primary': True}}
            )
    
    return jsonify({'message': 'Payment method deleted successfully!'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)