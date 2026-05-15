"""Integration test: recursive retrosynthesis for each molecule in scripts/zydus_queries.yaml.

For each molecule, calls the Chemformer retrosynthesis API recursively to build a
retrosynthesis tree, then extracts up to --max-pathways complete synthesis pathways
(sequences of reactions from starting materials to product) and evaluates each
pathway for chemical viability via PubChem.

Output: src/chemformer/data/zydus_queries_chemformer_recursive_{hash6}.yaml

Run from the project root:
    python scripts/integration_test_zydus_queries.py [options]

Options:
    --model       Checkpoint stem (default: backward_uspto50k)
    --url         API base URL
    --n-beams     Beam count per API call (default: 10)
    --max-depth   Max recursion depth (default: 3)
    --min-ll      Min log-likelihood to expand a reaction (default: -5.0)
    --max-mw      MW threshold below which a fragment is treated as a leaf (default: 300)
    --max-pathways  Max synthesis pathways to extract per molecule (default: 4)
"""

import argparse
import itertools
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import yaml
from rdkit import Chem
from rdkit.Chem import Descriptors

API_URL = "https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app"
QUERIES_FILE = Path("scripts/zydus_queries.yaml")
OUTPUT_DIR = Path("src/chemformer/data")
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_CACHE_DIR = Path("src/chemformer/data/pubchem")
PUBCHEM_RATE_DELAY = 0.22  # stay under PubChem's 5 req/s limit
PUBCHEM_PROPERTIES = "IUPACName,MolecularFormula,MolecularWeight,IsomericSMILES,InChIKey,Complexity,XLogP"

DEFAULT_MODEL = "backward_uspto50k"


# ── RDKit helpers ────────────────────────────────────────────────────────────

def mol_from_smiles(smiles: str) -> Optional[Chem.Mol]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"  [RDKit: could not parse SMILES: {smiles[:60]}]", file=sys.stderr)
    return mol


def canonical_smiles(smiles: str) -> str:
    """Return RDKit canonical SMILES, or the original if parsing fails."""
    mol = mol_from_smiles(smiles)
    return Chem.MolToSmiles(mol) if mol else smiles


def mol_weight(smiles: str) -> float:
    mol = mol_from_smiles(smiles)
    return Descriptors.MolWt(mol) if mol else float("inf")


# ── Chemformer API ────────────────────────────────────────────────────────────

def _predict(smiles: str, model: str, n_beams: int, url: str) -> list:
    endpoint = f"{url}/retrosynthesis/{model}/predict"
    try:
        r = requests.post(
            endpoint,
            json={"smiles": smiles, "n_beams": n_beams},
            timeout=180,
        )
        r.raise_for_status()
        return r.json().get("predictions", [])
    except Exception as exc:
        print(f"  [API error for {smiles[:50]}: {exc}]", file=sys.stderr)
        return []


def _is_leaf(smiles: str, max_mw: float) -> bool:
    return mol_weight(smiles) <= max_mw


def _split_reactants(dot_smiles: str) -> list:
    return [s.strip() for s in dot_smiles.split(".") if s.strip()]


# ── recursive tree expansion ──────────────────────────────────────────────────

def expand(smiles, depth, max_depth, min_ll, max_mw, n_beams, model, url, visited):
    smiles = canonical_smiles(smiles)
    node = {"smiles": smiles, "depth": depth}

    if smiles in visited:
        node["status"] = "already_expanded"
        return node

    # Only treat sub-fragments (depth > 0) as leaves — never the query molecule itself.
    if depth > 0 and _is_leaf(smiles, max_mw):
        node["status"] = "leaf"
        node["mol_weight"] = round(mol_weight(smiles), 2)
        return node

    if depth >= max_depth:
        node["status"] = "max_depth_reached"
        return node

    visited.add(smiles)
    indent = "  " * depth
    print(f"{indent}▶ depth={depth} {smiles[:70]}", file=sys.stderr)

    predictions = _predict(smiles, model, n_beams, url)
    viable = [p for p in predictions if p["log_likelihood"] >= min_ll]

    if not viable:
        node["status"] = "no_viable_reactions"
        node["best_ll"] = predictions[0]["log_likelihood"] if predictions else None
        return node

    node["status"] = "expanded"
    node["reactions"] = []
    for pred in viable:
        time.sleep(0.1)
        reactant_smiles = _split_reactants(pred["reactants_smiles"])
        reaction_node = {
            "log_likelihood": round(pred["log_likelihood"], 4),
            "reaction_smarts": pred["reaction_smarts"],
            "reactants": [
                expand(r, depth + 1, max_depth, min_ll, max_mw, n_beams, model, url, visited)
                for r in reactant_smiles
            ],
        }
        node["reactions"].append(reaction_node)

    return node


