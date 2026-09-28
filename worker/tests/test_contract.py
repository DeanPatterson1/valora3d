import pytest

from worker.contract import ERRORS, WorkerError, error_for_exit, parse_job, parse_params


def job(**over):
    base = {"job_id": "job_1-A", "glb_url": "https://x.r2.cloudflarestorage.com/u/m.glb",
            "output_put_urls": {"video": "https://h/v", "poster": "https://h/p"}, "params": {}}
    base.update(over)
    return base


def code_of(fn, *a):
    with pytest.raises(WorkerError) as e:
        fn(*a)
    return e.value.code


def test_minimal_job_gets_defaults():
    j = parse_job(job())
    assert j.job_id == "job_1-A"
    assert j.outputs == {"video": "https://h/v", "poster": "https://h/p"}
    p = j.params
    assert (p.prompt, p.world, p.aspect, p.tier, p.seed, p.duration, p.paint, p.finish, p.markers) == \
        ("", None, None, "preview", None, None, None, "gloss", [])


def test_full_params():
    p = parse_params({"prompt": "rain at night", "world": "rain_courtyard", "aspect": "16:9", "tier": "final",
                      "seed": 7, "duration": 10, "paint": "#AABBCC", "finish": "matte",
                      "markers": [{"anchor": {"space": "gltf", "point": [0, 0, 0]}, "text": "badge"}]})
    assert p.tier == "final" and p.duration == 10.0 and p.paint == "#AABBCC" and len(p.markers) == 1


@pytest.mark.parametrize("inp", [
    None, [], {},
    job(job_id="../etc"), job(job_id="x" * 65), job(job_id=5),
    job(glb_url=""), job(output_put_urls={"video": "https://h/v"}),
    job(output_put_urls={"video": "https://h/v", "poster": "https://h/p", "evil": "https://h/e"}),
    job(params=[]), job(params={"bogus": 1}),
])
def test_bad_jobs(inp):
    assert code_of(parse_job, inp) == "INVALID_INPUT"


@pytest.mark.parametrize("params", [
    {"prompt": 5}, {"prompt": "x" * 2001}, {"prompt": "a\x00b"},
    {"world": "Rain Courtyard"}, {"world": "../x"}, {"aspect": "4:3"}, {"tier": "keyframes"},
    {"seed": -1}, {"seed": 2 ** 31}, {"seed": True}, {"seed": 1.5},
    {"duration": 2}, {"duration": 31}, {"duration": "10"}, {"duration": True},
    {"paint": "red"}, {"paint": "#abc"}, {"finish": "chrome"},
    {"markers": {}}, {"markers": [{"text": "no anchor"}] }, {"markers": [{"anchor": {}}] * 9},
    {"markers": [{"anchor": {}, "text": "x" * 281}]},
])
def test_bad_params(params):
    assert code_of(parse_params, params) == "INVALID_INPUT"


def test_error_codes_are_complete():
    for code, (retry, msg) in ERRORS.items():
        e = WorkerError(code, "why")
        assert e.to_dict() == {"code": code, "message": msg, "detail": "why", "retryable": retry}
    with pytest.raises(ValueError):
        WorkerError("NOPE")


@pytest.mark.parametrize("code,err,stage,want", [
    (5, "input rejected: world", "direct", "INPUT_REJECTED"),
    (2, "usage", None, "WORKER_MISCONFIGURED"),
    (1, "Command '...' timed out after 60 seconds", "render", "RENDER_TIMEOUT"),
    (1, "The model has more than 5,000,000 vertices.", "ingest", "INPUT_REJECTED"),
    (1, "Only .glb (binary glTF) models are accepted.", "ingest", "INPUT_REJECTED"),
    (1, "Blender extract failed (exit 11): segfault", "ingest", "RENDER_FAILED"),
    (1, "Blender compile failed (exit 1)", "render", "RENDER_FAILED"),
    (1, None, None, "RENDER_FAILED"),
    (-9, None, "render", "RENDER_FAILED"),
])
def test_exit_mapping(code, err, stage, want):
    assert error_for_exit(code, err, stage).code == want
