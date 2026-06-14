# বেস ইমেজ (যেমন পাইথন)
FROM python:3.9-slim

# FFmpeg এবং অন্যান্য টুলস ইনস্টল করা
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# yt-dlp ইনস্টল করা
RUN pip install --no-cache-dir yt-dlp

# ওয়ার্কিং ডিরেক্টরি
WORKDIR /app
COPY . .

# লাইব্রেরি ইনস্টল করা
RUN pip install --no-cache-dir -r requirements.txt

# বট রান করা
CMD ["python", "main.py"]
