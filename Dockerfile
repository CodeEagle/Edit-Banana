FROM python:3.11-slim

ARG UPSTREAM_REPO=BIT-DataLab/Edit-Banana
ARG UPSTREAM_REF=0ed16c8
ARG SAM3_REPO=facebookresearch/sam3
ARG SAM3_REF=f6e51f59500a87c576c2df2323ce56b9fd7a12de

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OUTPUT_DIR=/app/output \
    EDIT_BANANA_UPSTREAM_REPO=${UPSTREAM_REPO} \
    EDIT_BANANA_SOURCE_REF=${UPSTREAM_REF} \
    EDIT_BANANA_SAM3_REPO=${SAM3_REPO} \
    EDIT_BANANA_SAM3_REF=${SAM3_REF}

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
    | tar -xz --strip-components=1 -C /app \
    && mkdir -p /tmp/sam3 \
    && curl -fsSL "https://codeload.github.com/${SAM3_REPO}/tar.gz/${SAM3_REF}" \
    | tar -xz --strip-components=1 -C /tmp/sam3 \
    && python - <<'PY'
from pathlib import Path

path = Path("/app/modules/text/ocr/__init__.py")
path.write_text(
    '''"""
OCR sources.

Includes:
    - LocalOCR: local Tesseract OCR
    - Pix2TextOCR: optional Pix2Text formula OCR
    - TextBlock, OCRResult: shared data structures
"""

from .base import TextBlock, OCRResult
from .local_ocr import LocalOCR

try:
    from .pix2text import Pix2TextOCR, Pix2TextBlock, Pix2TextResult
except Exception:
    Pix2TextOCR = None
    Pix2TextBlock = None
    Pix2TextResult = None

__all__ = [
    "TextBlock",
    "OCRResult",
    "LocalOCR",
    "Pix2TextOCR",
    "Pix2TextBlock",
    "Pix2TextResult",
]
''',
    encoding="utf-8",
)
PY

COPY docker/entrypoint.sh /usr/local/bin/lazycat-entrypoint
COPY docker/server_pa.py /app/server_pa.py

RUN chmod +x /usr/local/bin/lazycat-entrypoint \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && python -m pip install /tmp/sam3 \
    && python -m pip install -r requirements.txt python-multipart

EXPOSE 8000

CMD ["lazycat-entrypoint"]
