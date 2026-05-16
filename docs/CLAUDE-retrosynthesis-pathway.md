# Chemformer Retrosynthesis Service — Architecture Reference

## Overview

The system consists of a FastAPI service deployed on Google Cloud Run that exposes
Chemformer BART-based endpoints for retrosynthesis (product → reactants), forward
synthesis (reactants → product), reaction scoring, and molecular embeddings.
Two integration scripts drive automated testing and pathway viability validation.

---

## Cloud Run Deployment

**Project:** `biochem-db-by-hobs`  
**Service:** `chemformer-retrosynthesis`  
**Region:** `us-central1`  
**URL:** `https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app`

**Key settings:**
- Memory: 4 GiB (model loads ~2 GB into RAM)
- CPU: 2 vCPUs
- Timeout: 300 s
- Concurrency: 1 (model inference is not thread-safe)
- Min instances: 0 (scales to zero when idle)

**Model files are NOT baked into the Docker image.** They are downloaded from GCS
at container startup via env vars:

| Env var | Value |
|---|---|
| `CHEMFORMER_MODEL` | `gs://biochem-db-by-hobs/chemformer/retrosynthesis/backward_uspto50k.ckpt` |
| `CHEMFORMER_VOCAB` | `gs://biochem-db-by-hobs/chemformer/retrosynthesis/bart_vocab.json` |
| `CHEMFORMER_MODEL_DIR` | derived from `CHEMFORMER_MODEL` (same GCS prefix) |
| `CHEMFORMER_N_BEAMS` | `10` |
| `CHEMFORMER_N_GPUS` | `0` (CPU inference) |

**Redeploy workflow:**
```bash
docker build -t gcr.io/biochem-db-by-hobs/chemformer-retrosynthesis:latest .
docker push gcr.io/biochem-db-by-hobs/chemformer-retrosynthesis:latest
gcloud run deploy chemformer-retrosynthesis \
  --image gcr.io/biochem-db-by-hobs/chemformer-retrosynthesis:latest \
  --region us-central1 --quiet

# NEW REVISIONS DO NOT AUTO-RECEIVE TRAFFIC — always route manually:
REV=$(gcloud run revisions list --service chemformer-retrosynthesis \
      --region us-central1 --format="value(name)" | head -1)
gcloud run services update-traffic chemformer-retrosynthesis \
  --region us-central1 --to-revisions ${REV}=100
```

---

## API Endpoints

All endpoints live in `src/chemformer/service/retrosynthesis_service.py`.

### Retrosynthesis (product → reactants)

| Method | Path | Description |
|---|---|---|
| POST | `/retrosynthesis/predict` | Default model |
| POST | `/retrosynthesis/{model_name}/predict` | Named model |

**Request:** `{"smiles": "CC(=O)Oc1ccccc1C(=O)O", "n_beams": 10}`  
**Response:** ranked list of `{reaction_smarts, reactants_smiles, log_likelihood}`

### Forward Synthesis (reactants → product)

| Method | Path | Description |
|---|---|---|
| POST | `/synthesis/predict` | Default model |
| POST | `/synthesis/{model_name}/predict` | Named model |

**Request:** `{"smiles": "CC(=O)Cl.O=C(O)c1ccccc1O", "n_beams": 10}`  
Accepts plain reactant SMILES or reaction SMARTS (left side of `>>` is used).  
**Response:** ranked list of `{product_smiles, log_likelihood}`

### Reaction Viability Scoring

| Method | Path | Description |
|---|---|---|
| POST | `/synthesis/score` | Default model |
| POST | `/synthesis/{model_name}/score` | Named model |

**Request:** `{"reaction_smarts": "CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O"}`  
Also accepts a list of SMARTS strings.  
**Response:** `{model_name, scores: [{reaction_smarts, log_likelihood, n_product_tokens}]}`

Scoring uses **teacher-forced decoding**: the known product tokens are fed as
decoder input and the model returns log P(each token | reactants, prior tokens).
Mean per-token log-likelihood is reported. Higher (less negative) = more plausible.

### Molecular Embeddings

| Method | Path | Description |
|---|---|---|
| POST | `/embed/molecule` | Embed SMILES (default model) |
| POST | `/embed/molecule/{model_name}` | Named model |
| POST | `/embed/reaction` | Embed reaction SMARTS (default model) |
| POST | `/embed/reaction/{model_name}` | Named model |

Returns mean-pooled encoder vectors, shape `[n_inputs, 512]`.

### Utility

