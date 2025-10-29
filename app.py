import os
import time
import threading
from datetime import datetime
from flask import Flask, render_template_string, request
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

app = Flask(__name__)

HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"/><title>BMS Tracker</title>
<style>body{font-family:Arial;background:#f7f7f7;padding:30px}.card{max-width:520px;margin:auto;background:#fff;padding:20px;border-radius:8px}label{font-weight:600}input,button{width:100%;padding:8px;margin-top:6px;border-radius:6px;border:1px solid #ccc}button{background:#0b74de;color:#fff;border:none;padding:10px}</style>
</head>
<body>
  <div class="card">
    <h2>BookMyShow Tracker (Playwright)</h2>
    <form method="post">
      <label>BookMyShow Page Link</label><input name="link" required placeholder="https://...">
      <label>Movie Name (as on site)</label><input name="movie" required placeholder="Baahubali: The Epic">
      <label>From Time (e.g. 02:00 PM)</label><input name="from_time" required placeholder="02:00 PM">
      <label>To Time (e.g. 06:00 PM)</label><input name="to_time" required placeholder="06:00 PM">
      <label>Screen name (optional)</label><input name="screen" placeholder="PCX Screen">
      <label>Email to notify</label><input name="email" type="email" required placeholder="you@example.com">
      <button type="submit">Start Tracking</button>
    </form>
    <p style="font-size:13px;color:#666;margin-top:8px">Tracker runs in background on server. Email sent when a matching show appears.</p>
  </div>
</body>
</html>
"""

# read SMTP credentials from env
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "180"))

def send_email(to_email, subject, body_html):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("SMTP credentials missing; cannot send email.")
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

def parse_time_str(tstr):
    try:
        return datetime.strptime(tstr.strip(), "%I:%M %p")
    except Exception:
        return None

def start_tracking_background(data):
    track_url = data["link"].strip()
    movie_name = data["movie"].strip().lower()
    from_time = parse_time_str(data["from_time"])
    to_time = parse_time_str(data["to_time"])
    screen_name = data.get("screen","").strip().lower()
    notify_email = data["email"].strip()
    print("Started tracking:", movie_name, from_time.time(), to_time.time(), "screen=", screen_name)

    with sync_playwright() as p:
        # Use playwright chromium (bundled) headless
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            while True:
                try:
                    print("Loading page:", track_url)
                    page.goto(track_url, timeout=60000)
                    # wait a bit for JS to render showtimes
                    page.wait_for_timeout(4000)

                    content_lower = page.content().lower()
                    if movie_name not in content_lower:
                        print("Movie not found on page content yet.")
                    else:
                        # locate showtime and screen elements
                        # class names from your site: "sc-yr56qh-1" = show time, "sc-yr56qh-2" = screen label
                        show_locators = page.locator(".sc-yr56qh-1")
                        screen_locators = page.locator(".sc-yr56qh-2")

                        count = show_locators.count()
                        print(f"Found {count} show elements.")
                        matched = False

                        for i in range(count):
                            try:
                                st = show_locators.nth(i).inner_text().strip()
                            except PWTimeoutError:
                                continue
                            if not st:
                                continue
                            # parse time
                            try:
                                show_time = datetime.strptime(st, "%I:%M %p")
                            except:
                                # try alternate formats or skip
                                continue

                            stext = ""
                            if i < screen_locators.count():
                                try:
                                    stext = screen_locators.nth(i).inner_text().strip()
                                except:
                                    stext = ""

                            # check filters
                            if (from_time <= show_time <= to_time) and (not screen_name or screen_name in stext.lower()):
                                matched = True
                                body = f"""
                                <h3>Show found: {data['movie']}</h3>
                                <p><strong>Time:</strong> {st}<br>
                                <strong>Screen:</strong> {stext}<br>
                                <a href="{track_url}">Book Now</a></p>
                                """
                                send_email(notify_email, f"🎟️ {data['movie']} - Show Available", body)
                                print("Match found and email sent; exiting tracker for this job.")
                                break

                        if matched:
                            break
                        else:
                            print("No match yet. Sleeping...")
                    time.sleep(CHECK_INTERVAL)
                except Exception as inner:
                    print("Inner error during check:", inner)
                    time.sleep(60)
        finally:
            try:
                page.close()
                browser.close()
            except:
                pass

@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        data = request.form.to_dict()
        t = threading.Thread(target=start_tracking_background, args=(data,), daemon=True)
        t.start()
        return "<h3>Tracking started in background. You will receive an email when a matching show appears.</h3>"
    return render_template_string(HTML)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
