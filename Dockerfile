FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install browsers
RUN playwright install --with-deps chromium

COPY . /app

EXPOSE 8080
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4"]