# ── pathway extraction ────────────────────────────────────────────────────────

def _pathways_from_node(node):
    """Yield complete synthesis pathways (lists of reaction-step dicts) from a tree node."""
    status = node.get("status")
    if status in ("leaf", "already_expanded", "max_depth_reached", "no_viable_reactions"):
        yield []
        return

    for rxn in node.get("reactions", []):
        step = {
            "product_smiles": node["smiles"],
            "reactant_smiles": [r["smiles"] for r in rxn.get("reactants", [])],
            "log_likelihood": rxn["log_likelihood"],
            "reaction_smarts": rxn["reaction_smarts"],
        }
        sub_lists = [list(_pathways_from_node(r)) for r in rxn.get("reactants", [])]
        for combo in itertools.product(*sub_lists):
            yield [step] + [s for sub in combo for s in sub]


def extract_pathways(tree, max_pathways: int = 4) -> list:
    """Return up to max_pathways complete pathways, ranked by bottleneck log-likelihood."""
    all_paths = [p for p in _pathways_from_node(tree) if p]  # skip empty (root is leaf)
    if not all_paths:
        return []

    def score(path):
        return min(s["log_likelihood"] for s in path)

    all_paths.sort(key=score, reverse=True)
    return all_paths[:max_pathways]


def get_leaf_reactants(pathway: list) -> list:
    """Return SMILES that appear as reactants but are not produced by any step."""
    products = {step["product_smiles"] for step in pathway}
    seen = set()
    leaves = []
    for step in pathway:
        for smi in step["reactant_smiles"]:
            if smi not in products and smi not in seen:
                leaves.append(smi)
                seen.add(smi)
    return leaves


# ── PubChem viability evaluation ──────────────────────────────────────────────

def _pubchem_get(url: str, **kwargs) -> requests.Response:
    time.sleep(PUBCHEM_RATE_DELAY)
    return requests.get(url, timeout=30, **kwargs)


def cid_from_smiles(smiles: str) -> Optional[int]:
    time.sleep(PUBCHEM_RATE_DELAY)
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
    PUBCHEM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = PUBCHEM_CACHE_DIR / f"{cid}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    r = _pubchem_get(f"{PUBCHEM_BASE}/compound/cid/{cid}/property/{PUBCHEM_PROPERTIES}/JSON")
    if not r.ok:
        return {"cid": cid, "vendor_count": 0, "bioassay_count": 0}
    props = r.json()["PropertyTable"]["Properties"][0]

    rv = _pubchem_get(f"{PUBCHEM_BASE}/compound/cid/{cid}/xrefs/SourceName/JSON")
    vendor_count = len(
        rv.json().get("InformationList", {}).get("Information", [{}])[0].get("SourceName", [])
    ) if rv.ok else 0

    rb = _pubchem_get(f"{PUBCHEM_BASE}/compound/cid/{cid}/assaysummary/JSON")
    bioassay_count = len(rb.json().get("Table", {}).get("Row", [])) if rb.ok else 0

    compound = {
        "cid": cid,
        **{k: v for k, v in props.items() if k != "CID"},
        "vendor_count": vendor_count,
        "bioassay_count": bioassay_count,
    }
    cache_file.write_text(json.dumps(compound, indent=2))
    return compound


