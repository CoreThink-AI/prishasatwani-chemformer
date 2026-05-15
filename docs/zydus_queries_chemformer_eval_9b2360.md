# Chemformer Retrosynthesis Evaluation — 9b2360

**Date:** 2026-05-15  
**Git commit:** `9b23605c8e9735fb5b9cee40b4967616329a7a3f`  
**API:** `https://chemformer-retrosynthesis-knq67derjq-uc.a.run.app/retrosynthesis/predict`  
**Beams:** 5  
**Data:** [`src/chemformer/data/zydus_queries_chemformer_eval_9b2360.yaml`](../src/chemformer/data/zydus_queries_chemformer_eval_9b2360.yaml)

## Summary

| Molecule | CID | log-likelihood | Quality | Reactants found | Purchasable | Δ complexity |
|----------|-----|---------------|---------|-----------------|-------------|-------------|
| Aspirin | 2244 | -0.942 | 🟢 high | ✓ | ✓ | +25 |
| Ibuprofen | 3672 | -1.835 | 🟢 high | ✓ | ✓ | +24 |
| Paclitaxel | 36314 | -17.819 | 🔴 low | ✗ | ✗ | -1649 |
| Etoricoxib | 123619 | -2.785 | 🔴 low | ✗ | ✗ | -495 |
| Camlipixant | 76955630 | -3.965 | 🔴 low | ✗ | ✗ | -702 |
| Fluorinated_Imidazole | 84117446 | -2.507 | 🔴 low | ✗ | ✗ | n/a |
| Fluorinated_Imidazole | 56842878 | -2.645 | 🔴 low | ✗ | ✗ | n/a |
| Methoxy_Diphenylamine | 11435828 | -2.751 | 🔴 low | ✗ | ✗ | -189 |
| Tolyl_Pyridine | 603589 | -2.487 | 🟢 high | ✓ | ✓ | +0 |
| Orforglipron | 137319706 | -24.058 | 🔴 low | ✗ | ✗ | n/a |
| Acalabrutinib | 71226662 | -3.200 | 🔴 low | ✗ | ✗ | -733 |

## Per-molecule details

### Aspirin (CID 2244)

