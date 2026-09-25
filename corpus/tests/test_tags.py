from corpus.tags import TAGS, notes_of, tag_notes
from corpus.tests.test_schema import _rec


class FakeLaya:
    def __init__(self, choice, conf):
        self.choice, self.conf, self.calls = choice, conf, []

    def predict(self, inputs, questions):
        self.calls.append((inputs, questions))
        return {"answers": {"tag": {"choice": self.choice, "confidence": self.conf}}}


def test_notes_of_collects_never_thought_of_and_shot_notes():
    r = _rec()
    r["shots"][0]["notes"] = "light card visible"
    got = notes_of(r)
    assert ("yt-p38", "neverThoughtOf", "droplets race the cut") in got
    assert ("yt-p38", "shots[0].notes", "light card visible") in got


def test_tag_notes_uses_the_fixed_taxonomy_and_flags_low_confidence():
    rows = tag_notes([_rec()], FakeLaya("simulation", 0.42))
    assert rows == [{"ref": "yt-p38", "field": "neverThoughtOf", "note": "droplets race the cut",
                     "tag": "simulation", "confidence": 0.42, "needsReview": True}]
    rows = tag_notes([_rec()], FakeLaya("simulation", 0.9))
    assert rows[0]["needsReview"] is False


def test_unknown_choice_is_review_not_crash():
    rows = tag_notes([_rec()], FakeLaya("banana", 0.99))
    assert rows[0]["tag"] is None and rows[0]["needsReview"] is True
    assert set(TAGS) >= {"world", "camera", "lighting", "simulation"}
