"""The shipped catalog plus the test-only fixture blocks (engine/tests/fixtures/blocks) in a temp root.
The shipped catalog never contains a fixture block."""
import shutil
from pathlib import Path

from engine.catalog import BLOCKS_DIR, Catalog

FIXTURE_BLOCKS = Path(__file__).parent / "fixtures" / "blocks"


def catalog_with_fixtures(tmp_path):
    root = Path(tmp_path) / "catalog"
    ign = shutil.ignore_patterns("__pycache__")
    shutil.copytree(BLOCKS_DIR, root, ignore=ign)
    for kind_dir in sorted(p for p in FIXTURE_BLOCKS.iterdir() if p.is_dir()):
        for b in sorted(p for p in kind_dir.iterdir() if p.is_dir()):
            shutil.copytree(b, root / kind_dir.name / b.name, ignore=ign)
    return Catalog.load(root)
