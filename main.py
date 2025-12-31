import requests, time, re, smtplib, os
from email.mime.text import MIMEText

def get_env(key, default=""):
    return os.getenv(key) or default

self.config = {
    "WEBAPP_BASE": get_env("WEBAPP_BASE"),
    "SECRET": get_env("SECRET"),
    "SENDER_EMAIL": get_env("SENDER_EMAIL"),
    "APP_PASSWORD": get_env("APP_PASSWORD"),
    "RECEIVER_EMAIL": get_env("RECEIVER_EMAIL"),
}

REFUSE_RE = re.compile(
    r"Từ chối nhận hàng|Không liên hệ|Giao hàng không thành công|Khách hàng không nhận",
    re.IGNORECASE
)

def send_mail(subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = GMAIL_USER
    msg["To"] = RECEIVER
    msg["Subject"] = subject

    s = smtplib.SMTP("smtp.gmail.com", 587)
    s.starttls()
    s.login(GMAIL_USER, GMAIL_PASS)
    s.send_message(msg)
    s.quit()

def main():
    print("🚀 SPX Tracker started")

    while True:
        try:
            r = requests.get(
                f"{WEBAPP}?secret={SECRET}",
                timeout=15
            ).json()

            for item in r["data"]:
                if not REFUSE_RE.search(item["history"]):
                    continue

                bl = item["dataBL"]
                body = (
                    "THÔNG TIN ĐƠN HÀNG (B → L)\n\n"
                    f"Ngày: {bl[0]}\n"
                    f"Tên khách: {bl[1]}\n"
                    f"SĐT: {bl[2]}\n"
                    f"Sale: {bl[3]}\n"
                    f"Note: {bl[4]}\n"
                    f"Địa chỉ: {bl[5]}\n"
                    f"Sản phẩm: {bl[6]}\n"
                    f"Thành tiền: {bl[7]}\n"
                    f"Quà tặng: {bl[8]}\n"
                    f"Trạng thái: {bl[9]}\n"
                    f"Mã vận đơn: {bl[10]}\n\n"
                    "---- LỊCH SỬ SPX ----\n"
                    + item["history"]
                )

                send_mail(
                    f"[SPX] ĐƠN BỊ TỪ CHỐI / KHÔNG GIAO ĐƯỢC",
                    body
                )

                requests.post(WEBAPP, json={
                    "secret": SECRET,
                    "row": item["row"],
                    "log": f"MAIL_SENT | {time.strftime('%d/%m/%Y %H:%M')}"
                })

        except Exception as e:
            print("ERR:", e)

        time.sleep(300)  # 5 phút

if __name__ == "__main__":
    main()

