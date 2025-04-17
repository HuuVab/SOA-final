"""
User Authentication Microservice
--------------------------------
Handles user registration, authentication, and profile management.
"""

from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import jwt
import datetime
import os
from functools import wraps

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
users_collection = db['users']

# Create indexes for email (for uniqueness and faster queries)
users_collection.create_index("email", unique=True)

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
            current_user = users_collection.find_one({'_id': data['user_id']})
            if not current_user:
                return jsonify({'message': 'User not found!'}), 401
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if required fields are present
    if not all(key in data for key in ['email', 'password', 'name']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    # Check if user already exists
    if users_collection.find_one({'email': data['email']}):
        return jsonify({'message': 'User already exists!'}), 409
    
    # Hash the password
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    # Prepare user object
    new_user = {
        'email': data['email'],
        'password': hashed_password,
        'name': data['name'],
        'created_at': datetime.datetime.utcnow(),
        'is_active': True,
        'role': 'customer'  # Default role
    }
    
    # Insert user into database
    result = users_collection.insert_one(new_user)
    
    return jsonify({
        'message': 'User registered successfully!',
        'user_id': str(result.inserted_id)
    }), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'password']):
        return jsonify({'message': 'Missing email or password!'}), 400
    
    user = users_collection.find_one({'email': data['email']})
    
    if not user or not bcrypt.check_password_hash(user['password'], data['password']):
        return jsonify({'message': 'Invalid credentials!'}), 401
    
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

@app.route('/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    # Remove sensitive information
    user_data = {
        'id': str(current_user['_id']),
        'email': current_user['email'],
        'name': current_user['name'],
        'role': current_user['role'],
        'created_at': current_user['created_at']
    }
    
    return jsonify(user_data), 200

@app.route('/user/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json()
    
    # Fields that can be updated
    allowed_fields = ['name', 'phone', 'address']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'No valid fields to update!'}), 400
    
    # Update user in database
    users_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': update_data}
    )
    
    return jsonify({'message': 'Profile updated successfully!'}), 200

@app.route('/user/change-password', methods=['POST'])
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
    users_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'password': hashed_password}}
    )
    
    return jsonify({'message': 'Password changed successfully!'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
