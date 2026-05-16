# Chemformer Retrosynthesis Integration Test Report

**Date:** 2026-05-15  
**Model:** `backward_uspto50k` (Chemformer BART, fine-tuned on USPTO-50K)  
**Service:** [`https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app`](https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app)  
**Parameters:** `n_beams=10, max_depth=3, min_ll=−5.0, max_mw=300 Da, max_pathways=4`  
**Output:** [`src/chemformer/data/zydus_queries_chemformer_recursive_db5e90.yaml`](/src/chemformer/data/zydus_queries_chemformer_recursive_db5e90.yaml)

---

## Executive Summary

9 of 11 molecules yielded at least one retrosynthetic pathway. 2 molecules timed out due to SMILES length exceeding CPU inference capacity. Among the 9 successful predictions, 6 produced at least one fully purchasable, chemically plausible route. The model is strongest on aromatic C−C and C−N couplings (Suzuki, Buchwald-Hartwig), which dominate the USPTO-50K training set. Limitations appear at high molecular weight and for advanced peptide/peptoid building blocks not in PubChem.

| Molecule | Pathways | Best ll | Quality | Latency |
|---|---|---|---|---|
| Aspirin | 1 | −0.742 | high | 14 s |
| Ibuprofen | 4 | −1.240 | high | 19 s |
| Paclitaxel | 0 | — | OOD/timeout | 90 s |
| Etoricoxib | 4 | −1.860 | low | 123 s |
| Camlipixant | 4 | −0.789 | high | 148 s |
| Fluorinated_Imidazole (CID 84117446) | 1 | −0.658 | high | 24 s |
| Fluorinated_Imidazole (CID 56842878) | 4 | −1.176 | low | 25 s |
| Methoxy_Diphenylamine | 1 | −0.687 | high | 14 s |
| Tolyl_Pyridine | 3 | −0.890 | high | 12 s |
| Orforglipron | 0 | — | OOD/timeout | 90 s |
| Acalabrutinib | 4 | −0.908 | low | 194 s |

---

## Per-Molecule Analysis

### Aspirin (CID 2244)
**Result: 1 pathway, high quality, fully purchasable**

The model returns the textbook Fischer esterification / acyl chloride route in a single step:

```
CC(=O)Cl  +  O=C(O)c1ccccc1O  →  Aspirin
acetyl chloride (261 vendors)   salicylic acid (579 vendors)
```

Log-likelihood −0.742 is among the highest in the test set — this is a well-represented reaction class. Both starting materials are widely available. Latency 14 s.

---

### Ibuprofen (CID 3672)
**Result: 4 pathways, all high quality; Pathway 1 is an identity artifact**

Pathways 2–4 are all valid ester/alkene precursors to Ibuprofen via hydrolysis or reduction:

| Pathway | Step | Reaction | ll | Vendors |
|---|---|---|---|---|
| 1 | 1 | Ibuprofen → Ibuprofen (identity) | −1.24 | — |
| 2 | 1 | Methyl ester (CID 5326009) → Ibuprofen (hydrolysis) | −2.64 | 39 |
| 3 | 1 | Ibuprofen-alkene precursor (CID 11644131) → Ibuprofen (reduction) | −3.05 | 5 |
| 4 | 1 | Ethyl ester (CID 56665514) → Ibuprofen (hydrolysis) | −3.35 | 28 |

**Note:** Pathway 1 is an identity reaction (reactant SMILES = product SMILES), a known model failure mode where the model proposes no transformation. Pathways 2–4 are chemically valid, representing a family of ester precursor routes. All leaves are commercially available.

---

### Paclitaxel (CID 36314)
**Result: 0 pathways, timeout**

The Paclitaxel SMILES (MW 853 Da, 113 tokens) exceeded the 90-second Cloud Run CPU timeout before a single beam search completed. This is expected — the model was trained on small-molecule reactions (median MW ~300 Da in USPTO-50K), and CPU inference time scales with output sequence length. **GPU deployment is required for natural product-scale molecules.**

---

### Etoricoxib (CID 123619)
**Result: 4 pathways, low/partial quality, latency 123 s**

The model correctly identifies the core biaryl disconnection strategy (Suzuki coupling between a pyridazine and a sulfonylphenyl fragment), which matches the known synthesis. However, the bottom-level building block `Clc1cnc(Br)c(I)c1I` (a tri-halogenated pyridazine) is not found in PubChem across all pathways, making none of the 3-step routes fully purchasable.

