#!/usr/bin/env python3
# Database Management System Microservice
# RESTful API using Flask

from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime
import logging
from flask_cors import CORS
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

class DatabaseManager:
    def __init__(self, db_name=None):
        """Initialize the database manager with an optional database name"""
        if db_name is None:
            self.db_name = "ecommerce.sqlite"
        else:
            self.db_name = db_name if db_name.endswith('.sqlite') else f"{db_name}.sqlite"
        
        self.conn = None
        self.cursor = None
        self.connected = False

    def connect(self):
        """Connect to the database"""
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()
            self.connected = True
            logger.info(f"Connected to {self.db_name} successfully")
            return {"status": "success", "message": f"Connected to {self.db_name} successfully"}
        except sqlite3.Error as e:
            error_msg = f"Error connecting to database: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def disconnect(self):
        """Close the database connection"""
        if self.connected:
            self.conn.close()
            self.connected = False
            logger.info("Disconnected from database")
            return {"status": "success", "message": "Disconnected from database"}
        return {"status": "info", "message": "Not connected to any database"}
    
    def execute_query(self, query, params=None):
        """Execute a query and return results if any"""
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # If the query might return results (SELECT)
            if query.strip().upper().startswith("SELECT"):
                results = self.cursor.fetchall()
                
                # Format results as a list of dictionaries
                formatted_results = []
                for row in results:
                    formatted_results.append(dict(row))
                
                return {
                    "status": "success", 
                    "message": f"Query executed successfully. Retrieved {len(formatted_results)} rows.",
                    "data": formatted_results
                }
            else:
                self.conn.commit()
                return {
                    "status": "success", 
                    "message": f"Query executed successfully. {self.cursor.rowcount} rows affected.",
                    "rows_affected": self.cursor.rowcount
                }
        except sqlite3.Error as e:
            error_msg = f"Error executing query: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def create_table(self, table_name, columns):
        """Create a new table with specified columns
        
        Args:
            table_name (str): Name of the table to create
            columns (dict): Dictionary of column names and their data types/constraints
                Example: {"id": "INTEGER PRIMARY KEY", "name": "TEXT NOT NULL"}
        """
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            # Construct the CREATE TABLE query
            col_defs = [f"{col_name} {col_def}" for col_name, col_def in columns.items()]
            col_defs_str = ", ".join(col_defs)
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs_str})"
            
            # Execute the query
            self.cursor.execute(query)
            self.conn.commit()
            logger.info(f"Table '{table_name}' created successfully")
            return {"status": "success", "message": f"Table '{table_name}' created successfully"}
        except sqlite3.Error as e:
            error_msg = f"Error creating table: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def insert_data(self, table_name, data):
        """Insert data into a table
        
        Args:
            table_name (str): Name of the target table
            data (dict): Dictionary of column names and values to insert
        """
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            columns = list(data.keys())
            values = list(data.values())
            placeholders = ", ".join(["?"] * len(columns))
            
            query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            self.cursor.execute(query, values)
            self.conn.commit()
            logger.info(f"Data inserted into '{table_name}' successfully")
            return {
                "status": "success", 
                "message": f"Data inserted into '{table_name}' successfully",
                "last_row_id": self.cursor.lastrowid
            }
        except sqlite3.Error as e:
            error_msg = f"Error inserting data: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def select_data(self, table_name, columns="*", condition=None, params=None):
        """Select data from a table
        
        Args:
            table_name (str): Name of the target table
            columns (str): Columns to select, default is "*" (all)
            condition (str, optional): WHERE condition
            params (tuple, optional): Parameters for the condition
        """
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            query = f"SELECT {columns} FROM {table_name}"
            
            if condition:
                query += f" WHERE {condition}"
            
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            results = self.cursor.fetchall()
            
            # Format results as a list of dictionaries
            formatted_results = []
            for row in results:
                formatted_results.append(dict(row))
            
            return {
                "status": "success", 
                "message": f"Retrieved {len(formatted_results)} rows from '{table_name}'",
                "data": formatted_results
            }
        except sqlite3.Error as e:
            error_msg = f"Error selecting data: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def update_data(self, table_name, data, condition, params=None):
        """Update data in a table
        
        Args:
            table_name (str): Name of the target table
            data (dict): Dictionary of columns and values to update
            condition (str): WHERE condition
            params (tuple, optional): Parameters for the condition
        """
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
            query = f"UPDATE {table_name} SET {set_clause} WHERE {condition}"
            
            # Combine data values and condition parameters
            all_params = list(data.values())
            if params:
                all_params.extend(params)
            
            self.cursor.execute(query, all_params)
            self.conn.commit()
            rows_affected = self.cursor.rowcount
            logger.info(f"{rows_affected} row(s) updated in '{table_name}'")
            return {
                "status": "success", 
                "message": f"{rows_affected} row(s) updated in '{table_name}'",
                "rows_affected": rows_affected
            }
        except sqlite3.Error as e:
            error_msg = f"Error updating data: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def delete_data(self, table_name, condition=None, params=None):
        """Delete data from a table
        
        Args:
            table_name (str): Name of the target table
            condition (str, optional): WHERE condition
            params (tuple, optional): Parameters for the condition
        """
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            query = f"DELETE FROM {table_name}"
            
            if condition:
                query += f" WHERE {condition}"
            
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            self.conn.commit()
            rows_affected = self.cursor.rowcount
            logger.info(f"{rows_affected} row(s) deleted from '{table_name}'")
            return {
                "status": "success", 
                "message": f"{rows_affected} row(s) deleted from '{table_name}'",
                "rows_affected": rows_affected
            }
        except sqlite3.Error as e:
            error_msg = f"Error deleting data: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def get_table_schema(self, table_name):
        """Get the schema information for a specific table"""
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns = self.cursor.fetchall()
            
            # Format columns as a list of dictionaries
            formatted_columns = []
            for col in columns:
                formatted_columns.append({
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2],
                    "notnull": col[3],
                    "default_value": col[4],
                    "pk": col[5]
                })
            
            return {
                "status": "success", 
                "message": f"Retrieved schema for '{table_name}'",
                "schema": formatted_columns
            }
        except sqlite3.Error as e:
            error_msg = f"Error getting table schema: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def list_tables(self):
        """List all tables in the database"""
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = self.cursor.fetchall()
            table_list = [table[0] for table in tables]
            
            return {
                "status": "success", 
                "message": f"Found {len(table_list)} tables",
                "tables": table_list
            }
        except sqlite3.Error as e:
            error_msg = f"Error listing tables: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def drop_table(self, table_name):
        """Drop a table from the database"""
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.conn.commit()
            logger.info(f"Table '{table_name}' dropped successfully")
            return {"status": "success", "message": f"Table '{table_name}' dropped successfully"}
        except sqlite3.Error as e:
            error_msg = f"Error dropping table: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def backup_database(self, backup_dir="backups"):
        """Create a backup of the database"""
        if not self.connected:
            return {"status": "error", "message": "Not connected to database. Connect first."}
        
        try:
            # Create backup directory if it doesn't exist
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{backup_dir}/{os.path.splitext(self.db_name)[0]}_{timestamp}.sqlite"
            
            # Create backup connection
            backup_conn = sqlite3.connect(backup_filename)
            
            # Copy database content
            self.conn.backup(backup_conn)
            backup_conn.close()
            
            logger.info(f"Database backup created at {backup_filename}")
            return {
                "status": "success", 
                "message": f"Database backup created successfully",
                "backup_file": backup_filename
            }
        except sqlite3.Error as e:
            error_msg = f"Error backing up database: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    


