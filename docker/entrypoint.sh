#!/bin/sh
set -eu

mkdir -p /app/config /app/models "${OUTPUT_DIR:-/app/output}"

download_if_missing() {
  target_path="$1"
  source_url="$2"
  label="$3"

  if [ -f "$target_path" ] || [ -z "$source_url" ]; then
    return 0
  fi

  echo "Downloading missing ${label}..."
  curl -fL --retry 3 --retry-delay 2 -o "${target_path}.tmp" "$source_url"
  mv "${target_path}.tmp" "$target_path"
}

download_if_missing "${SAM3_CHECKPOINT_PATH:-/app/models/sam3.pt}" "${SAM3_CHECKPOINT_URL:-}" "SAM3 checkpoint"
download_if_missing "${SAM3_BPE_PATH:-/app/models/bpe_simple_vocab_16e6.txt.gz}" "${SAM3_BPE_URL:-}" "SAM3 tokenizer"

cat > /app/config/config.yaml <<EOF
sam3:
  checkpoint_path: "${SAM3_CHECKPOINT_PATH:-/app/models/sam3.pt}"
  bpe_path: "${SAM3_BPE_PATH:-/app/models/bpe_simple_vocab_16e6.txt.gz}"
  score_threshold: 0.5
  epsilon_factor: 0.02
  min_area: 100

prompt_groups:
  image:
    name: image
    score_threshold: 0.5
    min_area: 100
    priority: 2
  arrow:
    name: arrow
    score_threshold: 0.45
    min_area: 50
    priority: 4
  shape:
    name: shape
    score_threshold: 0.5
    min_area: 200
    priority: 3
  background:
    name: background
    score_threshold: 0.25
    min_area: 500
    priority: 1

multimodal:
  mode: "${MULTIMODAL_MODE:-api}"
  api_key: "${MULTIMODAL_API_KEY:-}"
  base_url: "${MULTIMODAL_BASE_URL:-}"
  model: "${MULTIMODAL_MODEL:-}"
  local_base_url: "${MULTIMODAL_LOCAL_BASE_URL:-http://localhost:11434/v1}"
  local_api_key: "${MULTIMODAL_LOCAL_API_KEY:-ollama}"
  local_model: "${MULTIMODAL_LOCAL_MODEL:-}"
  force_vlm_ocr: ${MULTIMODAL_FORCE_VLM_OCR:-false}
  max_tokens: ${MULTIMODAL_MAX_TOKENS:-4000}
  timeout: ${MULTIMODAL_TIMEOUT:-60}
  ca_cert_path: "${MULTIMODAL_CA_CERT_PATH:-}"
  proxy: "${MULTIMODAL_PROXY:-}"

paths:
  output_dir: "${OUTPUT_DIR:-/app/output}"
EOF

exec uvicorn server_pa:app --host 0.0.0.0 --port "${PORT:-8000}"
