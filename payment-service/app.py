#!/usr/bin/env python3
# Payment Service Microservice
# RESTful API using Flask

from flask import Flask, request, jsonify
import requests
import os
import uuid
import logging
from datetime import datetime
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

# Configuration from environment variables
DB_SERVICE_URL = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
CUSTOMER_SERVICE_URL = os.environ.get('CUSTOMER_SERVICE_URL', 'http://localhost:5000/api')
CART_SERVICE_URL = os.environ.get('CART_SERVICE_URL', 'http://localhost:5008/api')
EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')

# Initialize database tables
def initialize_payment_tables():
    """Initialize payment-related tables in the database"""
    try:
        # Connect to database
        connect_response = requests.post(
            f"{DB_SERVICE_URL}/connect",
            json={"db_name": "/data/payment.sqlite"}
        )
        
        logger.info(f"Database connection: {connect_response.json()}")

        tables_response = requests.get(f"{DB_SERVICE_URL}/tables")
        tables = tables_response.json().get('tables', [])
        
        # Create payment_methods table if it doesn't exist
        if 'payment_methods' not in tables:
            payment_methods_schema = {
                "payment_method_id": "TEXT PRIMARY KEY",
                "customer_id": "TEXT NOT NULL",
                "method_type": "TEXT NOT NULL",  # 'credit_card', 'paypal', etc.
                "card_number": "TEXT",  # Last 4 digits stored for reference
                "card_type": "TEXT",  # Visa, Mastercard, etc.
                "card_holder_name": "TEXT",
                "expiry_date": "TEXT",
                "billing_address": "TEXT",
                "is_default": "BOOLEAN DEFAULT 0",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "payment_methods", "columns": payment_methods_schema}
            )
            
            logger.info(f"Payment methods table initialization: {response.json()}")
            
        # Create delivery_addresses table if it doesn't exist
        if 'delivery_addresses' not in tables:
            addresses_schema = {
                "address_id": "TEXT PRIMARY KEY",
                "customer_id": "TEXT NOT NULL",
                "name": "TEXT NOT NULL",
                "address_line1": "TEXT NOT NULL",
                "address_line2": "TEXT",
                "city": "TEXT NOT NULL",
                "state": "TEXT NOT NULL",
                "country": "TEXT NOT NULL",
                "postal_code": "TEXT NOT NULL",
                "phone_number": "TEXT",
                "is_default": "BOOLEAN DEFAULT 0",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "delivery_addresses", "columns": addresses_schema}
            )
            
            logger.info(f"Delivery addresses table initialization: {response.json()}")
        
        # Create orders table if it doesn't exist
        if 'orders' not in tables:
            orders_schema = {
                "order_id": "TEXT PRIMARY KEY",
                "customer_id": "TEXT NOT NULL",
                "payment_method_id": "TEXT NOT NULL",
                "address_id": "TEXT NOT NULL",
                "total_amount": "REAL NOT NULL",
                "status": "TEXT NOT NULL",  # 'pending', 'processing', 'completed', 'failed'
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (payment_method_id)": "REFERENCES payment_methods(payment_method_id)",
                "FOREIGN KEY (address_id)": "REFERENCES delivery_addresses(address_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "orders", "columns": orders_schema}
            )
            
            logger.info(f"Orders table initialization: {response.json()}")
        
        # Create order_items table if it doesn't exist
        if 'order_items' not in tables:
            order_items_schema = {
                "order_item_id": "TEXT PRIMARY KEY",
                "order_id": "TEXT NOT NULL",
                "product_id": "TEXT NOT NULL",
                "quantity": "INTEGER NOT NULL",
                "price": "REAL NOT NULL",
                "discount": "REAL DEFAULT 0",
                "FOREIGN KEY (order_id)": "REFERENCES orders(order_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "order_items", "columns": order_items_schema}
            )
            
            logger.info(f"Order items table initialization: {response.json()}")
        
        # Create transactions table if it doesn't exist
        if 'transactions' not in tables:
            transactions_schema = {
                "transaction_id": "TEXT PRIMARY KEY",
                "order_id": "TEXT NOT NULL",
                "amount": "REAL NOT NULL",
                "payment_gateway": "TEXT NOT NULL",  # 'stripe', 'paypal', etc.
                "status": "TEXT NOT NULL",  # 'pending', 'completed', 'failed'
                "gateway_transaction_id": "TEXT",
                "gateway_response": "TEXT",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (order_id)": "REFERENCES orders(order_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "transactions", "columns": transactions_schema}
            )
            
            logger.info(f"Transactions table initialization: {response.json()}")
        
        return {"status": "success", "message": "Payment tables initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing payment tables: {str(e)}")
        return {"status": "error", "message": f"Error initializing payment tables: {str(e)}"}

