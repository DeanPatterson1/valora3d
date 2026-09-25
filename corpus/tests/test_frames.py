import shutil
import subprocess

import pytest

from corpus.frames import detect_cuts, extract, merge_cuts, sample_plan

FFMPEG = shutil.which("ffmpeg")


def test_merge_cuts_unions_and_merges_close_times():
    assert merge_cuts([2.5, 1.0, 1.05, 2.52, 7.0], gap=0.2) == [1.0, 2.5, 7.0]


def test_sample_plan_mid_and_pair_per_shot():
    plan = sample_plan(4.0, [1.0, 2.5])
    shots = sorted({p["shot"] for p in plan})
    assert shots == [0, 1, 2]
    s1 = [p for p in plan if p["shot"] == 1]
    assert [p["kind"] for p in s1] == ["mid", "pairA", "pairB"]
    assert s1[0]["t"] == pytest.approx(1.75)
    assert s1[2]["t"] - s1[1]["t"] == pytest.approx(0.2)
    assert all(0 <= p["t"] < 4.0 for p in plan)
    assert max(p["t"] for p in sample_plan(1.6, [1.0])) <= 1.55  # never past the last frame


def test_sample_plan_short_shot_has_no_pair():
    plan = sample_plan(1.3, [1.15])
    assert [p["kind"] for p in plan if p["shot"] == 1] == ["mid"]


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
def test_detect_cuts_and_extract_on_a_synthetic_clip(tmp_path):
    clip = tmp_path / "c.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-filter_complex",
                    "color=c=red:s=96x96:d=1:r=30[a];color=c=blue:s=96x96:d=1.5:r=30[b];"
                    "color=c=green:s=96x96:d=1:r=30[c];[a][b][c]concat=n=3:v=1:a=0",
                    "-pix_fmt", "yuv420p", str(clip)], check=True)
    cuts = detect_cuts(clip)
    assert [round(c, 1) for c in cuts] == [1.0, 2.5]
    paths = extract(clip, sample_plan(3.5, cuts), tmp_path / "frames")
    assert len(paths) >= 3 and all(p.exists() for p in paths)
