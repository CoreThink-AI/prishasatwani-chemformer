#!/usr/bin/env python3
"""
evaluate_retrosynthesis_routes.py — RDKit-based evaluation of AiZynthFinder
retrosynthesis route YAML files produced by evaluate_zydus_queries.py.

Appends an "evaluation:" block under _meta in each input file.

Usage:
    python scripts/evaluate_retrosynthesis_routes.py [FILE ...]

    If no FILE is given, processes all zydus_query_*.yaml in
    src/chemformer/data/.  Pass --force to re-evaluate existing results.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml
from rdkit import Chem
from rdkit.Chem import rdBase

# Hill order: C first, then H, then alphabetical
_HILL_ORDER = [6, 1, 7, 8, 9, 15, 16, 17, 35, 53]
_ATOMIC_SYM = {1:"H", 6:"C", 7:"N", 8:"O", 9:"F", 15:"P",
               16:"S", 17:"Cl", 35:"Br", 53:"I"}


# ---------------------------------------------------------------------------
# SMILES / atom utilities
# ---------------------------------------------------------------------------

def parse_smiles(smiles: str):
    """Return RDKit Mol or None. Suppresses RDKit stderr."""
    if not smiles or not smiles.strip():
        return None
    return Chem.MolFromSmiles(smiles.strip())


def is_valid_smiles(smiles: str) -> bool:
    return parse_smiles(smiles) is not None


def atom_counts(mol) -> Counter:
    """
    Return {atomic_num: count} for all heavy atoms plus implicit H.
    Explicit H in the graph are included via GetTotalNumHs().
    """
    counts: Counter = Counter()
    for atom in mol.GetAtoms():
        counts[atom.GetAtomicNum()] += 1
        counts[1] += atom.GetTotalNumHs()
    return counts


def molecular_formula(counts: Counter) -> str:
    """Format an atom-count Counter as a Hill-order molecular formula string."""
    parts = []
    for z in _HILL_ORDER:
        n = counts.get(z, 0)
        if n:
            sym = _ATOMIC_SYM.get(z, str(z))
            parts.append(sym if n == 1 else f"{sym}{n}")
    for z in sorted(k for k in counts if k not in _HILL_ORDER and counts[k]):
        sym = _ATOMIC_SYM.get(z, str(z))
        n = counts[z]
        parts.append(sym if n == 1 else f"{sym}{n}")
    return "".join(parts) or "none"


# ---------------------------------------------------------------------------
# Reaction evaluation
# ---------------------------------------------------------------------------

def evaluate_reaction(rxn_smiles: str) -> dict:
    """
    Evaluate one reaction SMILES stored in retrosynthetic direction:
        product >> precursor1 . precursor2 ...

    Returns a dict with keys:
        reaction_smiles       — input string
        all_smiles_valid      — bool: every fragment parses in RDKit
        balanced              — bool: True only when product == precursors atom-count
        implied_byproduct_formula — str (Hill), set when precursors > product
        phantom_atoms         — dict {symbol: count}, set when product > precursors
        note                  — human-readable summary
    """
    result: dict = {"reaction_smiles": rxn_smiles}

    if not rxn_smiles or ">>" not in rxn_smiles:
        result["all_smiles_valid"] = False
        result["note"] = "no >> separator"
        return result

    product_part, precursor_part = rxn_smiles.split(">>", 1)

    product_mols  = [parse_smiles(s) for s in product_part.split(".")  if s.strip()]
    precursor_mols = [parse_smiles(s) for s in precursor_part.split(".") if s.strip()]

    result["all_smiles_valid"] = all(
        m is not None for m in product_mols + precursor_mols
    )
    if not result["all_smiles_valid"]:
        result["note"] = "one or more SMILES fragments failed RDKit parse"
        return result

    p_counts = sum((atom_counts(m) for m in product_mols),   Counter())
    r_counts = sum((atom_counts(m) for m in precursor_mols), Counter())

    all_elems = set(p_counts) | set(r_counts)
    phantom   = {_ATOMIC_SYM.get(z, str(z)): p_counts[z] - r_counts[z]
                 for z in all_elems if p_counts[z] > r_counts[z]}
    surplus   = Counter({z: r_counts[z] - p_counts[z]
                         for z in all_elems if r_counts[z] > p_counts[z]})

    if phantom:
        result["balanced"] = False
        result["phantom_atoms"] = phantom
        result["note"] = (
            f"chemically implausible — atoms appear in product absent from "
            f"precursors: {phantom}"
        )
    elif surplus:
        result["balanced"] = False
        result["implied_byproduct_formula"] = molecular_formula(surplus)
        result["note"] = (
            f"retrosynthetic disconnection — forward reaction: precursors → "
            f"product + {molecular_formula(surplus)}"
        )
    else:
        result["balanced"] = True
        result["note"] = "atom-balanced (no byproduct)"

    return result


# ---------------------------------------------------------------------------
# Route-tree traversal
# ---------------------------------------------------------------------------

def collect_reaction_nodes(node: dict, out: list) -> None:
    """Depth-first walk of an AiZynthFinder route tree; appends reaction nodes."""
    if node.get("is_reaction"):
        out.append(node)
    for child in node.get("children", []):
        collect_reaction_nodes(child, out)


def evaluate_route(route: dict, category: str, route_index: int) -> dict:
    """
    Evaluate one route tree from AiZynthFinder output.

    Returns a dict suitable for embedding in the evaluation YAML block:
        category, route_index, target_smiles, target_smiles_valid, score,
        all_reaction_smiles_valid, chemically_plausible, reactions[].
    """
    target_smi = route.get("smiles", "")
    rxn_nodes: list = []
    collect_reaction_nodes(route, rxn_nodes)

    rxn_evals = []
    all_valid     = True
    all_plausible = True

    for rxn_node in rxn_nodes:
        rxn_eval = evaluate_reaction(rxn_node.get("smiles", ""))
        rxn_eval["policy_probability"] = (
            rxn_node.get("metadata", {}).get("policy_probability")
        )
        rxn_eval["precursors"] = [
            {
                "smiles":       child.get("smiles"),
                "smiles_valid": is_valid_smiles(child.get("smiles", "")),
                "in_stock":     child.get("in_stock"),
            }
            for child in rxn_node.get("children", [])
            if child.get("is_chemical")
        ]
        if not rxn_eval["all_smiles_valid"]:
            all_valid = False
        if rxn_eval.get("phantom_atoms"):
            all_plausible = False
        rxn_evals.append(rxn_eval)

    return {
        "category":                  category,
        "route_index":               route_index,
        "target_smiles":             target_smi,
        "target_smiles_valid":       is_valid_smiles(target_smi),
        "score":                     route.get("scores", {}),
        "all_reaction_smiles_valid": all_valid,
        "chemically_plausible":      all_plausible,
        "reactions":                 rxn_evals,
    }


# ---------------------------------------------------------------------------
# Full response evaluation
# ---------------------------------------------------------------------------

def evaluate_response(response: dict) -> dict:
    """
    Evaluate all routes in an AiZynthFinder response dict.

    Handles both the flat format ({stats, purchasable_routes, ...}) and the
    tracks-based format ({tracks: {"1": {...}, "2": {...}}}).

    Returns the "evaluation" dict to be stored under _meta.evaluation.
    """
    tracks_raw = response.get("tracks")

    if tracks_raw:
        # tracks-based format
        tracks_input = {str(k): v for k, v in tracks_raw.items()}
    else:
        # flat format — wrap in a synthetic single track
        tracks_input = {"1": response}

    eval_tracks = {}
    total = valid = plausible = 0

    for track_id, track in tracks_input.items():
        route_evals = []
        for category in ("purchasable_routes", "non_purchasable_routes"):
            for ri, route in enumerate(track.get(category, [])):
                total += 1
                rev = evaluate_route(route, category, ri)
                if rev["all_reaction_smiles_valid"]:
                    valid += 1
                if rev["chemically_plausible"]:
                    plausible += 1
                route_evals.append(rev)
        eval_tracks[track_id] = {
            "stats":            track.get("stats"),
            "route_evaluations": route_evals,
        }

    return {
        "tool":             "RDKit",
        "rdkit_version":    rdBase.rdkitVersion,
        "evaluation_note":  (
            "Reaction SMILES are stored in retrosynthetic direction "
            "(product>>precursors). Atom imbalance reflects implied byproducts "
            "(e.g. HCl, H2O, CH3COOH) that AiZynthFinder omits from the route "
            "representation. chemically_plausible=True means every reaction has "
            "valid SMILES and no phantom atoms (atoms that appear in the product "
            "but are absent from the precursors)."
        ),
        "summary": {
            "total_routes":                    total,
            "routes_with_all_valid_smiles":    valid,
            "routes_chemically_plausible":     plausible,
        },
        "tracks": eval_tracks,
    }


# ---------------------------------------------------------------------------
# File-level helpers
# ---------------------------------------------------------------------------

def evaluate_yaml_file(path: Path, force: bool = False) -> dict:
    """
    Load a zydus_query_*.yaml file, evaluate its response routes, and write
    the evaluation back under _meta.evaluation.  Returns the evaluation dict.

    Skips without writing if evaluation already present and force=False.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if not force and data.get("_meta", {}).get("evaluation"):
        return data["_meta"]["evaluation"]

    evaluation = evaluate_response(data.get("response", {}))
    data.setdefault("_meta", {})["evaluation"] = evaluation

    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False,
                  default_flow_style=False)

    return evaluation