# Initialize tables when the service starts
initialize_payment_tables()

# Authentication decorator (verify token with customer service)
def token_required(f):
    """Decorator to verify customer token with the customer service"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from Authorization header
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Authentication token is missing'}), 401
        
        # Validate token with customer service
        try:
            response = requests.post(
                f"{CUSTOMER_SERVICE_URL}/customers/validate-token",
                json={"token": token}
            )
            
            if response.status_code != 200 or response.json().get('valid') != True:
                return jsonify({'status': 'error', 'message': 'Invalid or expired token'}), 401
            
            # Get customer_id from response
            customer_id = response.json().get('customer').get('customer_id')
            kwargs['customer_id'] = customer_id
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Error validating authentication'}), 500
    
    return decorated

# Payment Method Operations
class PaymentMethodManager:
    def __init__(self, db_service_url):
        self.db_service_url = db_service_url
    
    def get_payment_methods(self, customer_id):
        """Get all payment methods for a customer"""
        try:
            response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            methods = response.json().get('data', [])
            
            # Mask sensitive data
            for method in methods:
                if 'card_number' in method and method['card_number']:
                    # Only keep the last 4 digits, the rest should be already masked in storage
                    method['card_number'] = f"****{method['card_number'][-4:]}"
            
            return {"status": "success", "payment_methods": methods}
        except Exception as e:
            logger.error(f"Error getting payment methods: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_payment_method(self, payment_method_id, customer_id):
        """Get a specific payment method for a customer"""
        try:
            response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "payment_method_id = ? AND customer_id = ?", "params": f"{payment_method_id},{customer_id}"}
            )
            
            methods = response.json().get('data', [])
            
            if not methods:
                return {"status": "error", "message": "Payment method not found"}
            
            method = methods[0]
            
            # Mask sensitive data
            if 'card_number' in method and method['card_number']:
                method['card_number'] = f"****{method['card_number'][-4:]}"
            
            return {"status": "success", "payment_method": method}
        except Exception as e:
            logger.error(f"Error getting payment method: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def add_payment_method(self, customer_id, payment_data):
        """Add a new payment method for a customer"""
        try:
            # Validate required fields
            required_fields = ['method_type']
            for field in required_fields:
                if field not in payment_data:
                    return {"status": "error", "message": f"Missing required field: {field}"}
            
            # Additional validation based on method type
            method_type = payment_data['method_type']
            if method_type == 'credit_card':
                cc_required = ['card_number', 'card_holder_name', 'expiry_date']
                for field in cc_required:
                    if field not in payment_data:
                        return {"status": "error", "message": f"Missing required field for credit card: {field}"}
                
                # Card type detection
                card_number = payment_data['card_number']
                if card_number.startswith('4'):
                    card_type = 'Visa'
                elif card_number.startswith('5'):
                    card_type = 'Mastercard'
                elif card_number.startswith('3'):
                    card_type = 'American Express'
                elif card_number.startswith('6'):
                    card_type = 'Discover'
                else:
                    card_type = 'Other'
                
                payment_data['card_type'] = card_type
                
                # Store only last 4 digits of card number
                payment_data['card_number'] = payment_data['card_number'][-4:]
            
            # Check if this should be the default payment method
            is_default = payment_data.get('is_default', False)
            
            # If making this default, clear any existing default
            if is_default:
                update_data = {
                    "is_default": False,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                requests.put(
                    f"{self.db_service_url}/tables/payment_methods/data",
                    json={"values": update_data, "condition": "customer_id = ? AND is_default = ?", "params": [customer_id, True]}
                )
            
            # Create payment method
            payment_method_id = str(uuid.uuid4())
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            payment_method_data = {
                "payment_method_id": payment_method_id,
                "customer_id": customer_id,
                "method_type": method_type,
                "card_number": payment_data.get('card_number'),
                "card_type": payment_data.get('card_type'),
                "card_holder_name": payment_data.get('card_holder_name'),
                "expiry_date": payment_data.get('expiry_date'),
                "billing_address": payment_data.get('billing_address'),
                "is_default": is_default,
                "created_at": now,
                "updated_at": now
            }
            
            response = requests.post(
                f"{self.db_service_url}/tables/payment_methods/data",
                json=payment_method_data
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to add payment method"}
            
            return {"status": "success", "payment_method_id": payment_method_id, "message": "Payment method added successfully"}
        except Exception as e:
            logger.error(f"Error adding payment method: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def update_payment_method(self, payment_method_id, customer_id, payment_data):
        """Update an existing payment method"""
        try:
            # Check if payment method exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "payment_method_id = ? AND customer_id = ?", "params": f"{payment_method_id},{customer_id}"}
            )
            
            methods = response.json().get('data', [])
            
            if not methods:
                return {"status": "error", "message": "Payment method not found"}
            
            # Check if this should be the default payment method
            is_default = payment_data.get('is_default')
            
            # If making this default, clear any existing default
            if is_default == True:
                update_data = {
                    "is_default": False,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                requests.put(
                    f"{self.db_service_url}/tables/payment_methods/data",
                    json={"values": update_data, "condition": "customer_id = ? AND is_default = ?", "params": [customer_id, True]}
                )
            
            # Update fields
            update_data = {}
            allowed_fields = ['method_type', 'card_holder_name', 'expiry_date', 'billing_address', 'is_default']
            
            for field in allowed_fields:
                if field in payment_data:
                    update_data[field] = payment_data[field]
            
            update_data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            response = requests.put(
                f"{self.db_service_url}/tables/payment_methods/data",
                json={"values": update_data, "condition": "payment_method_id = ?", "params": [payment_method_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to update payment method"}
            
            return {"status": "success", "message": "Payment method updated successfully"}
        except Exception as e:
            logger.error(f"Error updating payment method: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def delete_payment_method(self, payment_method_id, customer_id):
        """Delete a payment method"""
        try:
            # Check if payment method exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "payment_method_id = ? AND customer_id = ?", "params": f"{payment_method_id},{customer_id}"}
            )
            
            methods = response.json().get('data', [])
            
            if not methods:
                return {"status": "error", "message": "Payment method not found"}
            
            method = methods[0]
            
            # Check if this is the only payment method
            response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            all_methods = response.json().get('data', [])
            
            if len(all_methods) == 1:
                return {"status": "error", "message": "Cannot delete the only payment method"}
            
            # If this was the default payment method, set another one as default
            if method.get('is_default', False):
                # Find non-default payment method
                other_method = next((m for m in all_methods if m['payment_method_id'] != payment_method_id), None)
                
                if other_method:
                    update_data = {
                        "is_default": True,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    requests.put(
                        f"{self.db_service_url}/tables/payment_methods/data",
                        json={"values": update_data, "condition": "payment_method_id = ?", "params": [other_method['payment_method_id']]}
                    )
            
            # Delete payment method
            response = requests.delete(
                f"{self.db_service_url}/tables/payment_methods/data",
                json={"condition": "payment_method_id = ?", "params": [payment_method_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to delete payment method"}
            
            return {"status": "success", "message": "Payment method deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting payment method: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def set_default_payment_method(self, payment_method_id, customer_id):
        """Set a payment method as default"""
        try:
            # Check if payment method exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "payment_method_id = ? AND customer_id = ?", "params": f"{payment_method_id},{customer_id}"}
            )
            
            methods = response.json().get('data', [])
            
            if not methods:
                return {"status": "error", "message": "Payment method not found"}
            
            # Clear any existing default
            update_data = {
                "is_default": False,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            requests.put(
                f"{self.db_service_url}/tables/payment_methods/data",
                json={"values": update_data, "condition": "customer_id = ? AND is_default = ?", "params": [customer_id, True]}
            )
            
            # Set this payment method as default
            update_data = {
                "is_default": True,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            response = requests.put(
                f"{self.db_service_url}/tables/payment_methods/data",
                json={"values": update_data, "condition": "payment_method_id = ?", "params": [payment_method_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to set default payment method"}
            
            return {"status": "success", "message": "Default payment method updated successfully"}
        except Exception as e:
            logger.error(f"Error setting default payment method: {str(e)}")
            return {"status": "error", "message": str(e)}

# Address Operations
class AddressManager:
    def __init__(self, db_service_url):
        self.db_service_url = db_service_url
    
    def get_addresses(self, customer_id):
        """Get all delivery addresses for a customer"""
        try:
            response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            addresses = response.json().get('data', [])
            
            return {"status": "success", "addresses": addresses}
        except Exception as e:
            logger.error(f"Error getting addresses: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_address(self, address_id, customer_id):
        """Get a specific address for a customer"""
        try:
            response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "address_id = ? AND customer_id = ?", "params": f"{address_id},{customer_id}"}
            )
            
            addresses = response.json().get('data', [])
            
            if not addresses:
                return {"status": "error", "message": "Address not found"}
            
            return {"status": "success", "address": addresses[0]}
        except Exception as e:
            logger.error(f"Error getting address: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def add_address(self, customer_id, address_data):
        """Add a new delivery address for a customer"""
        try:
            # Validate required fields
            required_fields = ['name', 'address_line1', 'city', 'state', 'country', 'postal_code']
            for field in required_fields:
                if field not in address_data:
                    return {"status": "error", "message": f"Missing required field: {field}"}
            
            # Check if this should be the default address
            is_default = address_data.get('is_default', False)
            
            # If making this default, clear any existing default
            if is_default:
                update_data = {
                    "is_default": False,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                requests.put(
                    f"{self.db_service_url}/tables/delivery_addresses/data",
                    json={"values": update_data, "condition": "customer_id = ? AND is_default = ?", "params": [customer_id, True]}
                )
            
            # Create address
            address_id = str(uuid.uuid4())
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            address_data = {
                "address_id": address_id,
                "customer_id": customer_id,
                "name": address_data.get('name'),
                "address_line1": address_data.get('address_line1'),
                "address_line2": address_data.get('address_line2', ''),
                "city": address_data.get('city'),
                "state": address_data.get('state'),
                "country": address_data.get('country'),
                "postal_code": address_data.get('postal_code'),
                "phone_number": address_data.get('phone_number', ''),
                "is_default": is_default,
                "created_at": now,
                "updated_at": now
            }
            
            response = requests.post(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                json=address_data
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to add address"}
            
            return {"status": "success", "address_id": address_id, "message": "Address added successfully"}
        except Exception as e:
            logger.error(f"Error adding address: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def update_address(self, address_id, customer_id, address_data):
        """Update an existing delivery address"""
        try:
            # Check if address exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "address_id = ? AND customer_id = ?", "params": f"{address_id},{customer_id}"}
            )
            
            addresses = response.json().get('data', [])
            
            if not addresses:
                return {"status": "error", "message": "Address not found"}
            
            # Check if this should be the default address
            is_default = address_data.get('is_default')
            
            # If making this default, clear any existing default
            if is_default == True:
                update_data = {
                    "is_default": False,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                requests.put(
                    f"{self.db_service_url}/tables/delivery_addresses/data",
                    json={"values": update_data, "condition": "customer_id = ? AND is_default = ?", "params": [customer_id, True]}
                )
            
            # Update fields
            update_data = {}
            allowed_fields = ['name', 'address_line1', 'address_line2', 'city', 'state', 'country', 'postal_code', 'phone_number', 'is_default']
            
            for field in allowed_fields:
                if field in address_data:
                    update_data[field] = address_data[field]
            
            update_data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            response = requests.put(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                json={"values": update_data, "condition": "address_id = ?", "params": [address_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to update address"}
            
            return {"status": "success", "message": "Address updated successfully"}
        except Exception as e:
            logger.error(f"Error updating address: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def delete_address(self, address_id, customer_id):
        """Delete a delivery address"""
        try:
            # Check if address exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "address_id = ? AND customer_id = ?", "params": f"{address_id},{customer_id}"}
            )
            
            addresses = response.json().get('data', [])
            
            if not addresses:
                return {"status": "error", "message": "Address not found"}
            
            address = addresses[0]
            
            # Check if this is the only address
            response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            all_addresses = response.json().get('data', [])
            
            if len(all_addresses) == 1:
                return {"status": "error", "message": "Cannot delete the only address"}
            
            # If this was the default address, set another one as default
            if address.get('is_default', False):
                # Find non-default address
                other_address = next((a for a in all_addresses if a['address_id'] != address_id), None)
                
                if other_address:
                    update_data = {
                        "is_default": True,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    requests.put(
                        f"{self.db_service_url}/tables/delivery_addresses/data",
                        json={"values": update_data, "condition": "address_id = ?", "params": [other_address['address_id']]}
                    )
            
            # Delete address
            response = requests.delete(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                json={"condition": "address_id = ?", "params": [address_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to delete address"}
            
            return {"status": "success", "message": "Address deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting address: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def set_default_address(self, address_id, customer_id):
        """Set an address as default"""
        try:
            # Check if address exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "address_id = ? AND customer_id = ?", "params": f"{address_id},{customer_id}"}
            )
            
            addresses = response.json().get('data', [])
            
            if not addresses:
                return {"status": "error", "message": "Address not found"}
            
            # Clear any existing default
            update_data = {
                "is_default": False,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            requests.put(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                json={"values": update_data, "condition": "customer_id = ? AND is_default = ?", "params": [customer_id, True]}
            )
            
            # Set this address as default
            update_data = {
                "is_default": True,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            response = requests.put(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                json={"values": update_data, "condition": "address_id = ?", "params": [address_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to set default address"}
            
            return {"status": "success", "message": "Default address updated successfully"}
        except Exception as e:
            logger.error(f"Error setting default address: {str(e)}")
            return {"status": "error", "message": str(e)}

# Order and Payment Processing
class PaymentProcessor:
    def __init__(self, db_service_url, cart_service_url, email_service_url, email_service_api_key):
        self.db_service_url = db_service_url
        self.cart_service_url = cart_service_url
        self.email_service_url = email_service_url
        self.email_service_api_key = email_service_api_key
    
    def get_customer_cart(self, customer_id, token):
        """Get the customer's cart from cart service"""
        try:
            response = requests.get(
                f"{self.cart_service_url}/cart",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return None, "Failed to retrieve cart"
            
            return response.json().get('cart'), None
        except Exception as e:
            logger.error(f"Error retrieving cart: {str(e)}")
            return None, str(e)
    
    def process_payment(self, customer_id, payment_method_id, address_id, token):
        """Process payment for items in the cart"""
        try:
            # Get customer cart
            cart, error = self.get_customer_cart(customer_id, token)
            
            if error:
                return {"status": "error", "message": error}
            
            if not cart or not cart.get('items') or len(cart.get('items', [])) == 0:
                return {"status": "error", "message": "Cart is empty"}
            
            # Verify payment method exists and belongs to customer
            payment_response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "payment_method_id = ? AND customer_id = ?", "params": f"{payment_method_id},{customer_id}"}
            )
            
            payment_methods = payment_response.json().get('data', [])
            
            if not payment_methods:
                return {"status": "error", "message": "Payment method not found"}
            
            # Verify address exists and belongs to customer
            address_response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "address_id = ? AND customer_id = ?", "params": f"{address_id},{customer_id}"}
            )
            
            addresses = address_response.json().get('data', [])
            
            if not addresses:
                return {"status": "error", "message": "Delivery address not found"}
            
            # Create order
            order_id = str(uuid.uuid4())
            order_data = {
                "order_id": order_id,
                "customer_id": customer_id,
                "payment_method_id": payment_method_id,
                "address_id": address_id,
                "total_amount": cart.get('total_price', 0),
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            order_response = requests.post(
                f"{self.db_service_url}/tables/orders/data",
                json=order_data
            )
            
            if order_response.status_code != 200 or order_response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to create order"}
            
            # Create order items
            for item in cart.get('items', []):
                order_item_id = str(uuid.uuid4())
                
                order_item_data = {
                    "order_item_id": order_item_id,
                    "order_id": order_id,
                    "product_id": item.get('product_id'),
                    "quantity": item.get('quantity'),
                    "price": item.get('product', {}).get('price', 0),
                    "discount": item.get('discount_amount', 0)
                }
                
                item_response = requests.post(
                    f"{self.db_service_url}/tables/order_items/data",
                    json=order_item_data
                )
                
                if item_response.status_code != 200 or item_response.json().get('status') != 'success':
                    # Rollback order if item creation fails
                    self._rollback_order(order_id)
                    return {"status": "error", "message": "Failed to create order items"}
            
            # Process payment with external payment gateway (simplified for demo)
            payment_result = self._simulate_payment_gateway(order_id, cart.get('total_price', 0), payment_method_id)
            
            if not payment_result.get('success'):
                # Update order status to failed
                self._update_order_status(order_id, "failed")
                return {"status": "error", "message": payment_result.get('message', "Payment processing failed")}
            
            # Record transaction
            transaction_id = str(uuid.uuid4())
            transaction_data = {
                "transaction_id": transaction_id,
                "order_id": order_id,
                "amount": cart.get('total_price', 0),
                "payment_gateway": "simulation",  # In a real app, this would be the actual gateway name
                "status": "completed",
                "gateway_transaction_id": payment_result.get('transaction_id'),
                "gateway_response": payment_result.get('gateway_response'),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            transaction_response = requests.post(
                f"{self.db_service_url}/tables/transactions/data",
                json=transaction_data
            )
            
            if transaction_response.status_code != 200 or transaction_response.json().get('status') != 'success':
                # Payment was successful but recording transaction failed - just log the error
                logger.error(f"Failed to record transaction for order {order_id}")
            
            # Clear the cart
            requests.delete(
                f"{self.cart_service_url}/cart/clear",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            # Forward the payment success to the order service
            try:
                ORDER_SERVICE_URL = os.environ.get('ORDER_SERVICE_URL', 'http://localhost:5010/api')
                
                # Send webhook to order service
                order_response = requests.post(
                    f"{ORDER_SERVICE_URL}/orders/payment-webhook",
                    json={
                        "order_id": order_id,
                        "transaction_id": transaction_id,
                        "payment_status": "success"
                    },
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if order_response.status_code != 200:
                    logger.error(f"Failed to notify order service: {order_response.text}")
            except Exception as e:
                logger.error(f"Error notifying order service: {str(e)}")
            
            return {
                "status": "success", 
                "message": "Payment processed successfully", 
                "order_id": order_id,
                "transaction_id": transaction_id
            }
            
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _simulate_payment_gateway(self, order_id, amount, payment_method_id):
        """Simulate payment processing with external gateway"""
        # In a real application, this would integrate with Stripe, PayPal, etc.
        # For this demo, we'll simulate a successful payment most of the time
        
        # 90% success rate for simulation
        import random
        success = random.random() < 0.9
        
        if success:
            return {
                "success": True,
                "transaction_id": f"sim_{uuid.uuid4().hex[:10]}",
                "gateway_response": "Payment accepted",
                "message": "Payment processed successfully"
            }
        else:
            return {
                "success": False,
                "gateway_response": "Card declined",
                "message": "Payment was declined. Please try a different payment method."
            }
    
    def _rollback_order(self, order_id):
        """Rollback order creation if something fails"""
        # Delete order items
        requests.delete(
            f"{self.db_service_url}/tables/order_items/data",
            json={"condition": "order_id = ?", "params": [order_id]}
        )
        
        # Delete order
        requests.delete(
            f"{self.db_service_url}/tables/orders/data",
            json={"condition": "order_id = ?", "params": [order_id]}
        )
    
    def _update_order_status(self, order_id, status):
        """Update order status"""
        update_data = {
            "status": status,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        requests.put(
            f"{self.db_service_url}/tables/orders/data",
            json={"values": update_data, "condition": "order_id = ?", "params": [order_id]}
        )
    
    def _send_order_confirmation_email(self, customer_id, order_id, cart, address):
        """Send order confirmation email to customer"""
        try:
            # Get customer email
            response = requests.get(
                f"{self.db_service_url}/tables/customers/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            customers = response.json().get('data', [])
            
            if not customers:
                logger.error(f"Customer {customer_id} not found for order confirmation email")
                return
            
            customer_email = customers[0].get('email')
            customer_name = f"{customers[0].get('first_name')} {customers[0].get('last_name')}"
            
            # Create email content
            subject = f"Order Confirmation #{order_id[:8]}"
            
            # Format items for email
            items_text = "\n".join([
                f"- {item.get('quantity')} x {item.get('product', {}).get('name')} "
                f"(${float(item.get('product', {}).get('price', 0)):.2f} each)"
                for item in cart.get('items', [])
            ])
            
            # Format address for email
            # Handle address line 2 separately to avoid backslash in f-string expression
            address_line2_text = f"{address.get('address_line2')}\n" if address.get('address_line2') else ""
            address_text = (
                f"{address.get('name')}\n"
                f"{address.get('address_line1')}\n"
                f"{address_line2_text}"
                f"{address.get('city')}, {address.get('state')} {address.get('postal_code')}\n"
                f"{address.get('country')}"
            )
            
            message = (
                f"Dear {customer_name},\n\n"
                f"Thank you for your order! Your order #{order_id[:8]} has been confirmed.\n\n"
                f"Order Details:\n"
                f"{items_text}\n\n"
                f"Subtotal: ${float(cart.get('subtotal', 0)):.2f}\n"
                f"Discount: ${float(cart.get('discount', 0)):.2f}\n"
                f"Total: ${float(cart.get('total_price', 0)):.2f}\n\n"
                f"Shipping Address:\n"
                f"{address_text}\n\n"
                f"We'll notify you when your order ships.\n\n"
                f"Thank you for shopping with us!\n"
                f"The E-commerce Team"
            )
            
            # Send email through email service
            requests.post(
                f"{self.email_service_url}/send/notification",
                json={
                    "email": customer_email,
                    "subject": subject,
                    "message": message
                },
                headers={"X-API-Key": self.email_service_api_key}
            )
            
        except Exception as e:
            logger.error(f"Error sending order confirmation email: {str(e)}")
    
    def get_order_history(self, customer_id):
        """Get order history for a customer"""
        try:
            # Get all orders for this customer
            response = requests.get(
                f"{self.db_service_url}/tables/orders/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            orders = response.json().get('data', [])
            
            # Enrich orders with items
            for order in orders:
                # Get order items
                items_response = requests.get(
                    f"{self.db_service_url}/tables/order_items/data",
                    params={"condition": "order_id = ?", "params": order['order_id']}
                )
                
                order['items'] = items_response.json().get('data', [])
                
                # Get transaction information
                transaction_response = requests.get(
                    f"{self.db_service_url}/tables/transactions/data",
                    params={"condition": "order_id = ?", "params": order['order_id']}
                )
                
                transactions = transaction_response.json().get('data', [])
                if transactions:
                    order['transaction'] = transactions[0]
                
                # Get address information
                address_response = requests.get(
                    f"{self.db_service_url}/tables/delivery_addresses/data",
                    params={"condition": "address_id = ?", "params": order['address_id']}
                )
                
                addresses = address_response.json().get('data', [])
                if addresses:
                    order['shipping_address'] = addresses[0]
                
                # Get payment method information (mask sensitive data)
                payment_response = requests.get(
                    f"{self.db_service_url}/tables/payment_methods/data",
                    params={"condition": "payment_method_id = ?", "params": order['payment_method_id']}
                )
                
                payment_methods = payment_response.json().get('data', [])
                if payment_methods:
                    payment_method = payment_methods[0]
                    
                    # Mask card number
                    if 'card_number' in payment_method and payment_method['card_number']:
                        payment_method['card_number'] = f"****{payment_method['card_number'][-4:]}"
                    
                    order['payment_method'] = payment_method
            
            return {"status": "success", "orders": orders}
        except Exception as e:
            logger.error(f"Error getting order history: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_order_details(self, order_id, customer_id):
        """Get detailed information about a specific order"""
        try:
            # Get order data
            response = requests.get(
                f"{self.db_service_url}/tables/orders/data",
                params={"condition": "order_id = ? AND customer_id = ?", "params": f"{order_id},{customer_id}"}
            )
            
            orders = response.json().get('data', [])
            
            if not orders:
                return {"status": "error", "message": "Order not found"}
            
            order = orders[0]
            
            # Get order items
            items_response = requests.get(
                f"{self.db_service_url}/tables/order_items/data",
                params={"condition": "order_id = ?", "params": order_id}
            )
            
            order['items'] = items_response.json().get('data', [])
            
            # Get transaction information
            transaction_response = requests.get(
                f"{self.db_service_url}/tables/transactions/data",
                params={"condition": "order_id = ?", "params": order_id}
            )
            
            transactions = transaction_response.json().get('data', [])
            if transactions:
                order['transaction'] = transactions[0]
            
            # Get address information
            address_response = requests.get(
                f"{self.db_service_url}/tables/delivery_addresses/data",
                params={"condition": "address_id = ?", "params": order['address_id']}
            )
            
            addresses = address_response.json().get('data', [])
            if addresses:
                order['shipping_address'] = addresses[0]
            
            # Get payment method information (mask sensitive data)
            payment_response = requests.get(
                f"{self.db_service_url}/tables/payment_methods/data",
                params={"condition": "payment_method_id = ?", "params": order['payment_method_id']}
            )
            
            payment_methods = payment_response.json().get('data', [])
            if payment_methods:
                payment_method = payment_methods[0]
                
                # Mask card number
                if 'card_number' in payment_method and payment_method['card_number']:
                    payment_method['card_number'] = f"****{payment_method['card_number'][-4:]}"
                
                order['payment_method'] = payment_method
            
            return {"status": "success", "order": order}
        except Exception as e:
            logger.error(f"Error getting order details: {str(e)}")
            return {"status": "error", "message": str(e)}

# Initialize managers
payment_method_manager = PaymentMethodManager(DB_SERVICE_URL)
address_manager = AddressManager(DB_SERVICE_URL)
payment_processor = PaymentProcessor(DB_SERVICE_URL, CART_SERVICE_URL, EMAIL_SERVICE_URL, EMAIL_SERVICE_API_KEY)

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check connections to other services
        services_status = {}
        
        # Check DB service
        try:
            db_response = requests.get(f"{DB_SERVICE_URL}/health")
            services_status['db_service'] = "up" if db_response.status_code == 200 else "down"
        except:
            services_status['db_service'] = "down"
        
        # Check Customer service
        try:
            customer_response = requests.get(f"{CUSTOMER_SERVICE_URL}/health")
            services_status['customer_service'] = "up" if customer_response.status_code == 200 else "down"
        except:
            services_status['customer_service'] = "down"
        
        # Check Cart service
        try:
            cart_response = requests.get(f"{CART_SERVICE_URL}/health")
            services_status['cart_service'] = "up" if cart_response.status_code == 200 else "down"
        except:
            services_status['cart_service'] = "down"
        
        # Check Email service
        try:
            email_response = requests.get(f"{EMAIL_SERVICE_URL}/api/health")
            services_status['email_service'] = "up" if email_response.status_code == 200 else "down"
        except:
            services_status['email_service'] = "down"
        
        return jsonify({
            "status": "up",
            "service": "Payment API",
            "services": services_status,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            "status": "error",
            "service": "Payment API",
            "message": str(e),
            "version": "1.0.0"
        }), 500

# Payment Methods Routes
@app.route('/api/payment-methods', methods=['GET'])
@token_required
def get_payment_methods(customer_id):
    """Get all payment methods for a customer"""
    try:
        result = payment_method_manager.get_payment_methods(customer_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting payment methods: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/payment-methods/<payment_method_id>', methods=['GET'])
@token_required
def get_payment_method(customer_id, payment_method_id):
    """Get a specific payment method"""
    try:
        result = payment_method_manager.get_payment_method(payment_method_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 404
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting payment method: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/payment-methods', methods=['POST'])
@token_required
def add_payment_method(customer_id):
    """Add a new payment method"""
    try:
        data = request.get_json()
        
        result = payment_method_manager.add_payment_method(customer_id, data)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error adding payment method: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/payment-methods/<payment_method_id>', methods=['PUT'])
@token_required
def update_payment_method(customer_id, payment_method_id):
    """Update a payment method"""
    try:
        data = request.get_json()
        
        result = payment_method_manager.update_payment_method(payment_method_id, customer_id, data)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating payment method: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/payment-methods/<payment_method_id>', methods=['DELETE'])
@token_required
def delete_payment_method(customer_id, payment_method_id):
    """Delete a payment method"""
    try:
        result = payment_method_manager.delete_payment_method(payment_method_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting payment method: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/payment-methods/<payment_method_id>/set-default', methods=['PUT'])
@token_required
def set_default_payment_method(customer_id, payment_method_id):
    """Set a payment method as default"""
    try:
        result = payment_method_manager.set_default_payment_method(payment_method_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error setting default payment method: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Delivery Addresses Routes
@app.route('/api/addresses', methods=['GET'])
@token_required
def get_addresses(customer_id):
    """Get all delivery addresses for a customer"""
    try:
        result = address_manager.get_addresses(customer_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting addresses: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses/<address_id>', methods=['GET'])
@token_required
def get_address(customer_id, address_id):
    """Get a specific delivery address"""
    try:
        result = address_manager.get_address(address_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 404
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting address: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses', methods=['POST'])
@token_required
def add_address(customer_id):
    """Add a new delivery address"""
    try:
        data = request.get_json()
        
        result = address_manager.add_address(customer_id, data)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error adding address: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses/<address_id>', methods=['PUT'])
@token_required
def update_address(customer_id, address_id):
    """Update a delivery address"""
    try:
        data = request.get_json()
        
        result = address_manager.update_address(address_id, customer_id, data)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating address: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses/<address_id>', methods=['DELETE'])
@token_required
def delete_address(customer_id, address_id):
    """Delete a delivery address"""
    try:
        result = address_manager.delete_address(address_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting address: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses/<address_id>/set-default', methods=['PUT'])
@token_required
def set_default_address(customer_id, address_id):
    """Set an address as default"""
    try:
        result = address_manager.set_default_address(address_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error setting default address: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Order and Payment Routes
@app.route('/api/checkout', methods=['POST'])
@token_required
def checkout(customer_id):
    """Process checkout with payment"""
    try:
        data = request.get_json()
        
        # Get token from Authorization header
        auth_header = request.headers['Authorization']
        token = auth_header.split(' ')[1]
        
        if 'payment_method_id' not in data or 'address_id' not in data:
            return jsonify({
                "status": "error", 
                "message": "Payment method ID and delivery address ID are required"
            }), 400
        
        payment_method_id = data['payment_method_id']
        address_id = data['address_id']
        
        result = payment_processor.process_payment(customer_id, payment_method_id, address_id, token)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing checkout: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders', methods=['GET'])
@token_required
def get_order_history(customer_id):
    """Get order history for a customer"""
    try:
        result = payment_processor.get_order_history(customer_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting order history: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<order_id>', methods=['GET'])
@token_required
def get_order_details(customer_id, order_id):
    """Get detailed information about a specific order"""
    try:
        result = payment_processor.get_order_details(order_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 404
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting order details: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5009))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')