| Method | Path | Description |
|---|---|---|
| GET | `/models` | List default model, model dir, cached model names |
| GET | `/health` | `{"status": "ok"}` |

---

## Model Loading

Models are lazy-loaded on first request and cached in `_model_cache: Dict[str, Chemformer]`.
At startup, both `backward_uspto50k` and `uspto_50_last_v2` are eagerly pre-loaded
to eliminate cold-start latency on the first real request.

`{model_name}` in path segments maps to `{CHEMFORMER_MODEL_DIR}/{model_name}.ckpt` in GCS.

---

## Beam Search

Retrosynthesis and forward synthesis both use an **adaptive beam limit**:
- Initial limit = `max(64, n_input_tokens × 2)`, capped at 512
- If fewer than 50% of beams produce valid SMILES, limit doubles and retries
- This handles long product SMILES that need more decoder steps to terminate

Key constants in the service:
```python
_BEAM_LIMIT_MIN = 64
_BEAM_LIMIT_INPUT_SCALE = 2.0
_BEAM_LIMIT_MAX = 512
_VALID_SMILES_THRESHOLD = 0.5
```

---

## Integration Test Script: `scripts/integration_test_zydus_queries.py`

Performs recursive retrosynthesis for each molecule in `scripts/zydus_queries.yaml`.

**Algorithm:**
1. For each target molecule, call `POST /retrosynthesis/{model}/predict`
2. For each predicted reactant with MW > `--max-mw` (default 300 Da) and
   log-likelihood > `--min-ll` (default −5.0), recurse (up to `--max-depth`)
3. A **leaf** is a reactant with MW ≤ 300 Da or one that PubChem can identify
4. Extract up to `--max-pathways` complete root-to-leaf paths
5. For each leaf, query PubChem for vendor count (purchasability)
6. Classify pathway quality: `high` (all leaves purchasable), `low` (some missing)

**PubChem caching:**  
Results stored in `src/chemformer/data/pubchem/COMPOUND_CID_{cid}.json` with format:
```json
{"Record": {...}, "_meta": {"vendor_count": N, "bioassay_count": N}}
```
The `_meta` block is required because vendor count comes from a separate
`/xrefs/SourceName` endpoint not included in the main Record blob.

**Output:**  
`src/chemformer/data/zydus_queries_chemformer_recursive_{hash6}.yaml`

**Run:**
```bash
python scripts/integration_test_zydus_queries.py \
  --model backward_uspto50k --n-beams 10 --max-depth 3 \
  --min-ll -5.0 --max-mw 300 --max-pathways 4
```

---

## Validation Script: `scripts/zydus_integration_test_pathway_synthesis_validation.py`

Reads the retrosynthesis YAML output and scores each reaction step in the forward
direction using `POST /synthesis/{model}/score`.

**Algorithm:**
1. Load retrosynthesis YAML (newest matching `zydus_queries_chemformer_recursive_*.yaml`)
2. For each molecule → pathway → step, collect `reaction_smarts`
3. Batch-submit to `/synthesis/score` (one API call per pathway)
4. Compute mean forward log-likelihood per pathway
5. Pick best pathway per molecule (highest mean forward ll)
6. Write scored YAML + Markdown report

**Scoring interpretation:**

| Range | Label |
|---|---|
| > −2.0 | high |
| −2.0 to −5.0 | moderate |
| < −5.0 | low |

**Output:**
- `src/chemformer/data/zydus_synthesis_validation_{hash6}.yaml`
- `docs/zydus_synthesis_validation_report_{date}.md`

**Run:**
```bash
python scripts/zydus_integration_test_pathway_synthesis_validation.py \
  --model backward_uspto50k
```

---

## HTTP Client Notes

The API is served over HTTP/2 on Cloud Run. Python `requests` with a plain integer
`timeout=N` can be defeated by HTTP/2 PING keepalive frames (they reset the socket
timer without delivering data). Always use a tuple:
```python
timeout=(10, 90)  # (connect_timeout_s, read_timeout_s)
```

---

## Known Limitations

- **MW > 600 Da molecules timeout**: CPU beam search does not complete within 90 s
  for long SMILES (Paclitaxel 853 Da, Orforglipron 699 Da). GPU deployment needed.
- **Identity reactions**: Model occasionally emits product SMILES unchanged as
  the "reactant" (log-likelihood ≈ −1.2). Filter with `reactant == product` check.
- **Forward scoring uses the backward model**: `backward_uspto50k` was fine-tuned
  for retrosynthesis but the BART architecture is bidirectional and scores
  P(product|reactants) reasonably. A dedicated forward model would be more accurate.