**Input SMILES:** `CC(=O)OC1=CC=CC=C1C(=O)O`  
**Best log-likelihood:** -0.941845  
**Latency:** 14.378 s  
**Best reactants:** ``  
**Quality:** high  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CC(=O)OC1=CC=CC=C1C(=O)OCC` | [10728](https://pubchem.ncbi.nlm.nih.gov/compound/10728) | ethyl 2-acetyloxybenzoate | 105 | 237 | ✓ |

### Ibuprofen (CID 3672)

**Input SMILES:** `CC(C)CC1=CC=C(C=C1)[C@@H](C)C(=O)O`  
**Best log-likelihood:** -1.834675  
**Latency:** 8.755 s  
**Best reactants:** ``  
**Quality:** high  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CCOC(=O)[C@H](C)C1=CC=C(CC(C)C)C=C1` | [56665514](https://pubchem.ncbi.nlm.nih.gov/compound/56665514) | ethyl (2R)-2-[4-(2-methylpropyl)phenyl]p | 28 | 227 | ✓ |

### Paclitaxel (CID 36314)

**Input SMILES:** `CC1=C2[C@H](C(=O)[C@@]3([C@H](C[C@@H]4[C@]([C@H]3[C@@H]([C@@](C2(C)C)(C[C@@H]1OC(=O)[C@@H]([C@H](C5=CC=CC=C5)NC(=O)C6=CC=CC=C6)O)O)OC(=O)C7=CC=CC=C7)(CO4)OC(=O)C)O)C)OC(=O)C`  
**Best log-likelihood:** -17.819283  
**Latency:** 55.019 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CC(=O)O[C@@H]1C(C)=C2C(=O)[C@]3(C)[C@H](C[C@H]4…` | — | not found in PubChem | — | — | ✗ |
| `N[C@H](C(=O)O)C1=CC=CC=C1` | [99291](https://pubchem.ncbi.nlm.nih.gov/compound/99291) | (2S)-2-amino-2-phenylacetic acid | 169 | 141 | ✓ |

### Etoricoxib (CID 123619)

**Input SMILES:** `CC1=NC=C(C=C1)C2=C(C=C(C=N2)Cl)C3=CC=C(C=C3)S(=O)(=O)C`  
**Best log-likelihood:** -2.784513  
**Latency:** 19.866 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CC1=NC=C2C=CC(Cl)=CC3=CC(S(C)(=O)=O)=CC=C3C2=C1` | — | not found in PubChem | — | — | ✗ |
| `ClC(Cl)(Cl)Cl` | [5943](https://pubchem.ncbi.nlm.nih.gov/compound/5943) | tetrachloromethane | 141 | 19 | ✓ |

### Camlipixant (CID 76955630)

**Input SMILES:** `CC1=CC2=NC(=C(N2C=C1)C[C@H]3CN(CCO3)C(=O)OC)C4=C(C=C(C=C4F)C(=O)NC)F`  
**Best log-likelihood:** -3.964651  
**Latency:** 22.335 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CN` | [6329](https://pubchem.ncbi.nlm.nih.gov/compound/6329) | methanamine | 228 | 2 | ✓ |
| `COC(=O)N1CCO[C@@H](CC2=C3N=C4C=C(C)C=CN4C3=C(F)…` | — | not found in PubChem | — | — | ✗ |

### Fluorinated_Imidazole (CID 84117446)

**Input SMILES:** `CN1C=NC(=C1C2=CC=CC=C2F)C#N`  
**Best log-likelihood:** -2.507387  
**Latency:** 12.284 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CN1C=NC(=O)C1=C1C=CC=C1F` | — | not found in PubChem | — | — | ✗ |
| `N#C?` | — | not found in PubChem | — | — | ✗ |

### Fluorinated_Imidazole (CID 56842878)

**Input SMILES:** `C1C[C@H](N(C1)C(=O)[C@H](CC2=C(N=CN2)F)NC(=O)[C@@H]3CCC(=O)N3)C(=O)N`  
**Best log-likelihood:** -2.644887  
**Latency:** 21.295 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `NC(=O)[C@H]1CCCN1C(=O)[C@H](CC1=C(F)N=CN1)NC(=O…` | — | not found in PubChem | — | — | ✗ |

### Methoxy_Diphenylamine (CID 11435828)

**Input SMILES:** `CC1=CC=C(C=C1)NC2=CC=C(C=C2)OC`  
**Best log-likelihood:** -2.750577  
**Latency:** 11.457 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CC1=CC=C2NC(=C1)C=CC(O)=CC=2` | — | not found in PubChem | — | — | ✗ |
| `CO` | [887](https://pubchem.ncbi.nlm.nih.gov/compound/887) | methanol | 1161 | 2 | ✓ |

### Tolyl_Pyridine (CID 603589)

**Input SMILES:** `CC1=CC=C(C=C1)NC2=CN=CC=C2`  
**Best log-likelihood:** -2.486849  
**Latency:** 8.719 s  
**Best reactants:** ``  
**Quality:** high  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CC1=CC=C(NC2=CN=CC=C2)C=C1` | [603589](https://pubchem.ncbi.nlm.nih.gov/compound/603589) | N-(4-methylphenyl)pyridin-3-amine | 32 | 162 | ✓ |

### Orforglipron (CID 137319706)

**Input SMILES:** `C[C@H]1C[C@]1(C2=NOC(=O)N2)N3C4=C(C=C(C=C4)[C@H]5CCOC(C5)(C)C)C=C3C(=O)N6CCC7=NN(C(=C7[C@@H]6C)N8C=CN(C8=O)C9=C(C1=C(C=C9)N(N=C1)C)F)C1=CC(=C(C(=C1)C)F)C`  
**Best log-likelihood:** -24.057642  
**Latency:** 82.771 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `C=CC1=C(C2=NOC(=O)N2)N2C(=O)C3=CC4=CC(C=C(C)C)[…` | — | not found in PubChem | — | — | ✗ |

### Acalabrutinib (CID 71226662)

**Input SMILES:** `CC#CC(=O)N1CCC[C@H]1C2=NC(=C3N2C=CN=C3N)C4=CC=C(C=C4)C(=O)NC5=CC=CC=N5`  
**Best log-likelihood:** -3.199918  
**Latency:** 24.086 s  
**Best reactants:** ``  
**Quality:** low  

| Reactant SMILES | CID | Name | Vendors | Complexity | Purchasable |
|-----------------|-----|------|---------|------------|-------------|
| `CC#CC(=O)O` | [68535](https://pubchem.ncbi.nlm.nih.gov/compound/68535) | but-2-ynoic acid | 205 | 112 | ✓ |
| `NC1=NC=CN2C1=NC1=C3C=CC=C(NC(=O)C1=C2)N=CC=C3` | — | not found in PubChem | — | — | ✗ |

## Quality scale

| Quality | Meaning |
|---------|---------|
| 🟢 high | All reactants found in PubChem and commercially available |
| 🟡 partial | All reactants found but some not purchasable |
| 🔴 low | One or more reactants not found in PubChem |

*Generated by `scripts/zydus_queries_chemformer_responses_eval.py` from [`src/chemformer/data/zydus_queries_chemformer_eval_9b2360.yaml`](../src/chemformer/data/zydus_queries_chemformer_eval_9b2360.yaml)*
