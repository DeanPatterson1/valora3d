"""SubjectProfile: what ingest measured about an uploaded model (spec §4.1)."""
from dataclasses import MISSING, dataclass, field, fields, asdict

PROFILE_SCHEMA = "valora.profile/1"


@dataclass
class SubjectProfile:
    """Measured facts about one uploaded model, in placed coordinates (metres).

    Placement: the compiler must place every source-space vertex v (as imported,
    Z-up, source units) with

        placed = (v.x - sourceCenter[0], v.y - sourceCenter[1], v.z - sourceMinZ) * scaleFactor

    which centres the subject on XY, stands its lowest point on z=0 and converts
    source units to metres. boundsMin/boundsMax are the raw bounds under exactly
    that transform. Older documents without these fields load with the identity
    placement (centre 0, minZ 0, factor 1).

    Ingest extensions (all points placed coordinates; absent in phase-1 documents, which
    load with the empty defaults):

    glossShare         area share of gloss materials (the TIERS gloss mask definition)
    reflectionTargets  largest glossy patches by facing, where key reflections are aimed
    shoulderLine       per flank, the widest-point polyline along the long axis
    detailPoints       ranked, spread-out detail candidates (emissive, glints, sharp features)
    wheels             best-effort wheel circles with a confidence
    parts              per mesh object bounds and poly share (names never recorded)
    boundsPosed        True when bounds are a union over the subject's animation frames
    """
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
    sourceCenter: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # raw bounds centre, source units
    sourceMinZ: float = 0.0    # raw bounds min z, source units
    scaleFactor: float = 1.0   # source units -> metres
    glossShare: float = 0.0     # area share of gloss materials (metallic >= 0.5 or roughness <= 0.3; TIERS mask)
    reflectionTargets: list = field(default_factory=list)  # [{kind, point, normal, area}] glossy patches by facing
    shoulderLine: list = field(default_factory=list)       # [{side, points}] widest-point polyline per flank
    detailPoints: list = field(default_factory=list)       # [{kind, point, normal, score}] ranked, spread out
    wheels: list = field(default_factory=list)             # [{center, radius, axis, confidence}] best effort
    parts: list = field(default_factory=list)              # [{index, boundsMin, boundsMax, polyShare}]
    boundsPosed: bool = False   # bounds are a union over the subject's animation frames
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
