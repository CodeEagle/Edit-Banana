#!/usr/bin/env python3
"""
LazyCat-friendly FastAPI entrypoint for Edit Banana.

Changes from upstream:
- root page provides a simple upload UI
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
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          :root {{
            color-scheme: light;
          }}
          body {{
            margin: 0;
            min-height: 100vh;
            font-family: "SF Pro Display", "Helvetica Neue", sans-serif;
            background:
              radial-gradient(circle at top left, rgba(255, 219, 112, 0.4), transparent 28%),
              radial-gradient(circle at bottom right, rgba(176, 224, 230, 0.45), transparent 32%),
              linear-gradient(135deg, #fff7e8 0%, #f8fbff 100%);
            color: #18212f;
          }}
          .shell {{
            max-width: 1040px;
            margin: 0 auto;
            padding: 40px 20px 56px;
          }}
          .hero {{
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 24px;
            align-items: stretch;
          }}
          .panel {{
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(24, 33, 47, 0.08);
            border-radius: 28px;
            box-shadow: 0 20px 60px rgba(24, 33, 47, 0.08);
            backdrop-filter: blur(12px);
          }}
          .intro {{
            padding: 32px;
          }}
          .eyebrow {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 999px;
            background: #fff0c7;
            font-size: 13px;
            font-weight: 600;
            color: #805b00;
          }}
          h1 {{
            margin: 18px 0 14px;
            font-size: clamp(40px, 8vw, 72px);
            line-height: 0.95;
            letter-spacing: -0.05em;
          }}
          p {{
            margin: 0;
            line-height: 1.6;
            color: #445066;
          }}
          .meta {{
            margin-top: 24px;
            display: grid;
            gap: 10px;
            font-size: 14px;
          }}
          .meta strong {{
            color: #18212f;
          }}
          .uploader {{
            padding: 28px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 18px;
          }}
          .dropzone {{
            border: 1.5px dashed rgba(24, 33, 47, 0.16);
            border-radius: 20px;
            padding: 24px;
            background: rgba(248, 251, 255, 0.82);
          }}
          label {{
            display: block;
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 10px;
          }}
          input[type="file"] {{
            display: block;
            width: 100%;
            font-size: 15px;
          }}
          .actions {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
          }}
          button, .link-btn {{
            appearance: none;
            border: 0;
            border-radius: 999px;
            padding: 13px 18px;
            font-size: 14px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
          }}
          button {{
            background: linear-gradient(135deg, #121826 0%, #2e4f7f 100%);
            color: white;
          }}
          button:disabled {{
            opacity: 0.55;
            cursor: wait;
          }}
          .link-btn {{
            background: #eef4ff;
            color: #22477a;
          }}
          a {{
            color: #22477a;
          }}
          .status {{
            min-height: 24px;
            font-size: 14px;
            color: #445066;
          }}
          .status.error {{
            color: #b42318;
          }}
          .status.success {{
            color: #027a48;
          }}
          code {{
            background: rgba(24, 33, 47, 0.06);
            padding: 2px 7px;
            border-radius: 8px;
            font-size: 13px;
          }}
          .notice {{
            margin-top: 24px;
            padding: 16px 18px;
            border-radius: 18px;
            background: rgba(255, 244, 214, 0.9);
            color: #6b4f00;
            font-size: 14px;
          }}
          @media (max-width: 820px) {{
            .hero {{
              grid-template-columns: 1fr;
            }}
            .shell {{
              padding-top: 20px;
            }}
            .intro, .uploader {{
              padding: 22px;
            }}
          }}
        </style>
      </head>
      <body>
        <main class="shell">
          <section class="hero">
            <div class="panel intro">
              <div class="eyebrow">LazyCat build of Edit Banana</div>
              <h1>Edit<br/>Banana</h1>
              <p>This is a migration UI for the open-source API repository, not the upstream hosted demo frontend. Upload one image or PDF and the service will return an editable <code>.drawio.xml</code> file.</p>
              <div class="meta">
                <div><strong>Health:</strong> <a href="/health">/health</a></div>
                <div><strong>API docs:</strong> <a href="/docs">/docs</a></div>
                <div><strong>Source snapshot:</strong> <a href="{source_url}">{source_ref}</a></div>
                <div><strong>Model mount:</strong> <code>/app/models</code></div>
              </div>
              <div class="notice">
                The upstream repository does not ship the polished public web UI shown in its online demo, so this page is a local upload interface added for the LazyCat package.
              </div>
            </div>
            <div class="panel uploader">
              <div class="dropzone">
                <label for="file">Choose a PNG, JPG, PDF, BMP, TIFF, or WEBP file</label>
                <input id="file" type="file" accept=".png,.jpg,.jpeg,.pdf,.bmp,.tiff,.webp" />
              </div>
              <div class="actions">
                <button id="submit" type="button">Convert and download</button>
                <a class="link-btn" href="/docs">Open API docs</a>
              </div>
              <div id="status" class="status">Ready.</div>
            </div>
          </section>
        </main>
        <script>
          const fileInput = document.getElementById("file");
          const submitButton = document.getElementById("submit");
          const statusEl = document.getElementById("status");

          function setStatus(message, kind) {{
            statusEl.textContent = message;
            statusEl.className = "status" + (kind ? " " + kind : "");
          }}

          submitButton.addEventListener("click", async () => {{
            const file = fileInput.files[0];
            if (!file) {{
              setStatus("Select a file first.", "error");
              return;
            }}

            const formData = new FormData();
            formData.append("file", file);

            submitButton.disabled = true;
            setStatus("Uploading and converting. Large files can take a while.", "");

            try {{
              const response = await fetch("/convert", {{
                method: "POST",
                body: formData,
              }});

              if (!response.ok) {{
                let detail = "Conversion failed.";
                try {{
                  const payload = await response.json();
                  detail = payload.detail || detail;
                }} catch (_err) {{
                }}
                throw new Error(detail);
              }}

              const blob = await response.blob();
              const disposition = response.headers.get("content-disposition") || "";
              const match = disposition.match(/filename="?([^"]+)"?/);
              const downloadName = match ? match[1] : "edit-banana-output.drawio.xml";

              const url = window.URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.href = url;
              link.download = downloadName;
              document.body.appendChild(link);
              link.click();
              link.remove();
              window.URL.revokeObjectURL(url);
              setStatus("Conversion finished. Download started.", "success");
            }} catch (error) {{
              setStatus(error.message || "Conversion failed.", "error");
            }} finally {{
              submitButton.disabled = false;
            }}
          }});
        </script>
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
