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
import time
import random
import string
import requests
from datetime import datetime, timedelta
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
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'mrbeast6969gaming@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'yboo jclj ggli vflr')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'mrbeast6969gaming@gmail.com')

# Database Service configuration
DB_SERVICE_URL = os.environ.get('DB_SERVICE_URL', 'http://localhost:5003/api')

# Initialize email database tables
def initialize_email_tables():
    """Initialize database tables for email service"""
    try:
        # Connect to the database
        connect_response = requests.post(
            f"{DB_SERVICE_URL}/connect",
            json={"db_name": os.environ.get('DB_NAME', 'email.sqlite')}
        )
        app.logger.info(f"Database connection: {connect_response.json()}")

        # Check if tables exist
        tables_response = requests.get(f"{DB_SERVICE_URL}/tables")
        tables = tables_response.json().get('tables', [])
        
        # Create email_logs table if it doesn't exist
        if 'email_logs' not in tables:
            email_logs_schema = {
                "email_id": "TEXT PRIMARY KEY",
                "recipient": "TEXT NOT NULL",
                "subject": "TEXT NOT NULL",
                "email_type": "TEXT NOT NULL",
                "status": "TEXT NOT NULL",
                "sent_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "error_message": "TEXT"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "email_logs", "columns": email_logs_schema}
            )
            
            app.logger.info(f"Email logs table initialization: {response.json()}")
        
        # Create verification_codes table if it doesn't exist
        if 'verification_codes' not in tables:
            verification_codes_schema = {
                "email": "TEXT NOT NULL",
                "code": "TEXT NOT NULL",
                "code_type": "TEXT NOT NULL",
                "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "expires_at": "TIMESTAMP NOT NULL",
                "PRIMARY KEY": "(email, code_type)"
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables",
                json={"table_name": "verification_codes", "columns": verification_codes_schema}
            )
            
            app.logger.info(f"Verification codes table initialization: {response.json()}")
            
        return True
    except Exception as e:
        app.logger.error(f"Error initializing email tables: {str(e)}")
        return False

# Initialize tables when the service starts
initialization_successful = initialize_email_tables()

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

