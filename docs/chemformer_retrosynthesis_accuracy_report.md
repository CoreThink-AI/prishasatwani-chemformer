# Chemformer Retrosynthesis Accuracy & Viability Report

**Date:** 2026-05-15  
**Model checkpoints evaluated:** `backward_uspto50k` (pretrained), `uspto_50_last_v2` (fine-tuned)  
**API:** `https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app`  
**Data sources:**
- [`docs/etoricoxib_recursive_retrosynthesis_backward_uspto50k.yaml`](etoricoxib_recursive_retrosynthesis_backward_uspto50k.yaml) — 2-level tree, 5 beams
- [`docs/orforglipron_recursive_retrosynthesis_backward_uspto50k.yaml`](orforglipron_recursive_retrosynthesis_backward_uspto50k.yaml) — single-level, failed
- [`src/chemformer/data/zydus_queries_chemformer_eval_9b2360.yaml`](../src/chemformer/data/zydus_queries_chemformer_eval_9b2360.yaml) — 11 molecules, single-step evaluation

---

## 1. Summary

| Molecule | MW | log-likelihood | Viable pathway found? | Reactants purchasable |
|----------|----|---------------|-----------------------|-----------------------|
| Aspirin | 180 | −0.94 | Yes (1-step) | ✓ |
| Ibuprofen | 206 | −1.84 | Yes (1-step) | ✓ |
| Tolyl_Pyridine | 169 | −2.49 | Yes (1-step) | ✓ |
| Etoricoxib | 358 | −2.78 | Partial (2-step, chemically suspect) | ✗ |
| Fluorinated_Imidazole | ~140 | −2.51 | Partial | ✗ |
| Methoxy_Diphenylamine | 213 | −2.75 | Partial | ✗ |
| Acalabrutinib | 466 | −3.20 | No | ✗ |
| Camlipixant | 482 | −3.97 | No | ✗ |
| Paclitaxel | 854 | −17.82 | No | ✗ |
| Orforglipron | 880 | −24.06 | No | ✗ |

**Overall:** The model performs reliably for small, common molecules (MW < 250) but degrades sharply for drug-like molecules with MW > 350, and fails completely for large complex drugs.

---

## 2. Etoricoxib — Recursive Retrosynthesis Analysis

Etoricoxib (MW 358, COX-2 inhibitor) is the most informative test case because the tree expanded two levels and generated multiple alternative routes.

### Actual structure

Etoricoxib is a tri-aryl molecule: a 2-methylpyridine, a 6-chloropyridazine, and a 4-(methylsulfonyl)benzene, each connected to the others by single C–C bonds. The known industrial synthesis uses palladium-catalyzed coupling (Suzuki or Stille) to form the biaryl bonds, followed by sulfonyl group introduction via oxidation of a methylthio precursor.

### Route A — Best-ranked, 2-step (depth 0→2)

```
Step 1 (ll=−2.49): chloro-methylquinoline  +  methylsulfonyl-chloronaphthalene
                    (MW 169.5)                  (MW 231.5)
                          ↓ [coupling reaction?]
                    Fused tricyclic intermediate (MW ~325)

Step 2 (ll=−2.78): Fused tricyclic  +  CCl₄
                          ↓ [chlorination?]
                    Etoricoxib
```

**Assessment — LOW viability.**

- The proposed depth-1 intermediate (`CC1=NC=C2C=CC(Cl)=CC3=CC(S(C)(=O)=O)=CC=C3C2=C1`) is a *tricyclic fused ring* system, whereas Etoricoxib contains *three separate* rings connected by single C–C bonds. The model is proposing ring-fusion intermediates that do not match the actual topology of the product.
- Carbon tetrachloride (CCl₄) as a chlorinating reagent is rarely used in modern synthesis, is a toxic carcinogen, and has no established mechanism for converting a fused tricyclic into an open triaryl structure.
- The coupling in Step 1 (two fused bicyclics → tricyclic) has no obvious precedent and would require an unusual ring-forming C–C bond at a sterically congested position.
- Neither depth-2 reactant was found in PubChem by exact SMILES match, confirming they are not commercially available starting materials.

### Route B — Second-ranked, 1-step (depth 0, ll=−4.34)

```
Methylsulfonyl-naphthalene derivative  +  3,5-dichloropyridazine
(MW 234)                                    (MW 133)
        ↓
    Etoricoxib
```

**Assessment — MODERATE viability.**

- `ClC1=CC(Cl)=NC1` (3,5-dichloropyridazine analog) is a plausible electrophile for nucleophilic aromatic substitution (SNAr) or transition-metal-catalyzed coupling; halogenated diazines are standard building blocks in medicinal chemistry.
- The first reactant (`CC1=NC=C2C=CC=C(S(C)(=O)=O)C=CC2=C1`) is again a fused bicyclic in the SMILES notation, not the discrete aryl ring expected. This suggests the model may be systematically misinterpreting which atoms form rings versus tails in this structural class.
- The log-likelihood (−4.34) is lower confidence than Route A, which means the model itself "prefers" the chemically suspect Route A.

### Root cause of errors

The Chemformer model was trained on USPTO-50K reactions. Most USPTO-50K entries involve simpler transformations (ester hydrolysis, amide coupling, reductions, Suzuki coupling of monocyclic arenes). The model has not reliably learned to disconnect multi-ring heterocyclic drug scaffolds. Two failure modes appear here:

