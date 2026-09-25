import copy

import pytest

from corpus.schema import validate


def _rec(**over):
    r = {
        "schema": "valora.ref/1", "id": "yt-p38",
        "source": {"kind": "link", "platform": "youtube", "url": "https://www.youtube.com/shorts/gEJncZLWsJE",
                   "downloaded": False, "selection": "hand", "studiedAt": "2026-09-26", "timestampsS": [0, 10]},
        "method": "in_player", "qualityEstimate": "T3",
        "subject": {"category": "product", "sizeClass": "hand", "description": "soda can"},
        "format": {"aspect": "9:16", "durationS": 10, "fps": None, "shotCount": 2, "cutTimesS": [4.0]},
        "layout": {"kind": "full", "contentAspect": "9:16"},
        "shots": [
            {"startS": 0, "endS": 4.0, "cameraMove": "push", "lensClass": "normal", "cameraHeight": "low",
             "dutchTilt": False, "focus": "shallow", "subjectMotion": "static", "renderPass": "final", "notes": ""},
            {"startS": 4.0, "endS": 10, "cameraMove": "unclear", "lensClass": "macro", "cameraHeight": "eye",
             "dutchTilt": False, "focus": "shallow", "subjectMotion": "sim", "renderPass": "final", "notes": ""},
        ],
        "world": {"type": "abstract", "timeOfDay": "n/a", "weather": "n/a", "atmosphere": []},
        "lighting": {"setup": ["rim-heavy"], "keyDirection": "back", "colorTemps": "cool", "practicals": False},
        "grade": {"dominantHues": ["blue"], "contrast": "high", "saturation": "mid", "bloom": False,
                  "halation": None, "grain": False, "vignette": True},
        "effects": [], "simulation": ["fluid"], "surfaceState": ["condensation"], "secondarySubjects": [],
        "overlays": ["end_card"], "transitions": [{"atS": 4.0, "kind": "cut"}],
        "cameraImperfections": {k: "unclear" for k in (
            "motionBlur", "focusBreathing", "exposureAdaptation", "rollingShutter", "sensorNoise",
            "microShake", "lensFlare", "lensDistortion", "chromaticAberration")},
        "pacing": {"energy": "medium", "musicSyncCuts": None},
        "neverThoughtOf": ["droplets race the cut"],
        "evidence": {"format.cutTimesS": ["t=4.0s"], "shots[0].cameraMove": ["t=1.0s", "t=1.2s"]},
        "confidence": {"overall": "mid", "uncertainFields": []},
    }
    for path, v in over.items():
        node, *rest = path.split(".")
        tgt = r
        keys = [node] + rest
        for k in keys[:-1]:
            tgt = tgt[int(k)] if isinstance(tgt, list) else tgt[k]
        last = keys[-1]
        if isinstance(tgt, list):
            tgt[int(last)] = v
        else:
            tgt[last] = v
    return r


def test_valid_link_record():
    assert validate(_rec()) == []


def test_link_clip_is_never_downloaded():
    assert any("never downloaded" in p for p in validate(_rec(**{"source.downloaded": True})))


def test_vimeo_download_only_when_creator_enabled():
    r = _rec(**{"source.platform": "vimeo", "source.url": "https://vimeo.com/1", "source.downloaded": True})
    assert validate(r)
    r["source"]["vimeoDownloadEnabled"] = True
    r["method"] = "local_frames"
    r["source"]["localFile"] = "vimeo/vm-1.mp4"
    assert validate(r) == []


def test_stock_needs_hand_pick_licence_and_owner_download():
    r = _rec(**{"source": {"kind": "stock", "platform": "pexels", "url": "https://www.pexels.com/video/1/",
                           "downloaded": True, "selection": "hand", "studiedAt": "2026-09-26"}})
    probs = validate(r)
    assert any("licence" in p for p in probs) and any("downloadedBy" in p for p in probs)
    r["source"]["licence"] = {"name": "Pexels License", "url": "https://www.pexels.com/license/",
                              "checkedAt": "2026-09-26", "restricted": False}
    r["source"]["downloadedBy"] = "owner"
    r["source"]["localFile"] = "stock/pexels-video-1.mp4"
    r["method"] = "local_frames"
    assert validate(r) == []
    r["source"]["selection"] = "bulk"
    assert any("never bulk" in p for p in validate(r))


def test_restricted_stock_is_never_downloaded():
    r = _rec(**{"source": {"kind": "stock", "platform": "mixkit", "url": "https://mixkit.co/free-stock-video/x/",
                           "downloaded": True, "downloadedBy": "owner", "selection": "hand", "studiedAt": "2026-09-26",
                           "licence": {"name": "Mixkit Restricted License", "url": "https://mixkit.co/license/",
                                       "checkedAt": "2026-09-26", "restricted": True}}})
    r["method"] = "local_frames"
    assert any("restricted" in p for p in validate(r))


