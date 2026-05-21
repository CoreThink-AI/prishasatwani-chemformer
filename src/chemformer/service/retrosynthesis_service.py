"""FastAPI service for single-step retrosynthesis and molecular embeddings using Chemformer.

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
    POST /synthesis/predict                         - forward synthesis (default model)
    POST /synthesis/{model_name}/predict            - forward synthesis (named model)
    POST /synthesis/score                           - score reaction viability (default model)
    POST /synthesis/{model_name}/score              - score reaction viability (named model)
    POST /embed/molecule                            - embed one or more molecule SMILES
    POST /embed/molecule/{model_name}               - embed using a named checkpoint
    POST /embed/reaction                            - embed one or more reaction SMARTS
    POST /embed/reaction/{model_name}               - embed using a named checkpoint

Run locally:
    CHEMFORMER_MODEL=... CHEMFORMER_VOCAB=... uvicorn \\
        chemformer.service.retrosynthesis_service:app --port 8080
"""

import os
import tempfile
from pathlib import PurePosixPath
from typing import Dict, List, Union

import omegaconf as oc
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rdkit import Chem

import molbart.utils.data_utils as util
from molbart.constants import CONFIG_DIR
from molbart.data.util import BatchEncoder
from molbart.models import Chemformer

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


# Eagerly load all known models at startup to eliminate cold-start latency on first request.
_load_model(_DEFAULT_MODEL_NAME)
for _preload_name in ("backward_uspto50k", "uspto_50_last_v2"):
    if _preload_name != _DEFAULT_MODEL_NAME:
        try:
            _load_model(_preload_name)
        except Exception as _e:
            print(f"Warning: could not pre-load '{_preload_name}': {_e}")


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


class SynthesisRequest(BaseModel):
    smiles: str = Field(
        ...,
        description=(
            "Reactants SMILES (dot-separated) or reaction SMARTS `reactants>>`. "
            "If `>>` is present only the left side is used as encoder input."
        ),
        examples=["CC(=O)Cl.O=C(O)c1ccccc1O"],
    )
    n_beams: int = Field(
        default=_N_BEAMS,
        ge=1,
        le=50,
        description="Number of beam-search hypotheses to return (1–50).",
    )


class SynthesisPrediction(BaseModel):
    product_smiles: str = Field(description="Predicted product SMILES.")
    log_likelihood: float = Field(description="Model log-likelihood (higher = more confident).")


class SynthesisResponse(BaseModel):
    reactants_smiles: str = Field(description="Input reactants SMILES, echoed back.")
    model_name: str = Field(description="Checkpoint used.")
    predictions: List[SynthesisPrediction] = Field(
        description="Ranked list of predicted products, best first."
    )


class SynthesisScoreRequest(BaseModel):
    reaction_smarts: Union[str, List[str]] = Field(
        ...,
        description=(
            "One reaction SMARTS string or a list, in `reactants>>product` format. "
            "The model scores how likely the product is given the reactants."
        ),
        examples=["CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O"],
    )


class SynthesisScoreResult(BaseModel):
    reaction_smarts: str = Field(description="The scored reaction, echoed back.")
    log_likelihood: float = Field(
        description=(
            "Mean per-token log-likelihood of the product sequence given the reactants "
            "(teacher-forcing). Higher (less negative) = model considers the reaction more plausible."
        )
    )
    n_product_tokens: int = Field(description="Number of product tokens scored (excludes padding).")


class SynthesisScoreResponse(BaseModel):
    model_name: str = Field(description="Checkpoint used.")
    scores: List[SynthesisScoreResult] = Field(
        description="One score entry per input reaction."
    )


class EmbedMoleculeRequest(BaseModel):
    smiles: Union[str, List[str]] = Field(
        ...,
        description="One molecule SMILES or a list of SMILES to embed.",
        examples=["CC(=O)Oc1ccccc1C(=O)O"],
    )
    pooling: str = Field(
        default="mean",
        description=(
            "How to pool token-level encoder outputs into a single vector per molecule. "
            "`mean` averages over non-padding tokens (recommended for similarity/clustering); "
            "`first` returns the first (begin-of-sequence) token only."
        ),
    )


