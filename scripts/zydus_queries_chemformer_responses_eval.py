"""Evaluate Chemformer retrosynthesis responses by looking up predicted reactants on PubChem.

For each best_reactants_smiles in the responses YAML:
  - Split into individual reactant SMILES (dot-separated)
  - Query PubChem for each reactant by exact structure match
  - Cache full PubChem compound properties in src/chemformer/data/pubchem/{CID}.json
  - Record: CID, IUPAC name, complexity, vendor_count, bioassay_count, purchasable

Output: src/chemformer/data/zydus_queries_chemformer_eval_{hash6}.yaml

Usage:
    python scripts/zydus_queries_chemformer_responses_eval.py [responses.yaml]

If no file is given, uses the most recently modified
src/chemformer/data/zydus_queries_chemformer_responses_*.yaml file.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

import requests
import yaml

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CACHE_DIR = Path("src/chemformer/data/pubchem")
RESPONSES_GLOB = "src/chemformer/data/zydus_queries_chemformer_responses_*.yaml"
RATE_DELAY = 0.22  # stay under PubChem's 5 req/s limit

PROPERTIES = "IUPACName,MolecularFormula,MolecularWeight,IsomericSMILES,InChIKey,Complexity,XLogP"


# ── PubChem helpers ──────────────────────────────────────────────────────────

def _get(url: str, **kwargs) -> requests.Response:
    time.sleep(RATE_DELAY)
    r = requests.get(url, timeout=30, **kwargs)
    return r


def cid_from_smiles(smiles: str) -> Optional[int]:
    """Return the PubChem CID for an exact SMILES match, or None if not found."""
    time.sleep(RATE_DELAY)
    r = requests.post(
        f"{PUBCHEM_BASE}/compound/smiles/cids/JSON",
        data={"smiles": smiles},
        timeout=30,
    )
    if r.status_code != 200:
        return None
    cids = r.json().get("IdentifierList", {}).get("CID", [])
    return cids[0] if cids and cids[0] > 0 else None


def fetch_compound(cid: int) -> dict:
    """Fetch compound properties from PubChem, using a local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cid}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())

    # Properties
    r = _get(f"{PUBCHEM_BASE}/compound/cid/{cid}/property/{PROPERTIES}/JSON")
    if not r.ok:
        return {"cid": cid, "vendor_count": 0, "bioassay_count": 0}
    props = r.json()["PropertyTable"]["Properties"][0]

    # Vendor count (SourceName list)
    rv = _get(f"{PUBCHEM_BASE}/compound/cid/{cid}/xrefs/SourceName/JSON")
    vendor_count = len(rv.json().get("InformationList", {}).get("Information", [{}])[0].get("SourceName", [])) if rv.ok else 0

    # Bioassay count (assay summary)
    rb = _get(f"{PUBCHEM_BASE}/compound/cid/{cid}/assaysummary/JSON")
    bioassay_count = len(rb.json().get("Table", {}).get("Row", [])) if rb.ok else 0

    compound = {
        "cid": cid,
        **{k: v for k, v in props.items() if k != "CID"},
        "vendor_count": vendor_count,
        "bioassay_count": bioassay_count,
    }
    cache_file.write_text(json.dumps(compound, indent=2))
    return compound


# ── Evaluation logic ─────────────────────────────────────────────────────────

def split_reactants(dot_smiles: str) -> list:
    """Split a dot-separated multi-component SMILES into individual SMILES strings."""
    return [s.strip() for s in dot_smiles.split(".") if s.strip()]


