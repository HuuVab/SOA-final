#!/usr/bin/env python3
# Homepage Service for E-commerce Microservices Project
# Serves the user-facing frontend

from flask import Flask, render_template, request, jsonify, redirect, url_for
import requests
import os
import json
from flask_cors import CORS
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Environment variables
DB_SERVICE_URL = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')
CUSTOMER_SERVICE_URL = os.environ.get('CUSTOMER_SERVICE_URL', 'http://localhost:5000')
PORT = int(os.environ.get('PORT', 5004))

# Helper function to fetch data from database service
def fetch_from_db(endpoint, params=None):
    try:
        url = f"{DB_SERVICE_URL}/{endpoint}"
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching data from DB service: {e}")
        return {"status": "error", "message": str(e)}

# Helper function to fetch user data from customer service
def fetch_user_data(user_id, token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{CUSTOMER_SERVICE_URL}/api/users/{user_id}"
        response = requests.get(url, headers=headers)
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching user data: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/')
def home():
    """Render the homepage with featured products and categories"""
    try:
        # Fetch featured products from database service
        featured_products = fetch_from_db('products', {'featured': 'true'})
        
        # Fetch product categories
        categories_query = "SELECT DISTINCT category FROM products"
        categories_result = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": categories_query}
        ).json()
        
        # Get promotional banners (could be from a CMS or hardcoded for now)
        banners = [
            {"image": "banner1.jpg", "link": "/promotions/summer", "title": "Summer Sale"},
            {"image": "banner2.jpg", "link": "/new-arrivals", "title": "New Arrivals"}
        ]
        
        return render_template(
            'home.html',
            products=featured_products.get('data', []),
            categories=categories_result.get('data', []),
            banners=banners
        )
    except Exception as e:
        logger.error(f"Error rendering homepage: {e}")
        return render_template('error.html', message="Unable to load homepage content")

@app.route('/products')
def products():
    """Show all products or filtered by category"""
    try:
        category = request.args.get('category')
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        
        # Prepare filter parameters
        params = {}
        if category:
            params['category'] = category
        if min_price:
            params['min_price'] = min_price
        if max_price:
            params['max_price'] = max_price
            
        # Fetch products with filters
        products_result = fetch_from_db('products', params)
        
        # Fetch all categories for sidebar
        categories_query = "SELECT category, COUNT(*) as count FROM products GROUP BY category"
        categories_result = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": categories_query}
        ).json()
        
        return render_template(
            'products.html',
            products=products_result.get('data', []),
            categories=categories_result.get('data', []),
            current_category=category,
            min_price=min_price,
            max_price=max_price
        )
    except Exception as e:
        logger.error(f"Error rendering products page: {e}")
        return render_template('error.html', message="Unable to load products")

@app.route('/product/<product_id>')
def product_detail(product_id):
    """Show details for a specific product"""
    try:
        # Fetch product details
        product_result = fetch_from_db(f'products/{product_id}')
        
        if product_result.get('status') == 'error':
            return render_template('error.html', message="Product not found")
        
        # Fetch related products in same category
        product = product_result.get('data')[0]
        related_params = {'category': product.get('category'), 'exclude': product_id}
        related_products = fetch_from_db('products', related_params)
        
        return render_template(
            'product_detail.html',
            product=product,
            related_products=related_products.get('data', [])[:4]  # Show up to 4 related products
        )
    except Exception as e:
        logger.error(f"Error rendering product detail page: {e}")
        return render_template('error.html', message="Unable to load product details")

@app.route('/cart')
def shopping_cart():
    """Show the shopping cart"""
    # This would typically interact with a cart service or use client-side storage
    return render_template('cart.html')

@app.route('/checkout')
def checkout():
    """Show checkout process"""
    # This would require authentication and integration with an order service
    return render_template('checkout.html')

@app.route('/search')
def search():
    """Search for products"""
    try:
        query = request.args.get('q', '')
        if not query:
            return redirect(url_for('products'))
        
        # Search for products containing the query
        search_result = fetch_from_db('search/products', {'q': query})
        
        return render_template(
            'search_results.html',
            products=search_result.get('data', []),
            query=query
        )
    except Exception as e:
        logger.error(f"Error in search: {e}")
        return render_template('error.html', message="Unable to perform search")

@app.route('/account')
def account():
    """User account area - requires authentication"""
    # This would need authentication middleware and integration with customer service
    return render_template('account.html')

@app.route('/api/featured-products')
def api_featured_products():
    """API endpoint to get featured products (for AJAX updates)"""
    try:
        featured_products = fetch_from_db('products', {'featured': 'true'})
        return jsonify(featured_products)
    except Exception as e:
        logger.error(f"Error in API featured products: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/categories')
def api_categories():
    """API endpoint to get all categories (for AJAX updates)"""
    try:
        categories_query = "SELECT DISTINCT category FROM products"
        categories_result = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": categories_query}
        ).json()
        return jsonify(categories_result)
    except Exception as e:
        logger.error(f"Error in API categories: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Check if we can connect to dependent services
        db_health = requests.get(f"{DB_SERVICE_URL}/health").json()
        
        return jsonify({
            "status": "up",
            "service": "Homepage Service",
            "dependencies": {
                "database_service": db_health.get('status')
            },
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "warning",
            "service": "Homepage Service",
            "message": "One or more dependencies unavailable",
            "error": str(e),
            "version": "1.0.0"
        }), 200  # Still return 200 for health checks

# Main entry point
if __name__ == '__main__':
    # Run the Flask app
    logger.info(f"Starting Homepage Service on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')