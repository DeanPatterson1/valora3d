import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from worker import encode
from worker.contract import WorkerError
from worker.fake_site_job import png
from worker.tests.conftest import have_drawtext, system_font

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.mark.parametrize("fps,want", [(30, "30"), (30.0, "30"), (24, "24"), (15.0, "15"), (29.97, "2997/100"),
                                      (12.5, "25/2")])
def test_rate(fps, want):
    assert encode.rate(fps) == want


def test_rate_rejects_zero():
    with pytest.raises(WorkerError):
        encode.rate(0)


def test_mp4_argv():
    argv = encode.mp4_argv("/f", 30.0, "/o/video.mp4", "final", ffmpeg="ff")
    s = " ".join(argv)
    assert argv[0] == "ff" and argv[-1] == "/o/video.mp4"
    for part in ("-framerate 30", "-c:v libx264", "-pix_fmt yuv420p", "-movflags +faststart", "-crf 17", "-an",
                 "-colorspace bt709", "out_color_matrix=bt709", "-nostdin", "-start_number 1"):
        assert part in s, part
    assert argv[argv.index("-i") + 1].replace("\\", "/") == "/f/frame_%06d.png"
    assert "-crf 23" in " ".join(encode.mp4_argv("/f", 30, "/o.mp4", "preview"))


def test_poster():
    assert [encode.poster_index(n) for n in (1, 2, 3, 90, 300)] == [1, 1, 2, 31, 101]
    argv = encode.poster_argv("/f/frame_000031.png", "/o/poster.jpg", ffmpeg="ff")
    assert argv[:1] == ["ff"] and "-frames:v" in argv and argv[-1] == "/o/poster.jpg"


def _frames(d, n, skip=None, size=(16, 12)):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        if i != skip:
            png(d / f"frame_{i:06d}.png", *size, i)
    return d


def test_list_frames(tmp_path):
    assert len(encode.list_frames(_frames(tmp_path / "a", 5))) == 5
    for d in (_frames(tmp_path / "b", 5, skip=3), tmp_path / "empty", tmp_path / "missing"):
        if d.name == "empty":
            d.mkdir()
        with pytest.raises(WorkerError) as e:
            encode.list_frames(d)
        assert e.value.code == "FRAMES_MISSING"


def test_zip_frames(tmp_path):
    z = encode.zip_frames(_frames(tmp_path / "f", 4), tmp_path / "f.zip")
    with zipfile.ZipFile(z) as zf:
        assert zf.namelist() == [f"frame_{i:06d}.png" for i in range(1, 5)]


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_encode_real(tmp_path):
    frames = _frames(tmp_path / "frames", 12, size=(35, 63))        # odd sizes are padded to even
    res = encode.encode(frames, 24, tmp_path, "preview")
    assert res["frames"] == 12 and res["video"].stat().st_size > 0
    assert res["poster"].read_bytes()[:2] == b"\xff\xd8"
    if shutil.which("ffprobe"):
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=codec_name,pix_fmt,width,height,nb_frames", "-of", "csv=p=0",
                              str(res["video"])], capture_output=True, text=True).stdout.strip()
        assert out == "h264,34,62,yuv420p,12"
        head = res["video"].read_bytes()[:64]
        assert b"ftyp" in head and b"moov" in res["video"].read_bytes()[:4096]   # +faststart: moov up front


def test_encode_missing_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setenv("FFMPEG_EXE", str(tmp_path / "no-ffmpeg"))
    with pytest.raises(WorkerError) as e:
        encode.encode(_frames(tmp_path / "f", 2), 30, tmp_path)
    assert e.value.code == "WORKER_MISCONFIGURED"


# ---------------------------------------------------------------- watermark

@pytest.mark.parametrize("w,h,size,margin", [(540, 960, 23, 24), (960, 540, 23, 24), (1080, 1920, 45, 49),
                                             (1920, 1080, 45, 49), (100, 60, 10, 4)])
