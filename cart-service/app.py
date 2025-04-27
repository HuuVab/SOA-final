#!/usr/bin/env python3
# Cart Service Microservice
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
PRODUCT_SERVICE_URL = os.environ.get('PRODUCT_SERVICE_URL', 'http://localhost:5005/api')
PROMOTION_SERVICE_URL = os.environ.get('PROMOTION_SERVICE_URL', 'http://localhost:5006/api')

# Initialize database tables for carts
def initialize_cart_tables():
    """Initialize the cart and cart_items tables in the database"""
    try:
        # Connect to database
        connect_response = requests.post(
            f"{DB_SERVICE_URL}/connect",
            json={"db_name": "cart.sqlite"}
        )
        
        logger.info(f"Database connection: {connect_response.json()}")

        tables_response = requests.get(f"{DB_SERVICE_URL}/tables")
        tables = tables_response.json().get('tables', [])
        
        # Create carts table if it doesn't exist
        if 'carts' not in tables:
            cart_schema = {
                "cart_id": "TEXT PRIMARY KEY",
                "customer_id": "TEXT NOT NULL",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "carts", "columns": cart_schema}
            )
            
            logger.info(f"Carts table initialization: {response.json()}")
            
        # Create cart_items table if it doesn't exist
        if 'cart_items' not in tables:
            cart_items_schema = {
                "item_id": "TEXT PRIMARY KEY",
                "cart_id": "TEXT NOT NULL",
                "product_id": "TEXT NOT NULL",
                "quantity": "INTEGER NOT NULL DEFAULT 1",
                "added_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (cart_id)": "REFERENCES carts(cart_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "cart_items", "columns": cart_items_schema}
            )
            
            logger.info(f"Cart items table initialization: {response.json()}")
        
        return {"status": "success", "message": "Cart tables initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing cart tables: {str(e)}")
        return {"status": "error", "message": f"Error initializing cart tables: {str(e)}"}

# Initialize tables when the service starts
initialize_cart_tables()

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

