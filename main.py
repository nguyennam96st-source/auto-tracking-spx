import time
import requests
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# ================== CONFIG (ENV VAR) ==================
WEBAPP_BASE = os.getenv("WEBAPP_BASE")
SECRET = os.getenv("SECRET")

if not WEBAPP_BASE or not SECRET:
    raise RuntimeError("❌ Thiếu ENV VAR: WEBAPP_BASE hoặc SECRET")

# ================== CONSTANT ==================
LOOP_MINUTES = 15
REQUEST_DELAY = 1.5
BATCH_LIMIT = 200

# ================== REGEX ==================
ONLY_SPX_RE = re.compile(r"^SPX", re.IGNORECASE)

DELIVERED_RE = re.compile(
    r"Đã giao hàng|Delivered|Giao hàng thành công",
    re.IGNORECASE
)

RETURN_DONE_RE = re.compile(
    r"Trả hàng thành công|Đã trả hàng|Returned|Return completed",
    re.IGNORECASE
)

# ================== LOG ==================
def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

# ================== GOOGLE SHEET ==================
def fetch_list():
    try:
        url = f"{WEBAPP_BASE}?secret={SECRET}"
        r = requests.get(url, timeout=15)
        data = r.json()
        if not data.get("ok"):
            raise Exception(data.get("error"))
        return data.get("data", [])
    except Exception as e:
        log(f"❌ fetch_list error: {e}")
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
        requests.post(WEBAPP_BASE, json=payload, timeout=15)
    except Exception as e:
        log(f"❌ post_result error {tracking}: {e}")

# ================== SCRAPER ==================
def scrape_one(driver, tn):
    try:
        driver.get("https://spx.vn/track?" + tn)
        time.sleep(2.5)

        status = "Không đọc được"
        detail = ""
        body_text = driver.find_element(By.TAG_NAME, "body").text

        try:
            el = driver.find_element(By.CLASS_NAME, "order-status")
            status = el.text.strip().replace("\n", " ")
        except:
            pass

        try:
            timeline = driver.find_element(By.CLASS_NAME, "nss-comp-tracking-content")
            items = timeline.find_elements(By.CSS_SELECTOR, ".nss-comp-tracking-item")
            lines = []
            for i in items:
                txt = " - ".join([x.strip() for x in i.text.split("\n") if x.strip()])
                if txt:
                    lines.append(txt)
            detail = "\n".join(lines)
        except:
            detail = ""

        return status, time.strftime("%H:%M:%S %d/%m/%Y"), detail

    except Exception as e:
        return f"ERR: {e}", time.strftime("%H:%M:%S %d/%m/%Y"), ""

# ================== MAIN LOOP ==================
def main():
    log("🚀 SPX BOT STARTED (KOYEB MODE)")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    try:
        while True:
            log("📥 Fetch danh sách đơn...")
            data = fetch_list()

            if not data:
                log(f"😴 Không có đơn → ngủ {LOOP_MINUTES} phút")
                time.sleep(LOOP_MINUTES * 60)
                continue

            data = data[:BATCH_LIMIT]
            log(f"🔢 Tổng đơn xử lý: {len(data)}")

            for item in data:
                tn = (item.get("tracking") or "").strip()
                row = item.get("row")
                old_status = (item.get("status") or "").strip()

                if not tn or not ONLY_SPX_RE.match(tn):
                    continue

                if DELIVERED_RE.search(old_status) or RETURN_DONE_RE.search(old_status):
                    log(f"⏭️ Skip {tn} | {old_status}")
                    continue

                log(f"🔍 Tracking {tn} (Row {row})")
                status, tstr, detail = scrape_one(driver, tn)
                log(f"➡️ {tn} | {status}")

                post_result(tn, row, status, tstr, detail)
                time.sleep(REQUEST_DELAY)

            log(f"✅ Batch xong → ngủ {LOOP_MINUTES} phút")
            time.sleep(LOOP_MINUTES * 60)

    finally:
        driver.quit()

# ================== ENTRY ==================
if __name__ == "__main__":
    main()
