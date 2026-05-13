# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment setup

```bash
uv venv -p 3.8
source .venv/bin/activate
uv pip install -e .[dev]
PYTHONPATH=src python -m pytest
```

Python 3.8 is required (`pyproject.toml` pins `>=3.8.0,<3.9.0`). The `.python-version` file pins `3.8.20`.

## Common commands

```bash
# Run all tests (many failures are pre-existing — see docs/FIXME-pytests.md)
PYTHONPATH=src python -m pytest

# Run a single test file
PYTHONPATH=src python -m pytest tests/test_tokenizer.py -v

# Run a single test by name
PYTHONPATH=src python -m pytest tests/test_decoder.py::test_greedy_decode -v

# Inference scoring (runs backward/forward prediction from CLI)
PYTHONPATH=src python src/molbart/inference_score.py

# Start the retrosynthesis FastAPI service locally (UNTESTED! bart_vocab.json likely incopatible with *.ckpt!!!)
CHEMFORMER_MODEL=<path>.ckpt CHEMFORMER_VOCAB=src/molbart/bigmodels/bart_vocab.json \
    uvicorn chemformer.service.retrosynthesis_service:app --port 8080

# Get latent embeddings for a single molecule
PYTHONPATH=src python -m molbart.latent_embeddings_single
```

## Architecture

All source lives under `src/` with two main packages:

**`molbart/`** — core library
- `models/chemformer.py` — the `Chemformer` class: top-level orchestrator for loading checkpoints, building the model, and running `predict()` / `score_model()` / `fine_tune()`. Always instantiated with an `OmegaConf` config loaded from `src/molbart/config/predict.yaml` (or `fine_tune.yaml`, `pretrain.yaml`).
- `models/transformer_models.py` — `BARTModel` and `UnifiedModel` (PyTorch Lightning modules). `BARTModel` is the standard seq2seq backbone; `UnifiedModel` adds property prediction heads.
- `utils/samplers/beam_search_samplers.py` — `BeamSearchSampler` drives inference; calls `beamsearch()` in `beam_search_utils.py`. The `limit` parameter in `beamsearch()` caps generation steps (was 10, now 512).
- `utils/tokenizers.py` — `ChemformerTokenizer` wraps `pysmilesutils.SMILESTokenizer`. Vocabulary loaded from `bart_vocab.json` (523 tokens). Special tokens: `^` (begin), `&` (end), `<PAD>` (0), `?` (unk).
- `data/` — `SynthesisDataModule` for forward/backward prediction; `Uspto50DataModule` for pre-training. Use `reverse=True` on `SynthesisDataModule` for retrosynthesis (backward prediction).
- `config/` — Hydra YAML configs. `predict.yaml` is the entry point for inference.
- `decoder.py`, `tokeniser.py` — pickle compatibility shims for old Figshare checkpoints (map old class names `DecodeSampler`, `MolEncTokeniser` to current locations).
- `latent_embeddings.py`, `latent_embeddings_single.py` — encoder memory extraction (added from prishasatwani upstream).

**`chemformer/`**
- `service/retrosynthesis_service.py` — FastAPI app exposing `POST /retrosynthesis/predict` and `GET /health`. Configured entirely via env vars (`CHEMFORMER_MODEL`, `CHEMFORMER_VOCAB`, `CHEMFORMER_N_BEAMS`, `CHEMFORMER_N_GPUS`). Supports `gs://` URIs for GCS-hosted checkpoints.

**`pysmilesutils/`** — vendored tokenization library (do not modify; upstream is MolecularAI/pysmilesutils).

## Key config values

`src/molbart/config/predict.yaml` controls inference defaults. When using the `Chemformer` class programmatically, override via `OmegaConf`:
```python
cfg = oc.OmegaConf.load(f"{CONFIG_DIR}/predict.yaml")
cfg.task = "backward_prediction"   # or "forward_prediction", "mol_opt"
cfg.model_path = "/path/to/model.ckpt"
cfg.vocabulary_path = "/path/to/bart_vocab.json"
cfg.n_gpus = 0   # CPU inference
cfg.datamodule = None  # required when passing data manually
```

## Checkpoint compatibility

2021 Figshare Astrazenica pretraining checkpoints (e.g. `backward_uspto50k.ckpt`) pickle `molbart.decoder.DecodeSampler` and `molbart.tokeniser.MolEncTokeniser` [sic]. The shim files re-export these from their current locations so `torch.load()` works without errors.

When loading a new checkpoint, run:
```python
model = torch.load("model.ckpt")
model["hyper_parameters"]["vocabulary_size"] = model["hyper_parameters"].pop("vocab_size")
torch.save(model, "model_v2.ckpt")
```

## Known test failures

`tests/test_decoder.py` and `tests/test_round_trip_utils.py` error because `conftest.py` hardcodes `"molbart/config/..."` paths (without `src/` prefix). Run tests from the repo root with `PYTHONPATH=src`. The `decoder_test.py` failures are pre-existing shape mismatches unrelated to recent changes. See `docs/FIXME-pytests.md`.

## Deployment (Google Cloud Run)

```bash
docker build -t gcr.io/PROJECT/chemformer-retrosynthesis:latest .
docker push gcr.io/PROJECT/chemformer-retrosynthesis:latest
gcloud run deploy chemformer-retrosynthesis \
  --image gcr.io/PROJECT/chemformer-retrosynthesis:latest \
  --set-env-vars "CHEMFORMER_MODEL=gs://BUCKET/backward_uspto50k.ckpt,CHEMFORMER_VOCAB=gs://BUCKET/bart_vocab.json"
```

Model files are excluded from the Docker image via `.dockerignore`; supply them via env vars pointing to GCS URIs or local paths.
