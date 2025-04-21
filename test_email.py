import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def generate_random_code(length=6):
    """Generate a random code of specified length using digits and uppercase letters."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def send_email_with_code(sender_email, sender_password, receiver_email, code_length=6):
    # Generate random code
    random_code = generate_random_code(code_length)
    
    # Set up email content
    message = MIMEMultipart("alternative")
    message["Subject"] = "Your Verification Code"
    message["From"] = sender_email
    message["To"] = receiver_email
    
    # Create plain text version of email
    text = f"""\
    Hello,
    
    Your verification code is: {random_code}
    
    Please use this code to complete your verification process.
    
    This is an automated message, please do not reply.
    """
    
    # Create HTML version of email
    html = f"""\
    <html>
      <body>
        <p>Hello,</p>
        <p>Your verification code is: <strong>{random_code}</strong></p>
        <p>Please use this code to complete your verification process.</p>
        <p>This is an automated message, please do not reply.</p>
      </body>
    </html>
    """
    
    # Add both versions to the email
    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))
    
    try:
        # Create secure SMTP connection with Gmail
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        
        # Login to sender email
        server.login(sender_email, sender_password)
        
        # Send email
        server.sendmail(sender_email, receiver_email, message.as_string())
        
        # Close connection
        server.quit()
        
        print(f"Email sent successfully to {receiver_email}")
        print(f"The random code is: {random_code}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Example usage
if __name__ == "__main__":
    # Replace these with your actual email credentials
    sender_email = "huuvan060704@gmail.com"  # Your Gmail address
    sender_password = "myfq egnc sqko juuu"  # Your Gmail app password
    receiver_email = "huuvan0607042@gmail.com"  # The specific Gmail you want to send to
    
    # Send email with a 6-character random code
    send_email_with_code(sender_email, sender_password, receiver_email, code_length=6)