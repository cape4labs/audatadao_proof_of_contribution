FROM python:3.12-slim

WORKDIR /app

RUN apt update && apt install -y \
    libchromaprint-tools \
    ffmpeg \
    libsndfile1 \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["python", "-m", "my_proof"]
