"""The committed realism round driver: planning, the premium hook and the sheets, with no rendering."""
import json

import pytest

from harness import realism_round as rr


def test_dry_run_plans_every_shot_and_renders_nothing(monkeypatch, capsys):
    monkeypatch.setattr(rr, "render_shot", lambda *a, **k: pytest.fail("a dry run rendered"))
    assert rr.main(["--round", "rtest", "--prev", "r9", "--dry-run"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert set(p["shots"]) == set(rr.SHOTS) and set(p["sheets"]) == set(rr.SHEETS)
    assert p["shots"]["court"]["out"].endswith("real_rtest_court")


def test_unknown_shot_is_refused():
    with pytest.raises(SystemExit):
        rr.main(["--round", "rtest", "--shots", "nope", "--dry-run"])


def test_every_sheet_names_a_rendered_frame():
    for ref, _, shot, frame, _ in rr.SHEETS.values():
        assert frame in rr.SHOTS[shot][1]


@pytest.mark.parametrize("shot", sorted(rr.SHOTS))
def test_each_committed_script_passes_the_checker_after_the_premium_hook(shot):
    from engine.catalog import Catalog
    hook = rr.premium(rr.load_script(shot), rr.load_profile(), Catalog.load())
    assert hook["ok"] and hook["silhouetteWidth"] > 0


def test_sheets_mark_missing_frames_instead_of_failing(monkeypatch, tmp_path):
    monkeypatch.setattr(rr, "LOOK", tmp_path)
    monkeypatch.setattr(rr, "REFS", tmp_path / "refs")
    made = rr.build_sheets("rtest", "rprev")
    assert len(made) == len(rr.SHEETS) and all((tmp_path / "real_rtest_sbs" / f"{n}.png").exists()
                                                for n in rr.SHEETS)


def test_a_shot_can_take_its_previous_panel_from_another_round(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(rr, "LOOK", tmp_path)
    monkeypatch.setattr(rr, "REFS", tmp_path / "refs")
    real = rr._panel
    monkeypatch.setattr(rr, "_panel", lambda path, label: (seen.append(label), real(path, label))[1])
    rr.build_sheets("rtest", "r9", {"court": "r9z"})
    assert "engine r9z" in seen and "engine r9" in seen
