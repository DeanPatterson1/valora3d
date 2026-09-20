"""Checks for subprocess lifecycle guarantees used by the render queue."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import RenderCancelled, _run_process, _first_binary, encoding_settings, finish_filter, poster_frame
import watermark


class ProcessTests(unittest.TestCase):
    def test_delivery_quality_is_aspect_independent_and_finish_is_rain_scoped(self):
        for resolution in ([1920, 1080], [1080, 1920]):
            flags, bitrate = encoding_settings({'scene': 'rainy_courtyard'}, resolution)
            self.assertEqual(bitrate, 20000000)
            self.assertIn("[0:v]vignette=angle=PI/14,split=3[a][b][c];[b]noise=alls=13:allf=t+u:all_seed=20260916[n];[c]lutyuv=y='clip(250-val*1.35,45,250)':u=110:v=110[m];[a][n][m]maskedmerge[wm]", flags)
            self.assertNotIn('-crf', flags)
        flags, bitrate = encoding_settings({'scene': 'turntable'}, [2160, 3840])
        self.assertEqual(bitrate, 60000000)
        self.assertNotIn('-filter_complex', flags)
        flags, bitrate = encoding_settings({'scene': 'turntable'}, [1280, 720])
        self.assertIsNone(bitrate)
        self.assertEqual(flags, ['-preset', 'fast', '-crf', '18'])

    def test_documented_binary_overrides_take_precedence(self):
        with tempfile.TemporaryDirectory(prefix="render custom binaries ") as directory:
            for key in ("BLENDER", "FFMPEG"):
                binary = Path(directory) / (key.lower() + ".exe")
                binary.touch()
                with patch.dict(os.environ, {key + "_PATH": str(binary), key: sys.executable}):
                    self.assertEqual(_first_binary(key, key.lower(), []), str(binary.resolve()))

    def test_cancel_interrupts_process_without_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            cancelled = threading.Event()
            timer = threading.Timer(0.25, cancelled.set)
            timer.start()
            started = time.monotonic()
            try:
                with self.assertRaises(RenderCancelled):
                    _run_process([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), cancelled)
            finally:
                timer.cancel()
            self.assertLess(time.monotonic() - started, 4.5)

    def test_reads_complete_progress_before_process_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            lines = []
            script = 'import json; print("PROGRESS " + json.dumps({"frame": 12, "totalFrames": 12}), flush=True)'
            _run_process([sys.executable, "-c", script], Path(directory), threading.Event(), lines.append)
            self.assertEqual(json.loads(lines[-1][len("PROGRESS "):])["frame"], 12)
            self.assertIn("PROGRESS", (Path(directory) / "log.txt").read_text())

    def test_surfaces_renderer_error(self):
        with tempfile.TemporaryDirectory() as directory:
            script = 'print("ERROR Snapshot contains no meshes", flush=True); raise SystemExit(2)'
            with self.assertRaisesRegex(RuntimeError, "Snapshot contains no meshes"):
                _run_process([sys.executable, "-c", script], Path(directory), threading.Event())

    def test_grain_false_drops_the_rain_filter(self):
        flags, _ = encoding_settings({'scene': 'rainy_courtyard'}, [1920, 1080])
        self.assertIn('-filter_complex', flags)
        flags, _ = encoding_settings({'scene': 'rainy_courtyard', 'grain': False}, [1920, 1080])
        self.assertNotIn('-filter_complex', flags)
        flags, _ = encoding_settings({'scene': 'turntable'}, [1920, 1080])
        self.assertNotIn('-filter_complex', flags)            # spec-less orbit: unchanged
        flags, _ = encoding_settings({'scene': 'turntable', 'grain': True}, [1920, 1080])
        self.assertIn('-filter_complex', flags)               # the spec's flag applies to any scene

    def test_watermark_overlays_after_grain_and_maps_the_marked_stream(self):
        self.assertIsNone(finish_filter({'scene': 'turntable'}))
        self.assertEqual(finish_filter({'scene': 'turntable', 'watermark': True}), '[0:v][1:v]overlay=0:0[wm]')
        graph = finish_filter({'scene': 'rainy_courtyard', 'watermark': True})
        self.assertTrue(graph.startswith('[0:v]vignette'))
        self.assertTrue(graph.endswith('[s0];[s0][1:v]overlay=0:0[wm]'))   # the mark lands on the grained image, never under it
        flags, _ = encoding_settings({'scene': 'turntable', 'watermark': True}, [1280, 720])
        self.assertEqual(flags[flags.index('-map') + 1], '[wm]')
        flags, _ = encoding_settings({'scene': 'turntable', 'watermark': False}, [1280, 720])
        self.assertNotIn('-filter_complex', flags)

    def test_every_free_preview_preset_is_marked_and_the_client_cannot_clear_it(self):
        import jobs
        for preset, config in jobs.PRESETS.items():
            self.assertEqual(config['watermark'], preset in {'smoke', 'draft', 'film_preview'}, preset)
            self.assertEqual(jobs.canonical_settings(preset, 'turntable', '16:9')['watermark'], config['watermark'])

    def test_overlay_and_stamp_cover_the_frame(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            overlay = watermark.build_overlay(Path(directory) / 'wm.png', 320, 180)
            with Image.open(overlay) as mark:
                self.assertEqual(mark.size, (320, 180))
                alpha = mark.getchannel('A')
                self.assertGreater(alpha.getextrema()[1], 150)                     # the badge is solid
                # the tile reaches every quadrant, so a crop cannot dodge it
                for box in ((0, 0, 160, 90), (160, 0, 320, 90), (0, 90, 160, 180), (160, 90, 320, 180)):
                    self.assertGreater(alpha.crop(box).getextrema()[1], 40, box)
            still = Path(directory) / 'raw.jpg'
            Image.new('RGB', (320, 180), (20, 20, 20)).save(still, quality=90)
            stamped = watermark.stamp_still(still, overlay, Path(directory) / 'latest.jpg')
            with Image.open(stamped) as image:
                self.assertEqual(image.size, (320, 180))
                self.assertGreater(image.convert('L').getextrema()[1], 80)       # something white landed on the dark frame
            self.assertFalse((Path(directory) / 'latest-stamping.jpg').exists())


if __name__ == "__main__":
    unittest.main()


class PosterTests(unittest.TestCase):
    def test_walk_in_poster_sits_two_frames_before_the_first_cut(self):
        self.assertEqual(poster_frame({'scene': 'rainy_courtyard'}, 1, 12), 5)          # smoke: cut at frame 6
        self.assertEqual(poster_frame({'scene': 'rainy_courtyard'}, 1, 240), 100)       # film: cut at frame 101
        spec = {'camera': {'programme': 'walk-in-5-shot'}}
        self.assertEqual(poster_frame({'scene': 'rainy_courtyard', 'spec': spec}, 1, 240), 100)

    def test_orbit_and_tiny_renders_keep_frame_one(self):
        self.assertEqual(poster_frame({'scene': 'turntable'}, 1, 240), 1)
        self.assertEqual(poster_frame({'scene': 'turntable', 'spec': {'camera': {'programme': 'orbit'}}}, 1, 240), 1)
        self.assertEqual(poster_frame({'scene': 'rainy_courtyard'}, 1, 3), 1)
