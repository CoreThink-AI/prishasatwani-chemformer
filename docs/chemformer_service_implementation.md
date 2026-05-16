# Chemformer Service — Implementation Reference

**Source:** `src/chemformer/service/retrosynthesis_service.py`  
**Live URL:** `https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app`  
**Interactive docs:** [`/docs`](https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app/docs) (Swagger UI) · [`/redoc`](https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app/redoc)

---

## API Endpoints

### Retrosynthesis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/retrosynthesis/predict` | Single-step retrosynthesis (default model) |
| `POST` | `/retrosynthesis/{model_name}/predict` | Single-step retrosynthesis (named checkpoint) |

**Request body** (`RetrosynthesisRequest`):
```json
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "n_beams": 10
}
```
- `smiles` — SMILES of the target product molecule (required)
- `n_beams` — number of beam-search hypotheses to return (1–50, default: `CHEMFORMER_N_BEAMS`)

**Response** (`RetrosynthesisResponse`):
```json
{
  "product_smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "model_name": "uspto_50_last_v2",
  "predictions": [
    {
      "reaction_smarts": "CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O",
      "reactants_smiles": "CC(=O)Cl.O=C(O)c1ccccc1O",
      "log_likelihood": -0.74
    }
  ]
}
```

**Interpreting `log_likelihood`:**

| Range | Confidence |
|-------|-----------|
| > −2  | High — well-represented reaction class in USPTO-50K |
| −2 to −10 | Moderate — plausible but less common |
| < −10 | Low — likely out-of-distribution for this model |

**Internal call chain:**

1. `SynthesisDataModule` is constructed with `reactants=[smiles]`, `products=[smiles]`, `reverse=True` (backward/retrosynthesis mode). Both fields are set to the same product SMILES; the model uses only the encoder input side.
2. `chemformer.model.num_beams` and `n_unique_beams` are set to `n_beams`.
3. `chemformer.predict(dataloader=...)` runs beam search and returns `(sampled_smiles, log_likelihoods, _)`.
4. Each `(reactants, ll)` pair is packaged into a `RetrosynthesisPrediction` with `reaction_smarts = f"{reactants}>>{smiles}"`.

---

### Molecule Embeddings

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/embed/molecule` | Embed one or more molecule SMILES (default model) |
| `POST` | `/embed/molecule/{model_name}` | Embed using a named checkpoint |

**Request body** (`EmbedMoleculeRequest`):
```json
{
  "smiles": ["CC(=O)Oc1ccccc1C(=O)O", "CCO"],
  "pooling": "mean"
}
```
- `smiles` — a single SMILES string or a list of SMILES strings (required)
- `pooling` — `"mean"` (default, recommended) or `"first"`

**Response** (`EmbeddingResponse`):
```json
{
  "model_name": "uspto_50_last_v2",
  "pooling": "mean",
  "d_model": 512,
  "n_inputs": 2,
  "embeddings": [[0.031, -0.14, ...], [0.022, 0.09, ...]]
}
```
- `embeddings` shape: `[n_inputs, d_model]`

**Internal call chain (`_run_embed`):**

1. `BatchEncoder(tokenizer, masker=None, max_seq_len=512)` tokenizes the SMILES list into `encoder_ids` and `encoder_mask`, both shape `[n_tokens, batch_size]`.
2. `chemformer.model.encode({"encoder_input": encoder_ids, "encoder_pad_mask": encoder_mask})` runs the BART encoder; returns `memory` of shape `[n_tokens, batch_size, d_model]`.
3. `memory.permute(1, 0, 2)` reshapes to `[batch_size, n_tokens, d_model]`.
4. **Mean pooling** (`pooling="mean"`): `encoder_mask` (True = padding) is inverted to a float validity mask `[batch, n_tokens, 1]`; the encoder output is masked and summed, then divided by the count of valid tokens. Result shape: `[batch, d_model]`.
5. **First-token pooling** (`pooling="first"`): slices `memory[:, 0, :]`, equivalent to a CLS token. Shape: `[batch, d_model]`.

---

### Reaction Embeddings

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/embed/reaction` | Embed one or more reaction SMARTS (default model) |
| `POST` | `/embed/reaction/{model_name}` | Embed using a named checkpoint |

**Request body** (`EmbedReactionRequest`):
```json
{
  "reaction_smarts": "CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O",
  "encode_side": "reactants",
  "pooling": "mean"
}
```
- `reaction_smarts` — a single `"reactants>>product"` string or a list (required). The `>>` separator is mandatory.
- `encode_side` — `"reactants"` (default, left of `>>`) or `"product"` (right of `>>`)
- `pooling` — `"mean"` (default) or `"first"`

The response format is identical to the molecule embedding response. The `pooling` field in the response is annotated with the encode side, e.g. `"mean (reactants)"`.

**Internal call chain (`_run_embed_reaction`):**

