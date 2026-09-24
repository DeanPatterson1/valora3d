"""SubjectProfile: what ingest measured about an uploaded model (spec §4.1)."""
from dataclasses import MISSING, dataclass, field, fields, asdict

PROFILE_SCHEMA = "valora.profile/1"


@dataclass
class SubjectProfile:
    sizeM: list            # [x, y, z] metres
    boundsMin: list        # placed coords: centred on XY, bottom at z=0
    boundsMax: list
    unitGuess: str         # "m" | "cm" | "mm" | "in" | "unknown"
    scaleConfidence: str   # "high" | "low"
    upAxis: str            # "Z" after glTF import; "unknown" if doubtful
    sizeClass: str         # macro | hand | furniture | vehicle | architectural
    categoryHint: str      # hint only — never gates a feature (spec §4.1)
    materials: list = field(default_factory=list)  # [{class, share}]
    polyCount: int = 0
    rigged: bool = False
    animated: bool = False
    schema: str = PROFILE_SCHEMA

    @classmethod
    def from_dict(cls, d):
        if d.get("schema") != PROFILE_SCHEMA:
            raise ValueError(f"not a {PROFILE_SCHEMA} document")
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - known)
        if unknown:
            raise ValueError(f"unknown key(s) in {PROFILE_SCHEMA} document: {unknown}")
        missing = sorted(
            f.name for f in fields(cls)
            if f.name not in d and f.default is MISSING and f.default_factory is MISSING
        )
        if missing:
            raise ValueError(f"missing key(s) in {PROFILE_SCHEMA} document: {missing}")
        return cls(**d)

    def to_dict(self):
        return asdict(self)

    @property
    def center(self):
        return tuple((a + b) / 2 for a, b in zip(self.boundsMin, self.boundsMax))

    @property
    def half(self):
        return tuple((b - a) / 2 for a, b in zip(self.boundsMin, self.boundsMax))

    @property
    def radius(self):
        return sum(h * h for h in self.half) ** 0.5

    @property
    def longest(self):
        return max(self.sizeM)
