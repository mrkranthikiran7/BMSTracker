FROM python:3.11-slim

# ---------- Install dependencies ----------
RUN apt-get update && apt-get install -y \
    wget unzip gnupg ca-certificates curl \
    fonts-liberation libnss3 libxss1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libgbm1 libgtk-3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# ---------- Install latest Google Chrome ----------
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# ---------- Fetch Chrome version manually ----------
RUN CHROME_VERSION=$(google-chrome --version | grep -oP "[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+") && \
    echo "Installed Chrome version: $CHROME_VERSION" > /chrome_version.txt

# ---------- Download exact matching ChromeDriver ----------
RUN CHROME_VERSION=$(cat /chrome_version.txt | grep -oP "[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+") && \
    DRIVER_VERSION=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | \
                     grep -A 1 "\"Stable\"" | grep -oP "[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+") && \
    echo "ChromeDriver version: $DRIVER_VERSION" && \
    wget -q "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -rf /usr/local/bin/chromedriver-linux64 /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver

# ---------- Environment ----------
ENV DISPLAY=:99
WORKDIR /app
COPY . /app

# ---------- Python deps ----------
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Expose & run ----------
EXPOSE 8080
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4"]
