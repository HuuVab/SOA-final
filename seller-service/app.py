"""
Seller Authentication Microservice
---------------------------------
Handles seller registration, authentication, profile management, store settings, 
and payment information.
"""

from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import jwt
import datetime
import os
from functools import wraps
from bson.objectid import ObjectId

# Initialize Flask app
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')
mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
jwt_expiration = int(os.environ.get('JWT_EXPIRATION', 3600))  # 1 hour by default

# Connect to MongoDB
client = MongoClient(mongo_uri)
db = client['ecommerce']
sellers_collection = db['sellers']

# Create indexes for email (for uniqueness and faster queries)
sellers_collection.create_index("email", unique=True)
sellers_collection.create_index("store_name", unique=True)

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
            current_user = sellers_collection.find_one({'_id': ObjectId(data['user_id'])})
            if not current_user:
                return jsonify({'message': 'Seller not found!'}), 401
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if required fields are present
    if not all(key in data for key in ['email', 'password', 'name', 'store_name']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    # Check if seller already exists with this email
    if sellers_collection.find_one({'email': data['email']}):
        return jsonify({'message': 'Email already registered!'}), 409
    
    # Check if store name is already taken
    if sellers_collection.find_one({'store_name': data['store_name']}):
        return jsonify({'message': 'Store name already taken!'}), 409
    
    # Hash the password
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    # Prepare seller object
    new_seller = {
        'email': data['email'],
        'password': hashed_password,
        'name': data['name'],
        'store_name': data['store_name'],
        'created_at': datetime.datetime.utcnow(),
        'is_active': True,
        'is_verified': False,  # Sellers need verification before they can sell
        'role': 'seller',
        'business_info': {
            'business_type': data.get('business_type', 'individual'),
            'tax_id': data.get('tax_id', ''),
            'business_address': data.get('business_address', {}),
            'phone': data.get('phone', '')
        },
        'bank_accounts': [],  # Array for payment receiving methods
        'store_settings': {
            'logo_url': '',
            'banner_url': '',
            'description': data.get('description', ''),
            'categories': data.get('categories', []),
            'policies': {
                'return_policy': '',
                'shipping_policy': '',
                'store_policy': ''
            }
        }
    }
    
    # Insert seller into database
    result = sellers_collection.insert_one(new_seller)
    
    return jsonify({
        'message': 'Seller registered successfully! Account pending verification.',
        'seller_id': str(result.inserted_id)
    }), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'password']):
        return jsonify({'message': 'Missing email or password!'}), 400
    
    seller = sellers_collection.find_one({'email': data['email']})
    
    if not seller or not bcrypt.check_password_hash(seller['password'], data['password']):
        return jsonify({'message': 'Invalid credentials!'}), 401
    
    if not seller['is_active']:
        return jsonify({'message': 'Account is deactivated. Please contact support.'}), 403
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': str(seller['_id']),
        'email': seller['email'],
        'role': seller['role'],
        'store_name': seller['store_name'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=jwt_expiration)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({
        'token': token,
        'expires_in': jwt_expiration,
        'is_verified': seller['is_verified']
    }), 200

@app.route('/seller/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    # Remove sensitive information
    seller_data = {
        'id': str(current_user['_id']),
        'email': current_user['email'],
        'name': current_user['name'],
        'store_name': current_user['store_name'],
        'role': current_user['role'],
        'created_at': current_user['created_at'],
        'is_verified': current_user['is_verified'],
        'business_info': current_user.get('business_info', {}),
        'store_settings': current_user.get('store_settings', {})
    }
    
    # Mask bank account information
    if 'bank_accounts' in current_user:
        seller_data['bank_accounts'] = []
        for account in current_user['bank_accounts']:
            masked_account = account.copy()
            if 'account_number' in masked_account:
                masked_account['account_number'] = '*' * (len(account['account_number']) - 4) + account['account_number'][-4:]
            seller_data['bank_accounts'].append(masked_account)
    
    return jsonify(seller_data), 200

@app.route('/seller/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json()
    
    # Fields that can be updated
    allowed_fields = ['name']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    # Handle nested updates for business_info
    if 'business_info' in data and isinstance(data['business_info'], dict):
        for field, value in data['business_info'].items():
            if field in ['business_type', 'tax_id', 'phone']:
                update_data[f'business_info.{field}'] = value
            elif field == 'business_address' and isinstance(value, dict):
                for addr_field, addr_value in value.items():
                    update_data[f'business_info.business_address.{addr_field}'] = addr_value
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # Update seller in database
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Profile updated successfully!'}), 200

@app.route('/seller/change-password', methods=['POST'])
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
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'password': hashed_password}}
    )
    
    return jsonify({'message': 'Password changed successfully!'}), 200

@app.route('/seller/store-settings', methods=['GET'])
@token_required
def get_store_settings(current_user):
    store_settings = current_user.get('store_settings', {})
    return jsonify(store_settings), 200

@app.route('/seller/store-settings', methods=['PUT'])
@token_required
def update_store_settings(current_user):
    data = request.get_json()
    
    # Fields that can be updated
    allowed_fields = ['description', 'categories']
    update_data = {}
    
    for field in allowed_fields:
        if field in data:
            update_data[f'store_settings.{field}'] = data[field]
    
    # Handle nested updates for policies
    if 'policies' in data and isinstance(data['policies'], dict):
        for field, value in data['policies'].items():
            if field in ['return_policy', 'shipping_policy', 'store_policy']:
                update_data[f'store_settings.policies.{field}'] = value
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # Update store settings in database
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Store settings updated successfully!'}), 200