class EmbedReactionRequest(BaseModel):
    reaction_smarts: Union[str, List[str]] = Field(
        ...,
        description=(
            "One reaction SMARTS string or a list of them, in the format "
            "`reactants>>product`. The `>>` separator is required."
        ),
        examples=["CC(=O)Cl.O=C(O)c1ccccc1O>>CC(=O)Oc1ccccc1C(=O)O"],
    )
    encode_side: str = Field(
        default="reactants",
        description=(
            "Which side of the reaction to encode: `reactants` (left of `>>`) "
            "or `product` (right of `>>`). "
            "Use `reactants` for forward-synthesis context; `product` for retrosynthesis context."
        ),
    )
    pooling: str = Field(
        default="mean",
        description="Pooling strategy: `mean` (recommended) or `first`.",
    )


class EmbeddingResponse(BaseModel):
    model_name: str = Field(description="Checkpoint used for encoding.")
    pooling: str = Field(description="Pooling strategy applied.")
    d_model: int = Field(description="Embedding dimensionality (512 for BART-small).")
    n_inputs: int = Field(description="Number of inputs embedded.")
    embeddings: List[List[float]] = Field(
        description=(
            "Embeddings as a list of vectors, one per input. "
            "Shape: [n_inputs, d_model]."
        )
    )


# ── shared embedding logic ────────────────────────────────────────────────────

