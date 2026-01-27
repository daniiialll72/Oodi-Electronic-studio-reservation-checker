FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application and entrypoint script
COPY check_oodi_slots.py .
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Use entrypoint script to handle environment variables
ENTRYPOINT ["/app/docker-entrypoint.sh"]

