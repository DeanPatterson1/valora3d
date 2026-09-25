import json

from engine.__main__ import EXIT_BAD_INPUT, EXIT_CHECK_FAILED, EXIT_OK, main
from engine.director.memory import VarietyMemory

PROFILE = "engine/tests/fixtures/profiles/pocket_watch.json"


def _refuse(tmp_path):
    p = tmp_path / "refuse.json"
    p.write_text(json.dumps({"replies": [{"stop_reason": "refusal", "text": ""}] * 3}), encoding="utf-8")
    return f"fake:{p}"


def _direct(tmp_path, capsys, *extra):
    rc = main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path), *extra])
    return rc, json.loads(capsys.readouterr().out)


def test_new_user_prints_a_signed_token(tmp_path, capsys):
    assert main(["new-user", "--memory-dir", str(tmp_path)]) == EXIT_OK
    tok = capsys.readouterr().out.strip()
    assert VarietyMemory(tmp_path).valid_token(tok) and not VarietyMemory(tmp_path / "x").valid_token(tok)


def test_memory_flags_rotate_directions(tmp_path, capsys):
    u, ids = VarietyMemory(tmp_path / "m").issue_user_token(), []
    for s in range(3):
        rc, out = _direct(tmp_path, capsys, "--seed", str(s), "--user", u, "--memory-dir", str(tmp_path / "m"))
        assert rc == EXIT_OK
        ids.append(out["direction"]["id"])
    assert len(set(ids)) == 3


def test_like_and_replay_from_the_saved_record(tmp_path, capsys):
    rec = tmp_path / "a.replay.json"
    _direct(tmp_path, capsys, "--seed", "4", "--out-replay", str(rec))
    a = json.loads(rec.read_text(encoding="utf-8"))
    _, like = _direct(tmp_path, capsys, "--seed", "9", "--like", str(rec))
    assert like["direction"]["id"] == a["direction"]["id"]
    assert main(["replay", str(rec), "--profile", PROFILE]) == EXIT_OK        # no provider flag at all
    assert json.loads(capsys.readouterr().out)["script"] == a["script"]


def test_like_accepts_a_script_file_and_a_direction_id(tmp_path, capsys):
    out = tmp_path / "s.json"
    _, a = _direct(tmp_path, capsys, "--seed", "4", "--out", str(out))
    _, b = _direct(tmp_path, capsys, "--seed", "7", "--like", str(out))
    _, c = _direct(tmp_path, capsys, "--seed", "8", "--like", a["direction"]["id"])
    assert a["direction"]["id"] == b["direction"]["id"] == c["direction"]["id"]


def test_less_like_avoids_the_files_mood_and_opener(tmp_path, capsys):
    out = tmp_path / "s.json"
    _, a = _direct(tmp_path, capsys, "--seed", "4", "--out", str(out))
    for s in range(5, 8):
        _, b = _direct(tmp_path, capsys, "--seed", str(s), "--less-like", str(out))
        assert b["direction"]["axes"]["mood"] != a["direction"]["axes"]["mood"]
        assert b["direction"]["axes"]["opener"] != a["direction"]["axes"]["opener"]


def test_stale_replay_exits_3(tmp_path, capsys):
    rec = tmp_path / "a.replay.json"
    _direct(tmp_path, capsys, "--seed", "4", "--out-replay", str(rec))
    doc = json.loads(rec.read_text(encoding="utf-8"))
    doc["script"]["world"] = {"id": "moon", "params": {}}
    rec.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["replay", str(rec), "--profile", PROFILE]) == EXIT_CHECK_FAILED


def test_bad_inputs_exit_5(tmp_path, capsys):
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path), "--user", "alice@example.com",
                 "--memory-dir", str(tmp_path)]) == EXIT_BAD_INPUT
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path),
                 "--avoid", "mood=purple_rain"]) == EXIT_BAD_INPUT
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path),
                 "--like", "moon/clean/white/calm/arc_orbit/dry/calm"]) == EXIT_BAD_INPUT
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path), "--avoid", "mood"]) == EXIT_BAD_INPUT
    err = capsys.readouterr().err
    assert "Traceback" not in err and "input rejected" in err


def test_avoid_parses_axis_value(tmp_path, capsys):
    for s in range(4):
        _, out = _direct(tmp_path, capsys, "--seed", str(s), "--avoid", "mood=clean", "--avoid", "mood=vivid")
        assert out["direction"]["axes"]["mood"] not in ("clean", "vivid")


def test_variety_report_with_prompt(capsys):
    assert main(["variety-report", "--profile", PROFILE, "--prompt", "luxury", "--viable"]) == EXIT_OK
    r = json.loads(capsys.readouterr().out)
    assert r["pins"] == {"mood": "premium_dark"} and "viable" in r


def test_default_output_is_trimmed_and_json_full_is_not(tmp_path, capsys):
    _, out = _direct(tmp_path, capsys, "--seed", "4")
    assert "rawScript" not in out and "script" not in out.get("replay", {}) and out["script"]
    _, full = _direct(tmp_path, capsys, "--seed", "4", "--json-full")
    assert "rawScript" in full and full["replay"]["script"] == full["script"]
    _, verbose = _direct(tmp_path, capsys, "--seed", "4", "--verbose")
    assert verbose["replay"]["script"] == verbose["script"]


def test_user_without_a_memory_root_is_rejected(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("VALORA_VARIETY_DIR", raising=False)
    u = VarietyMemory(tmp_path).issue_user_token()
    assert main(["direct", "--profile", PROFILE, "--provider", _refuse(tmp_path), "--user", u]) == EXIT_BAD_INPUT


def test_variety_report_aspect_drives_both_enumeration_and_viability(capsys, monkeypatch):
    import engine.director.variety as v
    seen = []
    real = v.make_viable
    monkeypatch.setattr(v, "make_viable", lambda job, *a: (seen.append(dict(job.fmt)), real(job, *a))[1])
    assert main(["variety-report", "--profile", PROFILE, "--aspect", "1:1", "--viable"]) == EXIT_OK
    json.loads(capsys.readouterr().out)
    assert seen and all(f["aspect"] == "1:1" for f in seen)


def test_variety_report_rejects_an_unknown_aspect(capsys):
    assert main(["variety-report", "--profile", PROFILE, "--aspect", "3:7", "--viable"]) == EXIT_BAD_INPUT
    assert "input rejected" in capsys.readouterr().err