def _run_embed(smiles_list: List[str], model_name: str, pooling: str) -> EmbeddingResponse:
    """Encode a list of SMILES through the Chemformer encoder and pool the result."""
    if pooling not in ("mean", "first"):
        raise HTTPException(status_code=422, detail=f"Unknown pooling '{pooling}'. Use 'mean' or 'first'.")

    try:
        chemformer = _load_model(model_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not load model '{model_name}': {exc}")

    encoder = BatchEncoder(
        tokenizer=chemformer.tokenizer,
        masker=None,
        max_seq_len=util.DEFAULT_MAX_SEQ_LEN,
    )

    # encoder_ids, encoder_mask: [n_tokens, batch_size]
    encoder_ids, encoder_mask = encoder(smiles_list, mask=False, add_sep_token=False)
    encoder_ids = encoder_ids.to(chemformer.device)
    encoder_mask = encoder_mask.to(chemformer.device)

    with torch.no_grad():
        # memory: [n_tokens, batch_size, d_model]
        memory = chemformer.model.encode(
            {"encoder_input": encoder_ids, "encoder_pad_mask": encoder_mask}
        )
        # Reshape to [batch_size, n_tokens, d_model]
        memory = memory.permute(1, 0, 2)

    d_model = memory.shape[2]

    if pooling == "mean":
        # Average over non-padding positions; encoder_mask True = padding
        valid = (~encoder_mask.permute(1, 0)).float().unsqueeze(-1)  # [batch, n_tokens, 1]
        pooled = (memory * valid).sum(dim=1) / valid.sum(dim=1).clamp(min=1)  # [batch, d_model]
        embeddings = pooled.cpu().tolist()
    else:  # "first"
        embeddings = memory[:, 0, :].cpu().tolist()

    return EmbeddingResponse(
        model_name=model_name,
        pooling=pooling,
        d_model=d_model,
        n_inputs=len(smiles_list),
        embeddings=embeddings,
    )


def _run_embed_reaction(
    smarts_list: List[str],
    model_name: str,
    encode_side: str,
    pooling: str,
) -> EmbeddingResponse:
    """Split reaction SMARTS on '>>' and embed the chosen side."""
    if encode_side not in ("reactants", "product"):
        raise HTTPException(
            status_code=422,
            detail=f"Unknown encode_side '{encode_side}'. Use 'reactants' or 'product'.",
        )

    parsed = []
    for rxn in smarts_list:
        parts = rxn.split(">>")
        if len(parts) != 2:
            raise HTTPException(
                status_code=422,
                detail=f"Reaction must contain exactly one '>>' separator: {rxn[:80]}",
            )
        parsed.append(parts[0].strip() if encode_side == "reactants" else parts[1].strip())

    result = _run_embed(parsed, model_name, pooling)
    result.pooling = f"{pooling} ({encode_side})"
    return result


# ── shared synthesis (forward) logic ─────────────────────────────────────────

def _run_score_reactions(smarts_list: List[str], model_name: str) -> SynthesisScoreResponse:
    """Score reactions via teacher-forced decoder: returns per-token mean log-likelihood."""
    try:
        chemformer = _load_model(model_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not load model '{model_name}': {exc}")

    encoder = BatchEncoder(
        tokenizer=chemformer.tokenizer,
        masker=None,
        max_seq_len=util.DEFAULT_MAX_SEQ_LEN,
    )
    chemformer.model.to(chemformer.device)
    chemformer.model.eval()

    results = []
    for smarts in smarts_list:
        parts = smarts.split(">>")
        if len(parts) != 2:
            raise HTTPException(
                status_code=422,
                detail=f"Reaction must contain exactly one '>>' separator: {smarts[:80]}",
            )
        reactants, product = parts[0].strip(), parts[1].strip()

        enc_ids, enc_mask = encoder([reactants], mask=False, add_sep_token=False)
        dec_ids, dec_mask = encoder([product], mask=False, add_sep_token=False)

        enc_ids = enc_ids.to(chemformer.device)
        enc_mask = enc_mask.to(chemformer.device)
        dec_ids = dec_ids.to(chemformer.device)
        dec_mask = dec_mask.to(chemformer.device)

        # encode() returns [src_len, batch, d_model]
        with torch.no_grad():
            memory = chemformer.model.encode(
                {"encoder_input": enc_ids, "encoder_pad_mask": enc_mask}
            )
            # decode_batch expects: decoder_input [batch, tgt_len], memory_input [batch, src, d_model]
            token_log_probs = chemformer.model.decode_batch(
                {
                    "decoder_input": dec_ids.transpose(0, 1),          # [1, tgt_len]
                    "memory_input": memory.permute(1, 0, 2),            # [1, src_len, d_model]
                    "memory_pad_mask": enc_mask.transpose(0, 1),        # [1, src_len]
                },
                return_last=False,
            )  # → [tgt_len, 1, vocab_size]

        # Sum log P(token[i+1] | tokens[:i+1]) for non-padding positions
        tgt_len = dec_ids.shape[0]
        total_ll = 0.0
        n_tokens = 0
        for i in range(tgt_len - 1):
            if dec_mask[i + 1, 0].item():  # padding starts here
                break
            next_tok = dec_ids[i + 1, 0].item()
            total_ll += token_log_probs[i, 0, next_tok].item()
            n_tokens += 1

        mean_ll = total_ll / max(n_tokens, 1)
        results.append(SynthesisScoreResult(
            reaction_smarts=smarts,
            log_likelihood=round(mean_ll, 6),
            n_product_tokens=n_tokens,
        ))

    return SynthesisScoreResponse(model_name=model_name, scores=results)


def _run_synthesis(request: SynthesisRequest, model_name: str) -> SynthesisResponse:
    """Forward synthesis: encode reactants, beam-search decode predicted products."""
    try:
        chemformer = _load_model(model_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not load model '{model_name}': {exc}")

    # Accept either plain reactants SMILES or reaction SMARTS (use left side only)
    reactants = request.smiles.split(">>")[0].strip()

    encoder = BatchEncoder(
        tokenizer=chemformer.tokenizer,
        masker=None,
        max_seq_len=util.DEFAULT_MAX_SEQ_LEN,
    )
    encoder_ids, encoder_mask = encoder([reactants], mask=False, add_sep_token=False)
    batch = {
        "encoder_input": encoder_ids.to(chemformer.device),
        "encoder_pad_mask": encoder_mask.to(chemformer.device),
        "target_smiles": [reactants],
    }

    chemformer.model.num_beams = request.n_beams
    chemformer.model.n_unique_beams = request.n_beams
    chemformer.model.to(chemformer.device)
    chemformer.model.eval()

    n_input_tokens = int(encoder_ids.shape[0])
    limit = min(max(_BEAM_LIMIT_MIN, int(n_input_tokens * _BEAM_LIMIT_INPUT_SCALE)), _BEAM_LIMIT_MAX)

    sampler = chemformer.model.sampler
    while True:
        with torch.no_grad():
            smiles_batch, log_lhs_batch = chemformer.model.sample_molecules(
                batch, sampling_alg="beam", limit=limit,
            )
        if getattr(sampler, "sample_unique", False):
            smiles_batch = sampler.smiles_unique
            log_lhs_batch = sampler.log_lhs_unique

        n_beams = len(smiles_batch[0]) if len(smiles_batch) else 0
        n_valid = _count_valid(smiles_batch[0]) if n_beams else 0
        if n_beams == 0 or n_valid / n_beams >= _VALID_SMILES_THRESHOLD or limit >= _BEAM_LIMIT_MAX:
            break
        limit = min(limit * 2, _BEAM_LIMIT_MAX)
        print(f"Retrying synthesis beam search with limit={limit} ({n_valid}/{n_beams} valid)")

    if not len(smiles_batch) or not len(smiles_batch[0]):
        raise HTTPException(status_code=500, detail="Model returned no predictions.")

    predictions = [
        SynthesisPrediction(product_smiles=str(smi), log_likelihood=float(lh))
        for smi, lh in zip(smiles_batch[0], log_lhs_batch[0])
    ]
    return SynthesisResponse(
        reactants_smiles=reactants,
        model_name=model_name,
        predictions=predictions,
    )


# ── shared prediction logic ───────────────────────────────────────────────────

_BEAM_LIMIT_MIN = 64       # floor: never go below this
_BEAM_LIMIT_INPUT_SCALE = 2.0  # initial limit = input_tokens * this factor
_BEAM_LIMIT_MAX = 512      # hard ceiling for retries
_VALID_SMILES_THRESHOLD = 0.5  # retry if fewer than this fraction of beams are valid SMILES


def _count_valid(smiles_arr) -> int:
    """Count dot-separated reactant strings that are all valid SMILES."""
    count = 0
    for entry in smiles_arr:
        parts = str(entry).split(".")
        if all(Chem.MolFromSmiles(p) is not None for p in parts if p):
            count += 1
    return count


def _run_predict(request: RetrosynthesisRequest, model_name: str) -> RetrosynthesisResponse:
    try:
        chemformer = _load_model(model_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not load model '{model_name}': {exc}")

    # Build encoder batch directly — avoids SynthesisDataModule setup overhead (~300 ms/req)
    encoder = BatchEncoder(
        tokenizer=chemformer.tokenizer,
        masker=None,
        max_seq_len=util.DEFAULT_MAX_SEQ_LEN,
    )
    encoder_ids, encoder_mask = encoder([request.smiles], mask=False, add_sep_token=False)
    batch = {
        "encoder_input": encoder_ids.to(chemformer.device),
        "encoder_pad_mask": encoder_mask.to(chemformer.device),
        "target_smiles": [request.smiles],
    }

    chemformer.model.num_beams = request.n_beams
    chemformer.model.n_unique_beams = request.n_beams
    chemformer.model.to(chemformer.device)
    chemformer.model.eval()

    # Proactive: scale initial limit to input token length so long products get enough steps
    n_input_tokens = int(encoder_ids.shape[0])
    limit = max(_BEAM_LIMIT_MIN, int(n_input_tokens * _BEAM_LIMIT_INPUT_SCALE))
    limit = min(limit, _BEAM_LIMIT_MAX)

    sampler = chemformer.model.sampler
    smiles_batch = log_lhs_batch = None

    while True:
        with torch.no_grad():
            smiles_batch, log_lhs_batch = chemformer.model.sample_molecules(
                batch, sampling_alg="beam", limit=limit,
            )
        if getattr(sampler, "sample_unique", False):
            smiles_batch = sampler.smiles_unique
            log_lhs_batch = sampler.log_lhs_unique

        # Reactive: if too many outputs are truncated/invalid, double the limit and retry
        n_beams = len(smiles_batch[0]) if len(smiles_batch) else 0
        n_valid = _count_valid(smiles_batch[0]) if n_beams else 0
        if n_beams == 0 or n_valid / n_beams >= _VALID_SMILES_THRESHOLD or limit >= _BEAM_LIMIT_MAX:
            break
        limit = min(limit * 2, _BEAM_LIMIT_MAX)
        print(f"Retrying beam search with limit={limit} ({n_valid}/{n_beams} valid on previous run)")

    if not len(smiles_batch) or not len(smiles_batch[0]):
        raise HTTPException(status_code=500, detail="Model returned no predictions.")

    predictions = [
        RetrosynthesisPrediction(
            reaction_smarts=f"{reactants}>>{request.smiles}",
            reactants_smiles=str(reactants),
            log_likelihood=float(lh),
        )
        for reactants, lh in zip(smiles_batch[0], log_lhs_batch[0])
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


@app.post(
    "/embed/molecule",
    response_model=EmbeddingResponse,
    summary="Embed molecule SMILES (default model)",
    response_description="Mean-pooled encoder embeddings, one vector per input SMILES.",
)
def embed_molecule_default(request: EmbedMoleculeRequest):
    """Encode one or more molecule SMILES through the Chemformer encoder.

    Returns a fixed-size embedding vector per molecule (shape `[d_model]`).
    Mean pooling over non-padding tokens is the default and recommended setting
    for downstream tasks such as similarity search or clustering.
    """
    smiles_list = [request.smiles] if isinstance(request.smiles, str) else request.smiles
    return _run_embed(smiles_list, _DEFAULT_MODEL_NAME, request.pooling)


@app.post(
    "/embed/molecule/{model_name}",
    response_model=EmbeddingResponse,
    summary="Embed molecule SMILES (named model)",
    response_description="Mean-pooled encoder embeddings, one vector per input SMILES.",
)
def embed_molecule_named(model_name: str, request: EmbedMoleculeRequest):
    """Encode using a named checkpoint from `CHEMFORMER_MODEL_DIR`.

    `model_name` is the checkpoint filename stem (without `.ckpt`).
    Models are lazy-loaded on first request and cached in memory.
    """
    smiles_list = [request.smiles] if isinstance(request.smiles, str) else request.smiles
    return _run_embed(smiles_list, model_name, request.pooling)


@app.post(
    "/embed/reaction",
    response_model=EmbeddingResponse,
    summary="Embed reaction SMARTS (default model)",
    response_description="Mean-pooled encoder embeddings, one vector per reaction.",
)
def embed_reaction_default(request: EmbedReactionRequest):
    """Encode one or more reactions through the Chemformer encoder.

    Each reaction must be supplied as `reactants>>product` SMARTS notation.
    The `encode_side` field selects which half is passed to the encoder:
    - `reactants` (default): encodes the left-hand side — useful for forward-synthesis context.
    - `product`: encodes the right-hand side — useful for retrosynthesis context.
    """
    smarts_list = (
        [request.reaction_smarts]
        if isinstance(request.reaction_smarts, str)
        else request.reaction_smarts
    )
    return _run_embed_reaction(smarts_list, _DEFAULT_MODEL_NAME, request.encode_side, request.pooling)


@app.post(
    "/embed/reaction/{model_name}",
    response_model=EmbeddingResponse,
    summary="Embed reaction SMARTS (named model)",
    response_description="Mean-pooled encoder embeddings, one vector per reaction.",
)
def embed_reaction_named(model_name: str, request: EmbedReactionRequest):
    """Encode reactions using a named checkpoint from `CHEMFORMER_MODEL_DIR`."""
    smarts_list = (
        [request.reaction_smarts]
        if isinstance(request.reaction_smarts, str)
        else request.reaction_smarts
    )
    return _run_embed_reaction(smarts_list, model_name, request.encode_side, request.pooling)


@app.post(
    "/synthesis/predict",
    response_model=SynthesisResponse,
    summary="Predict products from reactants (default model)",
    response_description="Ranked predicted products for the input reactants.",
)
def synthesis_predict_default(request: SynthesisRequest):
    """Forward synthesis: encode reactants, beam-search decode predicted products.

    Accepts dot-separated reactant SMILES or reaction SMARTS (`reactants>>`).
    Uses the default checkpoint configured via `CHEMFORMER_MODEL`.
    """
    return _run_synthesis(request, _DEFAULT_MODEL_NAME)


@app.post(
    "/synthesis/{model_name}/predict",
    response_model=SynthesisResponse,
    summary="Predict products from reactants (named model)",
    response_description="Ranked predicted products for the input reactants.",
)
def synthesis_predict_named(model_name: str, request: SynthesisRequest):
    """Forward synthesis using a named checkpoint from `CHEMFORMER_MODEL_DIR`.

    `model_name` is the checkpoint filename stem (without `.ckpt`).
    """
    return _run_synthesis(request, model_name)


@app.post(
    "/synthesis/score",
    response_model=SynthesisScoreResponse,
    summary="Score reaction viability (default model)",
    response_description="Per-token mean log-likelihood for each scored reaction.",
)
def synthesis_score_default(request: SynthesisScoreRequest):
    """Score one or more reactions via teacher-forced decoding.

    Accepts `reactants>>product` SMARTS. Returns the mean per-token log-likelihood
    of the product sequence given the reactants — higher (less negative) means the
    model considers the reaction more plausible.
    Uses the default checkpoint configured via `CHEMFORMER_MODEL`.
    """
    smarts_list = (
        [request.reaction_smarts]
        if isinstance(request.reaction_smarts, str)
        else request.reaction_smarts
    )
    return _run_score_reactions(smarts_list, _DEFAULT_MODEL_NAME)


@app.post(
    "/synthesis/{model_name}/score",
    response_model=SynthesisScoreResponse,
    summary="Score reaction viability (named model)",
    response_description="Per-token mean log-likelihood for each scored reaction.",
)
def synthesis_score_named(model_name: str, request: SynthesisScoreRequest):
    """Score reactions using a named checkpoint from `CHEMFORMER_MODEL_DIR`.

    `model_name` is the checkpoint filename stem (without `.ckpt`).
    """
    smarts_list = (
        [request.reaction_smarts]
        if isinstance(request.reaction_smarts, str)
        else request.reaction_smarts
    )
    return _run_score_reactions(smarts_list, model_name)


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
