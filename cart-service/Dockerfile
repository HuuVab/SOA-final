FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port
EXPOSE 5008

# Set environment variables
ENV PORT=5008
ENV DB_SERVICE_URL=http://db-service:5003/api
ENV CUSTOMER_SERVICE_URL=http://customer-service:5000/api
ENV PRODUCT_SERVICE_URL=http://product-service:5005/api
ENV PROMOTION_SERVICE_URL=http://promotion-service:5006/api

# Run the application
CMD ["python", "app.py"]