# GPU RAG-Anything Worker Setup

目标主机：`litangchao@10.26.1.78`

本方案不需要 sudo。GPU 主机已有用户目录 Miniconda，但没有加入 PATH，因此直接使用绝对路径。

## Current State

- RAG-Anything repo: `/home/litangchao/codex-gpu/RAG-Anything`
- Python env: `/home/litangchao/codex-gpu/envs/raganything`
- RAG-Anything version: `1.3.1`
- PyTorch: `2.11.0+cu128`
- CUDA visible from PyTorch: yes
- GPU: 3 x NVIDIA L20
- `pip check`: no broken requirements

## Why This Works Without Sudo

System Python cannot create a normal venv because `ensurepip` is missing, and the user has no sudo permission to install `python3.10-venv`.

The host already has Miniconda under:

```bash
/home/litangchao/miniconda3
```

So the isolated worker environment is created with:

```bash
/home/litangchao/miniconda3/bin/conda create -y \
  -p /home/litangchao/codex-gpu/envs/raganything \
  python=3.10 pip
```

Then install RAG-Anything:

```bash
cd /home/litangchao/codex-gpu/RAG-Anything
/home/litangchao/codex-gpu/envs/raganything/bin/python -m pip install -e .
```

RAG-Anything currently pulls a CUDA 13 PyTorch wheel by default, which is not compatible with the host driver reporting CUDA 12.8. Replace it with cu128 wheels:

```bash
/home/litangchao/codex-gpu/envs/raganything/bin/python -m pip install \
  --force-reinstall \
  --index-url https://download.pytorch.org/whl/cu128 \
  torch torchvision
```

## Verify

```bash
/home/litangchao/codex-gpu/envs/raganything/bin/python - <<'PY'
import torch, raganything
print("raganything", getattr(raganything, "__version__", "unknown"))
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("cuda_version", torch.version.cuda)
print("device_count", torch.cuda.device_count())
print("device0", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")
PY
```

Expected:

```text
raganything 1.3.1
torch 2.11.0+cu128
cuda_available True
cuda_version 12.8
device_count 3
device0 NVIDIA L20
```

## Next Integration Step

Build a small GPU worker API around RAG-Anything:

```text
POST /parse
  file_path or uploaded file
  parser: mineru | docling | paddleocr
  parse_method: auto | ocr | txt

Response:
  content_list
  markdown
  assets
  parse_backend
  gpu_used
```

The local MVP should keep `agent/ingestion/raganything_pipeline.py` as the facade. If the GPU worker is configured, the facade calls the remote worker; otherwise it keeps using the local CPU fallback.
