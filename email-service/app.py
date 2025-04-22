"""
Email Microservice
-----------------
Handles all email communications, including verification emails with random codes, 
password resets, and marketing communications.
"""

from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
from functools import wraps
import redis
import time
import random
import string
# No longer need requests library as we removed EngageLab API
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'email_service_secret_key')
app.config['API_KEY'] = os.environ.get('EMAIL_SERVICE_API_KEY', 'email_service_api_key')

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = 'mrbeast6969gaming@gmail.com'
app.config['MAIL_PASSWORD'] = 'yboo jclj ggli vflr'
app.config['MAIL_DEFAULT_SENDER'] = 'mrbeast6969gaming@gmail.com'

# Redis for rate limiting and storing verification codes
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
try:
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
    redis_client.ping()  # Test connection
    app.logger.info("Redis connection successful")
except Exception as e:
    app.logger.warning(f"Redis connection failed: {e}. Rate limiting will be disabled.")
    redis_client = None

# API key required decorator
def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = None
        
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        
        if not api_key or api_key != app.config['API_KEY']:
            return jsonify({'message': 'Invalid or missing API key!'}), 401
            
        return f(*args, **kwargs)
    
    return decorated

# Rate limiting decorator
def rate_limit(limit=100, per=60, scope='global'):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Skip rate limiting if Redis is not available
            if redis_client is None:
                return f(*args, **kwargs)
                
            # Determine the key based on scope
            if scope == 'ip':
                key = f"rate_limit:{request.remote_addr}:{f.__name__}"
            elif scope == 'api_key':
                api_key = request.headers.get('X-API-Key', 'default')
                key = f"rate_limit:{api_key}:{f.__name__}"
            else:
                key = f"rate_limit:global:{f.__name__}"
                
            # Get current count and time
            try:
                current = redis_client.get(key)
                if current is None:
                    redis_client.set(key, 1, ex=per)
                    current = 1
                else:
                    current = int(current)
                    if current >= limit:
                        return jsonify({
                            'message': f'Rate limit exceeded. Try again in {redis_client.ttl(key)} seconds.'
                        }), 429
                    redis_client.incr(key)
            except Exception as e:
                app.logger.error(f"Redis error during rate limiting: {e}")
                # Continue without rate limiting if Redis fails
                
            return f(*args, **kwargs)
        return decorated
    return decorator

