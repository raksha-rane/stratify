FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy common module first (shared utilities)
COPY common /app/common

# Copy requirements and install Python dependencies
COPY data-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY data-service/ .

# Expose port
EXPOSE 5001

# Run the application
CMD ["python", "app.py"]
