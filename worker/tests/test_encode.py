import shutil
import subprocess
import zipfile

import pytest

from worker import encode
from worker.contract import WorkerError
from worker.fake_site_job import png

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