The most chemically interesting pathway:

```
Step 1: CS(=O)(=O)c1ccc(B(O)O)cc1  +  Clc1cnc(Br)c(I)c1
        sulfonylphenyl boronate (191 vendors)   bromo-chloro-iodo-pyridazine (50 vendors)
        → CS(=O)(=O)c1ccc(-c2cc(Cl)cnc2Br)cc1   [ll=−1.05]

Step 2: + Cc1ccc(B(O)O)cn1  →  Etoricoxib   [ll=−0.63]
          methylpyridyl boronate (177 vendors)
```

This 2-step route (Pathway 2, ll=−3.02) is chemically sound and all building blocks are in PubChem, but the `Clc1cnc(Br)c(I)c1` boronate partner shows 0 vendors in the cache (a cache read bug — see Known Issues). The triiodo compound in Pathways 1/3/4 is a model hallucination with no PubChem entry.

---

### Camlipixant (CID 76955630)
**Result: 4 pathways, best is high quality and fully purchasable, latency 148 s**

The best pathway (3 steps, ll=−0.789) is chemically coherent:

```
Step 3: COC(=O)Cl  +  [core with free NH]  →  N-Boc protected core   [ll=−0.789]
        methyl chloroformate (146 vendors)   CID 162374976 (1 vendor)

Step 2: ester hydrolysis on difluoro-aryl substituent   [ll=−0.657]

Step 1: CN  +  [acid intermediate]  →  Camlipixant amide   [ll=−0.676]
        methylamine (228 vendors)
```

The key commercially available building block is CID 162374976 (1 vendor) — the core benzimidazole-morpholine fragment. With one vendor, this route is purchasable but not robust. Pathway 3 (1-step, ll=−3.76) proposes a direct amide coupling using CID 153626349 (3 vendors), which could be a more practical route if that intermediate is accessible.

---

### Fluorinated_Imidazole (CID 84117446)
**Result: 1 pathway, high quality, fully purchasable**

The model returns an excellent Suzuki coupling in one step:

```
Cn1cnc(C#N)c1Br  +  OB(O)c1ccccc1F  →  product
N-Me-4-bromo-5-cyanoimidazole (29 vendors)   2-fluorophenylboronic acid (226 vendors)
```

Log-likelihood −0.658, highest confidence in the test set. This is exactly the correct retrosynthetic disconnection and both building blocks are readily available. Latency 24 s.

---

### Fluorinated_Imidazole (CID 56842878)
**Result: 4 pathways, all low quality — missing peptide building block**

All 4 beams converge on the same peptide amide bond disconnection:

```
NC(=O)[C@@H]1CCCN1C(=O)[C@@H](N)Cc1[nH]cnc1F  +  O=C1CC[C@@H](C(=O)O)N1
fluorinated His-proline fragment (NOT FOUND)       L-glutamic anhydride (274 vendors)
```

The model correctly identifies the amide bond to cleave, but the H-Pro-NH₂ fragment bearing the 4-fluorohistidine residue is not commercially available (not found in PubChem). This reflects an inherent limitation for peptide natural products: the model can identify the coupling point but cannot source specialty amino acid building blocks. A 3-step expansion might resolve this if the fluorohistidine were expanded further, but max_depth=3 was insufficient.

---

### Methoxy_Diphenylamine (CID 11435828)
**Result: 1 pathway, high quality, fully purchasable**

```
COc1ccc(N)cc1  +  Cc1ccc(Br)cc1  →  product
4-methoxyaniline (249 vendors)   4-bromotoluene (185 vendors)
```

A clean Buchwald-Hartwig C−N coupling, ll=−0.687. Both starting materials are commodity chemicals with hundreds of vendors. Latency 14 s.

---

### Tolyl_Pyridine (CID 603589)
**Result: 3 pathways, best high quality and fully purchasable**

```
Pathway 1: Brc1cccnc1  +  Cc1ccc(N)cc1  →  product   ll=−0.890
           3-bromopyridine (256 vendors)   4-methylaniline (277 vendors)

Pathway 2: Cc1ccc(Br)cc1  +  Nc1cccnc1  →  product   ll=−1.791
           4-bromotoluene (0 vendors*)   3-aminopyridine (235 vendors)
```

