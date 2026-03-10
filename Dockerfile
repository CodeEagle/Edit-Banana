FROM python:3.11-slim

ARG UPSTREAM_REPO=BIT-DataLab/Edit-Banana
ARG UPSTREAM_REF=0ed16c8

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OUTPUT_DIR=/app/output \
    EDIT_BANANA_UPSTREAM_REPO=${UPSTREAM_REPO} \
    EDIT_BANANA_SOURCE_REF=${UPSTREAM_REF}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN curl -fsSL "https://codeload.github.com/${UPSTREAM_REPO}/tar.gz/${UPSTREAM_REF}" \
    | tar -xz --strip-components=1 -C /app

COPY docker/entrypoint.sh /usr/local/bin/lazycat-entrypoint
COPY docker/server_pa.py /app/server_pa.py

RUN chmod +x /usr/local/bin/lazycat-entrypoint \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && python -m pip install -r requirements.txt python-multipart

EXPOSE 8000

CMD ["lazycat-entrypoint"]
