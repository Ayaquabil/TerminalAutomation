"""conftest.py — Ajoute la racine du projet au sys.path pour que `import config`
et `import src.xxx` fonctionnent lorsque pytest est lancé depuis n'importe quel
répertoire de travail.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
