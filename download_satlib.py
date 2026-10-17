"""Télécharge les instances 3-SAT aléatoires de SATLIB dans ``data/satlib``.

Ces 3200 fichiers (uf : satisfiables, uuf : insatisfiables) servent à
``validate.py`` et ``bench_q2.py``. Ils ne sont pas versionnés : ce sont des
données publiques, faciles à récupérer.

Usage :
    python download_satlib.py
"""

import io
import tarfile
import urllib.request
from pathlib import Path

URL = "https://www.cs.ubc.ca/~hoos/SATLIB/Benchmarks/SAT/RND3SAT/{}.tar.gz"
FAMILIES = ["uf20-91", "uf50-218", "uuf50-218", "uf75-325", "uuf75-325"]
TARGET = Path(__file__).resolve().parent / "data" / "satlib"


def download(family):
    """Extrait les fichiers .cnf de l'archive dans data/satlib/<famille>/."""
    with urllib.request.urlopen(URL.format(family), timeout=60) as response:
        archive = tarfile.open(fileobj=io.BytesIO(response.read()), mode="r:gz")
    directory = TARGET / family
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    # Certaines archives rangent les fichiers dans des sous-dossiers :
    # seul le nom du fichier est conservé.
    for member in archive.getmembers():
        if member.isfile() and member.name.endswith(".cnf"):
            data = archive.extractfile(member).read()
            (directory / Path(member.name).name).write_bytes(data)
            count += 1
    return count


if __name__ == "__main__":
    for family in FAMILIES:
        print(f"{family} : {download(family)} fichiers")
