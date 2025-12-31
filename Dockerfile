# Sử dụng Python 3.9 slim để nhẹ
FROM python:3.9-slim

# Cài đặt các gói hệ thống cần thiết cho Chrome và Python
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    --no-install-recommends

# Cài đặt Google Chrome (Stable)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy requirements và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào
COPY . .

# Mở port 8000 (Bắt buộc cho Koyeb)
EXPOSE 8000

# Chạy lệnh khởi động
CMD ["python", "main.py"]
