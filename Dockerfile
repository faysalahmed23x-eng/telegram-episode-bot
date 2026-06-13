FROM python:3.11-slim

# FFmpeg এবং অন্যান্য টুলস ইনস্টল করুন
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements copy করুন
COPY requirements.txt .

# Dependencies ইনস্টল করুন
RUN pip install --no-cache-dir -r requirements.txt

# সব ফাইল copy করুন
COPY . .

# ডাউনলোড ডিরেক্টরি তৈরি করুন
RUN mkdir -p /app/downloads

# Bot চালু করুন
CMD ["python", "main.py"]
