"""Integration test: POST each molecule in scripts/zydus_queries.yaml to the
Chemformer retrosynthesis API and write results to
src/chemformer/data/zydus_queries_chemformer_responses_{hash6}.yaml.

Run from the project root:
    python scripts/integration_test_zydus_queries.py [--n-beams N] [--url URL]
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

API_URL = "https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app/retrosynthesis/predict"
QUERIES_FILE = Path("scripts/zydus_queries.yaml")
OUTPUT_DIR = Path("src/chemformer/data")


def git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def query_molecule(smiles: str, n_beams: int, url: str, timeout: int = 120):
    """POST to the API and return (response_json, latency_seconds)."""
    t0 = time.monotonic()
    resp = requests.post(url, json={"smiles": smiles, "n_beams": n_beams}, timeout=timeout)
    latency = time.monotonic() - t0
    resp.raise_for_status()
    return resp.json(), latency


def best_prediction(predictions: list) -> dict:
    """Return the prediction with the highest (least negative) log_likelihood."""
    return max(predictions, key=lambda p: p["log_likelihood"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-beams", type=int, default=10)
    parser.add_argument("--url", default=API_URL)
    args = parser.parse_args()

    queries = yaml.safe_load(QUERIES_FILE.read_text())["molecules"]
    ref = git_hash()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"zydus_queries_chemformer_responses_{ref[:6]}.yaml"

    results = []
    for mol in queries:
        name = mol["query_name"]
        cid = mol["pubchem_cid"]
        smiles = mol["smiles"]
        print(f"  {name} (CID {cid}) ...", end=" ", flush=True)
        try:
            data, latency = query_molecule(smiles, args.n_beams, args.url)
            best = best_prediction(data["predictions"])
            print(f"ll={best['log_likelihood']:.3f}  {latency:.1f}s")
            results.append({
                "query_name": name,
                "pubchem_cid": cid,
                "input_smiles": smiles,
                "latency_s": round(latency, 3),
                "best_reactants_smiles": best["reactants_smiles"],
                "best_log_likelihood": round(best["log_likelihood"], 6),
                "best_reaction_smarts": best["reaction_smarts"],
            })
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({
                "query_name": name,
                "pubchem_cid": cid,
                "input_smiles": smiles,
                "error": str(exc),
            })

    output = {
        "metadata": {
            "git_hash": ref,
            "api_url": args.url,
            "n_beams": args.n_beams,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "results": results,
    }

    out_path.write_text(yaml.dump(output, allow_unicode=True, sort_keys=False, width=120))
    print(f"\nWrote {len(results)} results → {out_path}")


if __name__ == "__main__":
    main()
