from flask import Flask, render_template, jsonify, request
import os
import logging
import requests
from flask_cors import CORS
from flask import send_file
import io
from PIL import Image, ImageDraw, ImageFont
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
# In Docker, use service names instead of localhost
STORAGE_SERVICE_URL = os.environ.get('STORAGE_SERVICE_URL', 'http://ecommerce-storage-service:5005/api')
PROMOTION_SERVICE_URL = os.environ.get('PROMOTION_SERVICE_URL', 'http://ecommerce-promotion-service:5006/api')
CUSTOMER_SERVICE_URL = os.environ.get('CUSTOMER_SERVICE_URL', 'http://ecommerce-customer-service:5000/api')
CART_SERVICE_URL = os.environ.get('CART_SERVICE_URL', 'http://ecommerce-cart-service:5008/api')
PAYMENT_SERVICE_URL = os.environ.get('PAYMENT_SERVICE_URL', 'http://ecommerce-payment-service:5009/api')
ORDER_SERVICE_URL = os.environ.get('ORDER_SERVICE_URL', 'http://ecommerce-order-service:5010/api')
MEDIA_SERVICE_URL = os.environ.get('MEDIA_SERVICE_URL', 'http://media-service:5007/api')

@app.route('/')
def homepage():
    """Render the homepage"""
    return render_template('index.html')
    
@app.route('/login')
def login_page():
    """Render the login page"""
    return render_template('login.html')

@app.route('/account')
def account_page():
    """Render the account page"""
    return render_template('account.html')
    
@app.route('/verify-email')
def verify_email_page():
    """Render the email verification page"""
    return render_template('verify-email.html')
    
@app.route('/products')
def products_page():
    """Render the products page"""
    return render_template('products.html')
    
@app.route('/cart')
def cart_page():
    """Render the shopping cart page"""
    return render_template('cart.html')
    
@app.route('/checkout')
def checkout_page():
    """Render the checkout page"""
    return render_template('checkout.html')
    
@app.route('/orders')
def orders_page():
    """Render the orders history page"""
    return render_template('orders.html')
    
@app.route('/orders/<order_id>')
def order_detail_page(order_id):
    """Render the order detail page"""
    return render_template('order-detail.html', order_id=order_id)

