FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for database and backups
RUN mkdir -p /data/backups

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DB_NAME=/data/simple_db.sqlite
ENV PORT=5003

# Volume for persistent data
VOLUME ["/data"]

# Expose the port the app runs on
EXPOSE 5003

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "app:app"]