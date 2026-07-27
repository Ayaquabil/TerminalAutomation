import pytest
import shutil
from pathlib import Path
from src.pipeline_runner import run_full_pipeline
import config

def test_cross_contamination_template_voyage(tmp_path):
    """
    Simule la présence d'un fichier template nommé avec un faux voyage
    pour vérifier que le pipeline ne lit pas cette donnée.
    """
    # Préparer les répertoires temporaires pour ce test
    input_dir = tmp_path / "input"
    template_dir = tmp_path / "template"
    output_dir = tmp_path / "output"
    
    input_dir.mkdir()
    template_dir.mkdir()
    output_dir.mkdir()
    
    # Modifier temporairement la configuration pour utiliser ces dossiers
    original_input = config.INPUT_DIR
    original_template = config.TEMPLATE_DIR
    original_output = config.OUTPUT_DIR
    
    config.INPUT_DIR = input_dir
    config.TEMPLATE_DIR = template_dir
    config.OUTPUT_DIR = output_dir
    
    import src.import_data
    original_threshold = src.import_data.BLUE_CELL_TEMPLATE_THRESHOLD
    src.import_data.BLUE_CELL_TEMPLATE_THRESHOLD = 5

    original_vessel = getattr(config, "TARGET_VESSEL_NAME", "")
    original_vessel_norm = getattr(config, "TARGET_VESSEL_NORMALIZED", "")
    original_voyage_import = getattr(config, "VOYAGE_IMPORT", "")
    original_voyage_export = getattr(config, "VOYAGE_EXPORT", "")
    
    config.TARGET_VESSEL_NAME = "NORDIC AURORA"
    config.TARGET_VESSEL_NORMALIZED = "NORDICAURORA"
    config.VOYAGE_IMPORT = "FALLBACK_VOYAGE"
    config.VOYAGE_EXPORT = "FALLBACK_VOYAGE"
    
    try:
        # Copier les données de test du "second navire" (multi_vessel) vers input_dir
        # On suppose que ce navire n'a PAS de voyage "0EMNAN1MA"
        second_vessel_dir = Path("tests/fixtures/second_vessel")
        if not second_vessel_dir.exists():
            pytest.skip("Fixtures du second navire introuvables")
            
        for f in second_vessel_dir.iterdir():
            if f.is_file():
                shutil.copy(f, input_dir / f.name)
            
        # Créer un faux fichier template dans le dossier persistant
        # Ce fichier contient le nom "WRONGVESSEL" et le voyage "0EMNAN1MA"
        wrong_template = template_dir / "TPFREP_0EMNAN1MA_WRONGVESSEL.xlsx"
        # Créer un fichier Excel basique
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.cell(1, 1, "TERMINAL DEPARTURE AND PERFORMANCE REPORT")
        wb.save(wrong_template)
        
        # Lancer le pipeline
        result = run_full_pipeline()
        merged_dataset = result.merged
        
        # Vérifier que le faux voyage N'EST PAS extrait
        assert merged_dataset is not None
        assert merged_dataset.voyage != "0EMNAN1MA", "Contamination croisée détectée : le voyage extrait provient de l'ancien template."
        assert "WRONGVESSEL" not in (merged_dataset.vessel_name or "").upper(), "Contamination croisée détectée : le nom du navire extrait provient de l'ancien template."
        
    finally:
        # Restaurer la configuration
        config.INPUT_DIR = original_input
        config.TEMPLATE_DIR = original_template
        config.OUTPUT_DIR = original_output
        config.TARGET_VESSEL_NAME = original_vessel
        config.TARGET_VESSEL_NORMALIZED = original_vessel_norm
        config.VOYAGE_IMPORT = original_voyage_import
        config.VOYAGE_EXPORT = original_voyage_export
        src.import_data.BLUE_CELL_TEMPLATE_THRESHOLD = original_threshold