def print_evaluation_summary(path: Path, evaluation: dict) -> None:
    s = evaluation["summary"]
    print(f"{path.name}")
    print(f"  {s['total_routes']} routes  |  "
          f"{s['routes_with_all_valid_smiles']} valid SMILES  |  "
          f"{s['routes_chemically_plausible']} chemically plausible")
    for track_id, track_ev in evaluation["tracks"].items():
        for rev in track_ev["route_evaluations"]:
            rxn = rev["reactions"][0] if rev["reactions"] else {}
            byp = rxn.get("implied_byproduct_formula", "—")
            phant = rxn.get("phantom_atoms", {})
            flag = "✅" if rev["chemically_plausible"] else "❌"
            note = rxn.get("note", "")[:72]
            print(f"  {flag} track={track_id} route={rev['route_index']}"
                  f" [{rev['category'][:12]}]"
                  f"  byproduct={byp}"
                  f"  phantom={phant or '—'}"
                  f"  | {note}")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    default_dir = Path(__file__).resolve().parent.parent / "src" / "chemformer" / "data"

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="YAML files to evaluate (default: all zydus_query_*.yaml)")
    parser.add_argument("--force", action="store_true",
                        help="Re-evaluate files that already have evaluation data")
    args = parser.parse_args()

    paths = [Path(f) for f in args.files] if args.files else sorted(
        default_dir.glob("zydus_query_*.yaml")
    )

    if not paths:
        print(f"No files found in {default_dir}", file=sys.stderr)
        sys.exit(1)

    for path in paths:
        if not path.exists():
            print(f"SKIP (not found): {path}", file=sys.stderr)
            continue
        evaluation = evaluate_yaml_file(path, force=args.force)
        skipped = (not args.force and
                   evaluation == yaml.safe_load(path.read_text())
                   .get("_meta", {}).get("evaluation"))
        print_evaluation_summary(path, evaluation)


if __name__ == "__main__":
    main()
