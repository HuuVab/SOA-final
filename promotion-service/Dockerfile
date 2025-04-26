FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variables
ENV PORT=5006
ENV DB_SERVICE_URL=http://database-service:5003/api
ENV DB_NAME=/data/promotion.sqlite
ENV STORAGE_DB_NAME=/data/storage.sqlite
ENV FLASK_DEBUG=False

# Expose the port
EXPOSE 5006

# Command to run the service
CMD ["python", "app.py"]