"""データソースエンティティ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UpdateFrequency = Literal["monthly", "quarterly", "yearly", "irregular"]


@dataclass(frozen=True, slots=True)
class DataSource:
    id: str
    name: str
    url: str
    license: str
    update_frequency: UpdateFrequency
