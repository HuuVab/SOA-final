from flask import Flask, request, jsonify
import os
import logging
import uuid
import requests
from datetime import datetime
from flask_cors import CORS
from flask import send_from_directory
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

class PromotionService:
    def __init__(self, db_service_url=None, db_name=None, storage_db_name=None):
        """Initialize the promotion service with the database service URL and db names"""
        if db_service_url is None:
            self.db_service_url = "http://localhost:5003/api"
        else:
            self.db_service_url = db_service_url
            
        if db_name is None:
            self.db_name = "/data/promotion.sqlite"
        else:
            self.db_name = db_name
            
        if storage_db_name is None:
            self.storage_db_name = "/data/storage.sqlite"
        else:
            self.storage_db_name = storage_db_name
        
        self.initialized = False
        self.connect_to_db()
        if self.initialized:
            self.init_promotion_table()

    def connect_to_db(self):
        """Connect to the promotion database via the database service"""
        try:
            # Connect to the specified database
            connect_url = f"{self.db_service_url}/connect"
            response = requests.post(connect_url, json={"db_name": self.db_name})
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    logger.info(f"Connected to database {self.db_name} via database service")
                    self.initialized = True
                    return True
                else:
                    logger.error(f"Failed to connect to database: {result.get('message')}")
                    return False
            else:
                logger.error(f"Error connecting to database service: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to database service: {e}")
            return False

    def init_promotion_table(self):
        """Initialize the promotions table if it doesn't exist"""
        try:
            # Check if promotions table exists
            tables_url = f"{self.db_service_url}/tables"
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(tables_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                tables = data.get('tables', [])
                
                if 'promotions' not in tables:
                    # Create promotions table
                    create_table_url = f"{self.db_service_url}/tables"
                    columns = {
                        "promotion_id": "TEXT PRIMARY KEY",
                        "product_id": "TEXT NOT NULL",
                        "name": "TEXT NOT NULL",
                        "description": "TEXT",
                        "discount_type": "TEXT NOT NULL",  # 'percentage' or 'fixed_amount'
                        "discount_value": "REAL NOT NULL",
                        "start_date": "TEXT",
                        "end_date": "TEXT",
                        "is_active": "INTEGER DEFAULT 1",  # 1 = true, 0 = false
                        "created_at": "TEXT",
                        "updated_at": "TEXT"
                    }
                    
                    response = requests.post(
                        create_table_url, 
                        json={"table_name": "promotions", "columns": columns},
                        headers=headers
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Error creating promotions table: {response.text}")
                        return False
                    
                    logger.info("Promotions table created successfully")
                else:
                    logger.info("Promotions table already exists")
                
                return True
            else:
                logger.error(f"Error listing tables: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing promotions table: {e}")
            return False
    def get_all_products(self):
        """Get all available products from the storage service"""
        try:
            # Use environment variable or default to service name in docker network
            storage_service_url = os.environ.get('STORAGE_SERVICE_URL', 'http://localhost:5005')
            
            # Make API call to storage service
            api_url = f"{storage_service_url}/api/products"
            logger.info(f"Calling storage service API to get all products: {api_url}")
            
            api_response = requests.get(api_url, timeout=10)  # Longer timeout for potentially large data
            
            if api_response.status_code == 200:
                result = api_response.json()
                if result.get('status') == 'success' and result.get('data'):
                    return {
                        "status": "success", 
                        "message": f"Retrieved {len(result.get('data'))} products",
                        "data": result.get('data')
                    }
            
            # If API call failed, log detailed information
            logger.error(f"Failed to retrieve products from storage service: Status {api_response.status_code}, Response: {api_response.text}")
            
            return {
                "status": "error",
                "message": f"Could not retrieve products (Status: {api_response.status_code})"
            }
        except Exception as e:
            logger.error(f"Error retrieving products: {e}")
            return {"status": "error", "message": str(e)}
    def get_all_promotions(self):
        """Get all promotions"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
                
            url = f"{self.db_service_url}/tables/promotions/data"
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "message": f"Retrieved {len(result.get('data', []))} promotions",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving promotions: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving promotions: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_promotion(self, promotion_id):
        """Get a specific promotion by ID"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
                
            url = f"{self.db_service_url}/tables/promotions/data"
            params = {"condition": "promotion_id = ?", "params": promotion_id}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                promotions = result.get('data', [])
                
                if promotions:
                    # Get product details for this promotion
                    product_id = promotions[0]['product_id']
                    product = self.get_product(product_id)
                    
                    # Add product details to promotion
                    if product.get('status') == 'success' and product.get('data'):
                        promotions[0]['product'] = product.get('data')
                        
                        # Calculate discounted price
                        if 'price' in product.get('data', {}):
                            promotions[0]['discounted_price'] = self.calculate_discounted_price(
                                product.get('data')['price'],
                                promotions[0]['discount_type'],
                                promotions[0]['discount_value']
                            )
                    
                    return {
                        "status": "success",
                        "message": f"Retrieved promotion {promotion_id}",
                        "data": promotions[0]
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Promotion with ID {promotion_id} not found"
                    }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving promotion: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving promotion {promotion_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_product(self, product_id):
        """Get a product by calling the Storage Service API"""
        try:
            # Use environment variable or default to service name in docker network
            storage_service_url = os.environ.get('STORAGE_SERVICE_URL', 'http://localhost:5005')
            
            # Make API call to storage service
            api_url = f"{storage_service_url}/api/products/{product_id}"
            logger.info(f"Calling storage service API: {api_url}")
            
            api_response = requests.get(api_url, timeout=5)
            
            if api_response.status_code == 200:
                result = api_response.json()
                if result.get('status') == 'success' and result.get('data'):
                    return {
                        "status": "success", 
                        "message": f"Retrieved product {product_id}",
                        "data": result.get('data')
                    }
            
            # If API call failed, log detailed information
            logger.error(f"Failed to retrieve product from storage service: Status {api_response.status_code}, Response: {api_response.text}")
            
            return {
                "status": "error",
                "message": f"Product with ID {product_id} not found (Status: {api_response.status_code})"
            }
        except Exception as e:
            logger.error(f"Error retrieving product {product_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def create_promotion(self, promotion_data):
        """Create a new promotion"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
            
            # Check if required fields are present
            required_fields = ['product_id', 'name', 'discount_type', 'discount_value']
            missing_fields = [field for field in required_fields if field not in promotion_data]
            
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            # Validate discount type
            if promotion_data['discount_type'] not in ['percentage', 'fixed_amount']:
                return {
                    "status": "error",
                    "message": "Discount type must be 'percentage' or 'fixed_amount'"
                }
            
            # Validate product exists in storage database
            product_result = self.get_product(promotion_data['product_id'])
            if product_result['status'] == 'error':
                return {
                    "status": "error",
                    "message": f"Product not found: {product_result['message']}"
                }
            
            # Generate promotion ID if not provided
            if 'promotion_id' not in promotion_data:
                promotion_data['promotion_id'] = str(uuid.uuid4())
            
            # Set timestamps
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            promotion_data['created_at'] = now
            promotion_data['updated_at'] = now
            
            # Set default active status if not provided
            if 'is_active' not in promotion_data:
                promotion_data['is_active'] = 1
                
            # Insert promotion into database
            url = f"{self.db_service_url}/tables/promotions/data"
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(url, headers=headers, json=promotion_data)
            
            if response.status_code == 200:
                # Calculate discounted price
                product = product_result.get('data')
                discounted_price = self.calculate_discounted_price(
                    product['price'],
                    promotion_data['discount_type'],
                    promotion_data['discount_value']
                )
                
                # Return complete promotion with product info and discounted price
                return {
                    "status": "success",
                    "message": f"Promotion created successfully with ID {promotion_data['promotion_id']}",
                    "data": {
                        **promotion_data,
                        "product": product,
                        "discounted_price": discounted_price
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error creating promotion: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error creating promotion: {e}")
            return {"status": "error", "message": str(e)}
    
    def update_promotion(self, promotion_id, updates):
        """Update a promotion"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
            
            # Check if promotion exists
            promotion = self.get_promotion(promotion_id)
            if promotion['status'] == 'error':
                return promotion
            
            # If product_id is being updated, verify it exists
            if 'product_id' in updates:
                product_result = self.get_product(updates['product_id'])
                if product_result['status'] == 'error':
                    return {
                        "status": "error",
                        "message": f"Product not found: {product_result['message']}"
                    }
            
            # Validate discount type if being updated
            if 'discount_type' in updates and updates['discount_type'] not in ['percentage', 'fixed_amount']:
                return {
                    "status": "error",
                    "message": "Discount type must be 'percentage' or 'fixed_amount'"
                }
            
            # Add updated timestamp
            updates['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update in database
            url = f"{self.db_service_url}/tables/promotions/data"
            payload = {
                "values": updates,
                "condition": "promotion_id = ?",
                "params": [promotion_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.put(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                # Get the updated promotion with product info
                updated_promotion = self.get_promotion(promotion_id)
                return {
                    "status": "success",
                    "message": f"Promotion {promotion_id} updated successfully",
                    "data": updated_promotion.get('data')
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error updating promotion: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error updating promotion {promotion_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete_promotion(self, promotion_id):
        """Delete a promotion"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
            
            # Check if promotion exists
            promotion = self.get_promotion(promotion_id)
            if promotion['status'] == 'error':
                return promotion
            
            # Delete from database
            url = f"{self.db_service_url}/tables/promotions/data"
            payload = {
                "condition": "promotion_id = ?",
                "params": [promotion_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.delete(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Promotion {promotion_id} deleted successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error deleting promotion: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error deleting promotion {promotion_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_product_promotions(self, product_id):
        """Get all promotions for a specific product"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
            
            # Verify product exists
            product_result = self.get_product(product_id)
            if product_result['status'] == 'error':
                return {
                    "status": "error",
                    "message": f"Product not found: {product_result['message']}"
                }
            
            # Get promotions for this product
            url = f"{self.db_service_url}/tables/promotions/data"
            params = {"condition": "product_id = ?", "params": product_id}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                promotions = result.get('data', [])
                
                # Calculate discounted price for each promotion
                product = product_result.get('data')
                for promotion in promotions:
                    promotion['discounted_price'] = self.calculate_discounted_price(
                        product['price'],
                        promotion['discount_type'],
                        promotion['discount_value']
                    )
                
                return {
                    "status": "success",
                    "message": f"Found {len(promotions)} promotions for product {product_id}",
                    "product": product,
                    "promotions": promotions
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving promotions: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving promotions for product {product_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_active_promotions(self):
        """Get all currently active promotions"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_promotion_table()
            
            # Get current date in required format
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Build query to check active status and date range
            query = """
            SELECT * FROM promotions
            WHERE is_active = 1
            AND (start_date IS NULL OR start_date <= ?)
            AND (end_date IS NULL OR end_date >= ?)
            """
            
            url = f"{self.db_service_url}/execute"
            payload = {
                "query": query,
                "params": [current_date, current_date]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                promotions = result.get('data', [])
                
                # Enhance each promotion with product information and discounted price
                enhanced_promotions = []
                for promotion in promotions:
                    product_result = self.get_product(promotion['product_id'])
                    
                    if product_result['status'] == 'success' and product_result.get('data'):
                        product = product_result.get('data')
                        discounted_price = self.calculate_discounted_price(
                            product['price'],
                            promotion['discount_type'],
                            promotion['discount_value']
                        )
                        
                        enhanced_promotions.append({
                            **promotion,
                            "product": product,
                            "discounted_price": discounted_price
                        })
                    else:
                        # Include promotion even without product details
                        enhanced_promotions.append(promotion)
                
                return {
                    "status": "success",
                    "message": f"Found {len(enhanced_promotions)} active promotions",
                    "data": enhanced_promotions
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving active promotions: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving active promotions: {e}")
            return {"status": "error", "message": str(e)}
    
    def calculate_discounted_price(self, price, discount_type, discount_value):
        """Calculate discounted price based on discount type and value"""
        try:
            price = float(price)
            discount_value = float(discount_value)
            
            if discount_type == 'percentage':
                # Ensure percentage is between 0 and 100
                discount_percentage = min(max(discount_value, 0), 100)
                discounted_price = price * (1 - (discount_percentage / 100))
            elif discount_type == 'fixed_amount':
                # Ensure discount doesn't make price negative
                discounted_price = max(price - discount_value, 0)
            else:
                # Default case - no discount
                return price
            
            # Round to 2 decimal places
            return round(discounted_price, 2)
        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating discounted price: {e}")
            return price

# Create a global promotion service instance
db_service_url = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
db_name = os.environ.get('DB_NAME', '/data/promotion.sqlite')
storage_db_name = os.environ.get('STORAGE_DB_NAME', '/data/storage.sqlite')
promotion_service = PromotionService(db_service_url, db_name, storage_db_name)

@app.route('/api/promotions', methods=['GET'])
def get_promotions():
    """Get all promotions"""
    try:
        result = promotion_service.get_all_promotions()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_promotions route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>', methods=['GET'])
def get_promotion(promotion_id):
    """Get a specific promotion by ID"""
    try:
        result = promotion_service.get_promotion(promotion_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_promotion route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions', methods=['POST'])
def create_promotion():
    """Create a new promotion"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Promotion data is required"}), 400
        
        result = promotion_service.create_promotion(data)
        if result['status'] == 'error':
            return jsonify(result), 400
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error in create_promotion route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>', methods=['PUT'])
def update_promotion(promotion_id):
    """Update a promotion"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        result = promotion_service.update_promotion(promotion_id, data)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_promotion route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/<promotion_id>', methods=['DELETE'])
def delete_promotion(promotion_id):
    """Delete a promotion"""
    try:
        result = promotion_service.delete_promotion(promotion_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_promotion route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>/promotions', methods=['GET'])
def get_product_promotions(product_id):
    """Get all promotions for a specific product"""
    try:
        result = promotion_service.get_product_promotions(product_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product_promotions route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/promotions/active', methods=['GET'])
def get_active_promotions():
    """Get all currently active promotions"""
    try:
        result = promotion_service.get_active_promotions()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_active_promotions route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check connection to database service
        db_health_url = f"{promotion_service.db_service_url}/health"
        try:
            db_response = requests.get(db_health_url)
            db_status = "connected" if db_response.status_code == 200 else "disconnected"
            db_details = db_response.json() if db_response.status_code == 200 else {}
        except:
            db_status = "disconnected"
            db_details = {}
        
        return jsonify({
            "status": "up",
            "service": "Promotion API",
            "db_service": db_status,
            "db_service_url": promotion_service.db_service_url,
            "promotion_db": promotion_service.db_name,
            "storage_db": promotion_service.storage_db_name,
            "db_details": db_details,
            "initialized": promotion_service.initialized,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health_check route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/api/products', methods=['GET'])
def get_all_products():
    """Get all available products"""
    try:
        result = promotion_service.get_all_products()
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_all_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')
# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5006))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')