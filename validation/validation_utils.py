from pathlib import Path
from typing import Dict, List, Optional

from rdkit import Chem
from rdkit.Chem import AllChem, rdDetermineBonds, rdMolAlign

SDF_EXT = "sdf"
XYZ_EXT = "xyz"


def memoize_string_input(func):
    # NOTE(ilyaibraev): Usage of this decorator is not recommended due to unlimited memory usage
    cache = {}

    def wrapper(input_str: str):
        if input_str not in cache:
            cache[input_str] = func(input_str)
        return cache[input_str]

    return wrapper


@memoize_string_input
def get_inchikey_from_smiles(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    inchikey = Chem.rdinchi.MolToInchiKey(mol)
    return inchikey


def get_pachqa_structures(pachqa_structures_path) -> Dict[str, Path]:
    pachqa_structures_path = Path(pachqa_structures_path).absolute()
    pachqa_structures_mapped = {}
    for structure in pachqa_structures_path.glob("**/*.sdf"):
        inchikey = structure.parent.name
        path = structure.parent
        pachqa_structures_mapped[inchikey] = path
    return pachqa_structures_mapped


def get_ext(path: Path) -> str:
    return path.name.split(".")[-1]


def get_mol_with_ref(file: Path, file_ref: Path) -> Chem.Mol:
    mol = Chem.MolFromXYZFile(str(file))
    rdDetermineBonds.DetermineConnectivity(mol, useHueckel=True, charge=0)
    ref_mol = Chem.SDMolSupplier(str(file_ref))[0]
    mol = AllChem.AssignBondOrdersFromTemplate(ref_mol, mol)
    return mol


def read_mol(file: Path, file_ref: Optional[Path]) -> Chem.Mol:
    file1_ext = get_ext(file)
    if file1_ext == SDF_EXT:
        mol = Chem.SDMolSupplier(str(file))[0]
        ref_mol = Chem.SDMolSupplier(str(file_ref))[0]
        mol = AllChem.AssignBondOrdersFromTemplate(ref_mol, mol)
    elif file1_ext == XYZ_EXT and isinstance(file_ref, Path):
        mol = get_mol_with_ref(file, file_ref)
    else:
        raise ValueError("Not supported ext")
    for atom in mol.GetAtoms():
        atom.SetNumRadicalElectrons(0)
    return mol


def dump_mols(mol_arr: List[Chem.Mol], dump_name: str):
    with Chem.SDWriter(f"{dump_name}.sdf") as sdf_writer:
        for mol in mol_arr:
            mol = Chem.AddHs(mol, addCoords=True)
            sdf_writer.write(mol)
    for i, mol in enumerate(mol_arr):
        mol = Chem.AddHs(mol, addCoords=True)
        with Chem.SDWriter(f"{dump_name}_{i}.sdf") as sdf_writer:
            sdf_writer.write(mol)


def get_rmsd(mol1: Chem.Mol, mol2: Chem.Mol, dump: bool, dump_name: str, mirror_molecule: bool) -> float:
    mol1 = Chem.RemoveAllHs(mol1, sanitize=False)
    mol2 = Chem.RemoveAllHs(mol2, sanitize=False)
    normal = rdMolAlign.GetBestRMS(mol1, mol2)
    if dump:
        dump_mols([mol1, mol2], dump_name)
    if mirror_molecule:
        for i in range(mol2.GetNumAtoms()):
            pos = mol2.GetConformer().GetAtomPosition(i)
            mol2.GetConformer().SetAtomPosition(i, (-pos.x, pos.y, pos.z))
    rev = rdMolAlign.GetBestRMS(mol1, mol2)
    if dump and rev < normal:
        dump_mols([mol1, mol2], dump_name)
    return min(normal, rev)


def get_rmsd_between_two_molecules(
    file1: Path,
    file2: Path,
    ref: Optional[Path] = None,
    dump: bool = False,
    dump_name: str = "",
    mirror_molecule: bool = True,
) -> float:
    mol1 = read_mol(file1, ref)
    mol2 = read_mol(file2, ref)
    if dump and not dump_name:
        raise Exception("specify `dump_name` if you want to dump")
    return get_rmsd(mol1, mol2, dump, dump_name, mirror_molecule)
