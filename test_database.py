#!/usr/bin/env python3
# Simple Database Management System using SQLite

import sqlite3
import os
import sys
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name=None):
        """Initialize the database manager with an optional database name"""
        if db_name is None:
            self.db_name = "simple_db.sqlite"
        else:
            self.db_name = db_name if db_name.endswith('.sqlite') else f"{db_name}.sqlite"
        
        self.conn = None
        self.cursor = None
        self.connected = False

    def connect(self):
        """Connect to the database"""
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            self.connected = True
            print(f"Connected to {self.db_name} successfully")
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
    
    def disconnect(self):
        """Close the database connection"""
        if self.connected:
            self.conn.close()
            self.connected = False
            print("Disconnected from database")
    
    def execute_query(self, query, params=None):
        """Execute a query and return results if any"""
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return None
        
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # If the query might return results (SELECT)
            if query.strip().upper().startswith("SELECT"):
                return self.cursor.fetchall()
            else:
                self.conn.commit()
                return self.cursor.rowcount
        except sqlite3.Error as e:
            print(f"Error executing query: {e}")
            return None
    
    def create_table(self, table_name, columns):
        """Create a new table with specified columns
        
        Args:
            table_name (str): Name of the table to create
            columns (dict): Dictionary of column names and their data types/constraints
                Example: {"id": "INTEGER PRIMARY KEY", "name": "TEXT NOT NULL"}
        """
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return False
        
        try:
            # Construct the CREATE TABLE query
            col_defs = [f"{col_name} {col_def}" for col_name, col_def in columns.items()]
            col_defs_str = ", ".join(col_defs)
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs_str})"
            
            # Execute the query
            self.cursor.execute(query)
            self.conn.commit()
            print(f"Table '{table_name}' created successfully")
            return True
        except sqlite3.Error as e:
            print(f"Error creating table: {e}")
            return False
    
    def insert_data(self, table_name, data):
        """Insert data into a table
        
        Args:
            table_name (str): Name of the target table
            data (dict): Dictionary of column names and values to insert
        """
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return False
        
        try:
            columns = list(data.keys())
            values = list(data.values())
            placeholders = ", ".join(["?"] * len(columns))
            
            query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            self.cursor.execute(query, values)
            self.conn.commit()
            print(f"Data inserted into '{table_name}' successfully")
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data: {e}")
            return False
    
    def select_data(self, table_name, columns="*", condition=None, params=None):
        """Select data from a table
        
        Args:
            table_name (str): Name of the target table
            columns (str): Columns to select, default is "*" (all)
            condition (str, optional): WHERE condition
            params (tuple, optional): Parameters for the condition
        """
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return None
        
        try:
            query = f"SELECT {columns} FROM {table_name}"
            
            if condition:
                query += f" WHERE {condition}"
            
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error selecting data: {e}")
            return None
    
    def update_data(self, table_name, data, condition, params=None):
        """Update data in a table
        
        Args:
            table_name (str): Name of the target table
            data (dict): Dictionary of columns and values to update
            condition (str): WHERE condition
            params (tuple, optional): Parameters for the condition
        """
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return False
        
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
            print(f"{rows_affected} row(s) updated in '{table_name}'")
            return True
        except sqlite3.Error as e:
            print(f"Error updating data: {e}")
            return False
    
    def delete_data(self, table_name, condition=None, params=None):
        """Delete data from a table
        
        Args:
            table_name (str): Name of the target table
            condition (str, optional): WHERE condition
            params (tuple, optional): Parameters for the condition
        """
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return False
        
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
            print(f"{rows_affected} row(s) deleted from '{table_name}'")
            return True
        except sqlite3.Error as e:
            print(f"Error deleting data: {e}")
            return False
    
    def get_table_schema(self, table_name):
        """Get the schema information for a specific table"""
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return None
        
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting table schema: {e}")
            return None
    
    def list_tables(self):
        """List all tables in the database"""
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return None
        
        try:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = self.cursor.fetchall()
            return [table[0] for table in tables]
        except sqlite3.Error as e:
            print(f"Error listing tables: {e}")
            return None
    
    def drop_table(self, table_name):
        """Drop a table from the database"""
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return False
        
        try:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.conn.commit()
            print(f"Table '{table_name}' dropped successfully")
            return True
        except sqlite3.Error as e:
            print(f"Error dropping table: {e}")
            return False
    
    def backup_database(self, backup_dir="backups"):
        """Create a backup of the database"""
        if not self.connected:
            print("Not connected to database. Use connect() first.")
            return False
        
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
            
            print(f"Database backup created at {backup_filename}")
            return True
        except sqlite3.Error as e:
            print(f"Error backing up database: {e}")
            return False


