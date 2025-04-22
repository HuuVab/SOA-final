FROM python:3.9-slim

WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies with explicit pip upgrade
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create templates directory if it doesn't exist
RUN mkdir -p templates

# Expose port
EXPOSE 5002

# Command to run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]