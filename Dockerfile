# বেস ইমেজ (যেমন পাইথন)
FROM python:3.9-slim

# FFmpeg ইনস্টল করা (সবচেয়ে গুরুত্বপূর্ণ)
RUN apt-get update && apt-get install -y ffmpeg

# ওয়ার্কিং ডিরেক্টরি
WORKDIR /app
COPY . .

# লাইব্রেরি ইনস্টল করা
RUN pip install -r requirements.txt

# বট রান করা
CMD ["python", "main.py"]