def generate_random_code(length=6):
    """Generate a random code of specified length using digits and uppercase letters."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def send_email(to_email, subject, text_content, html_content):
    """Send an email using SMTP SSL (matching the working standalone script)"""
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = app.config['MAIL_DEFAULT_SENDER']
        message["To"] = to_email
        
        # Add text and HTML parts
        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))
        
        # Always use SMTP_SSL with port 465 (matching the working script)
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        
        # Login and send email
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.sendmail(
            app.config['MAIL_DEFAULT_SENDER'], 
            to_email, 
            message.as_string()
        )
        server.quit()
        
        app.logger.info(f"Email sent successfully to {to_email}")
        return True, "Email sent successfully"
        
    except Exception as e:
        app.logger.error(f"Error sending email to {to_email}: {str(e)}")
        return False, f"Error sending email: {str(e)}"

def store_verification_code(email, code, expiry_seconds=86400):
    """Store verification code in Redis with expiry"""
    if redis_client is None:
        app.logger.warning("Redis not available for storing verification code")
        return False
        
    try:
        key = f"verification_code:{email}"
        redis_client.set(key, code, ex=expiry_seconds)
        return True
    except Exception as e:
        app.logger.error(f"Error storing verification code: {str(e)}")
        return False

def get_verification_email_template(verification_code):
    """Return text and HTML content for verification email with code"""
    text = f'''
Hi there,

Your verification code is: {verification_code}

Please use this code to verify your email address. 
This code will expire in 24 hours.

Thanks,
The E-commerce Team
'''
    
    html = f'''
<html>
<head></head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #444;">Email Verification</h2>
        <p>Thank you for registering with our service. To complete your registration, please use the verification code below:</p>
        <div style="text-align: center; margin: 30px 0;">
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; font-size: 24px; letter-spacing: 5px; font-weight: bold;">
                {verification_code}
            </div>
        </div>
        <p style="color: #666; font-size: 14px;">
            This verification code will expire in 24 hours. If you did not create an account, you can safely ignore this email.
        </p>
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            The E-commerce Team
        </p>
    </div>
</body>
</html>
'''
    return text, html

def get_password_reset_template(reset_code):
    """Return text and HTML content for password reset email with code"""
    text = f'''
Hi there,

You requested to reset your password. Your password reset code is:
{reset_code}

Please use this code to reset your password.
This code will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email.

Thanks,
The E-commerce Team
'''
    
    html = f'''
<html>
<head></head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #444;">Password Reset</h2>
        <p>You requested to reset your password. Use the code below to set a new password:</p>
        <div style="text-align: center; margin: 30px 0;">
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; font-size: 24px; letter-spacing: 5px; font-weight: bold;">
                {reset_code}
            </div>
        </div>
        <p style="color: #666; font-size: 14px;">
            This password reset code will expire in 1 hour. If you didn't request a password reset, you can safely ignore this email.
        </p>
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            The E-commerce Team
        </p>
    </div>
</body>
</html>
'''
    return text, html

def get_welcome_template(user_name):
    """Return text and HTML content for welcome email"""
    text = f'''
Welcome {user_name}!

Thank you for joining our platform. We're excited to have you on board.

If you have any questions, feel free to reply to this email.

Best regards,
The E-commerce Team
'''
    
    html = f'''
<html>
<head></head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #444;">Welcome to Our Platform!</h2>
        <p>Hello {user_name},</p>
        <p>Thank you for joining our platform. We're excited to have you on board!</p>
        <p>Here are some things you can do now:</p>
        <ul>
            <li>Complete your profile</li>
            <li>Browse our products</li>
            <li>Follow us on social media</li>
        </ul>
        <p>If you have any questions, feel free to reply to this email.</p>
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            The E-commerce Team
        </p>
    </div>
</body>
</html>
'''
    return text, html

def get_notification_template(subject, message):
    """Return text and HTML content for general notification emails"""
    text = f'''
{subject}

{message}

Best regards,
The E-commerce Team
'''
    
    html = f'''
<html>
<head></head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #444;">{subject}</h2>
        <p>{message}</p>
        <p style="color: #666; font-size: 14px;">
            Best regards,<br>
            The E-commerce Team
        </p>
    </div>
</body>
</html>
'''
    return text, html

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    redis_status = "ok" if redis_client is not None else "unavailable"
    return jsonify({
        'status': 'ok', 
        'service': 'email-service',
        'redis': redis_status,
        'mail_server': app.config['MAIL_SERVER'],
        'mail_port': app.config['MAIL_PORT']
    }), 200

@app.route('/send/verification', methods=['POST'])
@api_key_required
@rate_limit(limit=50, per=3600, scope='api_key')  # Limit to 50 verification emails per hour per API key
def send_verification_email():
    """Send verification email with random code to new user"""
    data = request.get_json()
    
    if 'email' not in data:
        return jsonify({'message': 'Missing required email field!'}), 400
    
    email = data['email']
    code_length = data.get('code_length', 6)  # Default to 6 characters if not specified
    
    # Generate a random verification code
    verification_code = generate_random_code(code_length)
    
    # Store the verification code in Redis
    if redis_client is not None:
        stored = store_verification_code(email, verification_code)
        if not stored:
            app.logger.warning(f"Could not store verification code for {email} in Redis")
    
    # Get verification email template with code
    text_content, html_content = get_verification_email_template(verification_code)
    
    # Send email
    success, message = send_email(
        email, 
        'Verify your email address', 
        text_content, 
        html_content
    )
    
    if success:
        response_data = {
            'message': 'Verification email sent successfully!',
            'email': email
        }
        
        # Only include the code in the response if Redis is not available
        # This allows the API consumer to handle verification themselves
        if redis_client is None:
            response_data['verification_code'] = verification_code
            
        return jsonify(response_data), 200
    else:
        app.logger.error(f"Failed to send verification email to {email}: {message}")
        return jsonify({'message': message}), 500

@app.route('/verify/code', methods=['POST'])
@api_key_required
def verify_code():
    """Verify a code submitted by user"""
    if redis_client is None:
        return jsonify({'message': 'Verification service unavailable, Redis not connected!'}), 503
        
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'code']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data['email']
    submitted_code = data['code']
    
    # Get the stored code
    key = f"verification_code:{email}"
    stored_code = redis_client.get(key)
    
    if stored_code is None:
        return jsonify({'message': 'No verification code found or code expired!', 'verified': False}), 400
    
    # Compare codes (case-insensitive)
    if submitted_code.upper() == stored_code.decode('utf-8').upper():
        # Delete the code once verified
        redis_client.delete(key)
        return jsonify({'message': 'Email verified successfully!', 'verified': True}), 200
    else:
        return jsonify({'message': 'Invalid verification code!', 'verified': False}), 400

@app.route('/send/password-reset', methods=['POST'])
@api_key_required
@rate_limit(limit=10, per=3600, scope='ip')  # Limit to 10 password reset emails per hour per IP
def send_password_reset_email():
    """Send password reset email with code"""
    data = request.get_json()
    
    if 'email' not in data:
        return jsonify({'message': 'Missing required email field!'}), 400
    
    email = data['email']
    code_length = data.get('code_length', 8)  # Default to 8 characters if not specified
    
    # Generate a random reset code
    reset_code = generate_random_code(code_length)
    
    # Store the reset code in Redis (expires in 1 hour)
    if redis_client is not None:
        key = f"password_reset:{email}"
        redis_client.set(key, reset_code, ex=3600)
    
    # Get password reset email template with code
    text_content, html_content = get_password_reset_template(reset_code)
    
    # Send email
    success, message = send_email(
        email, 
        'Reset Your Password', 
        text_content, 
        html_content
    )
    
    if success:
        response_data = {
            'message': 'Password reset email sent successfully!',
            'email': email
        }
        
        # Only include the code in the response if Redis is not available
        if redis_client is None:
            response_data['reset_code'] = reset_code
            
        return jsonify(response_data), 200
    else:
        app.logger.error(f"Failed to send password reset email to {email}: {message}")
        return jsonify({'message': message}), 500

@app.route('/send/welcome', methods=['POST'])
@api_key_required
def send_welcome_email():
    """Send welcome email to newly verified user"""
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'name']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data['email']
    name = data['name']
    
    # Get welcome email template
    text_content, html_content = get_welcome_template(name)
    
    # Send email
    success, message = send_email(
        email, 
        'Welcome to Our Platform!', 
        text_content, 
        html_content
    )
    
    if success:
        return jsonify({'message': 'Welcome email sent successfully!'}), 200
    else:
        app.logger.error(f"Failed to send welcome email to {email}: {message}")
        return jsonify({'message': message}), 500

@app.route('/send/notification', methods=['POST'])
@api_key_required
@rate_limit(limit=200, per=3600, scope='api_key')  # Limit to 200 notifications per hour per API key
def send_notification_email():
    """Send notification email to user"""
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'subject', 'message']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data['email']
    subject = data['subject']
    message = data['message']
    
    # Get notification email template
    text_content, html_content = get_notification_template(subject, message)
    
    # Send email
    success, message_result = send_email(
        email, 
        subject, 
        text_content, 
        html_content
    )
    
    if success:
        return jsonify({'message': 'Notification email sent successfully!'}), 200
    else:
        app.logger.error(f"Failed to send notification email to {email}: {message_result}")
        return jsonify({'message': message_result}), 500

@app.route('/send/custom', methods=['POST'])
@api_key_required
@rate_limit(limit=100, per=3600, scope='api_key')  # Limit to 100 custom emails per hour per API key
def send_custom_email():
    """Send custom email with provided content"""
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'subject', 'text_content', 'html_content']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data['email']
    subject = data['subject']
    text_content = data['text_content']
    html_content = data['html_content']
    
    # Send email
    success, message = send_email(
        email, 
        subject, 
        text_content, 
        html_content
    )
    
    if success:
        return jsonify({'message': 'Custom email sent successfully!'}), 200
    else:
        app.logger.error(f"Failed to send custom email to {email}: {message}")
        return jsonify({'message': message}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)