def display_menu():
    """Display the main menu options"""
    print("\n===== Simple Database Management System =====")
    print("1. Connect to database")
    print("2. Create a new table")
    print("3. List all tables")
    print("4. View table schema")
    print("5. Insert data")
    print("6. Query data")
    print("7. Update data")
    print("8. Delete data")
    print("9. Drop table")
    print("10. Backup database")
    print("11. Execute custom SQL")
    print("12. Disconnect")
    print("0. Exit")
    print("===========================================")
    

def main():
    db_manager = DatabaseManager()
    
    while True:
        display_menu()
        choice = input("Enter your choice (0-12): ")
        
        if choice == "0":
            if db_manager.connected:
                db_manager.disconnect()
            print("Exiting program. Goodbye!")
            sys.exit(0)
        
        elif choice == "1":
            db_name = input("Enter database name (or press Enter for default 'simple_db'): ")
            if db_name:
                db_manager = DatabaseManager(db_name)
            db_manager.connect()
        
        elif choice == "2":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            table_name = input("Enter table name: ")
            columns = {}
            print("Enter column definitions (name and type, e.g., 'id INTEGER PRIMARY KEY')")
            print("Enter an empty name when done")
            
            while True:
                col_name = input("Column name (empty to finish): ").strip()
                if not col_name:
                    break
                col_type = input(f"Type for {col_name}: ").strip()
                columns[col_name] = col_type
            
            db_manager.create_table(table_name, columns)
        
        elif choice == "3":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if tables:
                print("\nTables in the database:")
                for i, table in enumerate(tables, 1):
                    print(f"{i}. {table}")
            else:
                print("No tables found in the database")
        
        elif choice == "4":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if not tables:
                print("No tables found in the database")
                continue
                
            print("\nTables in the database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            table_idx = int(input("Enter table number to view schema: ")) - 1
            if 0 <= table_idx < len(tables):
                schema = db_manager.get_table_schema(tables[table_idx])
                if schema:
                    print(f"\nSchema for table '{tables[table_idx]}':")
                    print("ID | Name | Type | NotNull | DefaultValue | PrimaryKey")
                    print("-" * 60)
                    for col in schema:
                        print(f"{col[0]} | {col[1]} | {col[2]} | {col[3]} | {col[4] if col[4] is not None else 'NULL'} | {col[5]}")
            else:
                print("Invalid table number")
        
        elif choice == "5":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if not tables:
                print("No tables found in the database")
                continue
                
            print("\nTables in the database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            table_idx = int(input("Enter table number to insert data: ")) - 1
            if 0 <= table_idx < len(tables):
                table_name = tables[table_idx]
                schema = db_manager.get_table_schema(table_name)
                
                data = {}
                print(f"\nEnter data for table '{table_name}':")
                for col in schema:
                    col_name = col[1]
                    col_type = col[2]
                    is_primary_key = col[5] == 1
                    
                    # Skip autoincrement primary keys
                    if is_primary_key and col_type.upper() == "INTEGER":
                        continue
                    
                    value = input(f"{col_name} ({col_type}): ")
                    
                    # Handle empty inputs for NOT NULL constraints
                    if col[3] == 1 and not value and not is_primary_key:
                        print(f"Column '{col_name}' cannot be NULL. Please provide a value.")
                        value = input(f"{col_name} ({col_type}): ")
                    
                    if value:  # Skip empty values
                        data[col_name] = value
                
                db_manager.insert_data(table_name, data)
            else:
                print("Invalid table number")
        
        elif choice == "6":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if not tables:
                print("No tables found in the database")
                continue
                
            print("\nTables in the database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            table_idx = int(input("Enter table number to query data: ")) - 1
            if 0 <= table_idx < len(tables):
                table_name = tables[table_idx]
                
                # Get columns from schema
                schema = db_manager.get_table_schema(table_name)
                print("\nAvailable columns:")
                for col in schema:
                    print(f"- {col[1]} ({col[2]})")
                
                columns = input("Enter columns to select (comma-separated, or * for all): ").strip()
                if not columns:
                    columns = "*"
                
                condition = input("Enter WHERE condition (optional): ").strip()
                
                if condition:
                    params_str = input("Enter parameters for condition (comma-separated, optional): ").strip()
                    params = tuple(params_str.split(",")) if params_str else None
                else:
                    params = None
                
                results = db_manager.select_data(table_name, columns, condition, params)
                
                if results:
                    # Get column names for display
                    if columns == "*":
                        col_names = [col[1] for col in schema]
                    else:
                        col_names = [col.strip() for col in columns.split(",")]
                    
                    # Print header
                    print("\nQuery Results:")
                    print(" | ".join(col_names))
                    print("-" * (sum(len(name) for name in col_names) + 3 * (len(col_names) - 1)))
                    
                    # Print data rows
                    for row in results:
                        print(" | ".join(str(item) for item in row))
                    
                    print(f"\nTotal: {len(results)} row(s)")
                else:
                    print("No results found or query error occurred")
            else:
                print("Invalid table number")
        
        elif choice == "7":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if not tables:
                print("No tables found in the database")
                continue
                
            print("\nTables in the database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            table_idx = int(input("Enter table number to update data: ")) - 1
            if 0 <= table_idx < len(tables):
                table_name = tables[table_idx]
                schema = db_manager.get_table_schema(table_name)
                
                # Show current data
                print(f"\nCurrent data in '{table_name}':")
                results = db_manager.select_data(table_name)
                if not results:
                    print("No data to update")
                    continue
                
                col_names = [col[1] for col in schema]
                print(" | ".join(col_names))
                print("-" * (sum(len(name) for name in col_names) + 3 * (len(col_names) - 1)))
                for row in results:
                    print(" | ".join(str(item) for item in row))
                
                # Get update condition
                condition = input("\nEnter WHERE condition for update: ")
                if not condition:
                    print("Update cancelled: WHERE condition is required")
                    continue
                
                params_str = input("Enter parameters for condition (comma-separated, optional): ").strip()
                params = tuple(params_str.split(",")) if params_str else None
                
                # Get columns to update
                data = {}
                print("\nEnter new values (leave empty to keep current value):")
                for col in schema:
                    col_name = col[1]
                    is_primary_key = col[5] == 1
                    
                    # Skip primary keys
                    if is_primary_key:
                        continue
                    
                    value = input(f"New value for {col_name}: ").strip()
                    if value:  # Only update non-empty values
                        data[col_name] = value
                
                if data:
                    db_manager.update_data(table_name, data, condition, params)
                else:
                    print("Update cancelled: No columns to update")
            else:
                print("Invalid table number")
        
        elif choice == "8":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if not tables:
                print("No tables found in the database")
                continue
                
            print("\nTables in the database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            table_idx = int(input("Enter table number to delete data from: ")) - 1
            if 0 <= table_idx < len(tables):
                table_name = tables[table_idx]
                
                # Show current data
                print(f"\nCurrent data in '{table_name}':")
                results = db_manager.select_data(table_name)
                if not results:
                    print("No data to delete")
                    continue
                
                schema = db_manager.get_table_schema(table_name)
                col_names = [col[1] for col in schema]
                print(" | ".join(col_names))
                print("-" * (sum(len(name) for name in col_names) + 3 * (len(col_names) - 1)))
                for row in results:
                    print(" | ".join(str(item) for item in row))
                
                delete_all = input("\nDelete all records? (y/n): ").lower() == 'y'
                
                if delete_all:
                    confirm = input("Are you sure you want to delete ALL records? This cannot be undone. (y/n): ").lower()
                    if confirm == 'y':
                        db_manager.delete_data(table_name)
                    else:
                        print("Delete operation cancelled")
                else:
                    condition = input("Enter WHERE condition for delete: ")
                    if not condition:
                        print("Delete cancelled: WHERE condition is required for safety")
                        continue
                    
                    params_str = input("Enter parameters for condition (comma-separated, optional): ").strip()
                    params = tuple(params_str.split(",")) if params_str else None
                    
                    confirm = input("Are you sure you want to delete these records? This cannot be undone. (y/n): ").lower()
                    if confirm == 'y':
                        db_manager.delete_data(table_name, condition, params)
                    else:
                        print("Delete operation cancelled")
            else:
                print("Invalid table number")
        
        elif choice == "9":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            tables = db_manager.list_tables()
            if not tables:
                print("No tables found in the database")
                continue
                
            print("\nTables in the database:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table}")
            
            table_idx = int(input("Enter table number to drop: ")) - 1
            if 0 <= table_idx < len(tables):
                table_name = tables[table_idx]
                confirm = input(f"Are you sure you want to drop table '{table_name}'? This cannot be undone. (y/n): ").lower()
                if confirm == 'y':
                    db_manager.drop_table(table_name)
                else:
                    print("Drop operation cancelled")
            else:
                print("Invalid table number")
        
        elif choice == "10":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            backup_dir = input("Enter backup directory (or press Enter for default 'backups'): ").strip()
            if not backup_dir:
                backup_dir = "backups"
            
            db_manager.backup_database(backup_dir)
        
        elif choice == "11":
            if not db_manager.connected:
                print("Please connect to a database first (Option 1)")
                continue
                
            print("\nEnter custom SQL query (be careful with this!):")
            sql = input("> ")
            
            if not sql:
                print("Query cancelled")
                continue
            
            # Check if it's a SELECT query
            is_select = sql.strip().upper().startswith("SELECT")
            
            # Execute the query
            result = db_manager.execute_query(sql)
            
            # Display results if it's a SELECT query
            if is_select and result:
                print("\nQuery Results:")
                for row in result:
                    print(row)
                print(f"\nTotal: {len(result)} row(s)")
        
        elif choice == "12":
            if db_manager.connected:
                db_manager.disconnect()
            else:
                print("Not currently connected to a database")
        
        else:
            print("Invalid choice. Please try again.")
        
        # Pause before showing menu again
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()