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
            json={"db_name": "/data/cart.sqlite"}
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
                "product_name": "TEXT",
                "quantity": "INTEGER NOT NULL DEFAULT 1",
                "original_price": "REAL",
                "has_promotion": "INTEGER DEFAULT 0",
                "promotion_id": "TEXT",
                "promotion_name": "TEXT",
                "discount_type": "TEXT",
                "discount_value": "REAL",
                "discounted_price": "REAL",
                "added_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "FOREIGN KEY (cart_id)": "REFERENCES carts(cart_id)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "cart_items", "columns": cart_items_schema}
            )
            
            logger.info(f"Cart items table initialization: {response.json()}")
        else:
            # Check if needed columns exist
            schema_response = requests.get(f"{DB_SERVICE_URL}/tables/cart_items/schema")
            
            if schema_response.status_code == 200:
                schema_data = schema_response.json()
                existing_columns = [col['name'] for col in schema_data.get('schema', [])]
                
                # Define columns to add if missing
                required_columns = {
                    "product_name": "TEXT",
                    "original_price": "REAL",
                    "has_promotion": "INTEGER DEFAULT 0",
                    "promotion_id": "TEXT",
                    "promotion_name": "TEXT", 
                    "discount_type": "TEXT",
                    "discount_value": "REAL",
                    "discounted_price": "REAL"
                }
                
                # Add any missing columns
                for column_name, column_type in required_columns.items():
                    if column_name not in existing_columns:
                        logger.info(f"Adding missing column: {column_name}")
                        alter_query = f"ALTER TABLE cart_items ADD COLUMN {column_name} {column_type}"
                        
                        alter_response = requests.post(
                            f"{DB_SERVICE_URL}/execute",
                            json={"query": alter_query}
                        )
                        
                        if alter_response.status_code == 200:
                            logger.info(f"Added column {column_name} to cart_items table")
                        else:
                            logger.error(f"Failed to add column {column_name}: {alter_response.text}")
        
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
    def refresh_cart_promotions(self, customer_id):
        """Refresh all promotions in the customer's cart"""
        try:
            # Get cart
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
            
            if response.status_code != 200:
                return {"status": "error", "message": "Failed to retrieve cart items"}
            
            items = response.json().get('data', [])
            updated_count = 0
            
            # Update promotions for each item
            for item in items:
                product_id = item['product_id']
                item_id = item['item_id']
                
                # Get product details to ensure we have the current price
                product_response = requests.get(
                    f"{self.product_service_url}/products/{product_id}"
                )
                
                if product_response.status_code != 200 or product_response.json().get('status') != 'success':
                    logger.warning(f"Could not retrieve product {product_id} during promotion refresh")
                    continue
                    
                product = product_response.json().get('data')
                original_price = float(product.get('price', 0))
                
                # Get current promotion
                promotion = self.get_product_promotion(product_id)
                update_data = {
                    "original_price": original_price,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                if promotion:
                    # Add promotion details
                    discounted_price = float(promotion.get('discounted_price', original_price))
                    update_data.update({
                        "has_promotion": 1,
                        "promotion_id": promotion.get('promotion_id'),
                        "promotion_name": promotion.get('name'),
                        "discount_type": promotion.get('discount_type'),
                        "discount_value": float(promotion.get('discount_value', 0)),
                        "discounted_price": discounted_price
                    })
                else:
                    # Clear promotion data
                    update_data.update({
                        "has_promotion": 0,
                        "promotion_id": None,
                        "promotion_name": None,
                        "discount_type": None,
                        "discount_value": None,
                        "discounted_price": None
                    })
                
                # Update the item
                update_response = requests.put(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json={"values": update_data, "condition": "item_id = ?", "params": [item_id]}
                )
                
                if update_response.status_code == 200:
                    updated_count += 1
            
            # Update cart timestamp
            if updated_count > 0:
                update_data = {
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                requests.put(
                    f"{self.db_service_url}/tables/carts/data",
                    json={"values": update_data, "condition": "cart_id = ?", "params": [cart_id]}
                )
            
            # Return the updated cart
            return self.get_cart_with_items(customer_id)
        except Exception as e:
            logger.error(f"Error refreshing cart promotions: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_product_promotion(self, product_id):
        """Get active promotion for a specific product"""
        if not self.promotion_service_url:
            return None
        
        try:
            # Fix the URL by removing the duplicate /api/
            if self.promotion_service_url.endswith('/api'):
                promotion_url = f"{self.promotion_service_url}/products/{product_id}/promotions"
            else:
                promotion_url = f"{self.promotion_service_url}/api/products/{product_id}/promotions"
            
            logger.info(f"Checking promotions at URL: {promotion_url}")
            response = requests.get(promotion_url)
            
            if response.status_code == 200 and response.json().get('status') == 'success':
                promotions = response.json().get('promotions', [])
                
                # Current date for checking validity
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Filter for active promotions that are valid based on dates
                active_promotions = [
                    p for p in promotions 
                    if p.get('is_active') == 1 and
                    (not p.get('start_date') or p.get('start_date') <= current_date) and
                    (not p.get('end_date') or p.get('end_date') >= current_date)
                ]
                
                # Sort by discount value to get the best promotion
                if active_promotions:
                    # Sort by discounted_price to get the best deal
                    if all('discounted_price' in p for p in active_promotions):
                        return min(active_promotions, key=lambda p: p.get('discounted_price'))
                    return active_promotions[0]
                
                return None
            
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
            total_items = 0
            total_original = 0
            total_discounted = 0
            total_savings = 0
            
            for item in items:
                # Get product details
                product_response = requests.get(
                    f"{self.product_service_url}/products/{item['product_id']}"
                )
                
                if product_response.status_code == 200 and product_response.json().get('status') == 'success':
                    product = product_response.json().get('data')
                    item['product'] = product
                    
                    # Calculate quantities
                    quantity = int(item['quantity'])
                    total_items += quantity
                    
                    # Determine pricing
                    original_price = float(item.get('original_price') or product.get('price', 0))
                    item_total_original = original_price * quantity
                    total_original += item_total_original
                    
                    # Check for promotions
                    if item.get('has_promotion') == 1 and item.get('discounted_price') is not None:
                        # Item has a promotion
                        discounted_price = float(item.get('discounted_price'))
                        item_total_discounted = discounted_price * quantity
                        item_savings = item_total_original - item_total_discounted
                        
                        # Add to item
                        item['original_price'] = original_price
                        item['discounted_price'] = discounted_price
                        item['discount_amount'] = original_price - discounted_price
                        item['total_original'] = item_total_original
                        item['total_discounted'] = item_total_discounted
                        item['total_savings'] = item_savings
                        
                        # Add to totals
                        total_discounted += item_total_discounted
                        total_savings += item_savings
                    else:
                        # No promotion - use regular price
                        item['original_price'] = original_price
                        item['discounted_price'] = original_price
                        item['discount_amount'] = 0
                        item['total_original'] = item_total_original
                        item['total_discounted'] = item_total_original
                        item['total_savings'] = 0
                        
                        total_discounted += item_total_original
                else:
                    # Product not found
                    logger.warning(f"Product not found for item {item['item_id']}")
                    item['product'] = {"name": "Unknown Product", "price": 0}
                    item['original_price'] = float(item.get('original_price', 0))
                    discounted_price = float(item.get('discounted_price', item.get('original_price', 0)))
                    
                    quantity = int(item['quantity'])
                    total_items += quantity
                    
                    item_total_original = item['original_price'] * quantity
                    item_total_discounted = discounted_price * quantity
                    
                    item['discounted_price'] = discounted_price
                    item['discount_amount'] = max(0, item['original_price'] - discounted_price)
                    item['total_original'] = item_total_original
                    item['total_discounted'] = item_total_discounted
                    item['total_savings'] = max(0, item_total_original - item_total_discounted)
                    
                    total_original += item_total_original
                    total_discounted += item_total_discounted
                    total_savings += item['total_savings']
            
            # Calculate tax if applicable
            tax_rate = float(os.environ.get('TAX_RATE', 0.0))
            tax = round(total_discounted * tax_rate, 2)
            
            # Calculate final total (after all discounts and taxes)
            final_total = round(total_discounted + tax, 2)
            
            # Format currency values to avoid floating-point issues
            formatted_values = {
                "subtotal": round(total_original, 2),
                "discount": round(total_savings, 2),
                "discounted_subtotal": round(total_discounted, 2),
                "tax": tax,
                "total": final_total,
                "total_price": final_total  # Also include total_price for backward compatibility
            }
            
            # Log detailed calculation for debugging
            logger.info(f"Cart calculation: {formatted_values}")
            
            return {
                "status": "success",
                "cart": {
                    "cart_id": cart_id,
                    "customer_id": customer_id,
                    "items": items,
                    "item_count": total_items,
                    "subtotal": formatted_values["subtotal"],
                    "discount": formatted_values["discount"],
                    "discounted_subtotal": formatted_values["discounted_subtotal"],
                    "tax_rate": tax_rate,
                    "tax": formatted_values["tax"],
                    "total": formatted_values["total"],
                    "total_price": formatted_values["total_price"],  # Also include total_price for backward compatibility
                    "created_at": cart.get('created_at'),
                    "updated_at": cart.get('updated_at')
                }
            }
        except Exception as e:
            logger.error(f"Error in get_cart_with_items: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def add_item_to_cart(self, customer_id, product_id, quantity=1):
        """Add an item to the customer's cart, including any active promotions"""
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
            
            # Check for active promotions for this product
            # Fix the URL by removing the duplicate /api/
            if self.promotion_service_url:
                # Make sure the URL is correct - remove any duplicate /api/
                if self.promotion_service_url.endswith('/api'):
                    promotion_url = f"{self.promotion_service_url}/products/{product_id}/promotions"
                else:
                    promotion_url = f"{self.promotion_service_url}/api/products/{product_id}/promotions"
                
                logger.info(f"Checking promotions at URL: {promotion_url}")
                promotion_response = requests.get(promotion_url)
                
                active_promotion = None
                discounted_price = None
                
                if promotion_response.status_code == 200:
                    promotion_data = promotion_response.json()
                    # Check if there are any active promotions
                    if promotion_data.get('status') == 'success' and promotion_data.get('promotions'):
                        promotions = promotion_data.get('promotions', [])
                        
                        # Filter for active promotions that are currently valid by date
                        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        active_promotions = [
                            p for p in promotions if 
                            p.get('is_active') == 1 and
                            (not p.get('start_date') or p.get('start_date') <= current_date) and
                            (not p.get('end_date') or p.get('end_date') >= current_date)
                        ]
                        
                        # Use the first active promotion (or most beneficial one in future enhancement)
                        if active_promotions:
                            active_promotion = active_promotions[0]
                            discounted_price = active_promotion.get('discounted_price')
                            logger.info(f"Found active promotion for product {product_id}: {active_promotion['name']}")
            
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
                
                # Update promotion info if available
                if active_promotion:
                    update_data["has_promotion"] = 1
                    update_data["promotion_id"] = active_promotion.get('promotion_id')
                    update_data["promotion_name"] = active_promotion.get('name')
                    update_data["original_price"] = float(product.get('price', 0))
                    update_data["discounted_price"] = float(discounted_price)
                    update_data["discount_type"] = active_promotion.get('discount_type')
                    update_data["discount_value"] = float(active_promotion.get('discount_value', 0))
                else:
                    update_data["has_promotion"] = 0
                    update_data["promotion_id"] = None
                    update_data["promotion_name"] = None
                    update_data["original_price"] = float(product.get('price', 0))
                    update_data["discounted_price"] = None
                    update_data["discount_type"] = None
                    update_data["discount_value"] = None
                
                # Remove updated_at if it's not in the schema
                update_data.pop("updated_at", None)
                
                response = requests.put(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json={"values": update_data, "condition": "item_id = ?", "params": [item['item_id']]}
                )
                
                if response.status_code != 200 or response.json().get('status') != 'success':
                    logger.error(f"Failed to update cart item: {response.text}")
                    return {"status": "error", "message": "Failed to update cart item"}
            else:
                # Add new item
                item_id = str(uuid.uuid4())
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                item_data = {
                    "item_id": item_id,
                    "cart_id": cart_id,
                    "product_id": product_id,
                    "product_name": product.get('name', 'Unknown Product'),
                    "quantity": quantity,
                    "original_price": float(product.get('price', 0)),
                    "has_promotion": 1 if active_promotion else 0,
                    "added_at": now
                }
                
                # Add promotion details if available
                if active_promotion:
                    item_data["promotion_id"] = active_promotion.get('promotion_id')
                    item_data["promotion_name"] = active_promotion.get('name')
                    item_data["discount_type"] = active_promotion.get('discount_type')
                    item_data["discount_value"] = float(active_promotion.get('discount_value', 0))
                    item_data["discounted_price"] = float(discounted_price)
                
                # Remove updated_at if it's not in the schema
                item_data.pop("updated_at", None)
                
                response = requests.post(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json=item_data
                )
                
                if response.status_code != 200 or response.json().get('status') != 'success':
                    logger.error(f"Failed to add item to cart: {response.text}")
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
        """Update the quantity of an item in the cart and refresh promotion"""
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
            
            # Check product stock
            product_response = requests.get(
                f"{self.product_service_url}/products/{product_id}"
            )
            
            if product_response.status_code == 200 and product_response.json().get('status') == 'success':
                product = product_response.json().get('data')
                stock = int(product.get('stock_quantity', 0))
                
                if quantity > stock:
                    return {"status": "error", "message": f"Cannot update quantity to {quantity}. Only {stock} in stock."}
                
                original_price = float(product.get('price', 0))
            else:
                # If we can't get the product, use the current price in the cart
                original_price = float(item.get('original_price', 0))
                stock = quantity  # Just assume we have enough stock
            
            if quantity == 0:
                # Remove item
                response = requests.delete(
                    f"{self.db_service_url}/tables/cart_items/data",
                    json={"condition": "item_id = ?", "params": [item_id]}
                )
                
                if response.status_code != 200 or response.json().get('status') != 'success':
                    return {"status": "error", "message": "Failed to remove cart item"}
            else:
                # Update quantity and refresh promotion
                promotion = self.get_product_promotion(product_id)
                
                update_data = {
                    "quantity": quantity,
                    "original_price": original_price,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Add promotion information if available
                if promotion:
                    discounted_price = float(promotion.get('discounted_price', original_price))
                    update_data.update({
                        "has_promotion": 1,
                        "promotion_id": promotion.get('promotion_id'),
                        "promotion_name": promotion.get('name'),
                        "discount_type": promotion.get('discount_type'),
                        "discount_value": float(promotion.get('discount_value', 0)),
                        "discounted_price": discounted_price
                    })
                else:
                    # Clear promotion data
                    update_data.update({
                        "has_promotion": 0,
                        "promotion_id": None,
                        "promotion_name": None,
                        "discount_type": None, 
                        "discount_value": None,
                        "discounted_price": original_price
                    })
                
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

@app.route('/api/cart/refresh-promotions', methods=['POST'])
@token_required
def refresh_cart_promotions(customer_id):
    """Refresh all promotions in the cart"""
    try:
        result = cart_manager.refresh_cart_promotions(customer_id)
        
        if result['status'] != 'success':
            return jsonify(result), 400
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error refreshing cart promotions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5008))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')