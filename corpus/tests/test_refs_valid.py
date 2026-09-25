import json

import pytest

from corpus import REFS_DIR
from corpus.schema import validate

RECORDS = sorted(REFS_DIR.glob("*.json"))


def test_there_are_records():
    assert len(RECORDS) >= 11


@pytest.mark.parametrize("path", RECORDS, ids=[p.stem for p in RECORDS])
def test_every_committed_record_validates(path):
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["id"] == path.stem
    assert validate(rec) == []
