import os
import time
import threading
from datetime import datetime
from flask import Flask, render_template_string, request
import smtplib
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

app = Flask(__name__)

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>BMS Tracker</title>
  <style>
    body{font-family:Arial;background:#f7f7f7;padding:30px}
    .card{max-width:520px;margin:auto;background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.08)}
    label{font-weight:600;margin-top:10px;display:block}
    input, button {width:100%; padding:8px; margin-top:6px; border-radius:6px; border:1px solid #ccc}
    button{background:#0b74de;color:#fff;border:none;padding:10px}
    .note{font-size:13px;color:#666;margin-top:8px}
  </style>
</head>
<body>
  <div class="card">
    <h2>BookMyShow Tracker</h2>
    <form method="post">
      <label>BookMyShow Page Link</label>
      <input name="link" required placeholder="https://...">

      <label>Movie Name (as on site)</label>
      <input name="movie" required placeholder="Baahubali: The Epic">

      <label>From Time (e.g. 02:00 PM)</label>
      <input name="from_time" required placeholder="02:00 PM">

      <label>To Time (e.g. 06:00 PM)</label>
      <input name="to_time" required placeholder="06:00 PM">

      <label>Screen name (optional)</label>
      <input name="screen" placeholder="PCX Screen">

      <label>Email to notify</label>
      <input name="email" type="email" required placeholder="you@example.com">

      <button type="submit">Start Tracking</button>
    </form>
    <p class="note">Tracking runs in background on server. You will receive an email when a matching show is found.</p>
  </div>
</body>
</html>
"""

# Read SMTP credentials from environment variables
SENDER_EMAIL = os.getenv("SENDER_EMAIL")  # your gmail address
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")  # app password (16 chars)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "180"))  # default 180 seconds

def send_email(to_email, subject, body_html):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("ERROR: SMTP credentials are not configured.")
        return False
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("Email sent to", to_email)
        return True
    except Exception as e:
        print("Failed to send email:", e)
        return False

def start_tracking_background(data):
    track_url = data["link"].strip()
    movie_name = data["movie"].strip().lower()
    from_time = datetime.strptime(data["from_time"].strip(), "%I:%M %p")
    to_time = datetime.strptime(data["to_time"].strip(), "%I:%M %p")
    screen_name = data.get("screen","").strip().lower()
    notify_email = data["email"].strip()
    print("Started tracking:", movie_name, from_time.time(), to_time.time(), "screen=", screen_name)

    # configure headless chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # chromedriver path inside Docker (we place chromedriver at /usr/local/bin/chromedriver)
    service = Service("/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        while True:
            try:
                print("Checking:", track_url)
                driver.get(track_url)
                time.sleep(8)  # allow page to render

                page_lower = driver.page_source.lower()
                if movie_name not in page_lower:
                    print("Movie not found on page.")
                else:
                    show_elems = driver.find_elements(By.CLASS_NAME, "sc-yr56qh-1")
                    screen_elems = driver.find_elements(By.CLASS_NAME, "sc-yr56qh-2")
                    matched = False
                    for i, se in enumerate(show_elems):
                        st = se.text.strip()
                        if not st:
                            continue
                        try:
                            show_time = datetime.strptime(st, "%I:%M %p")
                        except Exception:
                            continue
                        # check time window
                        if from_time <= show_time <= to_time:
                            stext = screen_elems[i].text.strip() if i < len(screen_elems) else ""
                            if (not screen_name) or (screen_name in stext.lower()):
                                matched = True
                                html_body = f"""
                                <h3>Show found: {data['movie']}</h3>
                                <p><strong>Time:</strong> {st}<br>
                                <strong>Screen:</strong> {stext}<br>
                                <a href="{track_url}">Book Now</a></p>
                                """
                                send_email(notify_email, f"🎟️ {data['movie']} - Show Available", html_body)
                                break
                    if matched:
                        print("Match found - stopping tracker for this job.")
                        break
                    else:
                        print("No match found yet.")
                time.sleep(CHECK_INTERVAL)
            except Exception as inner_e:
                print("Inner error:", inner_e)
                time.sleep(60)
    finally:
        driver.quit()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.form.to_dict()
        # start background thread for this job
        t = threading.Thread(target=start_tracking_background, args=(data,), daemon=True)
        t.start()
        return "<h3>Tracking started in background. You will receive an email when a matching show appears.</h3>"
    return render_template_string(HTML)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