def evaluate_result(result: dict, product_complexity: Optional[int]) -> dict:
    """Look up each reactant on PubChem and return an evaluation record."""
    reactants_raw = result.get("best_reactants_smiles", "")
    reactant_smiles_list = split_reactants(reactants_raw)

    reactant_records = []
    all_found = True
    all_purchasable = True

    for smi in reactant_smiles_list:
        print(f"      PubChem lookup: {smi[:60]}{'…' if len(smi) > 60 else ''}", end=" ", flush=True)
        cid = cid_from_smiles(smi)
        if cid is None:
            print("not found")
            all_found = False
            all_purchasable = False
            reactant_records.append({"smiles": smi, "found": False})
            continue

        compound = fetch_compound(cid)
        purchasable = compound.get("vendor_count", 0) > 0
        if not purchasable:
            all_purchasable = False
        print(f"CID {cid}  vendors={compound.get('vendor_count', 0)}  complexity={compound.get('Complexity', '?')}")
        reactant_records.append({
            "smiles": smi,
            "found": True,
            "cid": cid,
            "pubchem_name": compound.get("IUPACName"),
            "inchikey": compound.get("InChIKey"),
            "complexity": compound.get("Complexity"),
            "vendor_count": compound.get("vendor_count", 0),
            "bioassay_count": compound.get("bioassay_count", 0),
            "purchasable": purchasable,
        })

    # Complexity delta: sum(reactant complexity) - product_complexity
    reactant_complexities = [r["complexity"] for r in reactant_records if r.get("complexity") is not None]
    complexity_delta = (
        sum(reactant_complexities) - product_complexity
        if product_complexity is not None and reactant_complexities
        else None
    )

    quality = "high" if all_found and all_purchasable else ("partial" if all_found else "low")

    return {
        "query_name": result["query_name"],
        "pubchem_cid": result["pubchem_cid"],
        "input_smiles": result["input_smiles"],
        "best_log_likelihood": result.get("best_log_likelihood"),
        "latency_s": result.get("latency_s"),
        "quality": quality,
        "all_reactants_found": all_found,
        "all_reactants_purchasable": all_purchasable,
        "complexity_delta": complexity_delta,
        "reactants": reactant_records,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        responses_path = Path(sys.argv[1])
    else:
        candidates = sorted(Path(".").glob(RESPONSES_GLOB), key=lambda p: p.stat().st_mtime)
        if not candidates:
            sys.exit(f"No responses file found matching {RESPONSES_GLOB}")
        responses_path = candidates[-1]

    print(f"Evaluating {responses_path}")
    data = yaml.safe_load(responses_path.read_text())
    meta = data["metadata"]
    hash6 = meta["git_hash"][:6]

    # Pre-fetch product complexities from the queries YAML for delta calculation
    queries_file = Path("scripts/zydus_queries.yaml")
    product_complexity_by_cid: dict[int, int] = {}
    if queries_file.exists():
        for mol in yaml.safe_load(queries_file.read_text()).get("molecules", []):
            cid = mol.get("pubchem_cid")
            c = mol.get("complexity")
            if cid and c:
                product_complexity_by_cid[cid] = c

    eval_results = []
    for result in data["results"]:
        if "error" in result:
            eval_results.append({**result, "quality": "error"})
            continue
        print(f"  {result['query_name']} (CID {result['pubchem_cid']})")
        prod_complexity = product_complexity_by_cid.get(result["pubchem_cid"])
        eval_results.append(evaluate_result(result, prod_complexity))

    out_path = responses_path.parent / f"zydus_queries_chemformer_eval_{hash6}.yaml"
    output = {
        "metadata": {**meta, "responses_file": str(responses_path)},
        "results": eval_results,
    }
    out_path.write_text(yaml.dump(output, allow_unicode=True, sort_keys=False, width=120))
    print(f"\nWrote {len(eval_results)} evaluations → {out_path}")

    # Print summary table
    print(f"\n{'Molecule':<30} {'ll':>8}  {'quality':<8}  {'found':>5}  {'purchasable':>11}  {'Δcomplexity':>12}")
    print("-" * 85)
    for r in eval_results:
        if r.get("quality") == "error":
            print(f"  {r['query_name']:<28} ERROR")
            continue
        ll = f"{r['best_log_likelihood']:.3f}" if r.get("best_log_likelihood") is not None else "n/a"
        dc = f"{r['complexity_delta']:+d}" if r.get("complexity_delta") is not None else "n/a"
        print(
            f"  {r['query_name']:<28} {ll:>8}  {r['quality']:<8}  "
            f"{'yes' if r['all_reactants_found'] else 'no':>5}  "
            f"{'yes' if r['all_reactants_purchasable'] else 'no':>11}  "
            f"{dc:>12}"
        )


if __name__ == "__main__":
    main()
