"""FastAPI service for single-step retrosynthesis using Chemformer.

Environment variables:
    CHEMFORMER_MODEL     - default model: local path or gs:// URI to .ckpt file
    CHEMFORMER_MODEL_DIR - GCS prefix for named models (derived from CHEMFORMER_MODEL if unset)
                           e.g. gs://bucket/chemformer/retrosynthesis
    CHEMFORMER_VOCAB     - local path or gs:// URI to bart_vocab.json
    CHEMFORMER_N_BEAMS   - default beam count (default 10)
    CHEMFORMER_N_GPUS    - number of GPUs, default 0 (CPU)
    PORT                 - port to listen on, default 8080 (set by Cloud Run)

Endpoints:
    POST /retrosynthesis/predict                    - uses default model (CHEMFORMER_MODEL)
    POST /retrosynthesis/{model_name}/predict       - lazy-loads {MODEL_DIR}/{model_name}.ckpt

Run locally:
    CHEMFORMER_MODEL=... CHEMFORMER_VOCAB=... uvicorn \\
        chemformer.service.retrosynthesis_service:app --port 8080
"""

import os
import tempfile
from pathlib import PurePosixPath
from typing import Dict, List

import omegaconf as oc
import molbart.utils.data_utils as util
from fastapi import FastAPI, HTTPException
from molbart.constants import CONFIG_DIR
from molbart.data import SynthesisDataModule
from molbart.models import Chemformer
from pydantic import BaseModel, Field


# ── path helpers ─────────────────────────────────────────────────────────────

def _resolve_path(uri: str) -> str:
    """Download a gs:// URI to a temp file and return the local path, or pass through."""
    if not uri.startswith("gs://"):
        return uri
    from google.cloud import storage
    bucket_name, blob_path = uri[5:].split("/", 1)
    suffix = os.path.splitext(blob_path)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    print(f"Downloading {uri} → {tmp.name}")
    storage.Client().bucket(bucket_name).blob(blob_path).download_to_filename(tmp.name)
    return tmp.name


_DEFAULT_MODEL_URI = os.environ["CHEMFORMER_MODEL"]
_VOCAB_PATH = _resolve_path(os.environ["CHEMFORMER_VOCAB"])
_N_GPUS = int(os.environ.get("CHEMFORMER_N_GPUS", "0"))
_N_BEAMS = int(os.environ.get("CHEMFORMER_N_BEAMS", "10"))

# Derive model directory from CHEMFORMER_MODEL if not explicitly set.
# e.g. gs://bucket/chemformer/retrosynthesis/model.ckpt → gs://bucket/chemformer/retrosynthesis
_MODEL_DIR = os.environ.get(
    "CHEMFORMER_MODEL_DIR",
    _DEFAULT_MODEL_URI.rsplit("/", 1)[0],
)
_DEFAULT_MODEL_NAME = PurePosixPath(_DEFAULT_MODEL_URI).stem  # filename without .ckpt


# ── lazy model cache ──────────────────────────────────────────────────────────

_model_cache: Dict[str, Chemformer] = {}


def _load_model(model_name: str) -> Chemformer:
    if model_name in _model_cache:
        return _model_cache[model_name]

    model_uri = f"{_MODEL_DIR}/{model_name}.ckpt"
    print(f"Loading model '{model_name}' from {model_uri}")
    cfg = oc.OmegaConf.load(f"{CONFIG_DIR}/predict.yaml")
    cfg.task = "backward_prediction"
    cfg.train_mode = "eval"
    cfg.model_type = "bart"
    cfg.datamodule = None
    cfg.n_gpus = _N_GPUS
    cfg.n_beams = _N_BEAMS
    cfg.model_path = _resolve_path(model_uri)
    cfg.vocabulary_path = _VOCAB_PATH
    model = Chemformer(cfg)
    _model_cache[model_name] = model
    print(f"Model '{model_name}' loaded and cached.")
    return model


# Eagerly load the default model at startup so the first request isn't slow.
_load_model(_DEFAULT_MODEL_NAME)


# ── FastAPI app ───────────────────────────────────────────────────────────────

_DESCRIPTION = """
Predict synthetic routes for a target molecule using the Chemformer BART model
fine-tuned on USPTO-50K reactions (backward/retrosynthesis prediction).

## Model selection

Use the `{model_name}` path segment to select a checkpoint without redeploying:

| Endpoint | Model |
|----------|-------|
| `POST /retrosynthesis/predict` | default (`CHEMFORMER_MODEL` env var) |
| `POST /retrosynthesis/{model_name}/predict` | `{CHEMFORMER_MODEL_DIR}/{model_name}.ckpt` |

Models are lazy-loaded on first request and cached for subsequent calls.

## Interpreting log-likelihood

| Range | Confidence |
|-------|-----------|
| > −2  | High — well-represented reaction class |
| −2 to −10 | Moderate — plausible but less common |
| < −10 | Low — out-of-distribution for this model |

## Interactive docs
- **Swagger UI**: [`/docs`](/docs)
- **ReDoc**: [`/redoc`](/redoc)
- **OpenAPI JSON**: [`/openapi.json`](/openapi.json)
"""

