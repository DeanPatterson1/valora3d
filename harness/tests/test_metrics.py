import json
from pathlib import Path

import numpy as np
import pytest

from harness import metrics as m

TH = json.loads((Path(__file__).resolve().parents[1] / "thresholds.json").read_text())
H, W = 256, 144


def frame(rgb=0.3, mask=None, gloss=None, mist=None):
    img = np.full((H, W, 3), rgb, dtype=np.float32) if np.isscalar(rgb) else rgb
    mk = np.zeros((H, W), bool) if mask is None else mask
    return m.Frame(frame=1, t=0.0, shot=0, lens=50.0, fstop=4.0, rgb=img, mask=mk,
                   gloss=mk.copy() if gloss is None else gloss, mist=mist)


def centre_mask(h=0.5, w=0.5):
    mk = np.zeros((H, W), bool)
    mk[int(H * (0.5 - h / 2)):int(H * (0.5 + h / 2)), int(W * (0.5 - w / 2)):int(W * (0.5 + w / 2))] = True
    return mk


def test_box_mean_matches_naive():
    rng = np.random.default_rng(0)
    a = rng.random((20, 30))
    naive = np.array([[np.pad(a, 2, mode="edge")[y:y + 5, x:x + 5].mean() for x in range(30)] for y in range(20)])
    assert np.allclose(m.box_mean(a, 2), naive)


def test_b01():
    assert m.b01(frame(0.0, centre_mask()), TH["B-01"])[1] is False
    assert m.b01(frame(0.3, centre_mask()), TH["B-01"])[1] is True


def test_b02_bright_clipping():
    img = np.full((H, W, 3), 0.4, np.float32)
    img[:20] = 1.0  # ~8% blown
    assert m.b02(frame(img, centre_mask()), TH["B-02"], black_world=False)[1] is False
    assert m.b02(frame(0.4, centre_mask()), TH["B-02"], black_world=False)[1] is True


def test_b05_dominant_axis_coverage():
    assert m.b05(frame(0.3, centre_mask(0.1, 0.1)), TH["B-05"])[1] is False
    assert m.b05(frame(0.3, centre_mask(0.2, 0.9)), TH["B-05"])[1] is True  # wide subject fills the width


def test_t306_strips_pass_blobs_fail():
    mk = centre_mask(0.6, 0.8)
    strip = np.full((H, W, 3), 0.3, np.float32)
    strip[120:124, 30:110] = 0.95
    blob = np.full((H, W, 3), 0.3, np.float32)
    blob[115:130, 60:75] = 0.95
    assert m.t306(frame(strip, mk), TH["T3-06"], vehicle=False)[1] is True
    assert m.t306(frame(blob, mk), TH["T3-06"], vehicle=False)[1] is False