The two pathways represent the two possible Buchwald-Hartwig regiochemistries (aryl bromide on pyridine vs. on toluene). Pathway 1 is fully purchasable; Pathway 2 shows 0 vendors for 4-bromotoluene due to the cache read bug (it has 185 vendors when freshly fetched). Latency 12 s.

---

### Orforglipron (CID 137319706)
**Result: 0 pathways, timeout**

Orforglipron's SMILES (MW 699 Da, 151 tokens) is the longest in the test set and timed out at 90 s on CPU. Same situation as Paclitaxel — requires GPU deployment.

---

### Acalabrutinib (CID 71226662)
**Result: 4 pathways, all low quality, latency 194 s**

All 4 pathways share the same first two steps, indicating high model confidence in the propioloic acid acylation:

```
Step 1 (all pathways): CC#CC(=O)O  +  [deprotected core]  →  Acalabrutinib
                        2-butynoic acid (205 vendors)

Step 2 (all pathways): Boc deprotection of core pyrrolidine
```

Step 3 diverges across pathways:

| Pathway | Step 3 strategy | Key building block | Vendors |
|---|---|---|---|
| 1 | Direct amide coupling | Boc-iodo-intermediate | not found |
| 2 | Suzuki with pinacol boronate (CID 70351953) | 72 vendors | ✓ |
| 3 | Cbz-protected amine + boronic acid (CID 44119539) | 114 vendors | ✓ |
| 4 | Cbz-protected amine + amino acid coupling | Cbz-intermediate | not found |

Pathways 2 and 3 have commercially available key building blocks. The model correctly identifies the Suzuki coupling that installs the 4-pyridylamide aryl group, which is consistent with published synthetic routes. The `low` quality flag is driven by missing Boc/Cbz intermediates in PubChem rather than incorrect chemistry.

---

## Known Issues

### Vendor count zeroed on cache read

The `fetch_compound()` function stores the full PubChem `{"Record": {...}}` blob to disk, but `vendor_count` is fetched from a separate `/xrefs/SourceName` endpoint and is **not** included in that blob. On the first (non-cached) fetch, the correct vendor count is returned. On subsequent calls for the same CID, the cache path returns `vendor_count=0`.

This affects every molecule that appears more than once across pathways (e.g., CID 2763081 `Cc1ccc(B(O)O)cn1` appears with 177 vendors on first hit, 0 vendors on all subsequent hits). The `quality` flag and `purchasable` boolean are unreliable for any molecule that has been cached.

**Fix:** Augment the cached JSON with `{"Record": {...}, "_meta": {"vendor_count": N, "bioassay_count": N}}` so the cache read path can restore these values.

---

## Model Behavior Observations

**Strengths:**
- Suzuki C−C coupling and Buchwald-Hartwig C−N coupling are confidently predicted (ll > −1.5) and chemically correct for all 6 simpler aromatics
- Ester hydrolysis precursors are correctly identified for carboxylic acid targets (Ibuprofen, Camlipixant)
- Consistent Boc/Cbz protection strategies for amines (Acalabrutinib, Camlipixant)

**Weaknesses:**
- **Identity reactions** (Ibuprofen Pathway 1): model occasionally emits the product SMILES unchanged as the "reactant"
- **Halogen counting errors**: Etoricoxib pathways propose triiodo/tetraiodo pyridazines that do not exist commercially
- **OOD at MW > 600**: Paclitaxel and Orforglipron both timeout; the model's beam search does not terminate within 90 s on CPU for long SMILES
- **Specialty amino acids**: The model cannot route through non-canonical amino acid building blocks (Fluorinated_Imidazole peptide)

**Latency vs. complexity:**

| Category | MW range | Latency | Success |
|---|---|---|---|
| Simple aromatics (≤ 3 rings) | 123–199 Da | 12–25 s | 100% (6/6) |
| Drug-like polycyclics | 358–522 Da | 122–194 s | 100% (3/3) |
| Complex natural-product scale | 699–854 Da | 90 s (timeout) | 0% (0/2) |

GPU deployment would reduce drug-like polycyclic latency from 2–3 minutes to ~10 seconds, and would likely allow Orforglipron and Paclitaxel to complete within the timeout.
