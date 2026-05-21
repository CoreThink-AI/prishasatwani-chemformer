import sys

from rdkit import Chem
from rdkit.Chem import Descriptors


def mol_from_smiles(smiles: str) -> Chem.Mol:
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

