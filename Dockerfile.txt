# Use an official Python base
FROM python:3.11-slim

# Install dependencies for Chrome and chromedriver
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Chrome (stable)
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb || apt-get -f install -y \
    && rm /tmp/chrome.deb

# Install chromedriver matching Chrome
RUN CHROME_VERSION=$(google-chrome --product-version | cut -d'.' -f1,2) \
    && echo "Chrome major version: $CHROME_VERSION" \
    && LATEST=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -q "https://chromedriver.storage.googleapis.com/${LATEST}/chromedriver_linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver

# Copy app
WORKDIR /app
COPY . /app

# Install python deps
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4"]
