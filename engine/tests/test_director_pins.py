import pytest

from engine.director.pins import read_direction_pins


@pytest.mark.parametrize("prompt,pins", [
    ("", {}), ("make it look cool", {}), ("ad", {}),
    ("luxury", {"mood": "premium_dark"}),
    ("rainy night", {"mood": "teal_night"}),
    ("fun, bright and energetic social clip with quick cuts", {"mood": "vivid", "pace": "hype"}),
    ("moody cinematic 16:9 commercial", {"mood": "premium_dark"}),
    ("A premium launch ad for this: slow reveal from darkness, close-ups of the details, then a clean hero shot.",
     {"mood": "premium_dark", "pace": "calm"}),                       # first mention wins per axis
    ("sunset on the beach with music", {"mood": "warm_golden"}),
    ("black and white, on black", {"mood": "noir", "tone": "black"}),
    ("not dark, no neon, bright", {"mood": "vivid"}),                 # negated mentions are not pins
    ("without quick cuts", {}),
    ("studio shot, orbiting the product", {"world": "studio_cyc", "opener": "arc_orbit"}),
    ("low angle push in, black background", {"opener": "low_hero_push", "tone": "black"}),
    ("no orbit, just calm", {"pace": "calm"}),                        # a negated opener is not a pin
    ("funky", {}), ("nightstand", {}),                                # whole words only
])
def test_pins(prompt, pins):
    assert read_direction_pins(prompt) == pins
