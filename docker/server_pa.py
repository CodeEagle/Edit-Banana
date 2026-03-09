#!/usr/bin/env python3
"""
LazyCat-friendly FastAPI entrypoint for Edit Banana.

Changes from upstream:
- root page provides a branded upload UI
- /convert returns the generated file directly
- model/config validation errors are surfaced as 503
"""

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="Edit Banana API",
    description="Universal Content Re-Editor: image to editable DrawIO XML",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_ROOT, "static")), name="static")


def _load_pipeline():
    from main import Pipeline, load_config

    config = load_config()
    checkpoint_path = config.get("sam3", {}).get("checkpoint_path", "")
    bpe_path = config.get("sam3", {}).get("bpe_path", "")

    if not checkpoint_path or not os.path.exists(checkpoint_path):
        raise HTTPException(
            status_code=503,
            detail="Model files are not ready yet. Complete initialization and try again.",
        )

    if not bpe_path or not os.path.exists(bpe_path):
        raise HTTPException(
            status_code=503,
            detail="Model files are not ready yet. Complete initialization and try again.",
        )

    output_dir = config.get("paths", {}).get("output_dir", "/app/output")
    os.makedirs(output_dir, exist_ok=True)
    return Pipeline(config), output_dir


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
      <head>
        <title>Edit Banana</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          :root {
            color-scheme: light;
            --banana: #e28709;
            --banana-dark: #c46d00;
            --ink: #24324c;
            --muted: #75839b;
            --card: rgba(249, 247, 241, 0.94);
            --card-border: rgba(226, 210, 173, 0.7);
            --chip: #f5ddb0;
          }
          * {
            box-sizing: border-box;
          }
          body {
            margin: 0;
            min-height: 100vh;
            font-family: "Avenir Next", "Trebuchet MS", "Helvetica Neue", sans-serif;
            background:
              radial-gradient(circle at 18% 20%, rgba(255, 250, 212, 0.7), transparent 24%),
              radial-gradient(circle at 78% 70%, rgba(245, 222, 149, 0.55), transparent 22%),
              linear-gradient(180deg, #efe2b0 0%, #f6efcf 42%, #f2e8bc 100%);
            color: var(--ink);
            overflow-x: hidden;
          }
          body::before,
          body::after {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
          }
          body::before {
            opacity: 0.18;
            background-image:
              radial-gradient(circle at 24% 30%, rgba(255, 255, 255, 0.8) 0, rgba(255, 255, 255, 0) 16%),
              radial-gradient(circle at 76% 18%, rgba(255, 255, 255, 0.64) 0, rgba(255, 255, 255, 0) 13%),
              radial-gradient(circle at 70% 76%, rgba(255, 255, 255, 0.5) 0, rgba(255, 255, 255, 0) 15%);
          }
          body::after {
            opacity: 0.1;
            background:
              linear-gradient(90deg, rgba(255, 255, 255, 0.24) 0 1px, transparent 1px 46px),
              linear-gradient(rgba(255, 255, 255, 0.2) 0 1px, transparent 1px 46px);
            background-size: 46px 46px;
          }
          .shell {
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 42px 18px;
          }
          .panel {
            position: relative;
            width: min(100%, 582px);
            padding: 44px 46px 36px;
            border-radius: 36px;
            border: 1px solid var(--card-border);
            background: var(--card);
            box-shadow:
              0 30px 80px rgba(138, 109, 28, 0.12),
              inset 0 1px 0 rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(12px);
          }
          .stamp {
            position: absolute;
            width: 114px;
            height: 114px;
            border-radius: 999px;
            background: rgba(236, 201, 96, 0.14) url("/static/banana.jpg") center/72% no-repeat;
            opacity: 0.42;
            filter: saturate(0.9);
            pointer-events: none;
          }
          .stamp-left {
            left: 28px;
            bottom: 32px;
          }
          .stamp-right {
            right: 30px;
            top: 66px;
          }
          .brand {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
          }
          .brand img {
            width: 86px;
            height: 86px;
            object-fit: cover;
            border-radius: 999px;
            box-shadow: 0 16px 30px rgba(226, 135, 9, 0.2);
          }
          h1 {
            margin: 0;
            font-size: clamp(34px, 7vw, 58px);
            line-height: 0.96;
            letter-spacing: -0.05em;
            color: var(--banana);
          }
          .tagline {
            position: relative;
            z-index: 1;
            margin: 18px auto 0;
            max-width: 430px;
            text-align: center;
            line-height: 1.45;
            font-size: 17px;
            color: #687894;
          }
          .dropzone {
            position: relative;
            z-index: 1;
            margin-top: 28px;
            border: 2px dashed rgba(226, 135, 9, 0.8);
            border-radius: 28px;
            padding: 38px 24px 32px;
            background: linear-gradient(180deg, rgba(255, 251, 238, 0.88), rgba(250, 241, 212, 0.94));
            text-align: center;
          }
          label {
            cursor: pointer;
          }
          input[type="file"] {
            display: none;
          }
          .upload-button {
            width: 72px;
            height: 72px;
            margin: 0 auto 22px;
            display: grid;
            place-items: center;
            border-radius: 24px;
            background: linear-gradient(180deg, #f2a012, #e18405);
            box-shadow: 0 16px 24px rgba(225, 132, 5, 0.24);
            color: white;
          }
          .upload-button svg {
            width: 32px;
            height: 32px;
          }
          .dropzone h2 {
            margin: 0;
            font-size: clamp(24px, 5vw, 33px);
            line-height: 1.12;
            color: #24324c;
          }
          .dropzone p {
            margin: 10px 0 0;
            font-size: 16px;
            color: #98a3b7;
          }
          .file-name {
            min-height: 20px;
            margin-top: 14px;
            font-size: 14px;
            color: var(--banana-dark);
          }
          .chips {
            margin-top: 18px;
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
          }
          .chip {
            padding: 7px 12px;
            border-radius: 999px;
            background: var(--chip);
            color: var(--banana-dark);
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.06em;
          }
          .actions {
            margin-top: 20px;
            display: flex;
            justify-content: center;
          }
          button {
            appearance: none;
            border: 0;
            border-radius: 999px;
            padding: 15px 28px;
            font-size: 15px;
            font-weight: 800;
            color: white;
            background: linear-gradient(180deg, #f09a0d 0%, #d87d00 100%);
            box-shadow: 0 16px 26px rgba(216, 125, 0, 0.22);
            cursor: pointer;
            transition: transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease;
          }
          button:hover {
            transform: translateY(-1px);
            box-shadow: 0 20px 30px rgba(216, 125, 0, 0.26);
          }
          button:disabled {
            opacity: 0.58;
            cursor: wait;
            transform: none;
          }
          .status {
            margin-top: 24px;
            min-height: 24px;
            text-align: center;
            font-size: 14px;
            color: var(--muted);
          }
          .status.error {
            color: #b54708;
          }
          .status.success {
            color: #2f7f43;
          }
          .feature-grid {
            position: relative;
            z-index: 1;
            margin-top: 24px;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 18px;
          }
          .feature {
            min-height: 72px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 14px 12px;
            border-radius: 18px;
            background: rgba(235, 226, 211, 0.74);
            color: #776d60;
            text-align: center;
            font-weight: 700;
          }
          .feature-badge {
            min-width: 32px;
            height: 32px;
            padding: 0 8px;
            display: grid;
            place-items: center;
            border-radius: 999px;
            background: rgba(226, 135, 9, 0.14);
            color: var(--banana-dark);
            font-size: 11px;
            font-weight: 900;
            letter-spacing: 0.08em;
          }
          .feature-copy {
            line-height: 1.24;
          }
          .assist {
            margin-top: 18px;
            text-align: center;
            font-size: 13px;
            color: #8a95aa;
          }
          .assist strong {
            color: var(--ink);
          }
          @media (max-width: 820px) {
            .panel {
              padding: 34px 22px 26px;
              border-radius: 28px;
            }
            .brand {
              align-items: flex-start;
            }
            .brand img {
              width: 72px;
              height: 72px;
            }
            .feature-grid {
              grid-template-columns: 1fr;
              gap: 12px;
            }
            .stamp {
              width: 88px;
              height: 88px;
            }
          }
        </style>
      </head>
      <body>
        <main class="shell">
          <section class="panel">
            <div class="stamp stamp-left"></div>
            <div class="stamp stamp-right"></div>
            <div class="brand">
              <img src="/static/banana.jpg" alt="Edit Banana logo" />
              <h1>Edit Banana</h1>
            </div>
            <p class="tagline">Transform your images or PDF into editable Draw.io diagrams with AI magic</p>
            <form id="convert-form">
              <div class="dropzone">
                <label for="file">
                  <span class="upload-button" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none">
                      <path d="M12 16V4m0 0-4 4m4-4 4 4M5 14v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"></path>
                    </svg>
                  </span>
                  <h2>Drop your images or PDF here</h2>
                  <p>or click to browse</p>
                </label>
                <input id="file" type="file" accept=".png,.jpg,.jpeg,.pdf,.bmp,.tiff,.webp" />
                <div id="file-name" class="file-name"></div>
                <div class="chips">
                  <span class="chip">JPG</span>
                  <span class="chip">PNG</span>
                  <span class="chip">WEBP</span>
                  <span class="chip">PDF</span>
                </div>
              </div>
              <div class="actions">
                <button id="submit" type="submit">Convert and download</button>
              </div>
              <div id="status" class="status">Ready when you are.</div>
            </form>
            <div class="feature-grid" aria-hidden="true">
              <div class="feature"><span class="feature-badge">AI</span><span class="feature-copy">AI-<br/>Powered</span></div>
              <div class="feature"><span class="feature-badge">ED</span><span class="feature-copy">Fully<br/>Editable</span></div>
              <div class="feature"><span class="feature-badge">IO</span><span class="feature-copy">Export to<br/>Draw.io</span></div>
            </div>
            <div class="assist">Upload one file and the generated <strong>.drawio.xml</strong> download will start automatically.</div>
          </section>
        </main>
        <script>
          const form = document.getElementById("convert-form");
          const fileInput = document.getElementById("file");
          const submitButton = document.getElementById("submit");
          const statusEl = document.getElementById("status");
          const fileNameEl = document.getElementById("file-name");

          function setStatus(message, kind) {
            statusEl.textContent = message;
            statusEl.className = "status" + (kind ? " " + kind : "");
          }

          fileInput.addEventListener("change", () => {
            const file = fileInput.files[0];
            fileNameEl.textContent = file ? `Selected: ${file.name}` : "";
          });

          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const file = fileInput.files[0];
            if (!file) {
              setStatus("Select a file first.", "error");
              return;
            }

            const formData = new FormData();
            formData.append("file", file);

            submitButton.disabled = true;
            setStatus("Uploading and converting. Large files can take a while.", "");

            try {
              const response = await fetch("/convert", {
                method: "POST",
                body: formData,
              });

              if (!response.ok) {
                let detail = "Conversion failed.";
                try {
                  const payload = await response.json();
                  detail = payload.detail || detail;
                } catch (_err) {
                }
                throw new Error(detail);
              }

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
            } catch (error) {
              setStatus(error.message || "Conversion failed.", "error");
            } finally {
              submitButton.disabled = false;
            }
          });
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
        return FileResponse(
            path=result_path,
            media_type="application/xml",
            filename=result_file.name,
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
