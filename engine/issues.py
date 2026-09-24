from dataclasses import dataclass, asdict

SEVERITIES = ("repaired", "error")


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str
    severity: str  # "repaired" (fixed in place) or "error" (must go back to the director)

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"bad severity {self.severity!r}")

    def to_dict(self) -> dict:
        return asdict(self)


def errors(issues):
    return [i for i in issues if i.severity == "error"]
