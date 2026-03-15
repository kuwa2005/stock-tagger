# Stock Image Auto Tagger
# Florence-2 + FastAPI
# PyTorch + CUDA 済みベースイメージ
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY ram/ ./ram/

EXPOSE 7861

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7861"]
