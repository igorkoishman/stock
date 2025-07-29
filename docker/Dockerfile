# Base image
FROM python:3.11-slim

WORKDIR /app

# Install build tools and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copy application files
COPY app ./app
COPY run.py .
COPY gunicorn.conf.py .

# Expose Flask port
EXPOSE 5000

# Use Gunicorn to run the app factory
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]