1. Each reaction SMARTS is split on `">>"` (must yield exactly 2 parts; HTTP 422 otherwise).
2. The chosen side (`reactants` or `product`) is extracted as a plain SMILES/dot-SMILES string.
3. The resulting list of SMILES is passed to `_run_embed` — the encoder never sees `>>`, only valid SMILES.

**Choosing `encode_side`:**

| Use case | Recommended `encode_side` |
|---|---|
| Forward synthesis similarity (find reactions with similar starting materials) | `reactants` |
| Retrosynthesis context (cluster products by their synthetic accessibility) | `product` |
| Reaction classification | Either — compare both; `reactants` is more discriminative for reaction type |

---

### Utility Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/models` | List default model, model directory, and cached model names |
| `GET` | `/health` | Health check (`{"status": "ok"}`) — not included in OpenAPI schema |

---

## Model Loading and Caching

```
CHEMFORMER_MODEL=gs://bucket/path/model.ckpt
CHEMFORMER_MODEL_DIR=gs://bucket/path          ← derived automatically if unset
CHEMFORMER_VOCAB=gs://bucket/path/bart_vocab.json
```

At module import time, `_load_model(_DEFAULT_MODEL_NAME)` is called eagerly so the first real request isn't slow. Subsequent models are lazy-loaded on first use.

`_load_model(model_name)`:
1. Returns cached `Chemformer` if already in `_model_cache`.
2. Constructs `model_uri = f"{_MODEL_DIR}/{model_name}.ckpt"`.
3. If `model_uri` starts with `gs://`, `_resolve_path()` downloads it to a temp file via `google-cloud-storage`.
4. Loads `src/molbart/config/predict.yaml` via OmegaConf and overrides: `task="backward_prediction"`, `train_mode="eval"`, `model_type="bart"`, `datamodule=None`, `n_gpus`, `n_beams`, `model_path`, `vocabulary_path`.
5. Instantiates `Chemformer(cfg)` (loads PyTorch checkpoint, builds BART model, attaches tokenizer).
6. Stores in `_model_cache[model_name]` and returns.

**Available checkpoints in `gs://biochem-db-by-hobs/chemformer/retrosynthesis/`:**

| Stem | File | Notes |
|------|------|-------|
| `uspto_50_last_v2` | `uspto_50_last_v2.ckpt` | Fine-tuned on USPTO-50K; **default** |
| `backward_uspto50k` | `backward_uspto50k.ckpt` | AstraZeneca pretrained (2021 Figshare release) |

Both are BART-small (d_model=512, 6 encoder + 6 decoder layers, ~45M parameters).

---

## Tokenizer

`ChemformerTokenizer` wraps `pysmilesutils.SMILESTokenizer`. Vocabulary loaded from `bart_vocab.json` (523 tokens).

| Special token | Symbol | ID |
|---|---|---|
| Begin-of-sequence | `^` | — |
| End-of-sequence | `&` | — |
| Padding | `<PAD>` | 0 |
| Unknown | `?` | — |

`BatchEncoder.__call__(batch, mask=False, add_sep_token=False)`:
- Tokenizes, pads to the longest sequence in the batch.
- Returns `id_tensor: [n_tokens, batch_size]` and `mask_tensor: [n_tokens, batch_size]` (bool, True = padding).
- Truncates to `DEFAULT_MAX_SEQ_LEN = 512` if needed.

---

## Docker Image

**Source:** `Dockerfile` (multi-stage, Python 3.8)

```dockerfile
# ---- build stage ----
FROM python:3.8-slim AS builder
RUN apt-get install -y build-essential curl git libxrender1 libxext6
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN uv venv /venv && uv pip install --python /venv/bin/python --no-cache ".[service]"

# ---- runtime stage ----
FROM python:3.8-slim
RUN useradd --create-home --uid 1000 appuser   # Cloud Run requires non-root
COPY --from=builder /venv /venv
COPY --chown=appuser:appuser src/ ./src/
USER appuser
ENV PATH="/venv/bin:$PATH" PYTHONPATH="/app/src" PYTHONUNBUFFERED=1 CHEMFORMER_N_GPUS=0
CMD ["sh", "-c", "uvicorn chemformer.service.retrosynthesis_service:app \
     --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
```

**`pyproject.toml` `[service]` extras** (the only runtime additions over the base package):
```toml
service = [
    "uvicorn[standard]>=0.22.0",
    "google-cloud-storage>=2.0,<3.0",
]
```

**`.dockerignore`** excludes large data files from the build context:
```
src/chemformer/data/
*.tsv
```
Model checkpoints and vocabulary are **not baked into the image**; they are supplied at runtime via env vars pointing to GCS.

**Build and push:**
```bash
gcloud auth configure-docker --quiet
docker build -t gcr.io/biochem-db-by-hobs/chemformer-retrosynthesis:latest .
docker push gcr.io/biochem-db-by-hobs/chemformer-retrosynthesis:latest
```