1. **Fused-ring hallucination**: The beam search generates SMILES with extra ring-closure digits, producing fused polycyclics instead of the biphenyl-type connectivity expected.
2. **Reagent memorization**: CCl₄, H₂O₂ (`OO`), and identity reactions (product = reactant) appear as high-beam predictions, likely artifacts of common co-reagents in the training data being attached to unrelated transformations.

---

## 3. Orforglipron — Complete Failure

```
best_ll: −24.06   status: no_viable_reactions
```

Orforglipron (MW 880, GLP-1 receptor agonist) returned `no_viable_reactions` at the default threshold of −5.0. The best log-likelihood of −24 is ~5× worse than the cutoff, placing it firmly outside the model's learned reaction distribution. This is expected: Orforglipron contains a cyclopropyl-oxadiazolone, an N-substituted indazole, a dihydropyrazolopyridine, and stereocenters the model has never encountered in training.

No chemical analysis is possible from these outputs; the model abstains rather than hallucinating.

---

## 4. Broader Single-Step Evaluation (11 molecules)

From the evaluation in `zydus_queries_chemformer_eval_9b2360.yaml` (5 beams per molecule):

| Quality tier | Molecules | Characteristics |
|---|---|---|
| **High** (all reactants found + purchasable) | Aspirin, Ibuprofen, Tolyl_Pyridine | MW < 210, simple functional groups, abundant in USPTO-50K |
| **Partial/Low** (reactants not in PubChem) | Etoricoxib, Fluorinated_Imidazole, Methoxy_Diphenylamine, Acalabrutinib, Camlipixant | MW 200–480, heteroaromatic rings, drug-like complexity |
| **Complete failure** (ll < −10) | Paclitaxel (ll=−17.8), Orforglipron (ll=−24.1) | MW > 800, multi-ring natural-product-like or peptido-mimetic |

**Complexity delta** (sum of reactant PubChem complexity − product complexity) is positive for the high-quality molecules (+24 to +25), confirming the model correctly identifies that reactants are simpler than products. For complex drugs the delta is deeply negative (Etoricoxib −495, Acalabrutinib −733), reflecting fused-ring hallucinations increasing apparent complexity.

---

## 5. Model Comparison: `uspto_50_last_v2` vs. `backward_uspto50k`

For Etoricoxib, both models produced similar top predictions:

| | Fine-tuned (`uspto_50_last_v2`) | Pretrained (`backward_uspto50k`) |
|-|---|---|
| Best ll | −2.52 | −2.78 |
| Top reactants | Fused ring + CCl₄ | Fused ring + CCl₄ |
| 2nd-best | Fused ring + CCl₄ | Methylsulfonyl naphthalene + dichloropyridazine |
| Beam 4 | Fused ring + CCl₄ | 2-component open-ring coupling (more plausible) |

The fine-tuned model is marginally more confident but converges on the same chemically questionable Route A. The pretrained model shows slightly more diversity at lower beams; its beam 4 (`CC1=NC=C2C=CC(Cl)=CC2=C1 + CS(=O)(=O)C1=CC=CC=C1Cl`, ll=−5.39) is actually the most chemically rational prediction from either model — two separate aryl fragments coupling — though still low-ranked.

---

## 6. Limitations of the Current Pipeline

1. **No stereochemistry validation.** The model ignores stereocenters. Etoricoxib has none, but this matters for chiral drugs.
2. **MW-based leaf detection is crude.** Using estimated molecular weight as a proxy for "purchasable building block" misclassifies naphthalene-derived intermediates (MW ~200–230) as leaves even when they aren't commercially available.
3. **No reaction condition prediction.** The model outputs reactant SMILES but not solvent, catalyst, temperature, or yield. Even chemically valid routes are incomplete without this.
4. **No duplicate-SMILES normalization.** The `visited` set uses raw SMILES strings; tautomers or canonicalization variants of the same compound can be re-expanded.
5. **Concurrency = 1 on Cloud Run.** Recursive calls are serialized; a 3-level tree with 5 beams and 5 branches can require 30+ API calls, taking several minutes.
6. **Training data bias.** USPTO-50K skews toward C–C coupling, ester/amide formation, and reduction reactions on monocyclic arenes. Complex heterocyclic and natural-product chemistry is underrepresented.

---

## 7. Recommendations

**For better results on drug-like molecules:**

- **Lower `--min-ll` to −8.0 or −10.0** and post-filter by PubChem purchasability rather than log-likelihood alone.
- **Add RDKit canonicalization** to the `visited` set and to the leaf check (purchasable fingerprint lookup rather than MW cutoff).
- **Use a model fine-tuned on USPTO-full or Pistachio** (>3M reactions), which has better coverage of heterocyclic coupling chemistry.
- **Add a PubChem leaf check** as an alternative/supplement to MW: a fragment is a leaf if it has a PubChem CID and vendor_count > 0, regardless of MW.
- **Cross-validate against known synthesis routes** (e.g., the published Etoricoxib synthesis from Merck) to measure top-k accuracy, not just whether reactants exist in PubChem.

**For this deployment specifically:**

- The service is useful today for lead-finding on small fragments (MW < 250) and for screening which of several candidate intermediates are commercially available.
- It should not be used to generate primary synthesis plans for novel drug candidates without expert chemist review.
