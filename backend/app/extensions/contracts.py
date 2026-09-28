from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Extension:
    identity: str
    version: str
    handlers: dict[str, Callable] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    enabled: bool = True

    def health(self) -> dict: return {"status": "healthy" if self.enabled else "disabled"}