app = FastAPI(
    title="Chemformer Retrosynthesis",
    version="1.1",
    description=_DESCRIPTION,
    contact={"name": "CoreThink AI", "url": "https://github.com/CoreThink-AI/prishasatwani-chemformer"},
    license_info={"name": "MIT"},
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RetrosynthesisRequest(BaseModel):
    smiles: str = Field(
        ...,
        description="SMILES string of the target product molecule.",
        examples=["CC(=O)Oc1ccccc1C(=O)O"],
    )
    n_beams: int = Field(
        default=_N_BEAMS,
        ge=1,
        le=50,
        description="Number of beam-search hypotheses to return (1–50).",
    )


class RetrosynthesisPrediction(BaseModel):
    reaction_smarts: str = Field(
        description="Full reaction in SMARTS notation: reactants>>product.",
        examples=["CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O"],
    )
    reactants_smiles: str = Field(
        description="Dot-separated SMILES of predicted reactants.",
        examples=["CC(=O)Cl.O=C(O)c1ccccc1O"],
    )
    log_likelihood: float = Field(
        description="Model log-likelihood (higher = more confident). Values above −2 indicate high confidence.",
        examples=[-0.74],
    )


class RetrosynthesisResponse(BaseModel):
    product_smiles: str = Field(description="The input product SMILES, echoed back.")
    model_name: str = Field(description="Name of the checkpoint used for this prediction.")
    predictions: List[RetrosynthesisPrediction] = Field(
        description="Ranked list of retrosynthetic predictions, best first."
    )


# ── shared prediction logic ───────────────────────────────────────────────────

def _run_predict(request: RetrosynthesisRequest, model_name: str) -> RetrosynthesisResponse:
    try:
        chemformer = _load_model(model_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not load model '{model_name}': {exc}")

    datamodule = SynthesisDataModule(
        reactants=[request.smiles],
        products=[request.smiles],
        dataset_path="",
        tokenizer=chemformer.tokenizer,
        batch_size=1,
        max_seq_len=util.DEFAULT_MAX_SEQ_LEN,
        augment_prob=False,
        reverse=True,
    )
    datamodule.setup()

    chemformer.model.num_beams = request.n_beams
    chemformer.model.n_unique_beams = request.n_beams

    sampled_smiles, log_lhs, _ = chemformer.predict(dataloader=datamodule.full_dataloader())

    if not sampled_smiles:
        raise HTTPException(status_code=500, detail="Model returned no predictions.")

    predictions = [
        RetrosynthesisPrediction(
            reaction_smarts=f"{reactants}>>{request.smiles}",
            reactants_smiles=str(reactants),
            log_likelihood=float(lh),
        )
        for reactants, lh in zip(sampled_smiles[0], log_lhs[0])
    ]
    return RetrosynthesisResponse(
        product_smiles=request.smiles,
        model_name=model_name,
        predictions=predictions,
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.post(
    "/retrosynthesis/predict",
    response_model=RetrosynthesisResponse,
    summary="Predict retrosynthetic routes (default model)",
    response_description="Ranked retrosynthetic predictions for the input molecule.",
)
def predict_default(request: RetrosynthesisRequest):
    """Predict using the default checkpoint configured via `CHEMFORMER_MODEL`."""
    return _run_predict(request, _DEFAULT_MODEL_NAME)


@app.post(
    "/retrosynthesis/{model_name}/predict",
    response_model=RetrosynthesisResponse,
    summary="Predict retrosynthetic routes (named model)",
    response_description="Ranked retrosynthetic predictions for the input molecule.",
)
def predict_named(model_name: str, request: RetrosynthesisRequest):
    """Predict using a named checkpoint from `CHEMFORMER_MODEL_DIR`.

    `model_name` is the checkpoint filename stem (without `.ckpt`), e.g.
    `backward_uspto50k` or `uspto_50_last_v2`.
    Models are lazy-loaded on first request and cached in memory.
    """
    return _run_predict(request, model_name)


@app.get("/models", summary="List loaded models")
def list_models():
    """Return the default model name, model directory, and currently cached model names."""
    return {
        "default_model": _DEFAULT_MODEL_NAME,
        "model_dir": _MODEL_DIR,
        "loaded_models": list(_model_cache.keys()),
    }


@app.get("/health", summary="Health check", include_in_schema=False)
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "chemformer.service.retrosynthesis_service:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        log_level="info",
        reload=False,
    )
