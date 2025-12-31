import time
import threading
import requests
import smtplib
import re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask

# ==============================================================================
# 🔴 CẤU HÌNH (SỬA 3 DÒNG NÀY)
# ==============================================================================

# 1. URL WebApp Google Script (Lấy sau khi Deploy code ở trên)
WEBAPP_BASE = "https://script.google.com/macros/s/xxxxxxxxxxxxxxxxx/exec" 

# 2. Email Gmail dùng để gửi (Email Bot)
SMTP_EMAIL = "email_cua_bot@gmail.com"
SMTP_PASS  = "mat_khau_ung_dung_16_ky_tu" 

# 3. Email nhận báo cáo (Email Của Bạn)
RECEIVER_EMAIL = "email_cua_ban@gmail.com"

# ==============================================================================
# CODE XỬ LÝ
# ==============================================================================
LOOP_MINUTES = 15
SECRET_KEY = "VNGEN123"
SPX_PREFIX_RE = re.compile(r"^SPX", re.IGNORECASE)

# TỪ KHÓA BÁO ĐỘNG: Tìm các cụm từ này trong lịch sử
ALERT_REGEX = re.compile(
    r"(từ chối nhận|khách hàng không nhận|refused|cancelled by buyer|không thể liên hệ|giao hàng không thành công|liên hệ người nhận thất bại)", 
    re.IGNORECASE
)

app = Flask(__name__)
@app.route("/")
def health_check(): return "SPX Bot dang chay...", 200

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

class SPXBot:
    def __init__(self):
        self.driver = None

    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

    def init_driver(self):
        self.log("Khoi dong Chrome...")
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=opts)

    # Hàm gửi email
    def send_email_alert(self, tracking, status, detail, raw_data):
        if not SMTP_EMAIL or not SMTP_PASS: return
        try:
            subject = f"🚨 CẢNH BÁO SPX: Đơn {tracking} - {status}"
            body = f"""
            CẢNH BÁO ĐƠN HÀNG CẦN XỬ LÝ
            ==================================
            Mã vận đơn: {tracking}
            Lý do báo động: {status}
            
            CHI TIẾT LỊCH SỬ GIAO HÀNG:
            ----------------------------------
            {detail}
            
            THÔNG TIN ĐƠN TRÊN SHEET:
            ----------------------------------
            {raw_data}
            """
            msg = MIMEMultipart()
            msg['From'] = SMTP_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASS)
            server.send_message(msg)
            server.quit()
            self.log(f"📧 Da gui mail canh bao: {tracking}")
        except Exception as e:
            self.log(f"❌ Loi gui mail: {e}")

    def scrape_spx(self, tracking_code):
        try:
            url = f'https://spx.vn/track?{tracking_code}'
            self.driver.get(url)
            time.sleep(3) 

            status = "Khong lay duoc"
            detail_list = []

            # Lấy trạng thái chính (trên cùng)
            try:
                el = self.driver.find_element(By.CLASS_NAME, "order-status")
                status = el.text.strip().replace('\n', ' ')
            except: pass

            # Lấy danh sách lịch sử (timeline)
            try:
                items = self.driver.find_elements(By.CSS_SELECTOR, ".nss-comp-tracking-item")
                for item in items:
                    txt = item.text.replace("\n", " - ").strip()
                    if txt: detail_list.append(txt)
            except: pass

            full_detail = "\n".join(detail_list)
            return status, full_detail

        except Exception as e:
            return f"Error: {e}", ""

    def run_batch(self):
        self.log("Bat dau quet don...")
        try:
            # Gọi Google Script để lấy danh sách (đã lọc các đơn thành công)
            resp = requests.get(f"{WEBAPP_BASE}?secret={SECRET_KEY}", timeout=15)
            data = resp.json()
            if not data.get('ok'): return
            orders = data.get('data', [])
        except: return

        if not orders: 
            self.log("Khong co don can xu ly (Tat ca da Thanh cong hoac chua co don moi).")
            return

        if not self.driver: self.init_driver()

        for item in orders:
            tn = item.get('tracking')
            row = item.get('row')
            current_note = item.get('current_note')
            full_data = str(item.get('full_data'))

            if not SPX_PREFIX_RE.match(tn): continue

            self.log(f"Check: {tn}")
            new_status, new_detail = self.scrape_spx(tn)

            # --- KIỂM TRA LỖI TRONG LỊCH SỬ ---
            # Soi cả Status chính lẫn Nội dung chi tiết xem có từ khóa "Từ chối", "Không liên lạc được" không
            alert_match = ALERT_REGEX.search(new_detail) or ALERT_REGEX.search(new_status)
            
            note_content = ""
            
            if alert_match:
                reason = alert_match.group(0) # Ví dụ: "Từ chối nhận hàng"
                self.log(f" -> 🚨 PHAT HIEN: {reason}")
                
                # Tạo nội dung ghi chú cột Z
                note_content = f"⚠️ CAN XU LY: {reason} ({datetime.now().strftime('%H:%M %d/%m')})"

                # Nếu cột Z chưa có cảnh báo này thì mới gửi mail (tránh spam)
                if not current_note or "⚠️" not in current_note:
                    self.send_email_alert(tn, reason, new_detail, full_data)
                else:
                    self.log(" -> Da bao mail truoc do roi, bo qua.")
            else:
                self.log(f" -> OK (Dang giao/Thanh cong): {new_status}")

            # Gửi kết quả về Sheet
            try:
                payload = {
                    "secret": SECRET_KEY,
                    "row": row,
                    "tracking": tn,
                    "status": new_status,
                    "detail": new_detail,
                    "time": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                    "note": note_content # Ghi vào cột Z nếu có lỗi
                }
                requests.post(WEBAPP_BASE, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
            except: pass
            
            time.sleep(2) 

        if self.driver:
            self.driver.quit()
            self.driver = None
        self.log("Xong dot quet.")

    def loop(self):
        while True:
            self.run_batch()
            self.log(f"Nghi {LOOP_MINUTES} phut...")
            time.sleep(LOOP_MINUTES * 60)

def start_bot_thread():
    bot = SPXBot()
    t = threading.Thread(target=bot.loop, daemon=True)
    t.start()

if __name__ == "__main__":
    start_bot_thread()
    app.run(host="0.0.0.0", port=8000)
