"""Subject family: which sequence template and taste section apply. A HINT only (spec §4.1): it picks
defaults, and never unlocks or blocks a feature."""
FAMILIES = ("vehicle", "product", "furniture", "character")


def family(profile):
    if profile.rigged:
        return "character"
    return {"vehicle-like": "vehicle", "small-object": "product"}.get(profile.categoryHint, "furniture")
