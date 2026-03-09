#!/usr/bin/env python3
"""
LazyCat-friendly FastAPI entrypoint for Edit Banana.

Changes from upstream:
- root page is human-readable
- /convert returns the generated file directly
- model/config validation errors are surfaced as 503
"""

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="Edit Banana API",
    description="Universal Content Re-Editor: image to editable DrawIO XML",
    version="1.0.0",
)


def _load_pipeline():
    from main import Pipeline, load_config

    config = load_config()
    checkpoint_path = config.get("sam3", {}).get("checkpoint_path", "")
    bpe_path = config.get("sam3", {}).get("bpe_path", "")

    if not checkpoint_path or not os.path.exists(checkpoint_path):
        raise HTTPException(
            status_code=503,
            detail=(
                "SAM3 checkpoint is missing. Place the model file at "
                f"{checkpoint_path or '/app/models/sam3.pt'}."
            ),
        )

    if not bpe_path or not os.path.exists(bpe_path):
        raise HTTPException(
            status_code=503,
            detail=(
                "SAM3 BPE file is missing. Place the tokenizer file at "
                f"{bpe_path or '/app/models/bpe_simple_vocab_16e6.txt.gz'}."
            ),
        )

    output_dir = config.get("paths", {}).get("output_dir", "/app/output")
    os.makedirs(output_dir, exist_ok=True)
    return Pipeline(config), output_dir


@app.get("/", response_class=HTMLResponse)
def root():
    upstream_repo = os.environ.get("EDIT_BANANA_UPSTREAM_REPO", "BIT-DataLab/Edit-Banana")
    source_ref = os.environ.get("EDIT_BANANA_SOURCE_REF", "unknown")
    source_url = f"https://github.com/{upstream_repo}/tree/{source_ref}"
    return f"""
    <html>
      <head>
        <title>Edit Banana</title>
        <style>
          body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            max-width: 760px;
            margin: 48px auto;
            padding: 0 20px;
            line-height: 1.6;
            color: #1f2937;
          }}
          code {{
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 6px;
          }}
          a {{
            color: #2563eb;
          }}
        </style>
      </head>
      <body>
        <h1>Edit Banana</h1>
        <p>Upload a diagram image and get an editable <code>.drawio.xml</code> file back.</p>
        <ul>
          <li><a href="/docs">Open Swagger docs</a></li>
          <li><a href="/health">Health check</a></li>
          <li>Mounted model dir: <code>/app/models</code></li>
          <li>Mounted output dir: <code>/app/output</code></li>
          <li>Source snapshot: <a href="{source_url}">{source_ref}</a></li>
        </ul>
      </body>
    </html>
    """


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    name = file.filename or "diagram"
    ext = Path(name).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".pdf", ".bmp", ".tiff", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported format. Use image or PDF.")

    pipeline, output_dir = _load_pipeline()

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result_path = pipeline.process_image(
            tmp_path,
            output_dir=output_dir,
            with_refinement=False,
            with_text=True,
        )
        if not result_path or not os.path.exists(result_path):
            raise HTTPException(status_code=500, detail="Conversion failed.")

        result_file = Path(result_path)
        download_name = result_file.name
        return FileResponse(
            path=result_path,
            media_type="application/xml",
            filename=download_name,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
