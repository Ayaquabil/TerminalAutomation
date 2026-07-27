import urllib.request
from pathlib import Path

# Crée le dossier assets s'il n'existe pas
assets = Path(__file__).parent / "assets"
assets.mkdir(exist_ok=True)

logo_path = assets / "somaport_logo.png"
if not logo_path.exists():
    # L'utilisateur doit coller manuellement le logo ici
    print("Veuillez placer votre logo dans : assets/somaport_logo.png")
else:
    print(f"Logo trouvé : {logo_path}")
