from flask import Flask, request, jsonify
import os
import logging
import uuid
import requests
from datetime import datetime
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

UPLOAD_FOLDER = '/data/storage'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', MAX_CONTENT_LENGTH))

class ProductStorage:
    def __init__(self, db_service_url=None, db_name=None):
        """Initialize the product storage with the database service URL and db name"""
        if db_service_url is None:
            self.db_service_url = "http://localhost:5003/api"
        else:
            self.db_service_url = db_service_url
            
        if db_name is None:
            self.db_name = "/data/storage.sqlite"
        else:
            self.db_name = db_name
        
        self.initialized = False
        self.connect_to_db()
        if self.initialized:
            self.init_storage()

    def connect_to_db(self):
        """Connect to the database via the database service"""
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

    def init_storage(self):
        """Initialize the products table if it doesn't exist"""
        try:
            # Check if products table exists
            tables_url = f"{self.db_service_url}/tables"
            response = requests.get(tables_url)
            
            if response.status_code == 200:
                data = response.json()
                tables = data.get('tables', [])
                
                if 'products' not in tables:
                    # Create products table
                    create_table_url = f"{self.db_service_url}/tables"
                    columns = {
                        "product_id": "TEXT PRIMARY KEY",
                        "name": "TEXT NOT NULL",
                        "price": "REAL NOT NULL",
                        "description": "TEXT",
                        "category": "TEXT",
                        "manufacturer": "TEXT",
                        "stock_quantity": "INTEGER DEFAULT 0",
                        "image_url": "TEXT",
                        "created_at": "TEXT",
                        "updated_at": "TEXT"
                    }
                    
                    response = requests.post(
                        create_table_url, 
                        json={"table_name": "products", "columns": columns}
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Error creating products table: {response.text}")
                        return False
                    
                    logger.info("Products table created successfully")
                else:
                    # Check if we need to add the new columns to an existing table
                    schema_url = f"{self.db_service_url}/tables/products/schema"
                    schema_response = requests.get(schema_url)
                    
                    if schema_response.status_code == 200:
                        schema_data = schema_response.json()
                        schema_columns = [col['name'] for col in schema_data.get('schema', [])]
                        
                        # Check if the category column exists, if not add it
                        if 'category' not in schema_columns:
                            alter_query = "ALTER TABLE products ADD COLUMN category TEXT"
                            self._execute_query(alter_query)
                            logger.info("Added category column to products table")
                            
                        # Check if the manufacturer column exists, if not add it
                        if 'manufacturer' not in schema_columns:
                            alter_query = "ALTER TABLE products ADD COLUMN manufacturer TEXT"
                            self._execute_query(alter_query)
                            logger.info("Added manufacturer column to products table")
                    
                    logger.info("Products table already exists")
                
                # Create product_images table if it doesn't exist
                if 'product_images' not in tables:
                    # Create product_images table
                    create_table_url = f"{self.db_service_url}/tables"
                    columns = {
                        "image_id": "TEXT PRIMARY KEY",
                        "product_id": "TEXT NOT NULL",
                        "filename": "TEXT NOT NULL",
                        "path": "TEXT NOT NULL",
                        "alt_text": "TEXT",
                        "is_primary": "INTEGER DEFAULT 0",
                        "width": "INTEGER",
                        "height": "INTEGER",
                        "size_kb": "INTEGER",
                        "mime_type": "TEXT",
                        "sort_order": "INTEGER DEFAULT 0",
                        "created_at": "TEXT",
                        "FOREIGN KEY (product_id)": "REFERENCES products(product_id) ON DELETE CASCADE"
                    }
                    
                    response = requests.post(
                        create_table_url, 
                        json={"table_name": "product_images", "columns": columns}
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Error creating product_images table: {response.text}")
                        return False
                    
                    logger.info("Product_images table created successfully")
                
                return True
            else:
                logger.error(f"Error listing tables: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing storage: {e}")
            return False
    
    def _execute_query(self, query, params=None):
        """Execute a SQL query via the database service"""
        try:
            url = f"{self.db_service_url}/execute"
            payload = {"query": query}
            if params:
                payload["params"] = params
            
            response = requests.post(url, json=payload)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return None
    def allowed_file(self, filename):
        """Check if a filename has an allowed extension"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    def generate_product_image_path(self, product_id, filename):
        """Generate a unique filepath for an uploaded product image"""
        # Secure the filename to prevent directory traversal attacks
        filename = secure_filename(filename)
        
        # Get file extension
        _, ext = os.path.splitext(filename)
        
        # Generate a unique filename using uuid
        unique_filename = f"{str(uuid.uuid4())}{ext}"
        
        # Create year/month directory structure
        today = datetime.now()
        year_month = f"{today.year}/{today.month:02d}"
        
        # Construct directory path under product_id
        rel_directory = f"products/{product_id}/{year_month}"
        abs_directory = os.path.join(app.config['UPLOAD_FOLDER'], rel_directory)
        
        # Create directories if they don't exist
        os.makedirs(abs_directory, exist_ok=True)
        
        # Construct full path
        rel_path = f"{rel_directory}/{unique_filename}"
        abs_path = os.path.join(app.config['UPLOAD_FOLDER'], rel_path)
        
        return {
            'filename': unique_filename,
            'original_filename': filename,
            'relative_path': rel_path,
            'absolute_path': abs_path
        }
    def handle_product_image_upload(self, file, product_id, is_primary=False, alt_text=None, sort_order=0):
        """Handle a product image file upload"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            if not file or file.filename == '':
                return {
                    "status": "error",
                    "message": "No file selected"
                }
            
            if not self.allowed_file(file.filename):
                return {
                    "status": "error",
                    "message": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
                }
            
            # Check if product exists
            product = self.get_product(product_id)
            if product['status'] == 'error':
                return {
                    "status": "error",
                    "message": f"Product with ID {product_id} not found"
                }
            
            # Generate file path
            path_info = self.generate_product_image_path(product_id, file.filename)
            
            # Save the file
            file.save(path_info['absolute_path'])
            
            # Get file size
            file_size = os.path.getsize(path_info['absolute_path'])
            
            # Try to determine dimensions for images (this would require PIL/Pillow)
            width = None
            height = None
            
            # Determine mime type
            mime_type = mimetypes.guess_type(path_info['absolute_path'])[0]
            
            # Create image metadata
            image_data = {
                'image_id': str(uuid.uuid4()),
                'product_id': product_id,
                'filename': path_info['original_filename'],
                'path': path_info['relative_path'],
                'alt_text': alt_text or path_info['original_filename'],
                'is_primary': 1 if is_primary else 0,
                'width': width,
                'height': height,
                'size_kb': file_size // 1024,
                'mime_type': mime_type,
                'sort_order': sort_order,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add image metadata to database
            result = self.add_product_image(image_data)
            
            if result['status'] == 'success':
                # If this is a primary image, update the product's main image_url
                if is_primary:
                    self.update_product(product_id, {'image': path_info['relative_path']})
                return result
            else:
                # If database insert failed, clean up the file
                if os.path.exists(path_info['absolute_path']):
                    os.remove(path_info['absolute_path'])
                return result
            
        except Exception as e:
            logger.error(f"Error handling product image upload: {e}")
            return {"status": "error", "message": str(e)}    

    def get_product_image(self, image_id):
        """Get a specific product image by ID"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            url = f"{self.db_service_url}/tables/product_images/data"
            params = {"condition": "image_id = ?", "params": image_id}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                images = result.get('data', [])
                
                if images:
                    return {
                        "status": "success",
                        "message": f"Retrieved image {image_id}",
                        "data": images[0]
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Image with ID {image_id} not found"
                    }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving image: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving product image {image_id}: {e}")
            return {"status": "error", "message": str(e)}

    def get_product_images(self, product_id):
        """Get all images for a specific product"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            url = f"{self.db_service_url}/tables/product_images/data"
            params = {"condition": "product_id = ?", "params": product_id, "order_by": "sort_order, created_at"}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "message": f"Retrieved {len(result.get('data', []))} images for product {product_id}",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving images: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving images for product {product_id}: {e}")
            return {"status": "error", "message": str(e)}       

    def update_product_image(self, image_id, updates):
        """Update a product image"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            # Check if image exists
            check_result = self.get_product_image(image_id)
            if check_result['status'] == 'error':
                return check_result
            
            image_data = check_result['data']
            
            # Update image in database
            url = f"{self.db_service_url}/tables/product_images/data"
            payload = {
                "values": updates,
                "condition": "image_id = ?",
                "params": [image_id]
            }
            
            response = requests.put(url, json=payload)
            
            if response.status_code == 200:
                # If this is being set as primary, make sure all other images for this product are not primary
                if updates.get('is_primary') == 1:
                    product_id = image_data['product_id']
                    self._clear_other_primary_images(product_id, image_id)
                    
                    # Also update the product's main image_url
                    self.update_product(product_id, {'image': image_data['path']})
                    
                return self.get_product_image(image_id)
            else:
                return {
                    "status": "error",
                    "message": f"Error updating image: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error updating product image {image_id}: {e}")
            return {"status": "error", "message": str(e)}
    def _clear_other_primary_images(self, product_id, exclude_image_id):
        """Clear the is_primary flag from all other images of a product"""
        try:
            url = f"{self.db_service_url}/tables/product_images/data"
            payload = {
                "values": {"is_primary": 0},
                "condition": "product_id = ? AND image_id != ?",
                "params": [product_id, exclude_image_id]
            }
            
            requests.put(url, json=payload)
            return True
        except Exception as e:
            logger.error(f"Error clearing primary flag from other images: {e}")
            return False

    def delete_product_image(self, image_id):
        """Delete a product image and its file"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            # Check if image exists
            check_result = self.get_product_image(image_id)
            if check_result['status'] == 'error':
                return check_result
            
            image_data = check_result['data']
            product_id = image_data['product_id']
            is_primary = image_data.get('is_primary', 0) == 1
            
            # Delete the image file
            if image_data.get('path'):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], image_data['path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                    # Try to clean up empty directories
                    dir_path = os.path.dirname(file_path)
                    try:
                        # Remove directory if empty
                        if len(os.listdir(dir_path)) == 0:
                            os.rmdir(dir_path)
                            
                            # Try to remove parent directory if empty
                            parent_dir = os.path.dirname(dir_path)
                            if len(os.listdir(parent_dir)) == 0:
                                os.rmdir(parent_dir)
                    except Exception as e:
                        logger.warning(f"Error cleaning up directories: {e}")
            
            # Delete the image record
            url = f"{self.db_service_url}/tables/product_images/data"
            payload = {
                "condition": "image_id = ?",
                "params": [image_id]
            }
            
            response = requests.delete(url, json=payload)
            
            if response.status_code == 200:
                # If this was a primary image, find a new primary image
                if is_primary:
                    self._set_new_primary_image(product_id)
                
                return {
                    "status": "success",
                    "message": f"Image {image_id} deleted successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error deleting image: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error deleting product image {image_id}: {e}")
            return {"status": "error", "message": str(e)}

    def _set_new_primary_image(self, product_id):
        """Set a new primary image for a product after the current one is deleted"""
        try:
            # Get all images for this product
            images_result = self.get_product_images(product_id)
            
            if images_result['status'] == 'success' and images_result['data']:
                # Set the first image as primary
                first_image = images_result['data'][0]
                self.update_product_image(first_image['image_id'], {'is_primary': 1})
                
                # Update the product's main image_url
                self.update_product(product_id, {'image': first_image['path']})
                return True
            else:
                # No images left, clear the product's image_url
                self.update_product(product_id, {'image': ''})
                return False
        except Exception as e:
            logger.error(f"Error setting new primary image for product {product_id}: {e}")
            return False
    def get_all_products(self):
        """Get all products"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
                
            url = f"{self.db_service_url}/tables/products/data"
            response = requests.get(url)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "message": f"Retrieved {len(result.get('data', []))} products",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving products: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving products: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_product(self, product_id):
        """Get a specific product by ID with all its images"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
                
            url = f"{self.db_service_url}/tables/products/data"
            params = {"condition": "product_id = ?", "params": product_id}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                products = result.get('data', [])
                
                if products:
                    product = products[0]
                    
                    # Get all images for this product
                    images_result = self.get_product_images(product_id)
                    if images_result['status'] == 'success':
                        product['images'] = images_result['data']
                    else:
                        product['images'] = []
                    
                    return {
                        "status": "success",
                        "message": f"Retrieved product {product_id}",
                        "data": product
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Product with ID {product_id} not found"
                    }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving product: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving product {product_id}: {e}")
            return {"status": "error", "message": str(e)}
        
    def create_product(self, product_data):
        """Create a new product with optional images"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            # Extract images if provided
            images = product_data.pop('images', [])
            
            # Generate a unique product ID if not provided
            if 'id' in product_data:
                product_id = product_data.pop('id')
            else:
                product_id = str(uuid.uuid4())
                
            # Check if all required fields are present
            required_fields = ['name', 'price', 'description', 'stock']
            missing_fields = [field for field in required_fields if field not in product_data]
            
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            # Prepare data for database
            db_data = {
                "product_id": product_id,
                "name": product_data['name'],
                "price": float(product_data['price']),
                "description": product_data['description'],
                "stock_quantity": int(product_data.get('stock', 0)),
                "image_url": product_data.get('image', ""),
                "category": product_data.get('category', ""),
                "manufacturer": product_data.get('manufacturer', ""),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Insert into database
            url = f"{self.db_service_url}/tables/products/data"
            response = requests.post(url, json=db_data)
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Error creating product: {response.text}"
                }
                
            # Now handle any images that were provided as metadata (not file uploads)
            if images:
                for index, image_data in enumerate(images):
                    image_data['product_id'] = product_id
                    image_data['sort_order'] = index
                    
                    # Set the first image as primary if not specified
                    if index == 0 and 'is_primary' not in image_data:
                        image_data['is_primary'] = 1
                    
                    self.add_product_image(image_data)
            
            # Get the complete product with its images
            return self.get_product(product_id)
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            return {"status": "error", "message": str(e)}
    
    def update_product(self, product_id, updates):
        """Update a product"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            # Check if product exists
            product = self.get_product(product_id)
            if product['status'] == 'error':
                return product
            
            # Prepare data for database
            db_data = {}
            
            # Map fields to database columns
            field_mapping = {
                'name': 'name',
                'price': 'price',
                'description': 'description',
                'stock': 'stock_quantity',
                'image': 'image_url',
                'category': 'category',
                'manufacturer': 'manufacturer'
            }
            
            for key, value in updates.items():
                if key in field_mapping:
                    db_key = field_mapping[key]
                    db_data[db_key] = value
            
            # Add updated timestamp
            db_data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update in database
            url = f"{self.db_service_url}/tables/products/data"
            payload = {
                "values": db_data,
                "condition": "product_id = ?",
                "params": [product_id]
            }
            
            response = requests.put(url, json=payload)
            
            if response.status_code == 200:
                # Get the updated product
                updated_product = self.get_product(product_id)
                return {
                    "status": "success",
                    "message": f"Product {product_id} updated successfully",
                    "data": updated_product.get('data')
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error updating product: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete_product(self, product_id):
        """Delete a product and all its images"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            # Check if product exists
            product = self.get_product(product_id)
            if product['status'] == 'error':
                return product
            
            # Get all images for this product and delete them
            images_result = self.get_product_images(product_id)
            if images_result['status'] == 'success':
                for image in images_result['data']:
                    # Delete the image file
                    if image.get('path'):
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], image['path'])
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                logger.warning(f"Error removing file {file_path}: {e}")
            
            # Try to delete the product directory
            try:
                product_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"products/{product_id}")
                if os.path.exists(product_dir):
                    shutil.rmtree(product_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Error removing product directory: {e}")
            
            # Delete from database
            url = f"{self.db_service_url}/tables/products/data"
            payload = {
                "condition": "product_id = ?",
                "params": [product_id]
            }
            
            response = requests.delete(url, json=payload)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Product {product_id} deleted successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error deleting product: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def search_products(self, query):
        """Search for products by name or description"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            # Use database service to search
            search_query = """
            SELECT * FROM products
            WHERE name LIKE ? OR description LIKE ? OR category LIKE ? OR manufacturer LIKE ?
            """
            
            url = f"{self.db_service_url}/execute"
            search_param = f"%{query}%"
            payload = {
                "query": search_query,
                "params": [search_param, search_param, search_param, search_param]
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                products = result.get('data', [])
                
                return {
                    "status": "success",
                    "message": f"Found {len(products)} products matching '{query}'",
                    "data": products
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error searching products: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return {"status": "error", "message": str(e)}
            
    def get_products_by_category(self, category):
        """Get products by category"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
                
            url = f"{self.db_service_url}/tables/products/data"
            params = {"condition": "category = ?", "params": category}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                products = result.get('data', [])
                
                return {
                    "status": "success",
                    "message": f"Found {len(products)} products in category '{category}'",
                    "data": products
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving products by category: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving products by category {category}: {e}")
            return {"status": "error", "message": str(e)}
            
    def get_products_by_manufacturer(self, manufacturer):
        """Get products by manufacturer"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
                
            url = f"{self.db_service_url}/tables/products/data"
            params = {"condition": "manufacturer = ?", "params": manufacturer}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                products = result.get('data', [])
                
                return {
                    "status": "success",
                    "message": f"Found {len(products)} products by manufacturer '{manufacturer}'",
                    "data": products
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving products by manufacturer: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving products by manufacturer {manufacturer}: {e}")
            return {"status": "error", "message": str(e)}

    def get_all_categories(self):
        """Get all unique categories"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            query = "SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''"
            result = self._execute_query(query)
            
            if result and result.get('status') == 'success':
                categories = [item['category'] for item in result.get('data', [])]
                
                return {
                    "status": "success",
                    "message": f"Retrieved {len(categories)} categories",
                    "data": categories
                }
            else:
                return {
                    "status": "error",
                    "message": "Error retrieving categories"
                }
        except Exception as e:
            logger.error(f"Error retrieving categories: {e}")
            return {"status": "error", "message": str(e)}
            
    def get_all_manufacturers(self):
        """Get all unique manufacturers"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_storage()
            
            query = "SELECT DISTINCT manufacturer FROM products WHERE manufacturer IS NOT NULL AND manufacturer != ''"
            result = self._execute_query(query)
            
            if result and result.get('status') == 'success':
                manufacturers = [item['manufacturer'] for item in result.get('data', [])]
                
                return {
                    "status": "success",
                    "message": f"Retrieved {len(manufacturers)} manufacturers",
                    "data": manufacturers
                }
            else:
                return {
                    "status": "error",
                    "message": "Error retrieving manufacturers"
                }
        except Exception as e:
            logger.error(f"Error retrieving manufacturers: {e}")
            return {"status": "error", "message": str(e)}

# Create a global product storage instance
db_service_url = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
db_name = os.environ.get('DB_NAME', '/data/storage.sqlite')
product_storage = ProductStorage(db_service_url, db_name)

@app.route('/api/products/<product_id>/images', methods=['GET'])
def get_product_images(product_id):
    """Get all images for a product"""
    try:
        result = product_storage.get_product_images(product_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product_images route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>/images/upload', methods=['POST'])
def upload_product_image(product_id):
    """Upload an image for a product"""
    try:
        # Check if product exists
        product_check = product_storage.get_product(product_id)
        if product_check['status'] == 'error':
            return jsonify({"status": "error", "message": f"Product {product_id} not found"}), 404
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part in the request"}), 400
        
        file = request.files['file']
        alt_text = request.form.get('alt_text', '')
        is_primary = request.form.get('is_primary', '0') == '1'
        sort_order = int(request.form.get('sort_order', 0))
        
        result = product_storage.handle_product_image_upload(
            file, product_id, is_primary, alt_text, sort_order
        )
        
        if result['status'] == 'error':
            return jsonify(result), 400
        
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error in upload_product_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>/images/upload/multiple', methods=['POST'])
def upload_multiple_product_images(product_id):
    """Upload multiple images for a product"""
    try:
        # Check if product exists
        product_check = product_storage.get_product(product_id)
        if product_check['status'] == 'error':
            return jsonify({"status": "error", "message": f"Product {product_id} not found"}), 404
        
        # Check if files are in request
        if 'files[]' not in request.files:
            return jsonify({"status": "error", "message": "No files part in the request"}), 400
        
        files = request.files.getlist('files[]')
        
        if not files or len(files) == 0:
            return jsonify({"status": "error", "message": "No files selected"}), 400
        
        results = []
        success_count = 0
        
        for index, file in enumerate(files):
            # First image is primary if there are no images yet
            is_primary = (index == 0 and not product_check['data'].get('image_url'))
            
            result = product_storage.handle_product_image_upload(
                file, product_id, is_primary, file.filename, index
            )
            
            results.append(result)
            if result['status'] == 'success':
                success_count += 1
        
        return jsonify({
            "status": "success",
            "message": f"Uploaded {success_count} of {len(files)} images successfully",
            "results": results
        }), 201
    except Exception as e:
        logger.error(f"Error in upload_multiple_product_images route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['GET'])
def get_product_image(image_id):
    """Get a specific image by ID"""
    try:
        result = product_storage.get_product_image(image_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['PUT'])
def update_product_image(image_id):
    """Update an image"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        result = product_storage.update_product_image(image_id, data)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_product_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['DELETE'])
def delete_product_image(image_id):
    """Delete an image"""
    try:
        result = product_storage.delete_product_image(image_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_product_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>/set-primary', methods=['PUT'])
def set_primary_image(image_id):
    """Set an image as the primary image for its product"""
    try:
        result = product_storage.update_product_image(image_id, {'is_primary': 1})
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in set_primary_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/storage/serve/<path:filepath>', methods=['GET'])
def serve_storage_file(filepath):
    """Serve storage files - note: for development purposes only"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)
    except Exception as e:
        logger.error(f"Error serving storage file {filepath}: {e}")
        return jsonify({"status": "error", "message": "File not found"}), 404

@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all products"""
    try:
        result = product_storage.get_all_products()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product by ID"""
    try:
        result = product_storage.get_product(product_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def create_product():
    """Create a new product"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Product data is required"}), 400
        
        result = product_storage.create_product(data)
        if result['status'] == 'error':
            return jsonify(result), 400
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error in create_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        result = product_storage.update_product(product_id, data)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product"""
    try:
        result = product_storage.delete_product(product_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/search', methods=['GET'])
def search_products():
    """Search for products by name or description"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"status": "error", "message": "Search query is required"}), 400
        
        result = product_storage.search_products(query)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in search_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/category/<category>', methods=['GET'])
def get_products_by_category(category):
    """Get products by category"""
    try:
        result = product_storage.get_products_by_category(category)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_products_by_category route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/manufacturer/<manufacturer>', methods=['GET'])
def get_products_by_manufacturer(manufacturer):
    """Get products by manufacturer"""
    try:
        result = product_storage.get_products_by_manufacturer(manufacturer)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_products_by_manufacturer route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories"""
    try:
        result = product_storage.get_all_categories()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_categories route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/manufacturers', methods=['GET'])
def get_manufacturers():
    """Get all manufacturers"""
    try:
        result = product_storage.get_all_manufacturers()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_manufacturers route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check connection to database service
        db_health_url = f"{product_storage.db_service_url}/health"
        try:
            db_response = requests.get(db_health_url)
            db_status = "connected" if db_response.status_code == 200 else "disconnected"
            db_details = db_response.json() if db_response.status_code == 200 else {}
        except:
            db_status = "disconnected"
            db_details = {}
        
        return jsonify({
            "status": "up",
            "service": "Product Storage API",
            "db_service": db_status,
            "db_service_url": product_storage.db_service_url,
            "db_name": product_storage.db_name,
            "db_details": db_details,
            "initialized": product_storage.initialized,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health_check route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5005))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')