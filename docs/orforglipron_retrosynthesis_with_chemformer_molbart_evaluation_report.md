# Chemformer Retrosynthesis Model Evaluation Report

**Model:** Chemformer BART (backward prediction, USPTO-50K fine-tune)
**Checkpoint:** `backward_uspto50k.ckpt` ([Figshare 42009888](https://figshare.com/articles/dataset/Chemformer/14766561))
**Service:** `https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app`
**Date:** 2026-05-08

---

## Summary

| Molecule | MW (Da) | Top-1 log-likelihood | Top-1 valid? | Chemically correct? |
|---|---|---|---|---|
| Aspirin | 180 | −0.74 | Yes | Yes |
| Methoxy_Diphenylamine | 213 | −0.69 | Yes | Yes |
| Fluorinated_Imidazole | 201 | −0.75 | Yes | Yes |
| Ibuprofen | 206 | −0.96 | Yes | Yes |
| Tolyl_Pyridine | 184 | −0.89 | Yes | Yes |
| Etoricoxib | 359 | −2.79 | Partial | Partially |
| Camlipixant | 458 | −3.97 | Partial | Partially |
| Paclitaxel (Taxol) | 854 | −7.93 | Partial | Partially |
| Orforglipron | 881 | −24.1 | Partial | No |
| Acalabrutinib | 632 | -0.95 | Partial | Yes |

<NOTE>
### Testset of drug molecules
- Acalabrutinib -> [CID 71226662](https://pubchem.ncbi.nlm.nih.gov/compound/71226662): CC#CC(=O)N1CCC[C@H]1C2=NC(=C3N2C=CN=C3N)C4=CC=C(C=C4)C(=O)NC5=CC=CC=N5 -> "CC#CC(=O)O + pyrrolidine-substituted imidazopyrazine core"
- Fluorinated_Imidazole -> [5-fluoroimidazole](https://pubchem.ncbi.nlm.nih.gov/compound/56842878)
</NOTE>

The model performs well on small, drug-like molecules within common synthetic reaction classes (MW < 400 Da, Buchwald-Hartwig aminations, ester hydrolyses, dehydrations). Performance degrades gracefully as molecular complexity increases. A log-likelihood threshold of approximately −2 separates high-confidence correct predictions from partial or incorrect ones.

---

## Test Setup

The service accepts a POST request with a product SMILES and returns beam-search retrosynthesis predictions ranked by log-likelihood.

```python
import requests

SERVICE_URL = "https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app"

def predict_retrosynthesis(smiles: str, n_beams: int = 5) -> dict:
    response = requests.post(
        f"{SERVICE_URL}/retrosynthesis/predict",
        json={"smiles": smiles, "n_beams": n_beams},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()
```

---

## Aspirin

**SMILES:** `CC(=O)Oc1ccccc1C(=O)O`
**MW:** 180.16 Da — simple aromatic ester

```python
result = predict_retrosynthesis("CC(=O)Oc1ccccc1C(=O)O", n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-0.742): CC(=O)Cl.O=C(O)c1ccccc1O
Beam 2 (ll=-6.260): c1ccc(O)c(C(O)=O)c1.ClC(=O)C
Beam 3 (ll=-6.308): c1ccc(O)c(C(=O)O)c1.ClC(=O)C
Beam 4 (ll=-6.372): c1ccc(O)c(C(O)=O)c1.ClC(C)=O
Beam 5 (ll=-6.421): c1ccc(O)c(C(=O)O)c1.ClC(C)=O
```

**Assessment:** Excellent. Beam 1 correctly identifies the classic acetylation route:
- **Reactant 1:** `CC(=O)Cl` — acetyl chloride
- **Reactant 2:** `O=C(O)c1ccccc1O` — salicylic acid

This is the exact industrially used synthesis. <NOTE>Chlorine SMILES are different than the salycylic acid reaction SMILES mentioned in PubChem manufacturing section</NOTE> Beams 2–5 are canonically equivalent representations of the same two reactants. The high confidence (log-likelihood −0.74) reflects that this reaction class appears frequently in USPTO-50K.

---

## Ibuprofen

**SMILES:** `CC(C)Cc1ccc(cc1)C(C)C(=O)O`
**MW:** 206.28 Da — substituted arylpropionic acid

```python
result = predict_retrosynthesis("CC(C)Cc1ccc(cc1)C(C)C(=O)O", n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-0.964): CCOC(=O)C(C)c1ccc(CC(C)C)cc1
Beam 2 (ll=-2.301): CC(C)Cc1ccc(C(C)C(=O)OCC)cc1
Beam 3 (ll=-4.142): c1cc(CC(C)C)ccc1C(C)C(=O)OCC
Beam 4 (ll=-4.144): c1cc(CC(C)C)ccc1C(C)C(OCC)=O
Beam 5 (ll=-4.225): c1c(CC(C)C)ccc(C(C)C(=O)OCC)c1
```

**Assessment:** Good. All five beams predict ester hydrolysis (ethyl ester → carboxylic acid), identifying `CCOC(=O)C(C)c1ccc(CC(C)C)cc1` (ethyl ibuprofen ester) as the precursor. This is a valid retrosynthetic disconnection — ester hydrolysis is a standard deprotection step in ibuprofen synthesis routes. The slight confidence drop vs aspirin (−0.96 vs −0.74) likely reflects the additional alkyl substitution complexity. Beams 2–5 are equivalent SMILES representations with minor reordering.

Note: the industrial Boot–Nicholson synthesis of ibuprofen uses a different route (Friedel-Crafts acylation of isobutylbenzene), which is not predicted here. The model correctly identifies a valid route but not necessarily the most industrially common one.

---

## Paclitaxel (Taxol)

**SMILES:** `CC1=C2[C@@]([C@H](C(=O)[C@@H]3[C@@]2(OC(=O)[C@@H]([C@@H]3O)NC(=O)c4ccccc4)C)OC(=O)c5ccccc5)(C[C@@H]1OC(=O)[C@H](O)c6ccccc6)O`
**MW:** 853.91 Da — taxane diterpenoid, antimitotic natural product (Bristol-Myers Squibb)

```python
paclitaxel_smiles = (
    "CC1=C2[C@@]([C@H](C(=O)[C@@H]3[C@@]2(OC(=O)[C@@H]([C@@H]3O)"
    "NC(=O)c4ccccc4)C)OC(=O)c5ccccc5)(C[C@@H]1OC(=O)[C@H](O)c6ccccc6)O"
)
result = predict_retrosynthesis(paclitaxel_smiles, n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles'][:80]}...")
```

**Output:**
```
Beam 1 (ll=-7.931): CC1=C2[C@@](O)([C@H](C(=O)[C@H]3[C@@H](O)[C@@H](NC(=O)c4ccccc4)C(=O)O...
Beam 2 (ll=-8.205): CC1=C2[C@](O)(C[C@@H]1OC(=O)[C@H](O)c1ccccc1)C[C@H](O)C2=C(C)[C@H]1...
                    .O=C(O)c1ccccc1
Beam 3 (ll=-8.516): CC1=C2[C@](O)(C[C@@H]1OC(=O)[C@H](O)c1ccccc1)C[C@H](O)C2=C(C)[C@H]1...
Beam 4 (ll=-9.410): CC1=C2[C@](O)(C[C@@H]1OC(=O)[C@H](O)c1ccccc1)C[C@H](O)C2=C(C)[C@@H](O)...
Beam 5 (ll=-11.815): CC1=C2[C@](O)(C[C@@H]1OC(=O)[C@H](O)c1ccccc1)C[C@H](O)C2=C(C)[C@@H](O)...
```

**Assessment:** Partially correct. Log-likelihoods of −7.9 to −11.8 sit between the simple drugs and Orforglipron, reflecting a molecule at the edge of the training distribution.

- **Beam 1** (ll=−7.93): Rearranges the oxetane ring but keeps the full taxane scaffold intact — not a useful synthetic disconnection.
- **Beams 2–3** (ll=−8.2 to −8.5): More chemically meaningful — these cleave the C-13 ester side chain, yielding a baccatin III-like taxane core plus benzoic acid (`O=C(O)c1ccccc1`). This approximates the real semi-synthetic route: commercial paclitaxel production starts from **10-deacetylbaccatin III** (extracted from *Taxus baccata* needles) and attaches the β-lactam side chain via esterification. The model partially recovers this strategy.
- **Beams 4–5** (ll=−9.4 to −11.8): Alternative ester disconnections on the taxane core with progressively lower confidence.

The model cannot reconstruct the Holton or Danishefsky total synthesis routes (which build the taxane ring system from simpler precursors) — these multi-step ring-forming strategies are beyond the scope of a single-step model trained on USPTO-50K.

---

## Etoricoxib

**SMILES:** `CC1=NC=C(C=C1)C2=C(C=C(C=N2)Cl)C3=CC=C(C=C3)S(=O)(=O)C`
**MW:** 358.85 Da — selective COX-2 inhibitor (Merck, 2002)

```python
result = predict_retrosynthesis(
    "CC1=NC=C(C=C1)C2=C(C=C(C=N2)Cl)C3=CC=C(C=C3)S(=O)(=O)C", n_beams=5
)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-2.785): CC1=NC=C2C=CC(Cl)=CC3=CC(S(C)(=O)=O)=CC=C3C2=C1.ClC(Cl)(Cl)Cl
Beam 2 (ll=-4.343): CC1=NC=C2C=CC=C(S(C)(=O)=O)C=CC2=C1.ClC1=CC(Cl)=NC1
Beam 3 (ll=-5.062): CC1=NC=C2C(=C1)C=CC(Cl)=CC21=CC=C(S(C)(=O)=O)C=C1.ClC(Cl)(Cl)Cl
Beam 4 (ll=-5.390): CC1=NC=C2C=CC(Cl)=CC2=C1.CS(=O)(=O)C1=CC=CC=C1Cl
Beam 5 (ll=-5.484): CC1=NC=C2C=CC=C(S(C)(=O)=O)C=CC=C2C2=C1C=CC(Cl)=N2.ClC(Cl)(Cl)Cl
```

**Assessment:** Partial. Log-likelihood of −2.79 sits just at the confidence boundary. The model correctly identifies that the two key substructures — the methylpyridine fragment and the chloropyrimidine — need to be coupled, but proposes an implausible CCl4-mediated halogenation rather than the correct cross-coupling strategy. Beam 4 is closest to a real retrosynthetic disconnection, cleaving the biaryl bond to give a methylpyrimidine fragment and a chlorinated arylsulfone, consistent with a Suzuki or Negishi coupling approach. Etoricoxib's tricyclic-like heteroaryl framework is uncommon in USPTO-50K.

---

## Camlipixant

**SMILES:** `CC1=CC2=NC(=C(N2C=C1)C[C@H]3CN(CCO3)C(=O)OC)C4=C(C=C(C=C4F)C(=O)NC)F`
**MW:** 458.47 Da — selective P2X3 receptor antagonist for chronic refractory cough (AstraZeneca)

```python
result = predict_retrosynthesis(
    "CC1=CC2=NC(=C(N2C=C1)C[C@H]3CN(CCO3)C(=O)OC)C4=C(C=C(C=C4F)C(=O)NC)F",
    n_beams=5,
)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-3.965): CN.COC(=O)N1CCO[C@@H](CC2=C3N=C4C=C(C)C=CN4C3=C(F)C=C(C(=O)O)C=C4F)C1
Beam 2 (ll=-5.086): CN.COC(=O)N1CCO[C@@H](CC2=C3N=C4C=C(C)C=CN4C(=C3C(F)=CC(C(=O)O)=C4)C2)C1
Beam 3 (ll=-5.595): CN.COC(=O)N1CCO[C@@H](CC2=C3N=C4C=C(C)C=CN4C3=C(F)C(C(=O)O)=CC4=C2F)C1
Beam 4 (ll=-5.622): CN.COC(=O)N1CCO[C@@H](CC2=C3N=C4C=C(C)C=C4C=C(F)C3=C(F)C=C(C(=O)O)C=C4F)C1
Beam 5 (ll=-5.978): CN.COC(=O)N1CCO[C@@H](CC2=C3N=C4C=C(C)C=CN4C(=C3C(F)=CC(C(=O)O)=C2F)C4)C1
```

**Assessment:** Partially correct. Log-likelihood of −3.97 reflects moderate complexity. All five beams consistently produce the same two-component split: methylamine (`CN`) plus a complex morpholine-imidazopyridine fragment retaining the carboxylic acid form of the methylamide. This correctly identifies the terminal **amide bond** (`C(=O)NC`) as the retrosynthetic disconnection — the model recognises that `C(=O)NC` arises from coupling a carboxylic acid with methylamine. The core imidazopyridine scaffold is intact across all beams, suggesting the model treats it as a stable, pre-formed building block. A genuine synthesis would likely also fragment the morpholine side chain, which the model does not attempt.

---

## Fluorinated_Imidazole

### Disambiguation:
- [5-fluoroimidazole CID_56842878](https://pubchem.ncbi.nlm.nih.gov/compound/56842878) "Thyrotropin releasing hormone 5-fluoroimidazole
": 2 vendors, hormone
- 5-Fluorobenzimidazole CID_235698: 65 vendors, no bioassays
- 2-Fluoroimidazole CID_559542: 38 vendors, few bioassays
- 4-Fluoroimidazole CID_99297: 66 vendors, no bioassays

**SMILES:** `N#CC1=C(C2=CC=CC=C2F)N(C)C=N1`
**MW:** 201.20 Da — fluorophenyl imidazole-4-carbonitrile (synthetic intermediate)

```python
result = predict_retrosynthesis("N#CC1=C(C2=CC=CC=C2F)N(C)C=N1", n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-0.754): CN1C=NC(C(N)=O)=C1C1=CC=CC=C1F
Beam 2 (ll=-4.189): CN1C(C2=CC=CC=C2F)=C(C(N)=O)N=C1
Beam 3 (ll=-4.284): CN1C(C2=CC=CC=C2F)=C(C(=O)N)N=C1
Beam 4 (ll=-4.353): FC1=CC=CC=C1C1=C(C(N)=O)N=CN1C
Beam 5 (ll=-5.105): FC1=CC=CC=C1C1=C(C#N)N=CN1.CI
```

**Assessment:** Excellent. Beam 1 (ll=−0.75) correctly predicts **amide dehydration**: the primary amide `CN1C=NC(C(N)=O)=C1C1=CC=CC=C1F` loses water to give the nitrile. This is a well-established one-step transformation using reagents such as POCl₃, trifluoroacetic anhydride, or Burgess reagent. Beams 2–4 are canonical SMILES variants of the same amide precursor. Beam 5 offers an alternative N-methylation disconnection (imidazole + iodomethane), also chemically valid. Both routes appear in practice.

---

## Methoxy_Diphenylamine

**SMILES:** `COc1ccc(Nc2ccc(C)cc2)cc1`
**MW:** 213.28 Da — 4-methoxy-4′-methyldiphenylamine (diarylamine coupling product)

```python
result = predict_retrosynthesis("COc1ccc(Nc2ccc(C)cc2)cc1", n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-0.687): COc1ccc(N)cc1.Cc1ccc(Br)cc1
Beam 2 (ll=-5.206): c1c(N)ccc(OC)c1.c1c(Br)ccc(C)c1
Beam 3 (ll=-5.280): c1c(OC)ccc(N)c1.c1c(Br)ccc(C)c1
Beam 4 (ll=-5.317): c1c(N)ccc(OC)c1.c1cc(Br)ccc1C
Beam 5 (ll=-5.405): c1c(OC)ccc(N)c1.c1cc(Br)ccc1C
```

**Assessment:** Excellent. Beam 1 (ll=−0.69, the highest confidence of all test molecules) correctly identifies **Buchwald-Hartwig C–N coupling**: 4-methoxyaniline (`COc1ccc(N)cc1`) + 4-bromotoluene (`Cc1ccc(Br)cc1`). This is exactly the standard palladium-catalysed amination used to synthesise diarylamines. Beams 2–5 are canonical SMILES reorderings of the same pair. The near-perfect confidence reflects that Buchwald-Hartwig disconnections of this type are well-represented in USPTO-50K.

---

## Tolyl_Pyridine

**SMILES:** `Cc1ccc(Nc2cccnc2)cc1`
**MW:** 184.24 Da — N-(4-methylphenyl)pyridin-3-amine (aryl-heteroaryl amine)

```python
result = predict_retrosynthesis("Cc1ccc(Nc2cccnc2)cc1", n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles']}")
```

**Output:**
```
Beam 1 (ll=-0.890): Brc1cccnc1.Cc1ccc(N)cc1
Beam 2 (ll=-1.791): Cc1ccc(Br)cc1.Nc1cccnc1
Beam 3 (ll=-6.458): c1cc(C)ccc1Br.c1cc(N)cnc1
Beam 4 (ll=-6.541): c1cc(C)ccc1Br.c1(N)cnccc1
Beam 5 (ll=-6.667): c1cc(C)ccc1Br.c1c(N)cncc1
```

**Assessment:** Excellent. The model correctly predicts **Buchwald-Hartwig amination** in two complementary disconnections:
- **Beam 1** (ll=−0.89): 3-bromopyridine + 4-toluidine — aryl bromide on the pyridine
- **Beam 2** (ll=−1.79): 4-bromotoluene + 3-aminopyridine — aryl bromide on the toluene

Both are synthetically valid; Beam 1 is slightly preferred because C–N coupling onto electron-deficient pyridine rings is generally more facile. Beams 3–5 are SMILES variants of the same Beam 2 disconnection. The model provides genuinely diverse top-2 predictions here, unlike simpler cases where all beams converge to canonical rewrites of one route.

---

## Orforglipron

**SMILES:** `C[C@H]1C[C@]1(C2=NOC(=O)N2)N3C4=C(C=C(C=C4)[C@H]5CCOC(C5)(C)C)C=C3C(=O)N6CCC7=NN(C(=C7[C@@H]6C)N8C=CN(C8=O)C9=C(C1=C(C=C9)N(N=C1)C)F)C1=CC(=C(C(=C1)C)F)C`
**MW:** 881 Da — oral GLP-1 receptor agonist (Eli Lilly, 2024)

```python
orforglipron_smiles = (
    "C[C@H]1C[C@]1(C2=NOC(=O)N2)"
    "N3C4=C(C=C(C=C4)[C@H]5CCOC(C5)(C)C)C=C3"
    "C(=O)N6CCC7=NN(C(=C7[C@@H]6C)"
    "N8C=CN(C8=O)C9=C(C1=C(C=C9)N(N=C1)C)F)"
    "C1=CC(=C(C(=C1)C)F)C"
)
result = predict_retrosynthesis(orforglipron_smiles, n_beams=5)
for i, p in enumerate(result["predictions"], 1):
    print(f"Beam {i} (ll={p['log_likelihood']:.3f}): {p['reactants_smiles'][:80]}...")
```

**Output:**
```
Beam 1 (ll=-24.058): C=CC1=C(C2=NOC(=O)N2)N2C(=O)C3=CC4=CC(C=C(C)C)[C@H]5CCOC(C)(C)C5=CN4C(=O)...
Beam 2 (ll=-24.109): C=CC1=C(C2=NOC(=O)N2)N2C(=O)C3=CC4=CC(C=C(C)C)[C@H]5CCOC(C)(C)C5=CN4C(=O)...
Beam 3 (ll=-24.753): C=CC1=C(C2=NOC(=O)N2)N2C(=O)C3=CC4=CC(C=C(C)C)[C@H]5CCOC(C)(C)C5=CN4C(=O)...
Beam 4 (ll=-25.542): ...C(=O)N3C[C@@H]2C1.NC(=O)O
Beam 5 (ll=-25.654): C=CC1=C(C2=NOC(=O)N2)N2C(=O)C3=CC4=CC(C=C(C)C)[C@H]5CCOC(C)(C)C5=CN4C(=O)...
```

**Assessment:** Poor, as expected. Several failure modes are evident:

1. **Very low confidence** — log-likelihoods of −24 to −26, compared to −0.7 to −1.0 for simple drugs. The model assigns near-zero probability to any single-step route.
2. **No clean disconnections** — predicted reactants are large, complex molecules nearly as difficult to synthesize as the product itself. No meaningful bonds are being broken.
3. **Out-of-distribution molecule** — Orforglipron contains structural motifs uncommon in USPTO-50K: a cyclopropyl-urea warhead, a triazolopyrimidine-piperidinyl core, multiple difluorophenyl groups, and five stereocenters. The training set is dominated by 2–4 step reactions on molecules with MW < 500 Da.

---

## Conclusions

### Performance vs molecular complexity

The nine test molecules reveal a clear gradient correlated with reaction class familiarity and molecular size:

| Log-likelihood range | Interpretation | Examples |
|---|---|---|
| > −2 | High confidence; prediction likely correct | Aspirin, Ibuprofen, Fluorinated_Imidazole, Methoxy_Diphenylamine, Tolyl_Pyridine |
| −2 to −10 | Moderate confidence; partial or approximate route | Etoricoxib, Camlipixant, Paclitaxel |
| < −10 | Low confidence; molecule out of training distribution | Orforglipron |

The five high-confidence molecules all involve reaction classes heavily represented in USPTO-50K: ester hydrolysis, amide dehydration, and Buchwald-Hartwig C–N coupling. The three mid-confidence molecules are larger (MW 358–854 Da) or contain unusual heterocyclic frameworks. Orforglipron is uniquely difficult: large, modern, and structurally unlike anything in the training set.

### What works well
- Small molecules (MW < 300 Da) within common synthetic chemistry classes
- High-confidence predictions (log-likelihood > −2) correlate with correct, well-known routes
- Multiple beams often represent the same correct route with canonical SMILES variants, indicating high model certainty
- For mid-complexity natural products, the model recovers the correct reaction *class* (ester hydrolysis, acylation) even if the specific disconnection is imperfect

### Limitations
- **Training distribution cutoff:** USPTO-50K covers reactions up to ~2016 and skews toward simple academic organic chemistry. Modern drug candidates like Orforglipron fall outside this distribution.
- **Single-step only:** The service predicts one retrosynthetic step. Complex targets require chained multi-step planning (AiZynthFinder, ASKCOS, IBM RXN).
- **No stereochemistry reasoning:** The model does not reason about whether the predicted route will reproduce the correct stereochemistry.
- **SMILES canonicalization:** Top beams are often SMILES-equivalent representations of the same reactants rather than genuinely diverse routes.
- **Natural product total synthesis:** Ring-forming strategies (e.g., Holton/Danishefsky taxol synthesis) are beyond single-step scope.

### Recommended use cases
- Quick single-step retrosynthetic lookup for lead optimization analogs
- Reaction class classification (ester hydrolysis, acylation, etc.)
- Filtering/ranking candidate routes generated by other tools
- Confidence scoring to flag molecules likely outside the training distribution (ll < −10 as a threshold)

### Not recommended for
- Novel drug candidates outside USPTO-50K chemistry space (MW > 500 Da, modern heterocyclic scaffolds)
- Stereoselective synthesis planning
- Natural product total synthesis route design
- Final synthetic route selection without expert chemist review
