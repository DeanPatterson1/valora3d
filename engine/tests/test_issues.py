from engine.issues import Issue, errors


def test_issue_to_dict_and_errors_filter():
    a = Issue("param_clamped", "shots[0].camera.params.lensMm", "clamped 500 to 135", "repaired")
    b = Issue("unknown_block", "world.id", "no world 'moon'", "error")
    assert a.to_dict() == {
        "code": "param_clamped",
        "path": "shots[0].camera.params.lensMm",
        "message": "clamped 500 to 135",
        "severity": "repaired",
    }
    assert errors([a, b]) == [b]