# Cart operations class
class CartManager:
    def __init__(self, db_service_url, product_service_url, promotion_service_url=None):
        self.db_service_url = db_service_url
        self.product_service_url = product_service_url
        self.promotion_service_url = promotion_service_url
    
    def get_or_create_cart(self, customer_id):
        """Get an existing cart for a customer or create a new one"""
        try:
            # Check if customer already has a cart
            response = requests.get(
                f"{self.db_service_url}/tables/carts/data",
                params={"condition": "customer_id = ?", "params": customer_id}
            )
            
            carts = response.json().get('data', [])
            
            if carts:
                # Customer already has a cart
                return {"status": "success", "cart": carts[0]}
            else:
                # Create a new cart for the customer
                cart_id = str(uuid.uuid4())
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cart_data = {
                    "cart_id": cart_id,
                    "customer_id": customer_id,
                    "created_at": now,
                    "updated_at": now
                }
                
                response = requests.post(
                    f"{self.db_service_url}/tables/carts/data",
                    json=cart_data
                )
                
                if response.status_code != 200 or response.json().get('status') != 'success':
                    return {"status": "error", "message": "Failed to create cart"}
                
                return {"status": "success", "cart": cart_data}
        except Exception as e:
            logger.error(f"Error in get_or_create_cart: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_product_promotion(self, product_id):
        """Get active promotion for a specific product"""
        if not self.promotion_service_url:
            return None
        
        try:
            # Call the promotion service to get active promotions for this product
            response = requests.get(
                f"{self.promotion_service_url}/products/{product_id}/promotions"
            )
            
            if response.status_code == 200 and response.json().get('status') == 'success':
                promotions = response.json().get('promotions', [])
                
                # Filter for active promotions
                active_promotions = [p for p in promotions if p.get('is_active') == 1]
                
                # Sort by discount value to get the best promotion
                if active_promotions:
                    # For simplicity, we'll just take the first active promotion
                    # In a real system, you might want to select the best promotion for the customer
                    return active_promotions[0]
            
            return None
        except Exception as e:
            logger.warning(f"Error fetching promotion for product {product_id}: {e}")
            return None
    
    def get_cart_with_items(self, customer_id):
        """Get a customer's cart with all items and their details"""
        try:
            # Get or create cart
            cart_result = self.get_or_create_cart(customer_id)
            if cart_result['status'] != 'success':
                return cart_result
            
            cart = cart_result['cart']
            cart_id = cart['cart_id']
            
            # Get cart items
            response = requests.get(
                f"{self.db_service_url}/tables/cart_items/data",
                params={"condition": "cart_id = ?", "params": cart_id}
            )
            
            items = response.json().get('data', [])
            
            # Augment items with product details and promotions
            total_savings = 0
            for item in items:
                # Get product details
                product_response = requests.get(
                    f"{self.product_service_url}/products/{item['product_id']}"
                )
                
                if product_response.status_code == 200 and product_response.json().get('status') == 'success':
                    product = product_response.json().get('data')
                    item['product'] = product
                    original_price = float(product.get('price', 0))
                    
                    # Check for promotions
                    promotion = self.get_product_promotion(item['product_id'])
                    if promotion:
                        item['promotion'] = promotion
                        discounted_price = float(promotion.get('discounted_price', original_price))
                        
                        # Calculate item total with discount
                        item['original_price'] = original_price
                        item['discounted_price'] = discounted_price
                        item['discount_amount'] = original_price - discounted_price
                        item['total_original'] = item['quantity'] * original_price
                        item['total_discounted'] = item['quantity'] * discounted_price
                        item['total_savings'] = item['total_original'] - item['total_discounted']
                        
                        # Add to overall savings
                        total_savings += item['total_savings']
                    else:
                        # No promotion - use regular price
                        item['original_price'] = original_price
                        item['discounted_price'] = original_price
                        item['discount_amount'] = 0
                        item['total_original'] = item['quantity'] * original_price
                        item['total_discounted'] = item['total_original']
                        item['total_savings'] = 0
                else:
                    # Product not found
                    item['product'] = {"name": "Unknown Product", "price": 0}
                    item['original_price'] = 0
                    item['discounted_price'] = 0
                    item['discount_amount'] = 0
                    item['total_original'] = 0
                    item['total_discounted'] = 0
                    item['total_savings'] = 0
            
            # Calculate totals
            total_items = sum(item['quantity'] for item in items)
            total_original = sum(item['total_original'] for item in items)
            total_discounted = sum(item['total_discounted'] for item in items)
            
            return {
                "status": "success",
                "cart": {
                    "cart_id": cart_id,
                    "customer_id": customer_id,
                    "items": items,
                    "item_count": total_items,
                    "subtotal": total_original,
                    "discount": total_savings,
                    "total_price": total_discounted,
                    "created_at": cart.get('created_at'),
                    "updated_at": cart.get('updated_at')
                }
            }
        except Exception as e:
            logger.error(f"Error in get_cart_with_items: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def add_item_to_cart(self, customer_id, product_id, quantity=1):
        """Add an item to the customer's cart"""
        try:
            # Validate product exists
            product_response = requests.get(
                f"{self.product_service_url}/products/{product_id}"
            )
            
            if product_response.status_code != 200 or product_response.json().get('status') != 'success':
                return {"status": "error", "message": f"Product with ID {product_id} not found"}
            
            # Check product stock
            product = product_response.json().get('data')
            stock = int(product.get('stock_quantity', 0))
            
            if stock < quantity:
                return {"status": "error", "message": f"Not enough stock. Only {stock} available."}
            
            # Get or create cart
            cart_result = self.get_or_create_cart(customer_id)
            if cart_result['status'] != 'success':
                return cart_result
            
            cart = cart_result['cart']
            cart_id = cart['cart_id']
            
            # Check if product already in cart
            response = requests.get(
                f"{self.db_service_url}/tables/cart_items/data",
                params={"condition": "cart_id = ? AND product_id = ?", "params": f"{cart_id},{product_id}"}
            )
            
            existing_items = response.json().get('data', [])
            
            if existing_items:
                # Update quantity
                item = existing_items[0]
                new_quantity = int(item['quantity']) + quantity
                
                # Check if new quantity exceeds stock
                if new_quantity > stock:
                    return {"status": "error", "message": f"Cannot add {quantity} more. Only {stock} in stock and you have {item['quantity']} in cart."}
                
                update_data = {
                    "quantity": new_quantity
                }
                
                response = requests.put(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json={"values": update_data, "condition": "item_id = ?", "params": [item['item_id']]}
                )
                
                if response.status_code != 200 or response.json().get('status') != 'success':
                    return {"status": "error", "message": "Failed to update cart item"}
            else:
                # Add new item
                item_id = str(uuid.uuid4())
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                item_data = {
                    "item_id": item_id,
                    "cart_id": cart_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "added_at": now
                }
                
                response = requests.post(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json=item_data
                )
                
                if response.status_code != 200 or response.json().get('status') != 'success':
                    return {"status": "error", "message": "Failed to add item to cart"}
            
            # Update cart timestamp
            update_data = {
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            requests.put(
                f"{self.db_service_url}/tables/carts/data",
                json={"values": update_data, "condition": "cart_id = ?", "params": [cart_id]}
            )
            
            # Get updated cart
            return self.get_cart_with_items(customer_id)
        except Exception as e:
            logger.error(f"Error in add_item_to_cart: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def update_cart_item(self, customer_id, item_id, quantity):
        """Update the quantity of an item in the cart"""
        try:
            # Validate quantity
            if quantity < 0:
                return {"status": "error", "message": "Quantity cannot be negative"}
            
            # Get or create cart
            cart_result = self.get_or_create_cart(customer_id)
            if cart_result['status'] != 'success':
                return cart_result
            
            cart = cart_result['cart']
            cart_id = cart['cart_id']
            
            # Check if item exists and belongs to customer's cart
            response = requests.get(
                f"{self.db_service_url}/tables/cart_items/data",
                params={"condition": "item_id = ? AND cart_id = ?", "params": f"{item_id},{cart_id}"}
            )
            
            items = response.json().get('data', [])
            
            if not items:
                return {"status": "error", "message": f"Item with ID {item_id} not found in cart"}
            
            item = items[0]
            product_id = item['product_id']
            
            # Check product stock if increasing quantity
            if quantity > int(item['quantity']):
                product_response = requests.get(
                    f"{self.product_service_url}/products/{product_id}"
                )
                
                if product_response.status_code == 200 and product_response.json().get('status') == 'success':
                    product = product_response.json().get('data')
                    stock = int(product.get('stock_quantity', 0))
                    
                    if quantity > stock:
                        return {"status": "error", "message": f"Cannot update quantity to {quantity}. Only {stock} in stock."}
            
            if quantity == 0:
                # Remove item
                response = requests.delete(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json={"condition": "item_id = ?", "params": [item_id]}
                )
            else:
                # Update quantity
                update_data = {
                    "quantity": quantity
                }
                
                response = requests.put(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json={"values": update_data, "condition": "item_id = ?", "params": [item_id]}
                )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to update cart item"}
            
            # Update cart timestamp
            update_data = {
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            requests.put(
                f"{self.db_service_url}/tables/carts/data",
                json={"values": update_data, "condition": "cart_id = ?", "params": [cart_id]}
            )
            
            # Get updated cart
            return self.get_cart_with_items(customer_id)
        except Exception as e:
            logger.error(f"Error in update_cart_item: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def remove_cart_item(self, customer_id, item_id):
        """Remove an item from the cart"""
        try:
            # Get or create cart
            cart_result = self.get_or_create_cart(customer_id)
            if cart_result['status'] != 'success':
                return cart_result
            
            cart = cart_result['cart']
            cart_id = cart['cart_id']
            
            # Check if item exists and belongs to customer's cart
            response = requests.get(
                f"{self.db_service_url}/tables/cart_items/data",
                params={"condition": "item_id = ? AND cart_id = ?", "params": f"{item_id},{cart_id}"}
            )
            
            items = response.json().get('data', [])
            
            if not items:
                return {"status": "error", "message": f"Item with ID {item_id} not found in cart"}
            
            # Remove item
            response = requests.delete(
                f"{self.db_service_url}/tables/cart_items/data",
                json={"condition": "item_id = ?", "params": [item_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to remove cart item"}
            
            # Update cart timestamp
            update_data = {
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            requests.put(
                f"{self.db_service_url}/tables/carts/data",
                json={"values": update_data, "condition": "cart_id = ?", "params": [cart_id]}
            )
            
            # Get updated cart
            return self.get_cart_with_items(customer_id)
        except Exception as e:
            logger.error(f"Error in remove_cart_item: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def clear_cart(self, customer_id):
        """Remove all items from the cart"""
        try:
            # Get or create cart
            cart_result = self.get_or_create_cart(customer_id)
            if cart_result['status'] != 'success':
                return cart_result
            
            cart = cart_result['cart']
            cart_id = cart['cart_id']
            
            # Remove all items for this cart
            response = requests.delete(
                f"{self.db_service_url}/tables/cart_items/data",
                json={"condition": "cart_id = ?", "params": [cart_id]}
            )
            
            if response.status_code != 200 or response.json().get('status') != 'success':
                return {"status": "error", "message": "Failed to clear cart"}
            
            # Update cart timestamp
            update_data = {
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            requests.put(
                f"{self.db_service_url}/tables/carts/data",
                json={"values": update_data, "condition": "cart_id = ?", "params": [cart_id]}
            )
            
            # Get empty cart
            return self.get_cart_with_items(customer_id)
        except Exception as e:
            logger.error(f"Error in clear_cart: {str(e)}")
            return {"status": "error", "message": str(e)}

# Create cart manager instance
cart_manager = CartManager(DB_SERVICE_URL, PRODUCT_SERVICE_URL, PROMOTION_SERVICE_URL)

# API routes

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
        
        # Check Product service
        try:
            product_response = requests.get(f"{PRODUCT_SERVICE_URL}/health")
            services_status['product_service'] = "up" if product_response.status_code == 200 else "down"
        except:
            services_status['product_service'] = "down"
        
        return jsonify({
            "status": "up",
            "service": "Cart API",
            "services": services_status,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            "status": "error",
            "service": "Cart API",
            "message": str(e),
            "version": "1.0.0"
        }), 500

@app.route('/api/cart', methods=['GET'])
@token_required
def get_cart(customer_id):
    """Get the customer's cart"""
    try:
        result = cart_manager.get_cart_with_items(customer_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cart/items', methods=['POST'])
@token_required
def add_to_cart(customer_id):
    """Add an item to the cart"""
    try:
        data = request.get_json()
        
        if not data or 'product_id' not in data:
            return jsonify({"status": "error", "message": "Product ID is required"}), 400
        
        product_id = data['product_id']
        quantity = int(data.get('quantity', 1))
        
        if quantity <= 0:
            return jsonify({"status": "error", "message": "Quantity must be positive"}), 400
        
        result = cart_manager.add_item_to_cart(customer_id, product_id, quantity)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cart/items/<item_id>', methods=['PUT'])
@token_required
def update_cart_item(customer_id, item_id):
    """Update a cart item's quantity"""
    try:
        data = request.get_json()
        
        if not data or 'quantity' not in data:
            return jsonify({"status": "error", "message": "Quantity is required"}), 400
        
        quantity = int(data['quantity'])
        
        result = cart_manager.update_cart_item(customer_id, item_id, quantity)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating cart item: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cart/items/<item_id>', methods=['DELETE'])
@token_required
def remove_from_cart(customer_id, item_id):
    """Remove an item from the cart"""
    try:
        result = cart_manager.remove_cart_item(customer_id, item_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error removing from cart: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cart/clear', methods=['DELETE'])
@token_required
def clear_cart(customer_id):
    """Clear the entire cart"""
    try:
        result = cart_manager.clear_cart(customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error clearing cart: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5008))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')