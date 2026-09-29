"""engine.site_job: the local render job a site's render server shells out to (ingest -> direct -> render on the
site catalog). Blender is faked here; the real run is exercised end to end from ModVision's Render Studio."""
import argparse
import json
from pathlib import Path

import pytest

from engine import site_job
from engine.director.job import DirectorInputError
from engine.director.llm import FakeProvider
from engine.director.site import site_deliverable
from engine.tests.test_director_package import PROFILES, _p

REFUSE = [{"stop_reason": "refusal"}]


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)


def test_worlds_are_the_site_catalog_worlds_with_their_golden_stills():
    ws = {w["id"]: w for w in site_job.worlds()}
    assert set(ws) == {"studio_cyc", "rain_courtyard", "night_street", "golden_field"}
    assert ws["studio_cyc"]["golden"] is None                           # baseline, never a growth block
    assert ws["rain_courtyard"]["golden"].endswith("real_r16_court/beauty/0030.png")
    assert ws["golden_field"]["golden"].endswith("real_r15_field_golden/beauty/0030.png")
    assert all(w["description"] and "16:9" in w["aspects"] for w in ws.values())


def test_the_aspect_is_a_prompt_pin_unless_the_words_name_one():
    assert site_job.site_prompt("", "16:9") == "landscape 16:9"
    assert site_job.site_prompt("  moody\nrain ", "9:16") == "moody rain (vertical 9:16)"
    assert site_job.site_prompt("a vertical reel", "16:9") == "a vertical reel"      # the user's words win
    assert site_job.site_prompt("dusk", None) == "dusk"


@pytest.mark.parametrize("world,aspect", [("rain_courtyard", "16:9"), ("golden_field", "16:9"),
                                          ("night_street", "9:16"), ("rain_courtyard", "9:16")])
def test_direct_site_pins_the_world_and_the_aspect(world, aspect):
    res, rerolls = site_job.direct_site("", _p("sports_car"), world=world, aspect=aspect, seed=3,
                                        provider=FakeProvider(REFUSE))
    assert res.script["world"]["id"] == world and res.script["format"]["aspect"] == aspect
    assert site_deliverable(res.script) == [] and rerolls == 0


def test_direct_site_refuses_a_world_the_site_does_not_offer():
    with pytest.raises(DirectorInputError, match="not offered"):
        site_job.direct_site("", _p("sports_car"), world="snowy_pass", provider=FakeProvider(REFUSE))


def test_a_world_that_cannot_frame_the_subject_in_the_format_is_an_input_error():
    """The dice relax the avoid list when nothing in the pinned world is viable; the site says so instead of
    rendering another world (the sports car never frames on the night street at 16:9)."""
    with pytest.raises(DirectorInputError, match="could not make a night_street clip"):
        site_job.direct_site("", _p("sports_car"), world="night_street", aspect="16:9", seed=3,
                             provider=FakeProvider(REFUSE))


def test_direct_site_rerolls_past_an_undeliverable_script(monkeypatch):
    calls = []

    def fake_deliverable(script, growth=None):
        calls.append(script["replay"]["seed"] if "replay" in script else len(calls))
        return ["effect/snow"] if len(calls) == 1 else []
    monkeypatch.setattr("engine.director.site.site_deliverable", fake_deliverable)
    res, rerolls = site_job.direct_site("", _p("sports_car"), world="golden_field", seed=10,
                                        provider=FakeProvider(REFUSE))
    assert rerolls == 1 and len(calls) == 2


def _args(tmp_path, **kw):
    a = dict(model=str(tmp_path / "car.glb"), out=str(tmp_path / "job"), profile=None, prompt="", world=None,
             aspect=None, tier="preview", seed=5, duration=8.0, frame_step=1, paint=None, finish="gloss",
             provider="fake", timeout=60)
    a.update(kw)
    return argparse.Namespace(**a)


def test_run_ingests_directs_renders_and_writes_contiguous_frames(tmp_path, capsys):
    seen = {}

    def fake_ingest(model, workdir):
        seen["ingest"] = model
        return _p("sports_car")

    def fake_compile(script, profile, model, out, *, tier, frames, catalog, timeout_s, paint, passes=None):
        seen.update(tier=tier, frames=frames, paint=paint, world=script["world"]["id"])
        beauty = Path(out) / "beauty"
        beauty.mkdir(parents=True)
        for f in frames:
            (beauty / f"{f:04d}.png").write_bytes(b"png%d" % f)
        return {"ok": True}

    a = _args(tmp_path, world="night_street", frame_step=2, paint="#1A2B3C", finish="satin")
    assert site_job.run(a, provider=FakeProvider(REFUSE), compile_scene=fake_compile, ingest=fake_ingest) == 0
    out = tmp_path / "job"
    assert seen["world"] == "night_street" and seen["tier"] == "preview"
    assert seen["frames"] == list(range(1, 193, 2)) and seen["paint"]["color"] == "#1a2b3c"
    assert (out / "frames" / "frame_000001.png").read_bytes() == b"png1"
    assert (out / "frames" / "frame_000096.png").read_bytes() == b"png191"
    assert not (out / "frames" / "frame_000097.png").exists()
    done = json.loads((out / "site_job.json").read_text(encoding="utf-8"))
    assert done["frames"] == 96 and done["fps"] == 12 and done["direct"]["world"] == "night_street"
    stages = [json.loads(line[8:])["stage"] for line in capsys.readouterr().out.splitlines()
              if line.startswith("SITEJOB ")]
    assert stages == ["ingest", "direct", "render", "done"]


def test_main_reports_a_rejected_world_as_exit_5(tmp_path, capsys):
    prof = PROFILES / "sports_car.json"
    code = site_job.main(["run", "--model", str(tmp_path / "car.glb"), "--out", str(tmp_path / "o"),
                          "--profile", str(prof), "--world", "moon_base"])
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert code == site_job.EXIT_BAD_INPUT
    assert last.startswith("SITEJOB ") and json.loads(last[8:])["stage"] == "error"


def test_main_rejects_a_bad_paint_before_any_work(tmp_path, capsys):
    code = site_job.main(["run", "--model", "x.glb", "--out", str(tmp_path / "o"), "--paint", "red"])
    assert code == site_job.EXIT_BAD_INPUT
    assert "input rejected" in capsys.readouterr().out
