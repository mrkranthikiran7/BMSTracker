# ---------- Base image ----------
FROM python:3.11-slim

# ---------- System dependencies ----------
RUN apt-get update && apt-get install -y \
    wget unzip gnupg ca-certificates curl \
    fonts-liberation libnss3 libxss1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libgbm1 libgtk-3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# ---------- Install Google Chrome (fixed v120) ----------
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-linux.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable=120.0.6099.109-1 && \
    rm -rf /var/lib/apt/lists/*

# ---------- Install matching ChromeDriver (v120) ----------
RUN wget -q https://chromedriver.storage.googleapis.com/120.0.6099.109/chromedriver_linux64.zip -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver

# ---------- Environment ----------
ENV DISPLAY=:99
WORKDIR /app

# ---------- Copy project ----------
COPY . /app

# ---------- Python packages ----------
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Expose & run ----------
EXPOSE 8080
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4"]
