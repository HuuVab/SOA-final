 eCommerce Shop Microservices

A microservices-based eCommerce application built with Python and Docker. This project implements a scalable, maintainable architecture for an online shopping platform using service-oriented architecture (SOA) principles.

## 🚀 Architecture Overview

This application is composed of several independent microservices:

- **Cart Service**: Manages shopping cart functionality
- **Customer Service**: Handles user authentication, registration, and profile management
- **Database Service**: Centralizes database operations and management
- **Email Service**: Manages email notifications, alerts, and communications
- **Frontend Service**: Provides the user interface and client-side functionality
- **Media Service**: Handles image and media file storage and processing
- **Order Service**: Processes orders and order history
- **Payment Service**: Manages payment processing and financial transactions
- **Promotion Service**: Handles discounts, coupons, and special offers
- **Storage Service**: Provides file storage functionality

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Git

## 🛠️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/HuuVab/SOA-final.git
   cd SOA-final
   ```

2. Build and run the services:
   ```bash
   docker-compose up --build
   ```

## 🏗️ Project Structure

```
SOA-final/
├── cart-service/
│   ├── Dockerfile
│   └── src/
├── customer-service/
│   ├── Dockerfile
│   └── src/
├── data/
├── database-service/
│   ├── Dockerfile
│   └── src/
├── email-service/
│   ├── Dockerfile
│   └── src/
├── frontend-service/
│   ├── Dockerfile
│   └── src/
├── media-service/
│   ├── Dockerfile
│   └── src/
├── order-service/
│   ├── Dockerfile
│   └── src/
├── payment-service/
│   ├── Dockerfile
│   └── src/
├── promotion-service/
│   ├── Dockerfile
│   └── src/
├── storage-service/
│   ├── Dockerfile
│   └── src/
├── docker-compose.yml
├── .env.example
└── README.md
```
## 📞 Contact

Your Name - [huuvan060704@gmail.com]

Project Link: [https://github.com/HuuVab/SOA-final](https://github.com/HuuVab/SOA-final)