@app.route('/api/storage/serve/<path:filepath>', methods=['GET'])
def proxy_storage_file(filepath):
    """Proxy image requests to the storage service"""
    try:
        proxy_url = f"{STORAGE_SERVICE_URL}/storage/serve/{filepath}"
        logger.info(f"Proxying request to: {proxy_url}")
        
        response = requests.get(proxy_url, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Storage service returned status code {response.status_code}: {response.text}")
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        # Return the image with the correct content type
        return response.content, 200, {'Content-Type': response.headers.get('Content-Type', 'application/octet-stream')}
    except Exception as e:
        logger.error(f"Error proxying storage file {filepath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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

@app.route('/api/frontend/product-images/<product_id>', methods=['GET'])
def get_frontend_product_images(product_id):
    """Get images for a specific product for the frontend"""
    try:
        result = product_storage.get_product_images(product_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_frontend_product_images route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Customer API Proxy Routes
@app.route('/api/customers/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_customer_api(subpath):
    """Proxy requests to the customer service"""
    try:
        # Build the target URL
        target_url = f"{CUSTOMER_SERVICE_URL}/customers/{subpath}"
        logger.info(f"Proxying request to customer service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the customer service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to customer service {subpath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/customers', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_customer_root_api():
    """Proxy requests to the customer service root endpoint"""
    try:
        # Build the target URL
        target_url = f"{CUSTOMER_SERVICE_URL}/customers"
        logger.info(f"Proxying request to customer service root: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the customer service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to customer service root: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/search')
def search_page():
    """Render the search results page"""
    query = request.args.get('q', '')
    return render_template('search-results.html', query=query)

@app.route('/api/frontend/search')
def frontend_search():
    """Search for products and enrich with promotion data"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({
                "status": "error", 
                "message": "Search query is required"
            }), 400
        
        # Forward the search request to the storage service
        storage_response = requests.get(f"{STORAGE_SERVICE_URL}/products/search", 
                                       params={"q": query})
        
        if storage_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"Error searching products: {storage_response.text}"
            }), 500
        
        products_data = storage_response.json()
        
        # Fetch all active promotions to enrich product data
        promo_response = requests.get(f"{PROMOTION_SERVICE_URL}/promotions/active")
        
        # Create a map of product_id to promotion
        promotion_map = {}
        if promo_response.status_code == 200:
            promotions_data = promo_response.json()
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
            "message": f"Found {len(enriched_products)} products matching '{query}'",
            "data": enriched_products
        })
    
    except Exception as e:
        logger.error(f"Error in frontend_search route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Cart API Proxy Routes
@app.route('/api/cart', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_cart_root_api():
    """Proxy requests to the cart service root endpoint"""
    try:
        # Build the target URL
        target_url = f"{CART_SERVICE_URL}/cart"
        logger.info(f"Proxying request to cart service root: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the cart service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to cart service root: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cart/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_cart_api(subpath):
    """Proxy requests to the cart service"""
    try:
        # Build the target URL
        target_url = f"{CART_SERVICE_URL}/cart/{subpath}"
        logger.info(f"Proxying request to cart service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the cart service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to cart service {subpath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Payment API Proxy Routes
@app.route('/api/payment-methods', methods=['GET', 'POST'])
def proxy_payment_methods_root_api():
    """Proxy requests to the payment methods root endpoint"""
    try:
        # Build the target URL
        target_url = f"{PAYMENT_SERVICE_URL}/payment-methods"
        logger.info(f"Proxying request to payment service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the payment service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to payment methods service: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/payment-methods/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_payment_methods_api(subpath):
    """Proxy requests to the payment methods service"""
    try:
        # Build the target URL
        target_url = f"{PAYMENT_SERVICE_URL}/payment-methods/{subpath}"
        logger.info(f"Proxying request to payment methods service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the payment service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to payment methods service {subpath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses', methods=['GET', 'POST'])
def proxy_addresses_root_api():
    """Proxy requests to the addresses root endpoint"""
    try:
        # Build the target URL
        target_url = f"{PAYMENT_SERVICE_URL}/addresses"
        logger.info(f"Proxying request to addresses service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the payment service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to addresses service: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/addresses/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_addresses_api(subpath):
    """Proxy requests to the addresses service"""
    try:
        # Build the target URL
        target_url = f"{PAYMENT_SERVICE_URL}/addresses/{subpath}"
        logger.info(f"Proxying request to addresses service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the payment service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to addresses service {subpath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/checkout', methods=['POST'])
def proxy_checkout_api():
    """Proxy requests to the checkout endpoint"""
    try:
        # Build the target URL
        target_url = f"{PAYMENT_SERVICE_URL}/checkout"
        logger.info(f"Proxying request to checkout service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the payment service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to checkout service: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Order API Proxy Routes
@app.route('/api/orders', methods=['GET', 'POST'])
def proxy_orders_root_api():
    """Proxy requests to the orders root endpoint"""
    try:
        # Build the target URL
        target_url = f"{ORDER_SERVICE_URL}/orders"
        logger.info(f"Proxying request to orders service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the order service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to orders service: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_orders_api(subpath):
    """Proxy requests to the orders service"""
    try:
        # Build the target URL
        target_url = f"{ORDER_SERVICE_URL}/orders/{subpath}"
        logger.info(f"Proxying request to orders service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the order service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to orders service {subpath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500# app.py - Frontend Service

# Media Service Proxy Routes
@app.route('/api/media/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_media_api(subpath):
    """Proxy requests to the media service"""
    try:
        # Build the target URL
        target_url = f"{MEDIA_SERVICE_URL}/{subpath}"
        logger.info(f"Proxying request to media service: {target_url}")
        
        # Forward the request with its headers, params, and body
        headers = {key: value for key, value in request.headers if key != 'Host'}
        data = request.get_data()
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=data,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Forward the response from the media service
        response_headers = {key: value for key, value in response.headers.items()
                            if key.lower() not in ('transfer-encoding', 'content-encoding', 'content-length')}
        
        return response.content, response.status_code, response_headers
        
    except Exception as e:
        logger.error(f"Error proxying to media service {subpath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Media frontend API endpoints
@app.route('/api/frontend/featured-articles', methods=['GET'])
def get_featured_articles():
    """Get featured articles for the homepage"""
    try:
        limit = request.args.get('limit', 3, type=int)
        
        # Get featured published articles from media service
        response = requests.get(f"{MEDIA_SERVICE_URL}/articles/featured", 
                                params={"limit": limit})
        
        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"Error fetching featured articles: {response.text}"
            }), 500
        
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error in get_featured_articles route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/frontend/latest-news', methods=['GET'])
def get_latest_news():
    """Get latest news for the homepage"""
    try:
        limit = request.args.get('limit', 3, type=int)
        
        # Get latest news articles from media service
        response = requests.get(f"{MEDIA_SERVICE_URL}/articles", 
                                params={"type": "news", "status": "published", "limit": limit})
        
        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"Error fetching latest news: {response.text}"
            }), 500
        
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error in get_latest_news route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/media/serve/<path:filepath>', methods=['GET'])
def proxy_media_file(filepath):
    """Proxy media file requests to the media service"""
    try:
        # Build the target URL
        target_url = f"{MEDIA_SERVICE_URL}/media/serve/{filepath}"
        logger.info(f"Proxying media file request to: {target_url}")
        
        response = requests.get(target_url, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Media service returned status code {response.status_code}: {response.text}")
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        # Return the file with the correct content type
        return response.content, 200, {'Content-Type': response.headers.get('Content-Type', 'application/octet-stream')}
    except Exception as e:
        logger.error(f"Error proxying media file {filepath}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/news')
def news_page():
    """Render the news page"""
    return render_template('news.html')

@app.route('/articles')
def articles_page():
    """Render the articles page"""
    return render_template('articles.html')

@app.route('/articles/<article_id>')
def article_detail_page(article_id):
    """Render the article detail page"""
    return render_template('article-detail.html', article_id=article_id)

# Update health check to include media service
@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # [Existing health checks]
        
        # Check health of media service
        try:
            media_health = requests.get(f"{MEDIA_SERVICE_URL}/health")
            media_status = "up" if media_health.status_code == 200 else "down"
        except:
            media_status = "down"
        
        return jsonify({
            "status": "up",
            "storage_service": storage_status,
            "promotion_service": promo_status,
            "customer_service": customer_status,
            "cart_service": cart_status,
            "payment_service": payment_status,
            "order_service": order_status,
            "media_service": media_status,
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error in health_check route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Add these routes to app.py if they don't already exist
# Add these routes to app.py after the existing product-related routes

# Add this route to app.py to handle product detail API requests

@app.route('/product/<product_id>')
def product_detail_page(product_id):
    """Render the product detail page"""
    return render_template('product-detail.html', product_id=product_id)

@app.route('/api/frontend/product/<product_id>')
def get_frontend_product(product_id):
    """Get detailed product information with images, manufacturer, and promotions for frontend"""
    try:
        logger.info(f"Fetching product data for ID: {product_id}")
        
        # Fetch product from storage service
        storage_response = requests.get(f"{STORAGE_SERVICE_URL}/products/{product_id}")
        if storage_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"Product not found: {product_id}"
            }), 404
        
        product_data = storage_response.json()
        product = product_data.get('data', {})
        
        # Set has_promotion to false by default
        product['has_promotion'] = False
        
        # Fetch all active promotions to find one for this product
        promo_response = requests.get(f"{PROMOTION_SERVICE_URL}/promotions/active")
        
        # If promotion exists for this product, add it to the response
        if promo_response.status_code == 200:
            promotions_data = promo_response.json()
            
            for promotion in promotions_data.get('data', []):
                if promotion.get('product_id') == product_id:
                    # Found a promotion for this product
                    product['promotion'] = promotion
                    product['has_promotion'] = True
                    product['discounted_price'] = promotion.get('discounted_price')
                    break
        
        # Double-check: if product has discounted_price but has_promotion isn't set, fix it
        if 'discounted_price' in product and product.get('price') and product['discounted_price'] < product['price']:
            product['has_promotion'] = True
            logger.info(f"Fixed has_promotion flag for product {product_id} based on price difference")
        
        # Ensure manufacturer field is included in the response
        if 'manufacturer' not in product:
            logger.warning(f"Product {product_id} does not have manufacturer information")
            product['manufacturer'] = None
        
        return jsonify({
            "status": "success",
            "message": f"Retrieved product {product_id}",
            "data": product
        })
    
    except Exception as e:
        logger.error(f"Error in get_frontend_product route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/frontend/related-products')
def get_related_products():
    """Get related products based on category"""
    try:
        category = request.args.get('category')
        product_id = request.args.get('product_id')  # Current product ID to exclude
        limit = request.args.get('limit', 4, type=int)
        
        if not category:
            return jsonify({
                "status": "error", 
                "message": "Category parameter is required"
            }), 400
        
        # Fetch products from the same category
        storage_response = requests.get(f"{STORAGE_SERVICE_URL}/products", 
                                      params={"category": category})
        
        if storage_response.status_code != 200:
            return jsonify({
                "status": "error", 
                "message": f"Error fetching related products: {storage_response.text}"
            }), 500
        
        products_data = storage_response.json()
        products = products_data.get('data', [])
        
        # Filter out the current product
        if product_id:
            products = [p for p in products if str(p.get('product_id')) != str(product_id)]
        
        # Limit the number of products
        products = products[:limit]
        
        # Fetch promotions to enrich product data
        promo_response = requests.get(f"{PROMOTION_SERVICE_URL}/promotions/active")
        
        promotion_map = {}
        if promo_response.status_code == 200:
            promotions_data = promo_response.json()
            for promotion in promotions_data.get('data', []):
                p_id = promotion.get('product_id')
                if p_id:
                    # Keep the best promotion (lowest price)
                    if p_id in promotion_map:
                        current_price = promotion_map[p_id].get('discounted_price', float('inf'))
                        new_price = promotion.get('discounted_price', float('inf'))
                        if new_price < current_price:
                            promotion_map[p_id] = promotion
                    else:
                        promotion_map[p_id] = promotion
        
        # Enrich products with promotion information
        for product in products:
            p_id = product.get('product_id')
            if p_id in promotion_map:
                product['promotion'] = promotion_map[p_id]
                product['has_promotion'] = True
                product['discounted_price'] = promotion_map[p_id].get('discounted_price')
            else:
                product['has_promotion'] = False
        
        return jsonify({
            "status": "success",
            "message": f"Retrieved {len(products)} related products",
            "data": products
        })
    
    except Exception as e:
        logger.error(f"Error in get_related_products route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Add this to your app.py

@app.route('/api/placeholder/<width>/<height>')
def placeholder_image(width, height):
    """Generate a simple placeholder image of the specified dimensions"""
    try:
        width = int(width)
        height = int(height)
        text = request.args.get('text', f"{width} x {height}")
        
        # Generate a simple SVG placeholder - doesn't require PIL
        svg = f'''
        <svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="100%" height="100%" fill="#f0f0f0"/>
            <text x="50%" y="50%" font-family="Arial" font-size="14" fill="#888888"
                  text-anchor="middle" dominant-baseline="middle">
                {text}
            </text>
        </svg>
        '''
        
        return svg, 200, {'Content-Type': 'image/svg+xml'}
    except Exception as e:
        logger.error(f"Error generating placeholder: {str(e)}")
        return "Error generating placeholder", 500

# Add this to your app.py to ensure the test images are created

from PIL import Image, ImageDraw, ImageFont
import os

def create_test_images():
    """Create test product images if they don't exist"""
    try:
        # Create static/images directory if it doesn't exist
        os.makedirs('static/images', exist_ok=True)
        
        # Define test images
        test_images = [
            ('test1.jpg', 'Test 1'),
            ('test2.jpg', 'Test 2'),
            ('test3.jpg', 'Test 3')
        ]
        
        # Create each test image if it doesn't exist
        for filename, text in test_images:
            filepath = os.path.join('static/images', filename)
            
            if not os.path.exists(filepath):
                # Create a new image
                img = Image.new('RGB', (400, 400), color=(240, 240, 240))
                draw = ImageDraw.Draw(img)
                
                # Try to draw text
                try:
                    # Try to load a font, use default if not available
                    try:
                        font = ImageFont.truetype("arial.ttf", 40)
                    except:
                        font = ImageFont.load_default()
                    
                    # Draw text in center
                    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:4]
                    position = ((400 - text_width) // 2, (400 - text_height) // 2)
                    draw.text(position, text, fill=(0, 0, 0), font=font)
                    
                    # Draw border
                    draw.rectangle([0, 0, 399, 399], outline=(200, 200, 200))
                except Exception as e:
                    logger.warning(f"Error drawing text on test image: {e}")
                
                # Save the image
                img.save(filepath, 'JPEG')
                logger.info(f"Created test image: {filepath}")
    except Exception as e:
        logger.error(f"Error creating test images: {e}")

# Call this function when the app starts
create_test_images()

# Also update the storage serve route to handle test images
@app.route('/api/storage/serve/<path:filepath>')
def serve_storage_file(filepath):
    """Proxy image requests to the storage service or serve test images"""
    try:
        # Special handling for test images
        if filepath in ['test1.jpg', 'test2.jpg', 'test3.jpg']:
            # Try to serve from static folder
            try:
                return send_from_directory('static/images', filepath)
            except Exception as e:
                logger.warning(f"Error serving test image from static: {e}")
                # Fallback to placeholder
                return redirect(f"/api/placeholder/400/400?text={filepath}")
        
        # For other files, proxy to storage service
        proxy_url = f"{STORAGE_SERVICE_URL}/storage/serve/{filepath}"
        logger.info(f"Proxying request to: {proxy_url}")
        
        response = requests.get(proxy_url, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Storage service returned status code {response.status_code}: {response.text}")
            return redirect(f"/api/placeholder/400/400?text=Not+Found"), 302
            
        # Return the image with the correct content type
        return response.content, 200, {'Content-Type': response.headers.get('Content-Type', 'application/octet-stream')}
    except Exception as e:
        logger.error(f"Error serving storage file {filepath}: {e}")
        return redirect(f"/api/placeholder/400/400?text=Error"), 302

@app.route('/test-images/<filename>')
def test_image(filename):
    """Serve test images directly from static folder"""
    return send_from_directory('static/images', filename)
# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5012))
    app.config['PORT'] = port
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')