"""Render research corpus tooling (spec §9a). Host-only; never imported by engine/ or Blender.
Nothing in this package fetches or downloads a clip by itself."""
from pathlib import Path

REF_SCHEMA = "valora.ref/1"
ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "research" / "corpus"
REFS_DIR = CORPUS_DIR / "refs"
LOCAL_DIR = CORPUS_DIR / "local"      # clips and frames: gitignored, never committed