# Create a global database manager instance
db_manager = DatabaseManager(os.environ.get('DB_NAME', 'ecommerce.sqlite'))

# Initialize database connection and tables
def initialize_app():
    db_manager.connect()
    # Initialize e-commerce tables

# Call initialization function
initialize_app()

@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to a database"""
    try:
        data = request.get_json()
        db_name = data.get('db_name') if data else None
        
        if db_name:
            global db_manager
            db_manager = DatabaseManager(db_name)
        
        result = db_manager.connect()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in connect route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from the database"""
    try:
        result = db_manager.disconnect()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in disconnect route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/execute', methods=['POST'])
def execute_query():
    """Execute a custom SQL query"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({"status": "error", "message": "Query is required"}), 400
        
        query = data['query']
        params = data.get('params')
        
        result = db_manager.execute_query(query, params)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in execute_query route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables', methods=['GET'])
def list_tables():
    """List all tables in the database"""
    try:
        result = db_manager.list_tables()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in list_tables route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables', methods=['POST'])
def create_table():
    """Create a new table"""
    try:
        data = request.get_json()
        if not data or 'table_name' not in data or 'columns' not in data:
            return jsonify({
                "status": "error", 
                "message": "Table name and columns are required"
            }), 400
        
        table_name = data['table_name']
        columns = data['columns']
        
        result = db_manager.create_table(table_name, columns)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in create_table route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables/<table_name>', methods=['DELETE'])
def drop_table(table_name):
    """Drop a table"""
    try:
        result = db_manager.drop_table(table_name)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in drop_table route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables/<table_name>/schema', methods=['GET'])
def get_table_schema(table_name):
    """Get schema for a specific table"""
    try:
        result = db_manager.get_table_schema(table_name)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_table_schema route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables/<table_name>/data', methods=['GET'])
def select_data(table_name):
    """Select data from a table"""
    try:
        columns = request.args.get('columns', '*')
        condition = request.args.get('condition')
        params_str = request.args.get('params')
        
        # Parse params if provided
        params = None
        if params_str:
            params = tuple(params_str.split(','))
        
        result = db_manager.select_data(table_name, columns, condition, params)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in select_data route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables/<table_name>/data', methods=['POST'])
def insert_data(table_name):
    """Insert data into a table"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Data is required"}), 400
        
        result = db_manager.insert_data(table_name, data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in insert_data route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables/<table_name>/data', methods=['PUT'])
def update_data(table_name):
    """Update data in a table"""
    try:
        data = request.get_json()
        if not data or 'values' not in data or 'condition' not in data:
            return jsonify({
                "status": "error", 
                "message": "Update values and condition are required"
            }), 400
        
        values = data['values']
        condition = data['condition']
        params = data.get('params')
        
        result = db_manager.update_data(table_name, values, condition, params)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_data route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tables/<table_name>/data', methods=['DELETE'])
def delete_data(table_name):
    """Delete data from a table"""
    try:
        data = request.get_json()
        condition = data.get('condition') if data else None
        params = data.get('params') if data else None
        
        result = db_manager.delete_data(table_name, condition, params)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_data route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/backup', methods=['POST'])
def backup_database():
    """Create a database backup"""
    try:
        data = request.get_json()
        backup_dir = data.get('backup_dir', 'backups') if data else 'backups'
        
        result = db_manager.backup_database(backup_dir)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in backup_database route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all products or filter by parameters"""
    try:
        category = request.args.get('category')
        seller_id = request.args.get('seller_id')
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        
        conditions = []
        params = []
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        if seller_id:
            conditions.append("seller_id = ?")
            params.append(seller_id)
        
        if min_price:
            conditions.append("price >= ?")
            params.append(float(min_price))
        
        if max_price:
            conditions.append("price <= ?")
            params.append(float(max_price))
        
        condition = " AND ".join(conditions) if conditions else None
        
        result = db_manager.select_data("products", "*", condition, tuple(params) if params else None)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def create_product():
    """Create a new product"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Product data is required"}), 400
        
        # Generate a unique product ID if not provided
        if 'product_id' not in data:
            data['product_id'] = str(uuid.uuid4())
        
        # Set timestamps if not provided
        if 'created_at' not in data:
            data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if 'updated_at' not in data:
            data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        result = db_manager.insert_data("products", data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in create_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product by ID"""
    try:
        result = db_manager.select_data("products", "*", "product_id = ?", (product_id,))
        
        if not result.get('data'):
            return jsonify({"status": "error", "message": f"Product with ID {product_id} not found"}), 404
        
        # Get reviews for this product
        reviews = db_manager.select_data("reviews", "*", "product_id = ?", (product_id,))
        
        # Add reviews to the product data
        result['data'][0]['reviews'] = reviews.get('data', [])
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product by ID"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        # Set updated timestamp
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if product exists
        check_result = db_manager.select_data("products", "product_id", "product_id = ?", (product_id,))
        if not check_result.get('data'):
            return jsonify({"status": "error", "message": f"Product with ID {product_id} not found"}), 404
        
        result = db_manager.update_data("products", data, "product_id = ?", (product_id,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product by ID"""
    try:
        # Check if product exists
        check_result = db_manager.select_data("products", "product_id", "product_id = ?", (product_id,))
        if not check_result.get('data'):
            return jsonify({"status": "error", "message": f"Product with ID {product_id} not found"}), 404
        
        # Delete related reviews first (foreign key constraint)
        db_manager.delete_data("reviews", "product_id = ?", (product_id,))
        
        # Delete related order items (foreign key constraint)
        db_manager.delete_data("order_items", "product_id = ?", (product_id,))
        
        # Delete the product
        result = db_manager.delete_data("products", "product_id = ?", (product_id,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>/reviews', methods=['GET'])
def get_product_reviews(product_id):
    """Get all reviews for a specific product"""
    try:
        result = db_manager.select_data("reviews", "*", "product_id = ?", (product_id,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product_reviews route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/products/<product_id>/reviews', methods=['POST'])
def add_product_review(product_id):
    """Add a review for a specific product"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Review data is required"}), 400
        
        # Generate a unique review ID if not provided
        if 'review_id' not in data:
            data['review_id'] = str(uuid.uuid4())
        
        # Add product_id to the review data
        data['product_id'] = product_id
        
        # Set timestamp if not provided
        if 'created_at' not in data:
            data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Validate rating
        if 'rating' not in data or not (1 <= int(data['rating']) <= 5):
            return jsonify({"status": "error", "message": "Rating must be between 1 and 5"}), 400
        
        result = db_manager.insert_data("reviews", data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in add_product_review route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Get all orders or filter by customer_id"""
    try:
        customer_id = request.args.get('customer_id')
        status = request.args.get('status')
        
        conditions = []
        params = []
        
        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        condition = " AND ".join(conditions) if conditions else None
        
        result = db_manager.select_data("orders", "*", condition, tuple(params) if params else None)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_orders route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders', methods=['POST'])
def create_order():
    """Create a new order"""
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({"status": "error", "message": "Order data with items is required"}), 400
        
        # Extract order items
        items = data.pop('items', [])
        
        # Generate a unique order ID if not provided
        if 'order_id' not in data:
            data['order_id'] = str(uuid.uuid4())
        
        order_id = data['order_id']
        
        # Set timestamps if not provided
        if 'created_at' not in data:
            data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if 'updated_at' not in data:
            data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Set default status if not provided
        if 'status' not in data:
            data['status'] = 'pending'
        
        # Begin transaction
        db_manager.conn.execute("BEGIN TRANSACTION")
        
        try:
            # Insert the order
            order_result = db_manager.insert_data("orders", data)
            
            # Insert order items
            for item in items:
                # Generate a unique item ID if not provided
                if 'item_id' not in item:
                    item['item_id'] = str(uuid.uuid4())
                
                # Add order_id to the item
                item['order_id'] = order_id
                
                # Insert the item
                db_manager.insert_data("order_items", item)
                
                # Update product stock quantity
                product_id = item['product_id']
                quantity = item['quantity']
                
                # Get current stock
                stock_result = db_manager.select_data("products", "stock_quantity", "product_id = ?", (product_id,))
                if not stock_result.get('data'):
                    raise Exception(f"Product with ID {product_id} not found")
                
                current_stock = int(stock_result['data'][0]['stock_quantity'])
                new_stock = current_stock - quantity
                
                if new_stock < 0:
                    raise Exception(f"Insufficient stock for product {product_id}")
                
                # Update stock
                db_manager.update_data("products", {"stock_quantity": new_stock}, "product_id = ?", (product_id,))
            
            # Commit transaction
            db_manager.conn.commit()
            
            # Return complete order with items
            order_with_items = {
                "status": "success",
                "message": "Order created successfully",
                "order": data,
                "items": items
            }
            
            return jsonify(order_with_items)
        
        except Exception as e:
            # Rollback transaction on error
            db_manager.conn.rollback()
            raise e
    
    except Exception as e:
        logger.error(f"Error in create_order route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get a specific order by ID with its items"""
    try:
        # Get order details
        order_result = db_manager.select_data("orders", "*", "order_id = ?", (order_id,))
        
        if not order_result.get('data'):
            return jsonify({"status": "error", "message": f"Order with ID {order_id} not found"}), 404
        
        # Get order items
        items_result = db_manager.select_data("order_items", "*", "order_id = ?", (order_id,))
        
        # Combine results
        result = {
            "status": "success",
            "message": f"Retrieved order {order_id}",
            "order": order_result['data'][0],
            "items": items_result.get('data', [])
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_order route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<order_id>', methods=['PUT'])
def update_order(order_id):
    """Update an order's status"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Update data is required"}), 400
        
        # Set updated timestamp
        data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if order exists
        check_result = db_manager.select_data("orders", "order_id", "order_id = ?", (order_id,))
        if not check_result.get('data'):
            return jsonify({"status": "error", "message": f"Order with ID {order_id} not found"}), 404
        
        result = db_manager.update_data("orders", data, "order_id = ?", (order_id,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in update_order route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sellers/<seller_id>/products', methods=['GET'])
def get_seller_products(seller_id):
    """Get all products for a specific seller"""
    try:
        result = db_manager.select_data("products", "*", "seller_id = ?", (seller_id,))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_seller_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers/<customer_id>/orders', methods=['GET'])
def get_customer_orders(customer_id):
    """Get all orders for a specific customer"""
    try:
        result = db_manager.select_data("orders", "*", "customer_id = ?", (customer_id,))
        
        # Enrich with order items
        orders = result.get('data', [])
        for order in orders:
            order_id = order['order_id']
            items_result = db_manager.select_data("order_items", "*", "order_id = ?", (order_id,))
            order['items'] = items_result.get('data', [])
        
        return jsonify({
            "status": "success",
            "message": f"Retrieved orders for customer {customer_id}",
            "data": orders
        })
    except Exception as e:
        logger.error(f"Error in get_customer_orders route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats/products', methods=['GET'])
def get_product_stats():
    """Get statistics about products"""
    try:
        # Get total number of products
        count_query = "SELECT COUNT(*) as total_products FROM products"
        count_result = db_manager.execute_query(count_query)
        
        # Get products by category
        category_query = "SELECT category, COUNT(*) as count FROM products GROUP BY category"
        category_result = db_manager.execute_query(category_query)
        
        # Get average price
        avg_price_query = "SELECT AVG(price) as avg_price FROM products"
        avg_price_result = db_manager.execute_query(avg_price_query)
        
        # Get top sellers
        top_sellers_query = """
        SELECT p.product_id, p.name, p.price, SUM(oi.quantity) as total_sold
        FROM products p
        JOIN order_items oi ON p.product_id = oi.product_id
        GROUP BY p.product_id
        ORDER BY total_sold DESC
        LIMIT 5
        """
        top_sellers_result = db_manager.execute_query(top_sellers_query)
        
        # Combine results
        result = {
            "status": "success",
            "message": "Product statistics retrieved successfully",
            "total_products": count_result['data'][0]['total_products'] if count_result.get('data') else 0,
            "by_category": category_result.get('data', []),
            "avg_price": avg_price_result['data'][0]['avg_price'] if avg_price_result.get('data') else 0,
            "top_sellers": top_sellers_result.get('data', [])
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_product_stats route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats/orders', methods=['GET'])
def get_order_stats():
    """Get statistics about orders"""
    try:
        # Get total number of orders
        count_query = "SELECT COUNT(*) as total_orders FROM orders"
        count_result = db_manager.execute_query(count_query)
        
        # Get orders by status
        status_query = "SELECT status, COUNT(*) as count FROM orders GROUP BY status"
        status_result = db_manager.execute_query(status_query)
        
        # Get average order value
        avg_value_query = "SELECT AVG(total_amount) as avg_value FROM orders"
        avg_value_result = db_manager.execute_query(avg_value_query)
        
        # Get orders by date (last 7 days)
        date_query = """
        SELECT date(created_at) as order_date, COUNT(*) as count, SUM(total_amount) as total_sales
        FROM orders
        WHERE created_at >= date('now', '-7 days')
        GROUP BY date(created_at)
        ORDER BY order_date
        """
        date_result = db_manager.execute_query(date_query)
        
        # Combine results
        result = {
            "status": "success",
            "message": "Order statistics retrieved successfully",
            "total_orders": count_result['data'][0]['total_orders'] if count_result.get('data') else 0,
            "by_status": status_result.get('data', []),
            "avg_value": avg_value_result['data'][0]['avg_value'] if avg_value_result.get('data') else 0,
            "recent_orders": date_result.get('data', [])
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_order_stats route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/search/products', methods=['GET'])
def search_products():
    """Search for products by name, description, or category"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"status": "error", "message": "Search query is required"}), 400
        
        # Search in name, description, and category
        search_query = """
        SELECT * FROM products
        WHERE name LIKE ? OR description LIKE ? OR category LIKE ?
        """
        search_params = (f"%{query}%", f"%{query}%", f"%{query}%")
        
        result = db_manager.execute_query(search_query, search_params)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in search_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        return jsonify({
            "status": "up",
            "service": "Database Management API",
            "connected": db_manager.connected,
            "db_name": db_manager.db_name if db_manager.connected else None,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health_check route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5003))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')