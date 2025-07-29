FROM python:3.11-slim

WORKDIR /app

# Install build tools and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app ./app
COPY run.py .

# Expose Flask port
EXPOSE 5000

# Run using Flask dev server
CMD ["python", "run.py"]
