from dataclasses import dataclass, asdict

SEVERITIES = ("info", "repaired", "warning", "error")


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str
    severity: str  # "info" (the system decided something, e.g. which realism applies; nothing to fix),
    # "repaired" (fixed in place), "warning" (renders; worth a look) or "error" (back to the director)

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"bad severity {self.severity!r}")

    def to_dict(self) -> dict:
        return asdict(self)


def errors(issues):
    return [i for i in issues if i.severity == "error"]