def test_watermark_filter_scales_with_short_side(w, h, size, margin):
    f = encode.watermark_filter(w, h, "/usr/share/fonts/valora/Inter-SemiBold.ttf")
    assert f.startswith("drawtext=fontfile='/usr/share/fonts/valora/Inter-SemiBold.ttf':text='valora3d.com':")
    assert f":fontsize={size}:" in f and f":x=w-tw-{margin}:y=h-th-{margin}" in f
    assert "fontcolor=white@0.6" in f


def test_watermark_filter_escapes_windows_path():
    f = encode.watermark_filter(540, 960, r"C:\Fonts\it's.ttf")
    assert "fontfile='C\\:/Fonts/it'\\''s.ttf'" in f


def test_argv_with_watermark():
    mark = encode.watermark_filter(540, 960, "/f.ttf")
    argv = encode.mp4_argv("/f", 30, "/o.mp4", watermark=mark)
    vf = argv[argv.index("-vf") + 1]
    assert vf.startswith(mark + ",scale=")            # drawn on the RGB frame, before the YUV conversion
    assert "drawtext" not in " ".join(encode.mp4_argv("/f", 30, "/o.mp4"))
    p = encode.poster_argv("/f/frame_000001.png", "/o.jpg", ffmpeg="ff", watermark=mark)
    assert p[p.index("-vf") + 1] == mark and p[-1] == "/o.jpg"
    assert "-vf" not in encode.poster_argv("/f/frame_000001.png", "/o.jpg")


def test_watermark_font_config(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_WATERMARK_FONT", str(tmp_path / "missing.ttf"))
    assert encode.watermark_font() is None
    font = tmp_path / "f.ttf"
    font.write_bytes(b"x")
    monkeypatch.setenv("WORKER_WATERMARK_FONT", str(font))
    assert encode.watermark_font() == str(font)


def test_watermark_skipped_without_font(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_WATERMARK_FONT", str(tmp_path / "missing.ttf"))
    calls = []

    def fake_run(argv, what, timeout):
        calls.append(argv)
        Path(argv[-1]).write_bytes(b"x")
    monkeypatch.setattr(encode, "_run", fake_run)
    res = encode.encode(_frames(tmp_path / "f", 3), 30, tmp_path, watermark=True)
    assert res["watermarked"] is False and "font" in res["warnings"][0]
    assert not any("drawtext" in " ".join(a) for a in calls)
    res = encode.encode(_frames(tmp_path / "f", 3), 30, tmp_path)
    assert res["watermarked"] is False and res["warnings"] == []


def test_watermark_applied_to_both_outputs(monkeypatch, tmp_path):
    font = tmp_path / "f.ttf"
    font.write_bytes(b"x")
    monkeypatch.setenv("WORKER_WATERMARK_FONT", str(font))
    calls = []

    def fake_run(argv, what, timeout):
        calls.append(argv)
        Path(argv[-1]).write_bytes(b"x")
    monkeypatch.setattr(encode, "_run", fake_run)
    res = encode.encode(_frames(tmp_path / "f", 3, size=(64, 36)), 30, tmp_path, watermark=True)
    assert res["watermarked"] is True and res["warnings"] == []
    assert len(calls) == 2 and all("drawtext" in " ".join(a) for a in calls)


@pytest.mark.skipif(not (HAVE_FFMPEG and have_drawtext() and system_font()), reason="ffmpeg drawtext or a font missing")
@pytest.mark.parametrize("size", [(96, 170), (170, 96)])       # 9:16 and 16:9
def test_watermark_real(monkeypatch, tmp_path, size):
    monkeypatch.setenv("WORKER_WATERMARK_FONT", system_font())
    frames = _frames(tmp_path / "frames", 6, size=size)
    (tmp_path / "plain").mkdir()
    (tmp_path / "marked").mkdir()
    plain = encode.encode(frames, 24, tmp_path / "plain")
    marked = encode.encode(frames, 24, tmp_path / "marked", watermark=True)
    assert marked["watermarked"] is True and marked["frames"] == 6
    assert marked["poster"].read_bytes()[:2] == b"\xff\xd8"
    assert marked["poster"].read_bytes() != plain["poster"].read_bytes()
    assert marked["video"].read_bytes() != plain["video"].read_bytes()
