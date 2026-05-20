FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -e ./PaddleOCR-main \
    && python -m pip install flask gunicorn

EXPOSE 10000

CMD ["sh", "-c", "gunicorn -w 1 -b 0.0.0.0:${PORT:-10000} local_server.app:app"]