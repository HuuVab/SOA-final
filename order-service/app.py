#!/usr/bin/env python3
# Order Service Microservice
# RESTful API using Flask

from flask import Flask, request, jsonify
import requests
import os
import uuid
import logging
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

# Configuration from environment variables
DB_SERVICE_URL = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
CUSTOMER_SERVICE_URL = os.environ.get('CUSTOMER_SERVICE_URL', 'http://localhost:5000/api')
PAYMENT_SERVICE_URL = os.environ.get('PAYMENT_SERVICE_URL', 'http://localhost:5009/api')
PRODUCT_SERVICE_URL = os.environ.get('PRODUCT_SERVICE_URL', 'http://localhost:5005/api')
EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'http://localhost:5002')
EMAIL_SERVICE_API_KEY = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')

# Initialize database tables
def initialize_order_tables():
    """Initialize order-related tables in the database"""
    try:
        # Connect to database
        connect_response = requests.post(
            f"{DB_SERVICE_URL}/connect",
            json={"db_name": "/data/orders.sqlite"}
        )
        
        logger.info(f"Database connection: {connect_response.json()}")

        tables_response = requests.get(f"{DB_SERVICE_URL}/tables")
        tables = tables_response.json().get('tables', [])
        
        # Create orders table if it doesn't exist
        if 'orders' not in tables:
            orders_schema = {
                "order_id": "TEXT PRIMARY KEY",
                "customer_id": "TEXT NOT NULL",
                "transaction_id": "TEXT NOT NULL",
                "payment_method_id": "TEXT NOT NULL",
                "address_id": "TEXT NOT NULL",
                "total_amount": "REAL NOT NULL",
                "status": "TEXT NOT NULL",  # 'pending', 'processing', 'shipped', 'delivered', 'cancelled'
                "tracking_number": "TEXT",
                "carrier": "TEXT",
                "notes": "TEXT",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "estimated_delivery": "TIMESTAMP"
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
                "product_name": "TEXT NOT NULL",
                "product_image": "TEXT",
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
        
        # Create order_status_history table if it doesn't exist
        if 'order_status_history' not in tables:
            status_history_schema = {
                "history_id": "TEXT PRIMARY KEY",
                "order_id": "TEXT NOT NULL",
                "status": "TEXT NOT NULL",
                "notes": "TEXT",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (order_id)": "REFERENCES orders(order_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "order_status_history", "columns": status_history_schema}
            )
            
            logger.info(f"Order status history table initialization: {response.json()}")
        
        return {"status": "success", "message": "Order tables initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing order tables: {str(e)}")
        return {"status": "error", "message": f"Error initializing order tables: {str(e)}"}

# Initialize tables when the service starts
initialize_order_tables()

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

# Admin authentication decorator
def admin_required(f):
    """Decorator to verify admin token"""
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
        
        # TODO: Implement proper admin authentication
        # This is a simplified version for demo purposes
        admin_token = os.environ.get('ADMIN_TOKEN', 'admin-secret-token')
        
        if token != admin_token:
            return jsonify({'status': 'error', 'message': 'Invalid admin token'}), 401
        
        return f(*args, **kwargs)
    
    return decorated

# Order Management
class OrderManager:
    def __init__(self, db_service_url, payment_service_url, product_service_url, email_service_url, email_service_api_key):
        self.db_service_url = db_service_url
        self.payment_service_url = payment_service_url
        self.product_service_url = product_service_url
        self.email_service_url = email_service_url
        self.email_service_api_key = email_service_api_key
    
    def create_order_from_payment(self, payment_data):
        """Create an order from successful payment data"""
        try:
            # Extract data from payment response
            if not payment_data or 'transaction_id' not in payment_data or 'order_id' not in payment_data:
                return {"status": "error", "message": "Invalid payment data"}
            
            transaction_id = payment_data.get('transaction_id')
            payment_order_id = payment_data.get('order_id')
            
            # Verify payment with payment service
            # In a real application, you would verify the payment status
            # For demo purposes, we'll assume the payment service has verified it
            
            # Get order details from payment service
            payment_order_response = requests.get(
                f"{self.payment_service_url}/orders/{payment_order_id}",
                headers={"Authorization": request.headers.get('Authorization')}
            )
            
            if payment_order_response.status_code != 200:
                return {"status": "error", "message": "Failed to retrieve payment order details"}
            
            payment_order = payment_order_response.json().get('order')
            
            if not payment_order:
                return {"status": "error", "message": "Order details not found"}
            
            # Create a new order
            order_id = str(uuid.uuid4())
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Calculate estimated delivery (7 days from now)
            estimated_delivery = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            
            order_data = {
                "order_id": order_id,
                "customer_id": payment_order.get('customer_id'),
                "transaction_id": transaction_id,
                "payment_method_id": payment_order.get('payment_method_id'),
                "address_id": payment_order.get('address_id'),
                "total_amount": payment_order.get('total_amount', 0),
                "status": "processing",
                "tracking_number": None,
                "carrier": None,
                "notes": "Order created from successful payment",
                "created_at": now,
                "updated_at": now,
                "estimated_delivery": estimated_delivery
            }
            
            # Insert order
            order_response = requests.post(
                f"{self.db_service_url}/tables/orders/data",
                json=order_data
            )
            
            if order_response.status_code != 200 or order_response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to create order"}
            
            # Create order items
            for item in payment_order.get('items', []):
                order_item_id = str(uuid.uuid4())
                
                # Get product details from product service
                product_response = requests.get(
                    f"{self.product_service_url}/products/{item.get('product_id')}"
                )
                
                product_name = "Unknown Product"
                product_image = None
                
                if product_response.status_code == 200 and product_response.json().get('status') == 'success':
                    product = product_response.json().get('data')
                    product_name = product.get('name', "Unknown Product")
                    product_image = product.get('image_url')
                
                order_item_data = {
                    "order_item_id": order_item_id,
                    "order_id": order_id,
                    "product_id": item.get('product_id'),
                    "product_name": product_name,
                    "product_image": product_image,
                    "quantity": item.get('quantity'),
                    "price": item.get('price', 0),
                    "discount": item.get('discount', 0)
                }
                
                item_response = requests.post(
                    f"{self.db_service_url}/tables/order_items/data",
                    json=order_item_data
                )
                
                if item_response.status_code != 200 or item_response.json().get('status') != 'success':
                    logger.error(f"Failed to create order item: {item_response.json()}")
            
            # Record initial status
            self.add_status_history(order_id, "processing", "Order created and processing")
            
            # Send order confirmation email
            self._send_order_confirmation_email(
                payment_order.get('customer_id'),
                order_id, 
                payment_order.get('items', []),
                payment_order.get('total_amount', 0),
                payment_order.get('shipping_address', {})
            )
            
            return {
                "status": "success", 
                "message": "Order created successfully", 
                "order_id": order_id
            }
        except Exception as e:
            logger.error(f"Error creating order from payment: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_customer_orders(self, customer_id):
        """Get all orders for a customer"""
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
                
                # Get latest status history
                status_response = requests.get(
                    f"{self.db_service_url}/tables/order_status_history/data",
                    params={"condition": "order_id = ?", "params": order['order_id']}
                )
                
                status_history = status_response.json().get('data', [])
                
                # Sort by created_at descending
                status_history.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                
                order['status_history'] = status_history
            
            return {"status": "success", "orders": orders}
        except Exception as e:
            logger.error(f"Error getting customer orders: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_order_details(self, order_id, customer_id=None):
        """Get detailed information about a specific order"""
        try:
            # Construct the condition based on whether customer_id is provided
            condition = "order_id = ?"
            params = order_id
            
            if customer_id:
                condition = "order_id = ? AND customer_id = ?"
                params = f"{order_id},{customer_id}"
            
            # Get order data
            response = requests.get(
                f"{self.db_service_url}/tables/orders/data",
                params={"condition": condition, "params": params}
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
            
            # Get status history
            status_response = requests.get(
                f"{self.db_service_url}/tables/order_status_history/data",
                params={"condition": "order_id = ?", "params": order_id}
            )
            
            status_history = status_response.json().get('data', [])
            
            # Sort by created_at descending
            status_history.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            order['status_history'] = status_history
            
            # Get customer information
            customer_id = order.get('customer_id')
            if customer_id:
                try:
                    customer_response = requests.get(
                        f"{CUSTOMER_SERVICE_URL}/customers/profile",
                        headers={"Authorization": request.headers.get('Authorization')}
                    )
                    
                    if customer_response.status_code == 200:
                        customer_data = customer_response.json().get('customer', {})
                        order['customer'] = {
                            "customer_id": customer_data.get('customer_id'),
                            "email": customer_data.get('email'),
                            "first_name": customer_data.get('first_name'),
                            "last_name": customer_data.get('last_name'),
                            "phone": customer_data.get('phone')
                        }
                except Exception as e:
                    logger.error(f"Error fetching customer data: {str(e)}")
            
            # Get shipping address
            address_id = order.get('address_id')
            if address_id:
                try:
                    address_response = requests.get(
                        f"{self.payment_service_url}/addresses/{address_id}",
                        headers={"Authorization": request.headers.get('Authorization')}
                    )
                    
                    if address_response.status_code == 200:
                        address_data = address_response.json().get('address', {})
                        order['shipping_address'] = address_data
                except Exception as e:
                    logger.error(f"Error fetching address data: {str(e)}")
            
            return {"status": "success", "order": order}
        except Exception as e:
            logger.error(f"Error getting order details: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def update_order_status(self, order_id, status, notes=None, tracking_number=None, carrier=None):
        """Update an order's status and add to history"""
        try:
            # Check if order exists
            response = requests.get(
                f"{self.db_service_url}/tables/orders/data",
                params={"condition": "order_id = ?", "params": order_id}
            )
            
            orders = response.json().get('data', [])
            
            if not orders:
                return {"status": "error", "message": "Order not found"}
            
            order = orders[0]
            
            # Validate status transition
            current_status = order.get('status')
            
            if not self._is_valid_status_transition(current_status, status):
                return {
                    "status": "error", 
                    "message": f"Invalid status transition from {current_status} to {status}"
                }
            
            # Update order data
            update_data = {
                "status": status,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if tracking_number:
                update_data["tracking_number"] = tracking_number
            
            if carrier:
                update_data["carrier"] = carrier
            
            response = requests.put(
                f"{self.db_service_url}/tables/orders/data",
                json={"values": update_data, "condition": "order_id = ?", "params": [order_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to update order status"}
            
            # Add status to history
            history_result = self.add_status_history(order_id, status, notes)
            
            if history_result['status'] != 'success':
                return history_result
            
            # Send notification email if status changes
            if current_status != status:
                self._send_status_update_email(order_id, status)
            
            return {"status": "success", "message": "Order status updated successfully"}
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def add_status_history(self, order_id, status, notes=None):
        """Add a status change to the order's history"""
        try:
            history_id = str(uuid.uuid4())
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            history_data = {
                "history_id": history_id,
                "order_id": order_id,
                "status": status,
                "notes": notes,
                "created_at": now
            }
            
            response = requests.post(
                f"{self.db_service_url}/tables/order_status_history/data",
                json=history_data
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to add status history"}
            
            return {"status": "success", "message": "Status history added successfully"}
        except Exception as e:
            logger.error(f"Error adding status history: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def cancel_order(self, order_id, customer_id, reason):
        """Cancel an order if it's in a cancellable state"""
        try:
            # Check if order exists and belongs to customer
            response = requests.get(
                f"{self.db_service_url}/tables/orders/data",
                params={"condition": "order_id = ? AND customer_id = ?", "params": f"{order_id},{customer_id}"}
            )
            
            orders = response.json().get('data', [])
            
            if not orders:
                return {"status": "error", "message": "Order not found"}
            
            order = orders[0]
            current_status = order.get('status')
            
            # Check if order can be cancelled
            if current_status not in ['pending', 'processing']:
                return {
                    "status": "error", 
                    "message": f"Orders in '{current_status}' status cannot be cancelled"
                }
            
            # Update order status
            update_result = self.update_order_status(order_id, "cancelled", f"Cancelled by customer: {reason}")
            
            if update_result['status'] != 'success':
                return update_result
            
            # TODO: Handle refund if needed
            
            return {"status": "success", "message": "Order cancelled successfully"}
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _is_valid_status_transition(self, from_status, to_status):
        """Check if a status transition is valid"""
        # Define valid transitions
        valid_transitions = {
            'pending': ['processing', 'cancelled'],
            'processing': ['shipped', 'cancelled'],
            'shipped': ['delivered', 'cancelled'],
            'delivered': [],  # No transitions from delivered
            'cancelled': []   # No transitions from cancelled
        }
        
        # Check if the transition is valid
        return to_status in valid_transitions.get(from_status, [])
    
    def _send_order_confirmation_email(self, customer_id, order_id, items, total_amount, address):
        """Send order confirmation email to customer"""
        try:
            # Get customer email
            customer_response = requests.get(
                f"{self.db_service_url}/tables/customers/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            customers = customer_response.json().get('data', [])
            
            if not customers:
                logger.error(f"Customer {customer_id} not found for order confirmation email")
                return
            
            customer_email = customers[0].get('email')
            customer_name = f"{customers[0].get('first_name')} {customers[0].get('last_name')}"
            
            # Create email content
            subject = f"Order Confirmation #{order_id[:8]}"
            
            # Format items for email
            items_text = "\n".join([
                f"- {item.get('quantity')} x {item.get('product_name')} "
                f"(${float(item.get('price', 0)):.2f} each)"
                for item in items
            ])
            
            # Format address for email
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
                f"Thank you for your order! Your order #{order_id[:8]} has been confirmed and is now being processed.\n\n"
                f"Order Details:\n"
                f"{items_text}\n\n"
                f"Total: ${float(total_amount):.2f}\n\n"
                f"Shipping Address:\n"
                f"{address_text}\n\n"
                f"You can track your order status in your account. We'll notify you when your order ships.\n\n"
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
    
    def _send_status_update_email(self, order_id, new_status):
        """Send status update email to customer"""
        try:
            # Get order details
            order_result = self.get_order_details(order_id)
            
            if order_result['status'] != 'success':
                logger.error(f"Error getting order details for status update email: {order_result['message']}")
                return
            
            order = order_result['order']
            customer_id = order.get('customer_id')
            
            # Get customer email
            customer_response = requests.get(
                f"{self.db_service_url}/tables/customers/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            customers = customer_response.json().get('data', [])
            
            if not customers:
                logger.error(f"Customer {customer_id} not found for status update email")
                return
            
            customer_email = customers[0].get('email')
            customer_name = f"{customers[0].get('first_name')} {customers[0].get('last_name')}"
            
            # Create email content based on status
            subject = f"Order #{order_id[:8]} Update: {new_status.capitalize()}"
            
            message = f"Dear {customer_name},\n\n"
            
            if new_status == 'processing':
                message += (
                    f"Your order #{order_id[:8]} is now being processed. We're preparing your items for shipment.\n\n"
                    f"You can track your order status in your account. We'll notify you when your order ships.\n\n"
                )
            elif new_status == 'shipped':
                tracking_info = ""
                if order.get('tracking_number') and order.get('carrier'):
                    tracking_info = (
                        f"Tracking Number: {order.get('tracking_number')}\n"
                        f"Carrier: {order.get('carrier')}\n\n"
                    )
                
                message += (
                    f"Great news! Your order #{order_id[:8]} has been shipped and is on its way to you.\n\n"
                    f"{tracking_info}"
                    f"Estimated delivery: {order.get('estimated_delivery')}\n\n"
                )
            elif new_status == 'delivered':
                message += (
                    f"Your order #{order_id[:8]} has been delivered!\n\n"
                    f"We hope you enjoy your purchase. If you have any issues with your order, "
                    f"please contact our customer support.\n\n"
                )
            elif new_status == 'cancelled':
                message += (
                    f"Your order #{order_id[:8]} has been cancelled.\n\n"
                    f"If you have any questions about your cancellation, please contact our customer support.\n\n"
                )
            
            message += "Thank you for shopping with us!\nThe E-commerce Team"
            
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
            logger.error(f"Error sending status update email: {str(e)}")

# Initialize order manager
order_manager = OrderManager(
    DB_SERVICE_URL, 
    PAYMENT_SERVICE_URL, 
    PRODUCT_SERVICE_URL,
    EMAIL_SERVICE_URL,
    EMAIL_SERVICE_API_KEY
)

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
        
        # Check Payment service
        try:
            payment_response = requests.get(f"{PAYMENT_SERVICE_URL}/health")
            services_status['payment_service'] = "up" if payment_response.status_code == 200 else "down"
        except:
            services_status['payment_service'] = "down"
        
        # Check Product service
        try:
            product_response = requests.get(f"{PRODUCT_SERVICE_URL}/health")
            services_status['product_service'] = "up" if product_response.status_code == 200 else "down"
        except:
            services_status['product_service'] = "down"
        
        return jsonify({
            "status": "up",
            "service": "Order API",
            "services": services_status,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            "status": "error",
            "service": "Order API",
            "message": str(e),
            "version": "1.0.0"
        }), 500

# Order Routes - Customer Facing

@app.route('/api/orders', methods=['GET'])
@token_required
def get_customer_orders(customer_id):
    """Get all orders for the authenticated customer"""
    try:
        result = order_manager.get_customer_orders(customer_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting customer orders: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<order_id>', methods=['GET'])
@token_required
def get_customer_order_details(customer_id, order_id):
    """Get details for a specific order belonging to the customer"""
    try:
        result = order_manager.get_order_details(order_id, customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 404
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting order details: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<order_id>/cancel', methods=['POST'])
@token_required
def cancel_customer_order(customer_id, order_id):
    """Cancel an order if it's in a cancellable state"""
    try:
        data = request.get_json()
        
        if not data or 'reason' not in data:
            return jsonify({"status": "error", "message": "Cancellation reason is required"}), 400
        
        reason = data['reason']
        
        result = order_manager.cancel_order(order_id, customer_id, reason)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Order Routes - Payment Service Webhook

@app.route('/api/orders/payment-webhook', methods=['POST'])
def payment_webhook():
    """Webhook to create an order from successful payment"""
    try:
        data = request.get_json()
        
        # Forward the authorization header
        result = order_manager.create_order_from_payment(data)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in payment webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Order Routes - Admin

@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def get_all_orders():
    """Get all orders (admin only)"""
    try:
        # Get query parameters for filtering
        status = request.args.get('status')
        customer_id = request.args.get('customer_id')
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)
        
        # Construct condition string if filters are applied
        condition = " AND ".join(conditions) if conditions else None
        
        # Query the orders
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/orders/data",
            params={
                "condition": condition, 
                "params": ",".join(params) if params else None
            }
        )
        
        orders = response.json().get('data', [])
        
        return jsonify({"status": "success", "orders": orders})
    except Exception as e:
        logger.error(f"Error getting all orders: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/orders/<order_id>', methods=['GET'])
@admin_required
def get_admin_order_details(order_id):
    """Get order details (admin only)"""
    try:
        result = order_manager.get_order_details(order_id)
        
        if result['status'] != 'success':
            return jsonify(result), 404
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting admin order details: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/orders/<order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    """Update order status (admin only)"""
    try:
        data = request.get_json()
        
        if not data or 'status' not in data:
            return jsonify({"status": "error", "message": "Status is required"}), 400
        
        status = data['status']
        notes = data.get('notes')
        tracking_number = data.get('tracking_number')
        carrier = data.get('carrier')
        
        result = order_manager.update_order_status(order_id, status, notes, tracking_number, carrier)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5010))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')
