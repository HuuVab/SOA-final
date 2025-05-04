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
# Main entry point
if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5012))
    app.config['PORT'] = port
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')