@app.route('/seller/store-logo', methods=['POST'])
@token_required
def update_store_logo(current_user):
    # In a real app, you would handle file upload here
    # This is a placeholder for the endpoint
    
    data = request.get_json()
    if 'logo_url' not in data:
        return jsonify({'message': 'Logo URL is required!'}), 400
    
    # Update logo URL in database
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'store_settings.logo_url': data['logo_url']}}
    )
    
    return jsonify({'message': 'Store logo updated successfully!'}), 200

@app.route('/seller/store-banner', methods=['POST'])
@token_required
def update_store_banner(current_user):
    # In a real app, you would handle file upload here
    # This is a placeholder for the endpoint
    
    data = request.get_json()
    if 'banner_url' not in data:
        return jsonify({'message': 'Banner URL is required!'}), 400
    
    # Update banner URL in database
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'store_settings.banner_url': data['banner_url']}}
    )
    
    return jsonify({'message': 'Store banner updated successfully!'}), 200

# Bank account management endpoints
@app.route('/seller/bank-accounts', methods=['GET'])
@token_required
def get_bank_accounts(current_user):
    bank_accounts = current_user.get('bank_accounts', [])
    # Don't return full account numbers in response
    for account in bank_accounts:
        if 'account_number' in account:
            account['account_number'] = '*' * (len(account['account_number']) - 4) + account['account_number'][-4:]
    
    return jsonify(bank_accounts), 200

@app.route('/seller/bank-accounts', methods=['POST'])
@token_required
def add_bank_account(current_user):
    data = request.get_json()
    
    # Validate bank account data
    required_fields = ['account_holder_name', 'account_number', 'routing_number', 'bank_name', 'account_type']
    if not all(key in data for key in required_fields):
        return jsonify({'message': 'Missing required bank account fields!'}), 400
    
    # Check if max bank account limit is reached
    bank_accounts = current_user.get('bank_accounts', [])
    if len(bank_accounts) >= 2:
        return jsonify({'message': 'Maximum number of bank accounts (2) reached!'}), 400
    
    # Generate a unique ID for the bank account
    account_id = str(ObjectId())
    
    # Create new bank account object
    new_account = {
        'id': account_id,
        'account_holder_name': data['account_holder_name'],
        'account_number': data['account_number'],
        'routing_number': data['routing_number'],
        'bank_name': data['bank_name'],
        'account_type': data['account_type'],
        'is_primary': data.get('is_primary', False)
    }
    
    # If this is the first account or is_primary is True, ensure it's the only primary
    if new_account['is_primary'] or len(bank_accounts) == 0:
        new_account['is_primary'] = True
        sellers_collection.update_many(
            {'_id': current_user['_id'], 'bank_accounts.is_primary': True},
            {'$set': {'bank_accounts.$.is_primary': False}}
        )
    
    # Add the new bank account
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$push': {'bank_accounts': new_account}}
    )
    
    return jsonify({
        'message': 'Bank account added successfully!',
        'account_id': account_id
    }), 201

@app.route('/seller/bank-accounts/<account_id>', methods=['PUT'])
@token_required
def update_bank_account(current_user, account_id):
    data = request.get_json()
    
    # Find the bank account index
    bank_accounts = current_user.get('bank_accounts', [])
    account_index = next((i for i, acc in enumerate(bank_accounts) if acc.get('id') == account_id), None)
    
    if account_index is None:
        return jsonify({'message': 'Bank account not found!'}), 404
    
    # Fields that can be updated
    allowed_fields = ['account_holder_name', 'bank_name', 'is_primary']
    update_data = {f'bank_accounts.{account_index}.{k}': v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # If setting as primary, ensure it's the only primary
    if data.get('is_primary', False):
        sellers_collection.update_many(
            {'_id': current_user['_id'], 'bank_accounts.is_primary': True},
            {'$set': {'bank_accounts.$.is_primary': False}}
        )
        update_data[f'bank_accounts.{account_index}.is_primary'] = True
    
    # Update the bank account
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Bank account updated successfully!'}), 200

@app.route('/seller/bank-accounts/<account_id>', methods=['DELETE'])
@token_required
def delete_bank_account(current_user, account_id):
    # Check if bank account exists
    bank_accounts = current_user.get('bank_accounts', [])
    account = next((acc for acc in bank_accounts if acc.get('id') == account_id), None)
    
    if not account:
        return jsonify({'message': 'Bank account not found!'}), 404
    
    # Delete the bank account
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$pull': {'bank_accounts': {'id': account_id}}}
    )
    
    # If the deleted account was primary and there are other accounts, make one primary
    if account.get('is_primary', False) and len(bank_accounts) > 1:
        remaining_accounts = [acc for acc in bank_accounts if acc.get('id') != account_id]
        if remaining_accounts:
            sellers_collection.update_one(
                {'_id': current_user['_id'], 'bank_accounts.id': remaining_accounts[0]['id']},
                {'$set': {'bank_accounts.$.is_primary': True}}
            )
    
    return jsonify({'message': 'Bank account deleted successfully!'}), 200

# Verification status endpoint
@app.route('/seller/verification-status', methods=['GET'])
@token_required
def get_verification_status(current_user):
    verification_status = {
        'is_verified': current_user.get('is_verified', False),
        'verification_date': current_user.get('verification_date', None),
        'pending_info': current_user.get('pending_verification_info', [])
    }
    
    return jsonify(verification_status), 200

@app.route('/seller/request-verification', methods=['POST'])
@token_required
def request_verification(current_user):
    # In a real app, this would trigger a verification process
    # This is a simplified version
    
    # Check if already verified
    if current_user.get('is_verified', False):
        return jsonify({'message': 'Seller is already verified!'}), 400
    
    # Update verification request status
    sellers_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {
            'verification_requested': True,
            'verification_requested_date': datetime.datetime.utcnow()
        }}
    )
    
    return jsonify({'message': 'Verification request submitted successfully!'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)