@pytest.mark.parametrize("path,value", [
    ("shots.0.cameraMove", "zoomies"), ("format.aspect", "9x16"), ("world.type", "moon"),
    ("layout.kind", "collage"), ("cameraImperfections.motionBlur", "maybe"), ("qualityEstimate", "T9"),
])
def test_bad_enums(path, value):
    assert validate(_rec(**{path: value}))


def test_shots_must_tile_the_span_and_match_cuts():
    assert any("contiguous" in p for p in validate(_rec(**{"shots.1.startS": 4.5})))
    assert any("cutTimesS" in p for p in validate(_rec(**{"format.cutTimesS": [5.0]})))
    assert any("shotCount" in p for p in validate(_rec(**{"format.shotCount": 3})))


def test_evidence_required_for_cuts_and_every_known_camera_move():
    r = _rec()
    del r["evidence"]["shots[0].cameraMove"]
    assert any("evidence" in p for p in validate(r))
    r = _rec()
    del r["evidence"]["format.cutTimesS"]
    assert any("evidence" in p for p in validate(r))


def test_unknown_top_level_key_and_non_dict_never_raise():
    assert validate(_rec(**{"bogus": 1}))
    assert validate([]) and validate(None)
    assert validate(_rec(**{"source": "owner-refs-2026-09-19"}))  # pilot shape: a string source
    assert validate(_rec(**{"shots": 1}))


def test_own_render_uses_script_ground_truth():
    r = _rec(**{"source": {"kind": "own_render", "script": "corpus/ab.py#lens-35-vs-85", "downloaded": False,
                           "selection": "hand", "studiedAt": "2026-09-26"}, "qualityEstimate": None})
    r["ab"] = {"pair": "lens-35-vs-85", "param": "shots[0].camera.params.lensMm", "a": 35, "b": 85,
               "frames": [], "finding": None}
    assert any("script_ground_truth" in p for p in validate(r))
    r["method"] = "script_ground_truth"
    assert validate(r) == []


# --- review fixes 2026-09-24 (phase 3 chunk 0) ---

def _owner(**src):
    r = _rec(**{"id": "ref04", "method": "local_frames"})
    r["source"] = {"kind": "owner", "platform": "owner-refs", "url": None, "downloaded": True,
                   "selection": "hand", "studiedAt": "2026-09-24", **src}
    return r


def test_owner_records_are_the_pilot_or_assets_in_refs_only():
    assert validate(_owner()) == []
    assert any("owner" in p for p in validate(_owner(platform="youtube")))
    assert any("owner" in p for p in validate(_owner(url="https://www.youtube.com/watch?v=x")))
    r = _owner()
    r["id"] = "yt-p38"
    assert any("owner" in p for p in validate(r))
    r["source"]["file"] = "assets-in/refs/clips/new.mp4"
    assert validate(r) == []
    r["source"]["file"] = "research/corpus/local/stock/x.mp4"
    assert any("owner" in p for p in validate(r))


def _stock(platform="pexels", url="https://www.pexels.com/video/1/", lic_url="https://www.pexels.com/license/",
           name="Pexels License", restricted=False, checked="2026-09-26"):
    r = _rec()
    r["method"] = "local_frames"
    r["source"] = {"kind": "stock", "platform": platform, "url": url, "downloaded": True, "downloadedBy": "owner",
                   "localFile": "stock/x.mp4", "selection": "hand", "studiedAt": "2026-09-26",
                   "licence": {"name": name, "url": lic_url, "checkedAt": checked, "restricted": restricted}}
    return r


def test_url_host_must_match_the_platform():
    assert validate(_stock()) == []
    assert any("host" in p for p in validate(_stock(url="https://www.youtube.com/watch?v=x")))
    assert any("host" in p for p in validate(_stock(url="https://pexels.com.evil.io/video/1/")))
    assert any("licence.url" in p for p in validate(_stock(lic_url="https://example.com/license")))
    assert any("host" in p for p in validate(_rec(**{"source.url": "https://vimeo.com/1"})))
    assert validate(_rec(**{"source.url": "https://youtu.be/gEJncZLWsJE"})) == []
    r = _rec(**{"source.platform": "vimeo", "source.url": "https://www.youtube.com/watch?v=x"})
    assert any("host" in p for p in validate(r))


def test_restricted_licence_name_needs_the_flag_and_checked_at_is_a_date():
    r = _stock("mixkit", "https://mixkit.co/free-stock-video/x/", "https://mixkit.co/license/",
               "Mixkit Restricted License", restricted=False)
    assert any("restricted" in p for p in validate(r))
    assert any("checkedAt" in p for p in validate(_stock(checked="yesterday")))
    assert any("checkedAt" in p for p in validate(_stock(checked="2026-13-45")))


def test_downloaded_stock_names_its_local_file():
    r = _stock()
    del r["source"]["localFile"]
    assert any("localFile" in p for p in validate(r))


def test_in_player_evidence_is_timestamps_only():
    r = _rec()
    r["evidence"]["format.cutTimesS"] = ["frames/s01_mid_4.00.jpg"]
    assert any("t=" in p for p in validate(r))
    r["evidence"]["format.cutTimesS"] = ["t=4s"]
    assert validate(r) == []
