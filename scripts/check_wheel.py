"""Check the installed-shape CLI and all PDF inputs outside the checkout."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

wheel, = Path("dist").glob("*.whl")
with ZipFile(wheel) as archive:
    names = archive.namelist()
    assert "document_extractor/sample_data/manifest.json" in names
    assert len([name for name in names if name.startswith("document_extractor/sample_data/documents/") and name.endswith(".pdf")]) == 10
    with TemporaryDirectory(prefix="document-extraction-wheel-") as directory:
        archive.extractall(directory)
        script = '''
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from document_extractor import cli
assert Path(cli.__file__).is_relative_to(Path(sys.argv[1]))
raise SystemExit(cli.main(["--list-cases"]))
'''
        result = subprocess.run([sys.executable, "-c", script, directory], cwd=directory,
                                text=True, capture_output=True, check=True)
        data = json.loads(result.stdout)
        assert data["case_count"] == 10 and data["version"] == "1.0.0"
print("Packaged CLI, manifest and ten PDF inputs verified outside the checkout; no model called.")