def test_t307_planned_darks_and_highlights():
    mk = centre_mask(0.6, 0.8)
    img = np.full((H, W, 3), 0.4, np.float32)
    assert m.t307(frame(img, mk), TH["T3-07"])[1] is False
    img[:H // 2] = 0.05
    img[H // 2: H // 2 + 40] = 0.8
    assert m.t307(frame(img, mk), TH["T3-07"])[1] is True


def test_t308_blown_speculars():
    mk = centre_mask(0.6, 0.8)
    img = np.full((H, W, 3), 0.5, np.float32)
    img[100:110, 40:100] = 1.0
    assert m.t308(frame(img, mk), TH["T3-08"])[1] is False
    assert m.t308(frame(np.full((H, W, 3), 0.5, np.float32), mk), TH["T3-08"])[1] is True


def test_t309_silhouette_separation():
    mk = centre_mask()
    img = np.where(mk[..., None], 0.8, 0.1).repeat(3, -1).astype(np.float32)
    assert m.t309(frame(img, mk), TH["T3-09"])[1] is True
    assert m.t309(frame(np.full((H, W, 3), 0.5, np.float32), mk), TH["T3-09"])[1] is False


def test_t319_subject_chroma_over_background():
    mk = centre_mask()
    red_on_grey = np.where(mk[..., None], np.array([0.8, 0.1, 0.1]), 0.5).astype(np.float32)
    grey_on_red = np.where(mk[..., None], 0.5, np.array([0.8, 0.1, 0.1])).astype(np.float32)
    assert m.t319(frame(red_on_grey, mk), TH["T3-19"])[1] is True
    assert m.t319(frame(grey_on_red, mk), TH["T3-19"])[1] is False


def test_t207_far_background_is_softer():
    mk = centre_mask(0.3, 0.3)
    rng = np.random.default_rng(1)
    mist = np.tile(np.linspace(0, 1, H)[:, None], (1, W)).astype(np.float32)
    noisy = (0.4 + 0.2 * rng.random((H, W, 1))).repeat(3, -1).astype(np.float32)
    soft = noisy.copy()
    soft[mist > 0.6] = 0.4
    assert m.t207(frame(noisy, mk, mist=mist), TH["T2-07"])[1] is False
    assert m.t207(frame(soft, mk, mist=mist), TH["T2-07"])[1] is True


def test_t318_safe_zone():
    top_left = np.zeros((H, W), bool)
    top_left[:20, :20] = True
    assert m.t318(frame(0.3, top_left), TH["T3-18"], "9:16")[1] is False
    assert m.t318(frame(0.3, centre_mask()), TH["T3-18"], "9:16")[1] is True
    assert m.t318(frame(0.3, centre_mask()), TH["T3-18"], "16:9")[1] is None  # n/a


def _noise(seed, lo=0.3, amp=0.4):
    return (lo + amp * np.random.default_rng(seed).random((H, W, 1))).repeat(3, -1).astype(np.float32)


def test_t1x2_uniform_background_without_shadow_is_the_t1_signature():
    mk = centre_mask(0.4, 0.5)
    assert m.t1x2(frame(0.5, mk), TH["T1-X2"])[1] is False
    assert m.t1x2(frame(_noise(2), mk), TH["T1-X2"])[1] is True
    shadow = np.full((H, W, 3), 0.5, np.float32)
    ys, xs = np.nonzero(mk)
    shadow[ys.max() + 1: ys.max() + 1 + int(0.05 * H), xs.min():xs.max() + 1] = 0.1
    assert m.t1x2(frame(shadow, mk), TH["T1-X2"])[1] is True


def test_t202_reflections_show_the_environment():
    mk = centre_mask(0.5, 0.5)
    assert m.t202(frame(0.5, mk), TH["T2-02"])[1] is False
    grad = np.tile(np.linspace(0, 1, H)[:, None, None], (1, W, 3)).astype(np.float32)
    assert m.t202(frame(grad, mk), TH["T2-02"])[1] is True
    assert m.t202(frame(grad, mk, gloss=np.zeros((H, W), bool)), TH["T2-02"])[1] is None


def test_t206_subject_sharper_than_background():
    mk = centre_mask(0.5, 0.5)
    sharp_subject = np.where(mk[..., None], _noise(3), 0.4).astype(np.float32)
    sharp_bg = np.where(mk[..., None], 0.4, _noise(3)).astype(np.float32)
    assert m.t206(frame(sharp_subject, mk), TH["T2-06"])[1] is True
    assert m.t206(frame(sharp_bg, mk), TH["T2-06"])[1] is False
    deep = frame(sharp_bg, mk)
    deep.fstop = 8.0
    assert m.t206(deep, TH["T2-06"])[1] is None


def test_t303m_detail_fills_or_exceeds_the_frame():
    assert m.t303m(frame(0.3, centre_mask(0.3, 0.3)), TH["T3-03"])[1] is False
    assert m.t303m(frame(0.3, centre_mask(0.8, 0.8)), TH["T3-03"])[1] is True
    edge = np.zeros((H, W), bool)
    edge[:40, :40] = True  # small but cut by the frame edge
    assert m.t303m(frame(0.3, edge), TH["T3-03"])[1] is True


def test_t315_hook_subject_is_big_early():
    assert m.t315(frame(0.3, centre_mask(0.2, 0.2)), TH["T3-15"])[1] is False
    assert m.t315(frame(0.3, centre_mask(0.5, 0.5)), TH["T3-15"])[1] is True
    late = frame(0.3, centre_mask(0.2, 0.2))
    late.t = 3.0
    assert m.t315(late, TH["T3-15"])[1] is None


def test_t320_background_colour_consistent_across_shots():
    mk = centre_mask(0.3, 0.3)
    a, b, c = frame(0.3, mk), frame(0.32, mk), frame(np.full((H, W, 3), [0.8, 0.2, 0.1], np.float32), mk)
    b.shot, c.shot = 1, 1
    assert m.t320([a, b], TH["T3-20"])[1] is True
    assert m.t320([a, c], TH["T3-20"])[1] is False


def test_t322_long_lens_detail_is_shallow():
    mk = centre_mask(0.5, 0.5)
    sharp_subject = np.where(mk[..., None], _noise(4), 0.4).astype(np.float32)
    sharp_bg = np.where(mk[..., None], 0.4, _noise(4)).astype(np.float32)
    f1, f2 = frame(sharp_subject, mk), frame(sharp_bg, mk)
    f1.lens = f2.lens = 100.0
    assert m.t322(f1, TH["T3-22"])[1] is True
    assert m.t322(f2, TH["T3-22"])[1] is False
    assert m.t322(frame(sharp_bg, mk), TH["T3-22"])[1] is None  # 50 mm: n/a


def test_evaluate_aggregates_strictly_and_reports_unmeasured():
    from engine.catalog import Catalog
    from engine.profile import SubjectProfile
    fix = Path(__file__).resolve().parents[2] / "engine" / "tests" / "fixtures"
    prof = SubjectProfile.from_dict(json.loads((fix / "profiles" / "toycar.json").read_text()))
    script = json.loads((fix / "script_t3.json").read_text())
    good = frame(0.3, centre_mask(0.5, 0.6))
    black = frame(0.0, centre_mask(0.5, 0.6))
    black.frame, black.t, black.shot = 90, 3.0, 1  # shot 1 is a macro_detail (detail framing)
    r = m.evaluate([good, black], script, prof, Catalog.load(), TH)
    assert r["B-01"].status == "fail" and [v[0] for v in r["B-01"].value] == [1, 90]
    assert r["T3-15"].value == [(1, pytest.approx(0.3, abs=0.02), True)]  # hook: only t <= 0.5 s
    assert [v[0] for v in r["B-05"].value] == [1]  # full framing only
    assert [v[0] for v in r["T3-03"].value] == [90]  # detail framing only
    for iid in ("B-03", "T3-12", "T3-17", "T4-04"):
        assert r[iid].status == "unmeasured" and r[iid].detail
    assert r["T3-22"].status == "na"  # no frame at >= 85 mm


def _fixture(name):
    fix = Path(__file__).resolve().parents[2] / "engine" / "tests" / "fixtures"
    return json.loads((fix / name).read_text())


def test_evaluate_with_no_frames_is_unmeasured_never_na():
    from engine.catalog import Catalog
    from engine.profile import SubjectProfile
    prof = SubjectProfile.from_dict(_fixture("profiles/toycar.json"))
    r = m.evaluate([], _fixture("script_t3.json"), prof, Catalog.load(), TH)
    assert r and {v.status for v in r.values()} == {"unmeasured"}
