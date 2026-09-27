"""Loads the shared crime taxonomy (src/shared/taxonomy.json)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from ..config import get_settings


@dataclass(frozen=True)
class Taxonomy:
    version: str
    major: dict[str, dict]
    minor: dict[str, dict]
    mo_flags: dict[str, str]

    def major_of(self, minor: str) -> str:
        return self.minor[minor]["major"]

    def minor_label(self, minor: str) -> str:
        return self.minor[minor]["label"]

    def major_label(self, major: str) -> str:
        return self.major[major]["label"]


@lru_cache
def get_taxonomy() -> Taxonomy:
    data = json.loads(get_settings().taxonomy_path.read_text(encoding="utf-8"))
    return Taxonomy(version=data["version"], major=data["crime_major"], minor=data["crime_minor"],
                    mo_flags=data["mo_flags"])
