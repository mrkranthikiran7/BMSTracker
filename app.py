import os
import time
import multiprocessing
from datetime import datetime
from flask import Flask, render_template_string, request, send_file
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

app = Flask(__name__)
LOG_FILE = "tracker.log"

# ----------------- LOGGING -----------------
def log_message(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ----------------- HTML FRONTEND -----------------
HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"/><title>BMS Tracker</title>
<style>
body{font-family:Arial;background:#f5f5f5;padding:30px}
.card{max-width:520px;margin:auto;background:#fff;padding:20px;border-radius:10px;box-shadow:0 0 8px rgba(0,0,0,0.1)}
label{font-weight:600}
input,button{width:100%;padding:8px;margin-top:6px;border-radius:6px;border:1px solid #ccc}
button{background:#007bff;color:#fff;border:none;padding:10px;margin-top:15px}
a{color:#007bff}
</style>
</head>
<body>
  <div class="card">
    <h2>🎟️ BookMyShow Tracker</h2>
    <form method="post">
      <label>BookMyShow Page Link</label><input name="link" required placeholder="https://...">
      <label>Movie Name (as on site)</label><input name="movie" required placeholder="Baahubali: The Epic">
      <label>From Time (e.g. 04:00 PM)</label><input name="from_time" required placeholder="04:00 PM">
      <label>To Time (e.g. 09:00 PM)</label><input name="to_time" required placeholder="09:00 PM">
      <label>Screen name (optional)</label><input name="screen" placeholder="PVR Gold / IMAX">
      <label>Email to notify</label><input name="email" type="email" required placeholder="you@example.com">
      <button type="submit">Start Tracking</button>
    </form>
    <p style="font-size:13px;color:#555;margin-top:8px">
      ✅ Tracker runs on server every few minutes.<br>
      🔍 <a href="/logs" target="_blank">View Live Logs</a>
    </p>
  </div>
</body>
</html>
"""

# ----------------- EMAIL SETUP -----------------
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "180"))

def send_email(to_email, subject, body_html):
    log_message(f"📧 Sending email to {to_email} ...")
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        log_message("❌ Missing Gmail credentials in Render environment variables!")
        return False
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        log_message("✅ Email sent successfully.")
        return True
    except Exception as e:
        log_message(f"❌ Email failed: {e}")
        return False

# ----------------- UTIL -----------------
def parse_time_str(tstr):
    try:
        return datetime.strptime(tstr.strip(), "%I:%M %p")
    except Exception:
        log_message(f"⚠️ Could not parse time: {tstr}")
        return None

# ----------------- BACKGROUND TRACKER -----------------
def start_tracking_background(data):
    log_message("="*60)
    log_message(f"🚀 Tracker started at {datetime.now()} with data: {data}")
    log_message("="*60)

    track_url = data["link"].strip()
    movie_name = data["movie"].strip().lower()
    from_time = parse_time_str(data["from_time"])
    to_time = parse_time_str(data["to_time"])
    screen_name = data.get("screen", "").strip().lower()
    notify_email = data["email"].strip()

    if not from_time or not to_time:
        log_message("❌ Invalid from/to time. Exiting tracker.")
        return

    with sync_playwright() as p:
        log_message("🎬 Launching headless Chromium via Playwright...")
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            while True:
                try:
                    log_message(f"🌐 Navigating to {track_url}")
                    page.goto(track_url, timeout=60000)
                    page.wait_for_timeout(4000)
                    content = page.content().lower()

                    if movie_name not in content:
                        log_message(f"⚠️ Movie '{movie_name}' not found on page.")
                    else:
                        show_locators = page.locator(".sc-yr56qh-1")
                        screen_locators = page.locator(".sc-yr56qh-2")
                        count = show_locators.count()
                        log_message(f"🕒 Found {count} showtime entries on page.")

                        found = False
                        for i in range(count):
                            try:
                                st = show_locators.nth(i).inner_text().strip()
                                show_time = datetime.strptime(st, "%I:%M %p")
                            except Exception:
                                continue

                            stext = ""
                            if i < screen_locators.count():
                                try:
                                    stext = screen_locators.nth(i).inner_text().strip()
                                except:
                                    pass

                            if (from_time <= show_time <= to_time) and (not screen_name or screen_name in stext.lower()):
                                log_message(f"✅ Match found! Time: {st}, Screen: {stext}")
                                send_email(
                                    notify_email,
                                    f"🎟️ {data['movie']} - Show Available!",
                                    f"<h3>Show found for {data['movie']}</h3><p>Time: {st}<br>Screen: {stext}<br><a href='{track_url}'>Book Now</a></p>",
                                )
                                found = True
                                break

                        if found:
                            log_message("💌 Notification sent. Stopping tracker.")
                            break
                        else:
                            log_message(f"No matching shows yet. Sleeping {CHECK_INTERVAL}s...")
                    time.sleep(CHECK_INTERVAL)

                except Exception as inner:
                    log_message(f"⚠️ Error during tracking: {inner}")
                    time.sleep(60)
        finally:
            try:
                browser.close()
                log_message("🧹 Browser closed. Tracker exiting.")
            except:
                pass

# ----------------- FLASK ROUTES -----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.form.to_dict()
        log_message(f"📥 Received user input: {data}")
        p = multiprocessing.Process(target=start_tracking_background, args=(data,))
        p.start()
        log_message("🚀 Background tracking process started.")
        return "<h3>Tracking started! <a href='/logs' target='_blank'>View logs</a>.</h3>"
    return render_template_string(HTML)

@app.route("/logs")
def show_logs():
    if not os.path.exists(LOG_FILE):
        return "No logs yet. Submit a tracking request first."
    return send_file(LOG_FILE, mimetype="text/plain")

# ----------------- MAIN ENTRY -----------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    log_message(f"🌍 Server started on port {port}")
    app.run(host="0.0.0.0", port=port)
