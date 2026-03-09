#!/usr/bin/env python3
"""
LazyCat-friendly FastAPI entrypoint for Edit Banana.

Changes from upstream:
- root page provides a branded upload UI
- models can be downloaded on demand after user consent
- /convert returns the generated file directly
- model/config validation errors are surfaced as 503
"""

import os
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_DOWNLOAD_LOCK = threading.Lock()

app = FastAPI(
    title="Edit Banana API",
    description="Universal Content Re-Editor: image to editable DrawIO XML",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_ROOT, "static")), name="static")


def _load_config():
    from main import load_config

    return load_config()


def _model_status():
    config = _load_config()
    checkpoint_path = config.get("sam3", {}).get("checkpoint_path", "")
    bpe_path = config.get("sam3", {}).get("bpe_path", "")
    checkpoint_url = os.environ.get("SAM3_CHECKPOINT_URL", "").strip()
    bpe_url = os.environ.get("SAM3_BPE_URL", "").strip()

    files = [
        {
            "key": "checkpoint",
            "label": "SAM3 checkpoint",
            "path": checkpoint_path or "/app/models/sam3.pt",
            "exists": bool(checkpoint_path and os.path.exists(checkpoint_path)),
            "url_configured": bool(checkpoint_url),
        },
        {
            "key": "tokenizer",
            "label": "Tokenizer",
            "path": bpe_path or "/app/models/bpe_simple_vocab_16e6.txt.gz",
            "exists": bool(bpe_path and os.path.exists(bpe_path)),
            "url_configured": bool(bpe_url),
        },
    ]
    missing = [item["label"] for item in files if not item["exists"]]
    downloadable = all(item["exists"] or item["url_configured"] for item in files)

    return {
        "ready": not missing,
        "missing": missing,
        "downloadable": downloadable,
        "downloading": MODEL_DOWNLOAD_LOCK.locked(),
        "files": files,
    }


def _download_file(target_path: str, source_url: str, label: str) -> None:
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    request = Request(source_url, headers={"User-Agent": "Edit-Banana-LazyCat/1.0"})
    temp_path = f"{target_path}.tmp"

    try:
        with urlopen(request, timeout=300) as response, open(temp_path, "wb") as output_file:
            shutil.copyfileobj(response, output_file)
        os.replace(temp_path, target_path)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=502, detail=f"Failed to download {label}.")


def _ensure_models_downloaded() -> None:
    config = _load_config()
    checkpoint_path = config.get("sam3", {}).get("checkpoint_path", "") or "/app/models/sam3.pt"
    bpe_path = config.get("sam3", {}).get("bpe_path", "") or "/app/models/bpe_simple_vocab_16e6.txt.gz"
    checkpoint_url = os.environ.get("SAM3_CHECKPOINT_URL", "").strip()
    bpe_url = os.environ.get("SAM3_BPE_URL", "").strip()

    if not os.path.exists(checkpoint_path):
        if not checkpoint_url:
            raise HTTPException(
                status_code=400,
                detail="Checkpoint download URL is not configured.",
            )
        _download_file(checkpoint_path, checkpoint_url, "SAM3 checkpoint")

    if not os.path.exists(bpe_path):
        if not bpe_url:
            raise HTTPException(
                status_code=400,
                detail="Tokenizer download URL is not configured.",
            )
        _download_file(bpe_path, bpe_url, "tokenizer")


