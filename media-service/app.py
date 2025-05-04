#!/usr/bin/env python3
# Media Microservice using Database Service with dedicated database
# RESTful API using Flask for managing articles, news, and media

from flask import Flask, request, jsonify
import os
import logging
import uuid
import requests
from datetime import datetime
import json
import re
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flask import send_from_directory
import os
import mimetypes
from pathlib import Path
import shutil
from flask import Flask, request, jsonify,send_from_directory
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

UPLOAD_FOLDER = '/data/media'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', MAX_CONTENT_LENGTH))


class MediaService:
    def __init__(self, db_service_url=None, db_name=None):
        """Initialize the media service with the database service URL and db name"""
        if db_service_url is None:
            self.db_service_url = "http://localhost:5003/api"
        else:
            self.db_service_url = db_service_url
            
        if db_name is None:
            self.db_name = "/data/media.sqlite"
        else:
            self.db_name = db_name
        
        self.initialized = False
        self.connect_to_db()
        if self.initialized:
            self.init_tables()

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

    def allowed_file(self, filename):
        """Check if a filename has an allowed extension"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def generate_media_path(self, article_id, filename):
        """Generate a unique filepath for an uploaded image"""
        # Secure the filename to prevent directory traversal attacks
        filename = secure_filename(filename)
        
        # Get file extension
        _, ext = os.path.splitext(filename)
        
        # Generate a unique filename using uuid
        unique_filename = f"{str(uuid.uuid4())}{ext}"
        
        # Create year/month directory structure
        today = datetime.now()
        year_month = f"{today.year}/{today.month:02d}"
        
        # Construct directory path under article_id
        rel_directory = f"articles/{article_id}/{year_month}"
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

    def handle_image_upload(self, file, article_id):
        """Handle an image file upload"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
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
            
            # Generate file path
            path_info = self.generate_media_path(article_id, file.filename)
            
            # Save the file
            file.save(path_info['absolute_path'])
            
            # Get file size
            file_size = os.path.getsize(path_info['absolute_path'])
            
            # Try to determine dimensions for images
            width = None
            height = None
            
            # Determine mime type
            mime_type = mimetypes.guess_type(path_info['absolute_path'])[0]
            
            # Create image metadata
            image_data = {
                'image_id': str(uuid.uuid4()),
                'article_id': article_id,
                'filename': path_info['original_filename'],
                'path': path_info['relative_path'],
                'alt_text': path_info['original_filename'],  # Default alt text
                'size_kb': file_size // 1024,
                'mime_type': mime_type,
                'width': width,
                'height': height,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add image metadata to database
            result = self.add_image(image_data)
            
            if result['status'] == 'success':
                return result
            else:
                # If database insert failed, clean up the file
                if os.path.exists(path_info['absolute_path']):
                    os.remove(path_info['absolute_path'])
                return result
            
        except Exception as e:
            logger.error(f"Error handling image upload: {e}")
            return {"status": "error", "message": str(e)}

    def init_tables(self):
        """Initialize the required tables if they don't exist"""
        try:
            # Check if tables exist
            tables_url = f"{self.db_service_url}/tables"
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(tables_url,headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                tables = data.get('tables', [])
                
                # Create articles table if it doesn't exist
                if 'articles' not in tables:
                    self._create_articles_table()
                
                # Create images table if it doesn't exist
                if 'images' not in tables:
                    self._create_images_table()
                
                # Create tags table if it doesn't exist
                if 'tags' not in tables:
                    self._create_tags_table()
                
                # Create article_tags table if it doesn't exist
                if 'article_tags' not in tables:
                    self._create_article_tags_table()
                
                return True
            else:
                logger.error(f"Error listing tables: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing tables: {e}")
            return False
    
    def _create_articles_table(self):
        """Create the articles table"""
        try:
            create_table_url = f"{self.db_service_url}/tables"
            columns = {
                "article_id": "TEXT PRIMARY KEY",
                "title": "TEXT NOT NULL",
                "content": "TEXT NOT NULL",
                "summary": "TEXT",
                "type": "TEXT NOT NULL",  # 'article' or 'news'
                "author": "TEXT",
                "published_date": "TEXT",
                "status": "TEXT DEFAULT 'draft'",  # draft, published, archived
                "featured": "INTEGER DEFAULT 0",
                "featured_image_id": "TEXT",
                "view_count": "INTEGER DEFAULT 0",
                "created_at": "TEXT",
                "updated_at": "TEXT"
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(
                create_table_url, 
                json={"table_name": "articles", "columns": columns},
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Error creating articles table: {response.text}")
                return False
            
            logger.info("Articles table created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating articles table: {e}")
            return False
    
    def _create_images_table(self):
        """Create the images table"""
        try:
            create_table_url = f"{self.db_service_url}/tables"
            columns = {
                "image_id": "TEXT PRIMARY KEY",
                "article_id": "TEXT",
                "filename": "TEXT NOT NULL",
                "path": "TEXT NOT NULL",
                "alt_text": "TEXT",
                "caption": "TEXT",
                "width": "INTEGER",
                "height": "INTEGER",
                "size_kb": "INTEGER",
                "mime_type": "TEXT",
                "order_index": "INTEGER DEFAULT 0",
                "created_at": "TEXT",
                "FOREIGN KEY (article_id)": "REFERENCES articles(article_id) ON DELETE CASCADE"
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(
                create_table_url, 
                json={"table_name": "images", "columns": columns},
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Error creating images table: {response.text}")
                return False
            
            logger.info("Images table created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating images table: {e}")
            return False
    
    def _create_tags_table(self):
        """Create the tags table"""
        try:
            create_table_url = f"{self.db_service_url}/tables"
            columns = {
                "tag_id": "TEXT PRIMARY KEY",
                "name": "TEXT NOT NULL UNIQUE",
                "slug": "TEXT NOT NULL UNIQUE",
                "description": "TEXT",
                "created_at": "TEXT"
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(
                create_table_url, 
                json={"table_name": "tags", "columns": columns},
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Error creating tags table: {response.text}")
                return False
            
            logger.info("Tags table created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating tags table: {e}")
            return False
    
    def _create_article_tags_table(self):
        """Create the article_tags junction table"""
        try:
            create_table_url = f"{self.db_service_url}/tables"
            columns = {
                "article_id": "TEXT NOT NULL",
                "tag_id": "TEXT NOT NULL",
                "PRIMARY KEY (article_id, tag_id)": "",
                "FOREIGN KEY (article_id)": "REFERENCES articles(article_id) ON DELETE CASCADE",
                "FOREIGN KEY (tag_id)": "REFERENCES tags(tag_id) ON DELETE CASCADE"
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(
                create_table_url, 
                json={"table_name": "article_tags", "columns": columns},
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Error creating article_tags table: {response.text}")
                return False
            
            logger.info("Article_tags table created successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating article_tags table: {e}")
            return False
    
    def _execute_query(self, query, params=None):
        """Execute a SQL query via the database service"""
        try:
            url = f"{self.db_service_url}/execute"
            payload = {"query": query}
            if params:
                payload["params"] = params
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(url, headers=headers, json=payload)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return None
    
    def create_slug(self, text):
        """Generate a URL-friendly slug from the given text"""
        # Convert to lowercase and remove non-alphanumeric characters
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        # Replace whitespace with hyphens
        slug = re.sub(r'\s+', '-', slug.strip())
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{slug}-{timestamp}"
    
    # Article CRUD Operations
    
    def get_all_articles(self, type=None, status=None, limit=10, offset=0):
        """Get all articles with optional filtering"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Build query with optional filters
            conditions = []
            params = []
            
            if type:
                conditions.append("type = ?")
                params.append(type)
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            condition_str = " AND ".join(conditions) if conditions else None
            
            # Get articles
            url = f"{self.db_service_url}/tables/articles/data"
            request_params = {
                "columns": "article_id, title, summary, type, author, published_date, status, featured, featured_image_id, view_count, created_at, updated_at"
            }
            headers = {'X-Database-Name': self.db_name}
            if condition_str:
                request_params["condition"] = condition_str
                request_params["params"] = ",".join(params)
            
            response = requests.get(url, headers=headers,params=request_params)
            
            if response.status_code == 200:
                result = response.json()
                articles = result.get('data', [])
                
                # Add featured image URL for each article that has one
                for article in articles:
                    if article.get('featured_image_id'):
                        image_data = self.get_image(article['featured_image_id'])
                        if image_data.get('status') == 'success' and image_data.get('data'):
                            article['featured_image'] = image_data['data']
                
                # Apply pagination in memory
                paginated_articles = articles[offset:offset+limit] if articles else []
                
                return {
                    "status": "success",
                    "message": f"Retrieved {len(paginated_articles)} articles",
                    "total": len(articles),
                    "limit": limit,
                    "offset": offset,
                    "data": paginated_articles
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving articles: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving articles: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_article(self, article_id):
        """Get a specific article by ID with all related data"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Get article
            url = f"{self.db_service_url}/tables/articles/data"
            params = {"condition": "article_id = ?", "params": article_id}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                articles = result.get('data', [])
                
                if not articles:
                    return {
                        "status": "error",
                        "message": f"Article with ID {article_id} not found"
                    }
                
                article = articles[0]
                
                # Get images for this article
                images_result = self.get_article_images(article_id)
                if images_result['status'] == 'success':
                    article['images'] = images_result['data']
                else:
                    article['images'] = []
                
                # Get tags for this article
                tags_result = self.get_article_tags(article_id)
                if tags_result['status'] == 'success':
                    article['tags'] = tags_result['data']
                else:
                    article['tags'] = []
                
                # Increment view count
                self._increment_article_view_count(article_id)
                
                return {
                    "status": "success",
                    "message": f"Retrieved article {article_id}",
                    "data": article
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving article: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def _increment_article_view_count(self, article_id):
        """Increment the view_count for an article"""
        try:
            query = """
            UPDATE articles 
            SET view_count = view_count + 1 
            WHERE article_id = ?
            """
            
            self._execute_query(query, [article_id])
            return True
        except Exception as e:
            logger.error(f"Error incrementing view count for article {article_id}: {e}")
            return False
    
    def create_article(self, article_data):
        """Create a new article"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if required fields are present
            required_fields = ['title', 'content', 'type']
            missing_fields = [field for field in required_fields if field not in article_data]
            
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            # Generate article ID if not provided
            if 'article_id' not in article_data:
                article_data['article_id'] = str(uuid.uuid4())
            
            # Set timestamps
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            article_data['created_at'] = now
            article_data['updated_at'] = now
            
            # Set default values if not provided
            if 'status' not in article_data:
                article_data['status'] = 'draft'
            
            # Extract tags if provided
            tags = article_data.pop('tags', [])
            
            # Extract images data if provided
            images = article_data.pop('images', [])
            
            # Insert article into database
            url = f"{self.db_service_url}/tables/articles/data"
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(url, headers=headers, json=article_data)
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Error creating article: {response.text}"
                }
            
            # Process tags
            if tags:
                for tag in tags:
                    # Create tag if it doesn't exist
                    tag_result = self._create_or_get_tag(tag)
                    if tag_result['status'] == 'success':
                        # Associate tag with article
                        self._add_tag_to_article(article_data['article_id'], tag_result['data']['tag_id'])
            
            # Process images
            if images:
                for index, image_data in enumerate(images):
                    image_data['article_id'] = article_data['article_id']
                    image_data['order_index'] = index
                    self.add_image(image_data)
                    
                    # If this is the first image and no featured image is set, use it as featured
                    if index == 0 and 'featured_image_id' not in article_data:
                        if 'image_id' in image_data:
                            self._set_featured_image(article_data['article_id'], image_data['image_id'])
            
            # Get the complete article with related data
            return self.get_article(article_data['article_id'])
        except Exception as e:
            logger.error(f"Error creating article: {e}")
            return {"status": "error", "message": str(e)}
    
    def update_article(self, article_id, updates):
        """Update an article"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if article exists
            check_result = self.get_article(article_id)
            if check_result['status'] == 'error':
                return check_result
            
            # Update timestamp
            updates['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract tags if provided
            tags = None
            if 'tags' in updates:
                tags = updates.pop('tags')
            
            # Extract images data if provided
            images = None
            if 'images' in updates:
                images = updates.pop('images')
            
            # Update article in database
            url = f"{self.db_service_url}/tables/articles/data"
            payload = {
                "values": updates,
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.put(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Error updating article: {response.text}"
                }
            
            # Update tags if provided
            if tags is not None:
                # First remove all existing tags
                self._remove_all_tags_from_article(article_id)
                
                # Then add new tags
                for tag in tags:
                    tag_result = self._create_or_get_tag(tag)
                    if tag_result['status'] == 'success':
                        self._add_tag_to_article(article_id, tag_result['data']['tag_id'])
            
            # Update images if provided
            if images is not None:
                # First remove all existing images
                self._remove_all_images_from_article(article_id)
                
                # Then add new images
                for index, image_data in enumerate(images):
                    image_data['article_id'] = article_id
                    image_data['order_index'] = index
                    self.add_image(image_data)
                    
                    # If this is the first image and no featured image is set, use it as featured
                    if index == 0 and ('featured_image_id' not in updates or not updates['featured_image_id']):
                        if 'image_id' in image_data:
                            self._set_featured_image(article_id, image_data['image_id'])
            
            # Get the updated article with related data
            return self.get_article(article_id)
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete_article(self, article_id):
        """Delete an article and all related data"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if article exists
            check_result = self.get_article(article_id)
            if check_result['status'] == 'error':
                return check_result
            
            # Delete article from database
            # This will cascade delete related images and article_tags entries
            url = f"{self.db_service_url}/tables/articles/data"
            payload = {
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.delete(url,headers=headers, json=payload)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Article {article_id} deleted successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error deleting article: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error deleting article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def publish_article(self, article_id):
        """Publish an article by setting its status to 'published'"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if article exists
            check_result = self.get_article(article_id)
            if check_result['status'] == 'error':
                return check_result
            
            # Set status to published and update published_date
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updates = {
                "status": "published",
                "published_date": now,
                "updated_at": now
            }
            
            # Update article in database
            url = f"{self.db_service_url}/tables/articles/data"
            payload = {
                "values": updates,
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.put(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                return self.get_article(article_id)
            else:
                return {
                    "status": "error",
                    "message": f"Error publishing article: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error publishing article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def archive_article(self, article_id):
        """Archive an article by setting its status to 'archived'"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if article exists
            check_result = self.get_article(article_id)
            if check_result['status'] == 'error':
                return check_result
            
            # Set status to archived
            updates = {
                "status": "archived",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Update article in database
            url = f"{self.db_service_url}/tables/articles/data"
            payload = {
                "values": updates,
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.put(url,headers=headers, json=payload)
            
            if response.status_code == 200:
                return self.get_article(article_id)
            else:
                return {
                    "status": "error",
                    "message": f"Error archiving article: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error archiving article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def search_articles(self, query, limit=10, offset=0):
        """Search for articles by title, content, or summary"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Use database service to search
            search_query = """
            SELECT article_id, title, summary, type, author, published_date, status, 
                   featured, featured_image_id, view_count, created_at, updated_at
            FROM articles
            WHERE title LIKE ? OR content LIKE ? OR summary LIKE ? OR author LIKE ?
            ORDER BY 
                CASE 
                    WHEN status = 'published' THEN 1 
                    WHEN status = 'draft' THEN 2 
                    ELSE 3 
                END,
                created_at DESC
            """
            
            search_param = f"%{query}%"
            
            result = self._execute_query(
                search_query, 
                [search_param, search_param, search_param, search_param]
            )
            
            if result and result.get('status') == 'success':
                articles = result.get('data', [])
                
                # Add featured image URL for each article that has one
                for article in articles:
                    if article.get('featured_image_id'):
                        image_data = self.get_image(article['featured_image_id'])
                        if image_data.get('status') == 'success' and image_data.get('data'):
                            article['featured_image'] = image_data['data']
                
                # Apply pagination in memory
                total_count = len(articles)
                paginated_articles = articles[offset:offset+limit] if articles else []
                
                return {
                    "status": "success",
                    "message": f"Found {total_count} articles matching '{query}'",
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "data": paginated_articles
                }
            else:
                return {
                    "status": "error",
                    "message": "Error searching articles"
                }
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_featured_articles(self, limit=5):
        """Get featured articles"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Query for featured articles that are published
            query = """
            SELECT article_id, title, summary, type, author, published_date, status, 
                   featured, featured_image_id, view_count, created_at, updated_at
            FROM articles
            WHERE featured = 1 AND status = 'published'
            ORDER BY published_date DESC
            LIMIT ?
            """
            
            result = self._execute_query(query, [limit])
            
            if result and result.get('status') == 'success':
                articles = result.get('data', [])
                
                # Add featured image URL for each article that has one
                for article in articles:
                    if article.get('featured_image_id'):
                        image_data = self.get_image(article['featured_image_id'])
                        if image_data.get('status') == 'success' and image_data.get('data'):
                            article['featured_image'] = image_data['data']
                
                return {
                    "status": "success",
                    "message": f"Retrieved {len(articles)} featured articles",
                    "data": articles
                }
            else:
                return {
                    "status": "error",
                    "message": "Error retrieving featured articles"
                }
        except Exception as e:
            logger.error(f"Error retrieving featured articles: {e}")
            return {"status": "error", "message": str(e)}
    
    def _set_featured_image(self, article_id, image_id):
        """Set the featured image for an article"""
        try:
            # Update the article with the featured image ID
            url = f"{self.db_service_url}/tables/articles/data"
            payload = {
                "values": {"featured_image_id": image_id},
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.put(url,headers=headers, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error setting featured image for article {article_id}: {e}")
            return False
    
    # Image Operations
    
    def add_image(self, image_data):
        """Add an image to an article"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if required fields are present
            required_fields = ['article_id', 'filename', 'path']
            missing_fields = [field for field in required_fields if field not in image_data]
            
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
            
            # Generate image ID if not provided
            if 'image_id' not in image_data:
                image_data['image_id'] = str(uuid.uuid4())
            
            # Set timestamp
            image_data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Insert image into database
            url = f"{self.db_service_url}/tables/images/data"
            headers = {'X-Database-Name': self.db_name}
            response = requests.post(url, headers=headers, json=image_data)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Image added successfully with ID {image_data['image_id']}",
                    "data": image_data
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error adding image: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error adding image: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_image(self, image_id):
        """Get a specific image by ID"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            url = f"{self.db_service_url}/tables/images/data"
            params = {"condition": "image_id = ?", "params": image_id}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
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
            logger.error(f"Error retrieving image {image_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_article_images(self, article_id):
        """Get all images for a specific article"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            url = f"{self.db_service_url}/tables/images/data"
            params = {"condition": "article_id = ?", "params": article_id}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "message": f"Retrieved {len(result.get('data', []))} images for article {article_id}",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving images: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving images for article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def update_image(self, image_id, updates):
        """Update an image"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if image exists
            check_result = self.get_image(image_id)
            if check_result['status'] == 'error':
                return check_result
            
            # Update image in database
            url = f"{self.db_service_url}/tables/images/data"
            payload = {
                "values": updates,
                "condition": "image_id = ?",
                "params": [image_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.put(url,headers=headers, json=payload)
            
            if response.status_code == 200:
                return self.get_image(image_id)
            else:
                return {
                    "status": "error",
                    "message": f"Error updating image: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error updating image {image_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete_image(self, image_id):
        """Delete an image and its file from the filesystem"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if image exists
            check_result = self.get_image(image_id)
            if check_result['status'] == 'error':
                return check_result
            
            # Get the image data for file deletion
            image_data = check_result['data']
            
            # Check if this is a featured image for any article
            if image_data.get('article_id'):
                # Check if this is the featured image
                article_url = f"{self.db_service_url}/tables/articles/data"
                article_params = {
                    "condition": "article_id = ? AND featured_image_id = ?", 
                    "params": f"{image_data['article_id']},{image_id}"
                }
                headers = {'X-Database-Name': self.db_name}
                article_response = requests.get(article_url, headers=headers, params=article_params)
                
                if article_response.status_code == 200:
                    article_result = article_response.json()
                    if article_result.get('data'):
                        # This is a featured image, clear the reference
                        update_url = f"{self.db_service_url}/tables/articles/data"
                        update_payload = {
                            "values": {"featured_image_id": None},
                            "condition": "article_id = ? AND featured_image_id = ?",
                            "params": [image_data['article_id'], image_id]
                        }
                        requests.put(update_url, json=update_payload)
            
            # Delete the image file from filesystem
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
            
            # Delete the image metadata
            url = f"{self.db_service_url}/tables/images/data"
            payload = {
                "condition": "image_id = ?",
                "params": [image_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.delete(url,headers=headers, json=payload)
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": f"Image {image_id} deleted successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error deleting image metadata: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error deleting image {image_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def _remove_all_images_from_article(self, article_id):
        """Remove all images associated with an article, including files"""
        try:
            # First, get all images for this article
            images_result = self.get_article_images(article_id)
            
            if images_result['status'] == 'success' and images_result['data']:
                # Delete each image file
                for image in images_result['data']:
                    if image.get('path'):
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], image['path'])
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                logger.warning(f"Error removing file {file_path}: {e}")
                
                # Try to clean up the article directory
                try:
                    article_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"articles/{article_id}")
                    if os.path.exists(article_dir):
                        shutil.rmtree(article_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Error removing article directory: {e}")
            
            # Delete all image records from database
            url = f"{self.db_service_url}/tables/images/data"
            payload = {
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.delete(url,headers=headers, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error removing images from article {article_id}: {e}")
            return False
    
    # Tag Operations
    
    def _create_or_get_tag(self, tag_name):
        """Create a tag if it doesn't exist or get existing tag ID"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Check if tag exists
            url = f"{self.db_service_url}/tables/tags/data"
            params = {"condition": "name = ?", "params": tag_name}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                existing_tags = result.get('data', [])
                
                if existing_tags:
                    # Tag exists, return it
                    return {
                        "status": "success",
                        "message": f"Tag '{tag_name}' already exists",
                        "data": existing_tags[0]
                    }
                else:
                    # Tag doesn't exist, create it
                    tag_data = {
                        "tag_id": str(uuid.uuid4()),
                        "name": tag_name,
                        "slug": self.create_slug(tag_name),
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    create_url = f"{self.db_service_url}/tables/tags/data"
                    headers = {'X-Database-Name': self.db_name}
                    create_response = requests.post(create_url,headers=headers, json=tag_data)
                    
                    if create_response.status_code == 200:
                        return {
                            "status": "success",
                            "message": f"Tag '{tag_name}' created successfully",
                            "data": tag_data
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"Error creating tag: {create_response.text}"
                        }
            else:
                return {
                    "status": "error",
                    "message": f"Error checking tag existence: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error creating or getting tag '{tag_name}': {e}")
            return {"status": "error", "message": str(e)}
    
    def _add_tag_to_article(self, article_id, tag_id):
        """Associate a tag with an article"""
        try:
            # Check if the association already exists
            url = f"{self.db_service_url}/tables/article_tags/data"
            params = {"condition": "article_id = ? AND tag_id = ?", "params": f"{article_id},{tag_id}"}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('data'):
                    # Association already exists
                    return True
                
                # Create the association
                association_data = {
                    "article_id": article_id,
                    "tag_id": tag_id
                }
                
                create_response = requests.post(url,headers=headers, json=association_data)
                return create_response.status_code == 200
            else:
                return False
        except Exception as e:
            logger.error(f"Error adding tag {tag_id} to article {article_id}: {e}")
            return False
    
    def _remove_all_tags_from_article(self, article_id):
        """Remove all tag associations for an article"""
        try:
            url = f"{self.db_service_url}/tables/article_tags/data"
            payload = {
                "condition": "article_id = ?",
                "params": [article_id]
            }
            headers = {'X-Database-Name': self.db_name}
            response = requests.delete(url,headers=headers, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error removing tags from article {article_id}: {e}")
            return False
    
    def get_article_tags(self, article_id):
        """Get all tags for a specific article"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # Join query to get tags associated with the article
            query = """
            SELECT t.tag_id, t.name, t.slug, t.description
            FROM tags t
            JOIN article_tags at ON t.tag_id = at.tag_id
            WHERE at.article_id = ?
            """
            
            result = self._execute_query(query, [article_id])
            
            if result and result.get('status') == 'success':
                return {
                    "status": "success",
                    "message": f"Retrieved {len(result.get('data', []))} tags for article {article_id}",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "status": "error",
                    "message": "Error retrieving article tags"
                }
        except Exception as e:
            logger.error(f"Error retrieving tags for article {article_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_all_tags(self):
        """Get all tags"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            url = f"{self.db_service_url}/tables/tags/data"
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "message": f"Retrieved {len(result.get('data', []))} tags",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "status": "error",
                    "message": f"Error retrieving tags: {response.text}"
                }
        except Exception as e:
            logger.error(f"Error retrieving tags: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_articles_by_tag(self, tag_slug, limit=10, offset=0):
        """Get articles associated with a specific tag"""
        try:
            if not self.initialized:
                self.connect_to_db()
                if self.initialized:
                    self.init_tables()
            
            # First get the tag ID from the slug
            url = f"{self.db_service_url}/tables/tags/data"
            params = {"condition": "slug = ?", "params": tag_slug}
            headers = {'X-Database-Name': self.db_name}
            response = requests.get(url,headers=headers, params=params)
            
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Error retrieving tag: {response.text}"
                }
            
            result = response.json()
            tags = result.get('data', [])
            
            if not tags:
                return {
                    "status": "error",
                    "message": f"Tag with slug '{tag_slug}' not found"
                }
            
            tag_id = tags[0]['tag_id']
            
            # Query to get articles associated with the tag
            query = """
            SELECT a.article_id, a.title, a.summary, a.type, a.author, a.published_date, a.status, 
                   a.featured, a.featured_image_id, a.view_count, a.created_at, a.updated_at
            FROM articles a
            JOIN article_tags at ON a.article_id = at.article_id
            WHERE at.tag_id = ?
            ORDER BY 
                CASE 
                    WHEN a.status = 'published' THEN 1 
                    WHEN a.status = 'draft' THEN 2 
                    ELSE 3 
                END,
                a.created_at DESC
            """
            
            result = self._execute_query(query, [tag_id])
            
            if result and result.get('status') == 'success':
                articles = result.get('data', [])
                
                # Add featured image URL for each article that has one
                for article in articles:
                    if article.get('featured_image_id'):
                        image_data = self.get_image(article['featured_image_id'])
                        if image_data.get('status') == 'success' and image_data.get('data'):
                            article['featured_image'] = image_data['data']
                
                # Apply pagination in memory
                total_count = len(articles)
                paginated_articles = articles[offset:offset+limit] if articles else []
                
                return {
                    "status": "success",
                    "message": f"Found {total_count} articles with tag '{tags[0]['name']}'",
                    "tag": tags[0],
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "data": paginated_articles
                }
            else:
                return {
                    "status": "error",
                    "message": "Error retrieving articles by tag"
                }
        except Exception as e:
            logger.error(f"Error retrieving articles by tag {tag_slug}: {e}")
            return {"status": "error", "message": str(e)}

# Create a global media service instance
db_service_url = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
db_name = os.environ.get('DB_NAME', '/data/media.sqlite')
media_service = MediaService(db_service_url, db_name)

# Article Endpoints

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """Get all articles with optional filtering"""
    try:
        type = request.args.get('type')  # 'article' or 'news'
        status = request.args.get('status')  # 'draft', 'published', 'archived'
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        result = media_service.get_all_articles(type, status, limit, offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_articles route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>', methods=['GET'])
def get_article(article_id):
    """Get a specific article by ID"""
    try:
        result = media_service.get_article(article_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_article route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles', methods=['POST'])
def create_article():
    """Create a new article"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Article data is required"}), 400
        
        result = media_service.create_article(data)
        if result['status'] == 'error':
            return jsonify(result), 400
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error in create_article route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>', methods=['PUT'])
def update_article(article_id):
    """Update an article"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        result = media_service.update_article(article_id, data)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_article route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>', methods=['DELETE'])
def delete_article(article_id):
    """Delete an article"""
    try:
        result = media_service.delete_article(article_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_article route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/publish', methods=['PUT'])
def publish_article(article_id):
    """Publish an article"""
    try:
        result = media_service.publish_article(article_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in publish_article route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/archive', methods=['PUT'])
def archive_article(article_id):
    """Archive an article"""
    try:
        result = media_service.archive_article(article_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in archive_article route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/search', methods=['GET'])
def search_articles():
    """Search for articles"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        if not query:
            return jsonify({"status": "error", "message": "Search query is required"}), 400
        
        result = media_service.search_articles(query, limit, offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in search_articles route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/featured', methods=['GET'])
def get_featured_articles():
    """Get featured articles"""
    try:
        limit = int(request.args.get('limit', 5))
        result = media_service.get_featured_articles(limit)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_featured_articles route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Image Endpoints

@app.route('/api/articles/<article_id>/images', methods=['GET'])
def get_article_images(article_id):
    """Get all images for an article"""
    try:
        result = media_service.get_article_images(article_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_article_images route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['GET'])
def get_image(image_id):
    """Get a specific image by ID"""
    try:
        result = media_service.get_image(image_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/images/upload', methods=['POST'])
def upload_image(article_id):
    """Upload an image for an article"""
    try:
        # Check if article exists
        article_check = media_service.get_article(article_id)
        if article_check['status'] == 'error':
            return jsonify({"status": "error", "message": f"Article {article_id} not found"}), 404
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part in the request"}), 400
        
        file = request.files['file']
        result = media_service.handle_image_upload(file, article_id)
        
        if result['status'] == 'error':
            return jsonify(result), 400
        
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error in upload_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/images/upload/multiple', methods=['POST'])
def upload_multiple_images(article_id):
    """Upload multiple images for an article"""
    try:
        # Check if article exists
        article_check = media_service.get_article(article_id)
        if article_check['status'] == 'error':
            return jsonify({"status": "error", "message": f"Article {article_id} not found"}), 404
        
        # Check if files are in request
        if 'files[]' not in request.files:
            return jsonify({"status": "error", "message": "No files part in the request"}), 400
        
        files = request.files.getlist('files[]')
        
        if not files or len(files) == 0:
            return jsonify({"status": "error", "message": "No files selected"}), 400
        
        results = []
        success_count = 0
        
        for file in files:
            result = media_service.handle_image_upload(file, article_id)
            results.append(result)
            if result['status'] == 'success':
                success_count += 1
        
        # Check if any featured image is set for this article
        if success_count > 0 and article_check['data'].get('featured_image_id') is None:
            # Set the first successful uploaded image as featured
            for result in results:
                if result['status'] == 'success':
                    media_service._set_featured_image(article_id, result['data']['image_id'])
                    break
        
        return jsonify({
            "status": "success",
            "message": f"Uploaded {success_count} of {len(files)} images successfully",
            "results": results
        }), 201
    except Exception as e:
        logger.error(f"Error in upload_multiple_images route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/media/serve/<path:filepath>', methods=['GET'])
def serve_media(filepath):
    """Serve media files - note: for development purposes only"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)
    except Exception as e:
        logger.error(f"Error serving media file {filepath}: {e}")
        return jsonify({"status": "error", "message": "File not found"}), 404

@app.route('/api/images', methods=['POST'])
def add_image():
    """Add an image to an article"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Image data is required"}), 400
        
        result = media_service.add_image(data)
        if result['status'] == 'error':
            return jsonify(result), 400
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error in add_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['PUT'])
def update_image(image_id):
    """Update an image"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        result = media_service.update_image(image_id, data)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/<image_id>', methods=['DELETE'])
def delete_image(image_id):
    """Delete an image"""
    try:
        result = media_service.delete_image(image_id)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_image route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Tag Endpoints

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """Get all tags"""
    try:
        result = media_service.get_all_tags()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_tags route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tags/<tag_slug>/articles', methods=['GET'])
def get_articles_by_tag(tag_slug):
    """Get articles by tag"""
    try:
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        result = media_service.get_articles_by_tag(tag_slug, limit, offset)
        if result['status'] == 'error':
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_articles_by_tag route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/articles/<article_id>/tags', methods=['GET'])
def get_article_tags(article_id):
    """Get tags for an article"""
    try:
        result = media_service.get_article_tags(article_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_article_tags route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check connection to database service
        db_health_url = f"{media_service.db_service_url}/health"
        try:
            db_response = requests.get(db_health_url)
            db_status = "connected" if db_response.status_code == 200 else "disconnected"
            db_details = db_response.json() if db_response.status_code == 200 else {}
        except:
            db_status = "disconnected"
            db_details = {}
        
        return jsonify({
            "status": "up",
            "service": "Media API",
            "db_service": db_status,
            "db_service_url": media_service.db_service_url,
            "db_name": media_service.db_name,
            "db_details": db_details,
            "initialized": media_service.initialized,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health_check route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')
    
# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5007))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')