---

## Deploying to Google Cloud Run

**Project:** `biochem-db-by-hobs` · **Region:** `us-central1` · **Service:** `chemformer-retrosynthesis`

```bash
gcloud run deploy chemformer-retrosynthesis \
  --image gcr.io/biochem-db-by-hobs/chemformer-retrosynthesis:latest \
  --region us-central1 \
  --platform managed \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 1 \
  --set-env-vars "\
CHEMFORMER_MODEL=gs://biochem-db-by-hobs/chemformer/retrosynthesis/uspto_50_last_v2.ckpt,\
CHEMFORMER_VOCAB=gs://biochem-db-by-hobs/chemformer/retrosynthesis/bart_vocab.json,\
CHEMFORMER_MODEL_DIR=gs://biochem-db-by-hobs/chemformer/retrosynthesis,\
CHEMFORMER_N_BEAMS=10,\
CHEMFORMER_N_GPUS=0" \
  --quiet
```

**Sizing rationale:**

| Setting | Value | Reason |
|---|---|---|
| `--memory 4Gi` | 4 GB | ~537 MB checkpoint → ~2 GB resident RAM under PyTorch; second model doubles that |
| `--cpu 2` | 2 vCPU | CPU-only inference; beam search is sequential but benefits from 2 cores during tokenization |
| `--timeout 300` | 5 min | Beam search on large molecules can exceed 60 s at n_beams=10 on CPU |
| `--concurrency 1` | 1 req | Chemformer inference is not thread-safe; a second request would corrupt in-flight tensors |

**Traffic routing** — Cloud Run sometimes creates a new revision but does not shift traffic automatically. Check and correct:
```bash
# List revisions
gcloud run revisions list --service chemformer-retrosynthesis --region us-central1

# Force 100 % to the latest revision (replace revision name)
gcloud run services update-traffic chemformer-retrosynthesis \
  --region us-central1 \
  --to-revisions chemformer-retrosynthesis-XXXXX-xxx=100
```

**GCS access** — the Cloud Run service account needs Storage Object Viewer:
```bash
PROJECT_NUMBER=$(gcloud projects describe biochem-db-by-hobs --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gsutil iam ch serviceAccount:${SA}:objectViewer gs://biochem-db-by-hobs
```

**Public access** (already configured; verify with):
```bash
gcloud run services get-iam-policy chemformer-retrosynthesis --region us-central1
# Expected: allUsers → roles/run.invoker
```

---

## Checkpoint Compatibility

The 2021 AstraZeneca Figshare checkpoints (`backward_uspto50k.ckpt`) use `vocab_size` in their `hyper_parameters` dict; the current `Chemformer` class expects `vocabulary_size`. Fix before uploading:

```python
import torch
m = torch.load("backward_uspto50k.ckpt", map_location="cpu")
hp = m["hyper_parameters"]
if "vocab_size" in hp and "vocabulary_size" not in hp:
    hp["vocabulary_size"] = hp.pop("vocab_size")
    torch.save(m, "backward_uspto50k_v2.ckpt")
```

The shim files `src/molbart/decoder.py` and `src/molbart/tokeniser.py` handle the pickle-path renames (`molbart.decoder.DecodeSampler` → current location, etc.) so `torch.load()` succeeds without errors.

---

## Local Development

```bash
uv venv -p 3.8 && source .venv/bin/activate
uv pip install -e ".[service]"

CHEMFORMER_MODEL=/path/to/model.ckpt \
CHEMFORMER_VOCAB=src/molbart/bigmodels/bart_vocab.json \
PYTHONPATH=src \
uvicorn chemformer.service.retrosynthesis_service:app --port 8080 --reload
```

Then test:
```bash
# Retrosynthesis
curl -s -X POST http://localhost:8080/retrosynthesis/predict \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CC(=O)Oc1ccccc1C(=O)O", "n_beams": 5}' | python3 -m json.tool

# Molecule embedding (single)
curl -s -X POST http://localhost:8080/embed/molecule \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CC(=O)Oc1ccccc1C(=O)O"}' | python3 -m json.tool

# Molecule embedding (batch)
curl -s -X POST http://localhost:8080/embed/molecule \
  -H "Content-Type: application/json" \
  -d '{"smiles": ["CCO", "CC(=O)O", "c1ccccc1"], "pooling": "mean"}' | python3 -m json.tool

# Reaction embedding (reactants side)
curl -s -X POST http://localhost:8080/embed/reaction \
  -H "Content-Type: application/json" \
  -d '{"reaction_smarts": "CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O",
       "encode_side": "reactants"}' | python3 -m json.tool

# Named model
curl -s -X POST http://localhost:8080/embed/molecule/backward_uspto50k \
  -H "Content-Type: application/json" \
  -d '{"smiles": "CCO"}' | python3 -m json.tool
```