# Rate limiting decorator using database instead of Redis
def rate_limit(limit=100, per=60, scope='global'):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not initialization_successful:
                # Skip rate limiting if database connection failed
                return f(*args, **kwargs)
                
            # Determine the key based on scope
            if scope == 'ip':
                identifier = f"{request.remote_addr}:{f.__name__}"
            elif scope == 'api_key':
                api_key = request.headers.get('X-API-Key', 'default')
                identifier = f"{api_key}:{f.__name__}"
            else:
                identifier = f"global:{f.__name__}"
                
            # Get current time
            current_time = datetime.now()
            time_window_start = (current_time - timedelta(seconds=per)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Query the rate limiting
            try:
                # Count emails in the time window
                query = f"""
                SELECT COUNT(*) as count 
                FROM email_logs 
                WHERE email_type = ? AND sent_at > ?
                """
                
                params = [identifier, time_window_start]
                
                response = requests.post(
                    f"{DB_SERVICE_URL}/execute",
                    json={"query": query, "params": params}
                )
                
                result = response.json()
                if result.get('status') == 'success' and result.get('data'):
                    count = result['data'][0]['count']
                    if count >= limit:
                        wait_time = per - (current_time - datetime.strptime(time_window_start, "%Y-%m-%d %H:%M:%S")).seconds
                        return jsonify({
                            'message': f'Rate limit exceeded. Try again in {wait_time} seconds.'
                        }), 429
            except Exception as e:
                app.logger.error(f"Database error during rate limiting: {e}")
                # Continue without rate limiting if database query fails
                
            return f(*args, **kwargs)
        return decorated
    return decorator

def generate_random_code(length=6):
    """Generate a random code of specified length using digits and uppercase letters."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def log_email(recipient, subject, email_type, status, error_message=None):
    """Log email to database"""
    if not initialization_successful:
        app.logger.warning("Database not available for logging email")
        return
        
    try:
        email_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        email_data = {
            "email_id": email_id,
            "recipient": recipient,
            "subject": subject,
            "email_type": email_type,
            "status": status,
            "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": error_message
        }
        
        response = requests.post(
            f"{DB_SERVICE_URL}/tables/email_logs/data",
            json=email_data
        )
        
        if response.status_code != 200:
            app.logger.error(f"Failed to log email: {response.json()}")
    except Exception as e:
        app.logger.error(f"Error logging email: {str(e)}")

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
        
        # Log successful email
        log_email(to_email, subject, "general", "sent")
        
        app.logger.info(f"Email sent successfully to {to_email}")
        return True, "Email sent successfully"
        
    except Exception as e:
        # Log failed email
        log_email(to_email, subject, "general", "failed", str(e))
        
        app.logger.error(f"Error sending email to {to_email}: {str(e)}")
        return False, f"Error sending email: {str(e)}"

def store_verification_code(email, code, code_type="verification", expiry_seconds=86400):
    """Store verification code in database with expiry"""
    if not initialization_successful:
        app.logger.warning("Database not available for storing verification code")
        return False
        
    try:
        # Calculate expiry time
        expiry_time = (datetime.now() + timedelta(seconds=expiry_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if there's an existing code for this email and type
        check_query = """
        SELECT email FROM verification_codes 
        WHERE email = ? AND code_type = ?
        """
        
        check_response = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": check_query, "params": [email, code_type]}
        )
        
        result = check_response.json()
        
        if result.get('status') == 'success' and result.get('data'):
            # Update existing code
            update_data = {
                "code": code,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "expires_at": expiry_time
            }
            
            response = requests.put(
                f"{DB_SERVICE_URL}/tables/verification_codes/data",
                json={
                    "values": update_data,
                    "condition": "email = ? AND code_type = ?",
                    "params": [email, code_type]
                }
            )
        else:
            # Insert new code
            code_data = {
                "email": email,
                "code": code,
                "code_type": code_type,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "expires_at": expiry_time
            }
            
            response = requests.post(
                f"{DB_SERVICE_URL}/tables/verification_codes/data",
                json=code_data
            )
        
        if response.status_code != 200:
            app.logger.error(f"Failed to store verification code: {response.json()}")
            return False
            
        return True
    except Exception as e:
        app.logger.error(f"Error storing verification code: {str(e)}")
        return False

def get_verification_code(email, code_type="verification"):
    """Get verification code from database"""
    if not initialization_successful:
        app.logger.warning("Database not available for retrieving verification code")
        return None
        
    try:
        query = """
        SELECT code, expires_at FROM verification_codes 
        WHERE email = ? AND code_type = ? AND expires_at > ?
        """
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        response = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": query, "params": [email, code_type, current_time]}
        )
        
        result = response.json()
        
        if result.get('status') == 'success' and result.get('data'):
            return result['data'][0]['code']
        
        return None
    except Exception as e:
        app.logger.error(f"Error getting verification code: {str(e)}")
        return None

def delete_verification_code(email, code_type="verification"):
    """Delete verification code from database"""
    if not initialization_successful:
        app.logger.warning("Database not available for deleting verification code")
        return False
        
    try:
        response = requests.delete(
            f"{DB_SERVICE_URL}/tables/verification_codes/data",
            json={
                "condition": "email = ? AND code_type = ?",
                "params": [email, code_type]
            }
        )
        
        if response.status_code != 200:
            app.logger.error(f"Failed to delete verification code: {response.json()}")
            return False
            
        return True
    except Exception as e:
        app.logger.error(f"Error deleting verification code: {str(e)}")
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


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    db_status = "ok" if initialization_successful else "unavailable"
    return jsonify({
        'status': 'ok', 
        'service': 'email-service',
        'database': db_status,
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
    
    # Store the verification code in database
    stored = store_verification_code(email, verification_code, "verification", 86400)  # 24 hours
    
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
        # Log verification email specifically
        log_email(email, 'Verify your email address', "verification", "sent")
        
        response_data = {
            'message': 'Verification email sent successfully!',
            'email': email
        }
        
        # Only include the code in the response if database storage failed
        if not stored:
            response_data['verification_code'] = verification_code
            
        return jsonify(response_data), 200
    else:
        app.logger.error(f"Failed to send verification email to {email}: {message}")
        return jsonify({'message': message}), 500

@app.route('/verify/code', methods=['POST'])
@api_key_required
def verify_code():
    """Verify a code submitted by user"""
    data = request.get_json()
    
    if not all(key in data for key in ['email', 'code']):
        return jsonify({'message': 'Missing required fields!'}), 400
    
    email = data['email']
    submitted_code = data['code']
    
    # Get the stored code
    stored_code = get_verification_code(email, "verification")
    
    if stored_code is None:
        return jsonify({'message': 'No verification code found or code expired!', 'verified': False}), 400
    
    # Compare codes (case-insensitive)
    if submitted_code.upper() == stored_code.upper():
        # Delete the code once verified
        delete_verification_code(email, "verification")
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
    
    # Store the reset code in database (expires in 1 hour)
    stored = store_verification_code(email, reset_code, "password_reset", 3600)  # 1 hour
    
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
        # Log password reset email specifically
        log_email(email, 'Reset Your Password', "password_reset", "sent")
        
        response_data = {
            'message': 'Password reset email sent successfully!',
            'email': email
        }
        
        # Only include the code in the response if database storage failed
        if not stored:
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
        # Log welcome email specifically
        log_email(email, 'Welcome to Our Platform!', "welcome", "sent")
        return jsonify({'message': 'Welcome email sent successfully!'}), 200
    else:
        app.logger.error(f"Failed to send welcome email to {email}: {message}")
        return jsonify({'message': message}), 500

@app.route('/api/send/notification', methods=['POST'])
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
        # Log notification email specifically
        log_email(email, subject, "notification", "sent")
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
        # Log custom email specifically
        log_email(email, subject, "custom", "sent")
        return jsonify({'message': 'Custom email sent successfully!'}), 200
    else:
        app.logger.error(f"Failed to send custom email to {email}: {message}")
        return jsonify({'message': message}), 500

@app.route('/emails/logs', methods=['GET'])
@api_key_required
def get_email_logs():
    """Get email sending logs with optional filtering"""
    if not initialization_successful:
        return jsonify({'message': 'Database not available for email logs!'}), 503
    
    email = request.args.get('email')
    status = request.args.get('status')
    email_type = request.args.get('type')
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    
    conditions = []
    params = []
    
    if email:
        conditions.append("recipient = ?")
        params.append(email)
    
    if status:
        conditions.append("status = ?")
        params.append(status)
    
    if email_type:
        conditions.append("email_type = ?")
        params.append(email_type)
    
    if date_from:
        conditions.append("sent_at >= ?")
        params.append(date_from)
    
    if date_to:
        conditions.append("sent_at <= ?")
        params.append(date_to)
    
    # Construct condition string if filters are applied
    condition = " AND ".join(conditions) if conditions else None
    
    try:
        # Query the logs
        response = requests.get(
            f"{DB_SERVICE_URL}/tables/email_logs/data",
            params={
                "condition": condition, 
                "params": ",".join(params) if params else None
            }
        )
        
        result = response.json()
        
        if result.get('status') != 'success':
            return jsonify({'message': 'Failed to retrieve email logs!'}), 500
        
        return jsonify({
            'message': 'Email logs retrieved successfully!',
            'logs': result.get('data', [])
        }), 200
    except Exception as e:
        app.logger.error(f"Error retrieving email logs: {str(e)}")
        return jsonify({'message': f'Error retrieving email logs: {str(e)}'}), 500

@app.route('/stats', methods=['GET'])
@api_key_required
def get_email_stats():
    """Get email sending statistics"""
    if not initialization_successful:
        return jsonify({'message': 'Database not available for email statistics!'}), 503
    
    try:
        # Get total emails sent
        total_query = "SELECT COUNT(*) as total FROM email_logs"
        total_response = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": total_query}
        )
        
        # Get emails by type
        type_query = "SELECT email_type, COUNT(*) as count FROM email_logs GROUP BY email_type"
        type_response = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": type_query}
        )
        
        # Get emails by status
        status_query = "SELECT status, COUNT(*) as count FROM email_logs GROUP BY status"
        status_response = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": status_query}
        )
        
        # Get daily email counts for last 7 days
        daily_query = """
        SELECT date(sent_at) as day, COUNT(*) as count 
        FROM email_logs 
        WHERE sent_at >= date('now', '-7 day') 
        GROUP BY date(sent_at)
        """
        daily_response = requests.post(
            f"{DB_SERVICE_URL}/execute",
            json={"query": daily_query}
        )
        
        # Compile stats
        stats = {
            'total_emails': total_response.json().get('data', [{}])[0].get('total', 0),
            'by_type': type_response.json().get('data', []),
            'by_status': status_response.json().get('data', []),
            'daily': daily_response.json().get('data', [])
        }
        
        return jsonify({
            'message': 'Email statistics retrieved successfully!',
            'stats': stats
        }), 200
    except Exception as e:
        app.logger.error(f"Error retrieving email statistics: {str(e)}")
        return jsonify({'message': f'Error retrieving email statistics: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)