import time
import requests
import re
import os
import smtplib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ================== REGEX RULE ==================
SPX_ONLY_RE = re.compile(r"^SPX", re.IGNORECASE)

DELIVERED_RE = re.compile(
    r"Đã giao hàng|Delivered|Giao hàng thành công",
    re.IGNORECASE
)

RETURN_DONE_RE = re.compile(
    r"Trả hàng thành công|Đã trả hàng|Returned|Return completed",
    re.IGNORECASE
)

REFUSED_RE = re.compile(
    r"Từ chối nhận hàng|Khách hàng không nhận|Refused|Cancelled by buyer",
    re.IGNORECASE
)

# ================== ENV CONFIG ==================
WEBAPP_BASE = os.getenv("WEBAPP_BASE")
SECRET = os.getenv("SECRET")

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "15"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.5"))
BATCH_LIMIT = int(os.getenv("BATCH_LIMIT", "200"))

# ================== EMAIL ==================
def send_email(tracking, status, detail):
    if not all([SENDER_EMAIL, APP_PASSWORD, RECEIVER_EMAIL]):
        print("⚠️ Email config missing – skip sending mail")
        return

    try:
        subject = f"[SPX ALERT] Đơn {tracking} bị TỪ CHỐI / TRẢ HÀNG"
        body = f"""
Mã vận đơn: {tracking}

Trạng thái: {status}

Lịch sử:
{detail}

-- SPX Tracker (Koyeb)
"""

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"📧 Sent email for {tracking}")

    except Exception as e:
        print(f"❌ Email error: {e}")

# ================== GOOGLE SCRIPT ==================
def fetch_list():
    try:
        url = f"{WEBAPP_BASE}?secret={SECRET}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if not data.get("ok"):
            raise Exception(data.get("error"))
        return data.get("data", [])
    except Exception as e:
        print(f"❌ Fetch error: {e}")
        return []

def post_result(tracking, row, status, time_str, detail):
    try:
        payload = {
            "secret": SECRET,
            "tracking": tracking,
            "row": row,
            "status": status,
            "time": time_str,
            "detail": detail
        }
        requests.post(WEBAPP_BASE, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Post error: {e}")

# ================== SCRAPER ==================
def scrape_one(driver, tn):
    driver.get("https://spx.vn/track?" + tn)
    time.sleep(2.5)

    status = "Không đọc được"
    detail = ""
    body = driver.find_element(By.TAG_NAME, "body").text

    try:
        status_el = driver.find_element(By.CLASS_NAME, "order-status")
        status = status_el.text.replace("\n", " ").strip()
    except:
        pass

    try:
        timeline = driver.find_element(By.CLASS_NAME, "nss-comp-tracking-content")
        items = timeline.find_elements(By.CSS_SELECTOR, ".nss-comp-tracking-item")
        lines = []
        for i in items:
            raw = [x.strip() for x in i.text.split("\n") if x.strip()]
            if len(raw) >= 3:
                lines.append(f"{raw[0]} - {raw[1]} - {' '.join(raw[2:])}")
            else:
                lines.append(" - ".join(raw))
        detail = "\n".join(lines)
    except:
        pass

    return status, time.strftime("%H:%M:%S %d/%m/%Y"), detail

# ================== MAIN LOOP ==================
def main():
    print("🚀 SPX Tracker started on Koyeb")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 🚨 QUAN TRỌNG: chỉ rõ đường dẫn Chrome trên Koyeb
    chrome_options.binary_location = "/usr/bin/chromium"
    
    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"),
        options=chrome_options
    )


    while True:
        data = fetch_list()

        for item in data[:BATCH_LIMIT]:
            tn = (item.get("tracking") or "").strip()
            row = item.get("row")
            old_status = (item.get("status") or "").strip()

            if not SPX_ONLY_RE.match(tn):
                continue

            if DELIVERED_RE.search(old_status) or RETURN_DONE_RE.search(old_status):
                continue

            print(f"🔍 Tracking {tn}")

            status, time_val, detail = scrape_one(driver, tn)
            print(f"→ {status}")

            if REFUSED_RE.search(status):
                send_email(tn, status, detail)

            post_result(tn, row, status, time_val, detail)
            time.sleep(REQUEST_DELAY)

        print(f"⏳ Sleep {LOOP_MINUTES} minutes")
        time.sleep(LOOP_MINUTES * 60)

if __name__ == "__main__":
    main()

