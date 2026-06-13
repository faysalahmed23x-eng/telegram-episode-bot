RUN apt-get update && apt-get install -y \
    ffmpeg \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
