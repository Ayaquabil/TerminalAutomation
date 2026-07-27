"""Script utilitaire pour lancer pytest et la vérification de conformité."""
import subprocess
import sys
import os

os.chdir(r"C:\Users\ayaqu\Desktop\testbeltaki\TerminalAutomation")

print("=== VERIFICATION REFERENCE ===")
from tests.verify_reference import run_verification
success = run_verification()
print("Verification result:", "OK" if success else "FAILED")

print("\n=== RUNNING PYTEST ===")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
    capture_output=False,
)
sys.exit(result.returncode)