def _load_pipeline():
    from main import Pipeline

    config = _load_config()
    checkpoint_path = config.get("sam3", {}).get("checkpoint_path", "")
    bpe_path = config.get("sam3", {}).get("bpe_path", "")

    if not checkpoint_path or not os.path.exists(checkpoint_path):
        raise HTTPException(
            status_code=503,
            detail="Model files are not ready yet. Download them from the home page first.",
        )

    if not bpe_path or not os.path.exists(bpe_path):
        raise HTTPException(
            status_code=503,
            detail="Model files are not ready yet. Download them from the home page first.",
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
            --overlay: rgba(25, 22, 16, 0.5);
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
            transition: filter 180ms ease, opacity 180ms ease;
          }
          .panel.blocked {
            filter: blur(4px);
            opacity: 0.55;
            pointer-events: none;
            user-select: none;
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
          .modal {
            position: fixed;
            inset: 0;
            display: none;
            place-items: center;
            padding: 20px;
            background: var(--overlay);
            z-index: 20;
          }
          .modal.visible {
            display: grid;
          }
          .modal-card {
            width: min(100%, 420px);
            padding: 28px 24px;
            border-radius: 28px;
            background: rgba(255, 251, 240, 0.98);
            border: 1px solid rgba(224, 205, 163, 0.92);
            box-shadow: 0 24px 60px rgba(50, 38, 15, 0.22);
          }
          .modal-card h3 {
            margin: 0;
            font-size: 28px;
            line-height: 1.05;
            color: var(--ink);
          }
          .modal-card p {
            margin: 14px 0 0;
            font-size: 15px;
            line-height: 1.55;
            color: #6c7890;
          }
          .modal-card ul {
            margin: 14px 0 0;
            padding-left: 18px;
            color: #6c7890;
            font-size: 14px;
            line-height: 1.5;
          }
          .consent {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            margin-top: 18px;
            padding: 12px 14px;
            border-radius: 16px;
            background: rgba(244, 231, 193, 0.42);
            color: #5d563f;
            font-size: 14px;
          }
          .consent input {
            margin-top: 3px;
          }
          .modal-actions {
            display: flex;
            gap: 12px;
            margin-top: 18px;
          }
          .secondary-button {
            background: rgba(236, 225, 203, 0.95);
            color: #65563d;
            box-shadow: none;
          }
          .modal-note {
            margin-top: 14px;
            min-height: 20px;
            font-size: 13px;
            color: #8b95aa;
          }
          .modal-note.error {
            color: #b54708;
          }
          .modal-note.success {
            color: #2f7f43;
          }
          .hidden {
            display: none;
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
            .modal-actions {
              flex-direction: column;
            }
          }
        </style>
      </head>
      <body>
        <main class="shell">
          <section id="main-panel" class="panel blocked">
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
              <div id="status" class="status">Checking model status...</div>
            </form>
            <div class="feature-grid" aria-hidden="true">
              <div class="feature"><span class="feature-badge">AI</span><span class="feature-copy">AI-<br/>Powered</span></div>
              <div class="feature"><span class="feature-badge">ED</span><span class="feature-copy">Fully<br/>Editable</span></div>
              <div class="feature"><span class="feature-badge">IO</span><span class="feature-copy">Export to<br/>Draw.io</span></div>
            </div>
            <div class="assist">Upload one file and the generated <strong>.drawio.xml</strong> download will start automatically.</div>
          </section>
        </main>

        <div id="model-modal" class="modal visible" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-card">
            <h3 id="modal-title">Prepare model files</h3>
            <p id="modal-body">This app needs model files before it can convert diagrams.</p>
            <ul id="missing-files"></ul>
            <label class="consent" for="consent-checkbox">
              <input id="consent-checkbox" type="checkbox" />
              <span>I agree to download the required model files into this workspace storage.</span>
            </label>
            <div class="modal-actions">
              <button id="download-models" type="button">Download and continue</button>
              <button id="refresh-status" class="secondary-button" type="button">Refresh status</button>
            </div>
            <div id="modal-note" class="modal-note">Waiting for confirmation.</div>
          </div>
        </div>

        <script>
          const form = document.getElementById("convert-form");
          const fileInput = document.getElementById("file");
          const submitButton = document.getElementById("submit");
          const statusEl = document.getElementById("status");
          const fileNameEl = document.getElementById("file-name");
          const mainPanel = document.getElementById("main-panel");
          const modelModal = document.getElementById("model-modal");
          const modalBody = document.getElementById("modal-body");
          const missingFiles = document.getElementById("missing-files");
          const consentCheckbox = document.getElementById("consent-checkbox");
          const downloadButton = document.getElementById("download-models");
          const refreshButton = document.getElementById("refresh-status");
          const modalNote = document.getElementById("modal-note");

          function setStatus(message, kind) {
            statusEl.textContent = message;
            statusEl.className = "status" + (kind ? " " + kind : "");
          }

          function setModalNote(message, kind) {
            modalNote.textContent = message;
            modalNote.className = "modal-note" + (kind ? " " + kind : "");
          }

          function showModal() {
            modelModal.classList.add("visible");
            mainPanel.classList.add("blocked");
          }

          function hideModal() {
            modelModal.classList.remove("visible");
            mainPanel.classList.remove("blocked");
          }

          function renderMissingFiles(items) {
            missingFiles.innerHTML = "";
            items.forEach((item) => {
              const li = document.createElement("li");
              li.textContent = item;
              missingFiles.appendChild(li);
            });
            missingFiles.classList.toggle("hidden", items.length === 0);
          }

          function applyModelState(state) {
            if (state.ready) {
              hideModal();
              submitButton.disabled = false;
              setStatus("Ready when you are.", "");
              return;
            }

            showModal();
            submitButton.disabled = true;
            renderMissingFiles(state.missing || []);

            if (state.downloading) {
              modalBody.textContent = "Model download is already running. This page will unlock once the files are ready.";
              setModalNote("Refreshing status...", "");
              downloadButton.disabled = true;
              refreshButton.disabled = false;
              setStatus("Downloading model files. This can take several minutes.", "");
              return;
            }

            if (!state.downloadable) {
              modalBody.textContent = "The required model files are missing, and download links are not configured yet.";
              setModalNote("Ask the administrator to configure the missing model URL first.", "error");
              downloadButton.disabled = true;
              refreshButton.disabled = false;
              setStatus("Model download is not configured yet.", "error");
              return;
            }

            modalBody.textContent = "This app needs to download the required model files once before it can convert diagrams.";
            downloadButton.disabled = false;
            refreshButton.disabled = false;
            setModalNote("Confirm below to start downloading.", "");
            setStatus("Models are not ready yet.", "");
          }

          async function fetchModelStatus() {
            const response = await fetch("/model-status", { cache: "no-store" });
            if (!response.ok) {
              throw new Error("Failed to read model status.");
            }
            return response.json();
          }

          async function refreshModelStatus() {
            try {
              const state = await fetchModelStatus();
              applyModelState(state);
              return state;
            } catch (error) {
              setModalNote(error.message || "Failed to load model status.", "error");
              setStatus("Unable to load model status.", "error");
              showModal();
              return null;
            }
          }

          fileInput.addEventListener("change", () => {
            const file = fileInput.files[0];
            fileNameEl.textContent = file ? `Selected: ${file.name}` : "";
          });

          refreshButton.addEventListener("click", async () => {
            refreshButton.disabled = true;
            setModalNote("Refreshing status...", "");
            await refreshModelStatus();
            refreshButton.disabled = false;
          });

          downloadButton.addEventListener("click", async () => {
            if (!consentCheckbox.checked) {
              setModalNote("Please confirm the download agreement first.", "error");
              return;
            }

            downloadButton.disabled = true;
            refreshButton.disabled = true;
            setModalNote("Downloading model files. Please keep this page open.", "");
            setStatus("Downloading model files. This can take several minutes.", "");

            try {
              const response = await fetch("/initialize-models", { method: "POST" });
              if (!response.ok) {
                let detail = "Model download failed.";
                try {
                  const payload = await response.json();
                  detail = payload.detail || detail;
                } catch (_err) {
                }
                throw new Error(detail);
              }

              setModalNote("Download complete. Unlocking the upload page.", "success");
              await refreshModelStatus();
            } catch (error) {
              setModalNote(error.message || "Model download failed.", "error");
              setStatus(error.message || "Model download failed.", "error");
              downloadButton.disabled = false;
              refreshButton.disabled = false;
            }
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

          refreshModelStatus();
        </script>
      </body>
    </html>
    """


@app.get("/model-status")
def model_status():
    return _model_status()


@app.post("/initialize-models")
def initialize_models():
    status = _model_status()
    if status["ready"]:
        return {"status": "ok", "ready": True}

    if not status["downloadable"]:
        raise HTTPException(
            status_code=400,
            detail="Model download is not configured yet.",
        )

    if not MODEL_DOWNLOAD_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Model download is already in progress.",
        )

    try:
        _ensure_models_downloaded()
        return {"status": "ok", "ready": True}
    finally:
        MODEL_DOWNLOAD_LOCK.release()


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
