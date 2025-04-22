FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories for static files if they don't exist
RUN mkdir -p /app/static/images
RUN mkdir -p /app/static/css
RUN mkdir -p /app/static/js

# Set environment variables
ENV PORT=5004
ENV FLASK_APP=app.py
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 5004

CMD ["python", "app.py"]