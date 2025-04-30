# app.py - Frontend Service
from flask import Flask, render_template, jsonify, request
import os
import logging
import requests
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)  # Enable CORS for all routes

# Service URLs from environment variables with defaults
STORAGE_SERVICE_URL = os.environ.get('STORAGE_SERVICE_URL', 'http://localhost:5005/api')
PROMOTION_SERVICE_URL = os.environ.get('PROMOTION_SERVICE_URL', 'http://localhost:5006/api')

@app.route('/')
def homepage():
    """Render the homepage"""
    return render_template('index.html')

@app.route('/api/frontend/products')
def get_products():
    """Fetch products from storage service and enrich with promotion data"""
    try:
        # Fetch all products from storage service
        storage_response = requests.get(f"{STORAGE_SERVICE_URL}/products")
        if storage_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"Error fetching products: {storage_response.text}"
            }), 500
        
        products_data = storage_response.json()
        
        # Fetch all active promotions
        promo_response = requests.get(f"{PROMOTION_SERVICE_URL}/promotions/active")
        if promo_response.status_code != 200:
            # If promotions can't be fetched, continue with just the products
            logger.warning(f"Error fetching promotions: {promo_response.text}")
            return jsonify(products_data)
        
        promotions_data = promo_response.json()
        
        # Create a map of product_id to promotion for faster lookup
        promotion_map = {}
        for promotion in promotions_data.get('data', []):
            product_id = promotion.get('product_id')
            if product_id:
                # A product might have multiple promotions, keep the best one
                if product_id in promotion_map:
                    current_price = promotion_map[product_id].get('discounted_price', float('inf'))
                    new_price = promotion.get('discounted_price', float('inf'))
                    if new_price < current_price:
                        promotion_map[product_id] = promotion
                else:
                    promotion_map[product_id] = promotion
        
        # Enrich product data with promotion information
        enriched_products = []
        for product in products_data.get('data', []):
            product_id = product.get('product_id')
            if product_id in promotion_map:
                product['promotion'] = promotion_map[product_id]
                product['has_promotion'] = True
                product['discounted_price'] = promotion_map[product_id].get('discounted_price')
            else:
                product['has_promotion'] = False
            
            enriched_products.append(product)
        
        return jsonify({
            "status": "success",
            "message": f"Retrieved {len(enriched_products)} products with promotion data",
            "data": enriched_products
        })
    
    except Exception as e:
        logger.error(f"Error in get_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/frontend/featured-products')
def get_featured_products():
    """Get a limited number of featured products for the homepage"""
    try:
        # Here we could implement logic to select featured products
        # For now, we'll just limit to a few products
        limit = request.args.get('limit', 6, type=int)
        
        # Get all products with promotion data
        response = requests.get(f"http://localhost:{app.config['PORT']}/api/frontend/products")
        if response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"Error fetching products: {response.text}"
            }), 500
        
        all_products = response.json()
        
        # Simple selection: prioritize products with promotions, then limit
        products = all_products.get('data', [])
        # Sort by having a promotion first, then by price
        products.sort(key=lambda p: (not p.get('has_promotion', False), p.get('price', float('inf'))))
        
        featured_products = products[:limit]
        
        return jsonify({
            "status": "success",
            "message": f"Retrieved {len(featured_products)} featured products",
            "data": featured_products
        })
    except Exception as e:
        logger.error(f"Error in get_featured_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/frontend/categories')
def get_categories():
    """Get product categories from storage service"""
    try:
        response = requests.get(f"{STORAGE_SERVICE_URL}/categories")
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error in get_categories route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Check health of storage service
        try:
            storage_health = requests.get(f"{STORAGE_SERVICE_URL}/health")
            storage_status = "up" if storage_health.status_code == 200 else "down"
        except:
            storage_status = "down"
        
        # Check health of promotion service
        try:
            promo_health = requests.get(f"{PROMOTION_SERVICE_URL}/health")
            promo_status = "up" if promo_health.status_code == 200 else "down"
        except:
            promo_status = "down"
        
        return jsonify({
            "status": "up",
            "storage_service": storage_status,
            "promotion_service": promo_status,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health_check route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5012))
    app.config['PORT'] = port
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')