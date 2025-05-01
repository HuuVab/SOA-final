FROM python:alpine

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p static/images

# Environment variables
ENV PORT=5012
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=false
ENV STORAGE_SERVICE_URL=http://storage-service:5005/api
ENV PROMOTION_SERVICE_URL=http://promotion-service:5006/api

EXPOSE 5012

CMD ["python", "app.py"]