def evaluate_leaves(leaf_smiles: list) -> dict:
    """Query PubChem for each leaf SMILES; return viability record."""
    records = []
    all_found = True
    all_purchasable = True

    for smi in leaf_smiles:
        short = smi[:55] + ("…" if len(smi) > 55 else "")
        print(f"        PubChem: {short}", end=" ", flush=True)
        cid = cid_from_smiles(smi)
        if cid is None:
            print("not found")
            all_found = False
            all_purchasable = False
            records.append({"smiles": smi, "found": False})
            continue

        compound = fetch_compound(cid)
        purchasable = compound.get("vendor_count", 0) > 0
        if not purchasable:
            all_purchasable = False
        print(f"CID {cid}  vendors={compound.get('vendor_count', 0)}")
        records.append({
            "smiles": smi,
            "found": True,
            "cid": cid,
            "pubchem_name": compound.get("IUPACName"),
            "inchikey": compound.get("InChIKey"),
            "complexity": compound.get("Complexity"),
            "vendor_count": compound.get("vendor_count", 0),
            "purchasable": purchasable,
        })

    quality = "high" if all_found and all_purchasable else ("partial" if all_found else "low")
    return {
        "quality": quality,
        "all_found": all_found,
        "all_purchasable": all_purchasable,
        "leaf_reactants": records,
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def pathway_to_dict(pathway: list, rank: int, viability: dict) -> dict:
    """Serialize a pathway to a YAML-friendly dict."""
    min_ll = min(s["log_likelihood"] for s in pathway) if pathway else None
    return {
        "pathway_rank": rank,
        "step_count": len(pathway),
        "min_log_likelihood": round(min_ll, 4) if min_ll is not None else None,
        "quality": viability["quality"],
        "all_leaves_found": viability["all_found"],
        "all_leaves_purchasable": viability["all_purchasable"],
        "steps": [
            {
                "step": i + 1,
                "product_smiles": s["product_smiles"],
                "reactant_smiles": s["reactant_smiles"],
                "log_likelihood": s["log_likelihood"],
                "reaction_smarts": s["reaction_smarts"],
            }
            for i, s in enumerate(pathway)
        ],
        "leaf_reactants": viability["leaf_reactants"],
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=API_URL)
    parser.add_argument("--n-beams", type=int, default=10)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--min-ll", type=float, default=-5.0)
    parser.add_argument("--max-mw", type=float, default=300.0)
    parser.add_argument("--max-pathways", type=int, default=4)
    args = parser.parse_args()

    queries = yaml.safe_load(QUERIES_FILE.read_text())["molecules"]
    ref = git_hash()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"zydus_queries_chemformer_recursive_{ref[:6]}.yaml"

    results = []
    for mol in queries:
        name = mol["query_name"]
        cid = mol["pubchem_cid"]
        smiles = mol["smiles"]
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"  {name} (CID {cid})", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        t0 = time.monotonic()
        try:
            tree = expand(
                smiles=smiles,
                depth=0,
                max_depth=args.max_depth,
                min_ll=args.min_ll,
                max_mw=args.max_mw,
                n_beams=args.n_beams,
                model=args.model,
                url=args.url,
                visited=set(),
            )
            latency = round(time.monotonic() - t0, 2)

            pathways = extract_pathways(tree, max_pathways=args.max_pathways)

            evaluated_pathways = []
            for rank, pathway in enumerate(pathways, 1):
                print(f"    Pathway {rank} ({len(pathway)} step(s)):", file=sys.stderr)
                leaves = get_leaf_reactants(pathway)
                viability = evaluate_leaves(leaves)
                evaluated_pathways.append(pathway_to_dict(pathway, rank, viability))

            if not pathways:
                # Tree exists but no viable pathways (no_viable_reactions or all OOD)
                best_ll = tree.get("best_ll")
                evaluated_pathways = []
                print(f"    No viable pathways. best_ll={best_ll}", file=sys.stderr)

            results.append({
                "query_name": name,
                "pubchem_cid": cid,
                "input_smiles": smiles,
                "latency_s": latency,
                "tree_status": tree.get("status"),
                "pathways_found": len(evaluated_pathways),
                "best_ll": tree.get("best_ll"),
                "pathways": evaluated_pathways,
            })

        except Exception as exc:
            latency = round(time.monotonic() - t0, 2)
            print(f"    ERROR: {exc}", file=sys.stderr)
            results.append({
                "query_name": name,
                "pubchem_cid": cid,
                "input_smiles": smiles,
                "latency_s": latency,
                "error": str(exc),
            })

    output = {
        "metadata": {
            "git_hash": ref,
            "api_url": args.url,
            "model": args.model,
            "n_beams": args.n_beams,
            "max_depth": args.max_depth,
            "min_ll": args.min_ll,
            "max_mw": args.max_mw,
            "max_pathways": args.max_pathways,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "results": results,
    }

    out_path.write_text(yaml.dump(output, allow_unicode=True, sort_keys=False, width=120))
    print(f"\nWrote {len(results)} results → {out_path}", file=sys.stderr)

    # Summary table to stdout
    print(f"\n{'Molecule':<28} {'pathways':>8}  {'best pathway ll':>15}  {'quality':<8}")
    print("-" * 68)
    for r in results:
        if "error" in r:
            print(f"  {r['query_name']:<26} ERROR")
            continue
        pw = r.get("pathways", [])
        n = len(pw)
        best_ll = pw[0]["min_log_likelihood"] if pw else None
        quality = pw[0]["quality"] if pw else ("ood" if r.get("tree_status") == "no_viable_reactions" else "—")
        ll_str = f"{best_ll:.3f}" if best_ll is not None else "n/a"
        print(f"  {r['query_name']:<26} {n:>8}  {ll_str:>15}  {quality:<8}")


if __name__ == "__main__":
    main()
