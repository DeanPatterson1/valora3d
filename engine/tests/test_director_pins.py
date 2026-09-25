import pytest

from engine.director.pins import read_direction_pins


@pytest.mark.parametrize("prompt,pins", [
    ("", {}), ("make it look cool", {}), ("ad", {}),
    ("luxury", {"mood": "premium_dark"}),
    ("rainy night", {"mood": "teal_night", "weather": "rain"}),   # phase 5 Task 87: weather pins
    ("fun, bright and energetic social clip with quick cuts", {"mood": "vivid", "pace": "hype"}),
    ("moody cinematic 16:9 commercial", {"mood": "premium_dark"}),
    ("A premium launch ad for this: slow reveal from darkness, close-ups of the details, then a clean hero shot.",
     {"mood": "premium_dark", "pace": "calm"}),                       # first mention wins per axis
    ("sunset on the beach with music", {"mood": "warm_golden"}),
    ("black and white, on black", {"mood": "noir", "tone": "black"}),
    ("not moody, no neon, bright", {"mood": "vivid"}),                # negated mentions are not pins
    ("without quick cuts", {}),
    ("studio shot, orbiting the product", {"world": "studio_cyc", "opener": "arc_orbit"}),
    ("low angle push in, black background", {"opener": "low_hero_push", "tone": "black"}),
    ("no orbit, just calm", {"pace": "calm"}),                        # a negated opener is not a pin
    ("funky", {}), ("nightstand", {}),                                # whole words only
])
def test_pins(prompt, pins):
    assert read_direction_pins(prompt) == pins


MOODY = {"mood": "premium_dark"}


@pytest.mark.parametrize("positive,negative", [
    ("moody", "not moody"),
    ("orbiting the product", "no orbiting"),
    ("quick cuts", "without quick cuts"),
    ("on black", "never on black"),
    ("studio", "avoid studio"),
    ("neon", "zero neon"),
])
def test_paired_positive_and_negated_pin_phrases(positive, negative):
    assert read_direction_pins(positive) != {} and read_direction_pins(negative) == {}


@pytest.mark.parametrize("prompt", [
    'no "moody"', "no “moody”", "no ‘moody’", "no 'moody'", "no (moody)", "no [moody]",
    "no—moody", "no–moody", "no‒moody", "no−moody", "no-moody", "without «moody»",
    "don’t go moody", "don't go moody",
])
def test_punctuation_and_unicode_do_not_hide_a_negation(prompt):
    assert read_direction_pins(prompt) == {}


@pytest.mark.parametrize("prompt", [
    '"moody"', "(moody)", "“moody”", "—moody—",
    "no neon — moody",                 # a spaced dash ends the negated clause
    "(no neon) moody",                        # so does a closing bracket
    "not not moody", "not without moody",    # an even number of negators is positive
])
def test_quoted_bracketed_and_double_negated_mentions_are_pins(prompt):
    assert read_direction_pins(prompt)["mood"] == "premium_dark"


def test_odd_negation_is_still_negative():
    assert read_direction_pins("not not not moody") == {}
    assert read_direction_pins("no moody-free") == MOODY   # 'no' + '-free': two negations


def test_capability_detection_shares_the_negation_reader():
    from engine.director.capabilities import detect
    assert [a["capability"] for a in detect("rain")] == [a["capability"] for a in detect("not without rain")] != []
    assert detect('no "rain"') == detect("no—rain") == detect("no (rain)") == []
    assert detect("no text — rain") != []


@pytest.mark.parametrize("prompt", [
    "no (very) moody", "not [really] moody", "no (very (very)) moody", "without {a bit} moody",
])
def test_a_negation_outside_brackets_reaches_past_them(prompt):
    assert read_direction_pins(prompt) == {}


@pytest.mark.parametrize("prompt", [
    "(no rush) moody", "[not neon] moody", "(a (no) b) moody", "((no neon)) moody", "(x (no neon) moody)",
])
def test_a_negation_inside_brackets_stays_inside(prompt):
    assert read_direction_pins(prompt)["mood"] == "premium_dark"


def test_capability_bracket_scope():
    from engine.director.capabilities import detect
    assert detect("no (heavy) rain") == []
    assert detect("(no text) rain") != []
