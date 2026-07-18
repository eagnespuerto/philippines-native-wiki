"""Load `species.json` and provide filter/search helpers.

Kept dependency-free (stdlib only) so the app can boot even if Pillow is
unavailable -- the UI still lists species text-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DATA_JSON = Path(__file__).resolve().parent.parent / "data" / "species.json"
DATA_ROOT = DATA_JSON.parent


REGION_LABELS = {
    "ncr": "Metro Manila (NCR)",
    "region3": "Region III (Central Luzon)",
    "calabarzon": "CALABARZON (Region IV-A)",
}

HABITAT_LABELS = {
    "forest": "Forest",
    "wetland": "Wetland",
    "coastal": "Coastal",
    "urban": "Urban / suburban",
    "grassland": "Grassland",
    "mountain": "Mountain",
    "farmland": "Farmland",
}


@dataclass
class Species:
    id: str
    common_name: str
    scientific_name: str
    kind: str                          # "animal" | "plant"
    group: str                         # mammal, bird, tree, ...
    regions: list[str] = field(default_factory=list)
    habitats: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    edible: bool = False
    summary: str = ""
    wikipedia_url: str = ""
    image_file: str | None = None
    image_credit: str = ""
    image_source_url: str = ""
    location_notes: str = ""

    @property
    def image_path(self) -> Path | None:
        if not self.image_file:
            return None
        return DATA_ROOT / self.image_file

    @classmethod
    def from_json(cls, obj: dict) -> "Species":
        return cls(
            id=obj["id"],
            common_name=obj.get("commonName", ""),
            scientific_name=obj.get("scientificName", ""),
            kind=obj.get("kind", ""),
            group=obj.get("group", ""),
            regions=list(obj.get("regions", [])),
            habitats=list(obj.get("habitats", [])),
            colors=list(obj.get("colors", [])),
            edible=bool(obj.get("edible", False)),
            summary=obj.get("summary", ""),
            wikipedia_url=obj.get("wikipediaUrl", ""),
            image_file=obj.get("imageFile"),
            image_credit=obj.get("imageCredit", ""),
            image_source_url=obj.get("imageSourceUrl", ""),
            location_notes=obj.get("locationNotes", ""),
        )


def load_species(path: Path = DATA_JSON) -> list[Species]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python scripts/build_wiki.py` first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Species.from_json(e) for e in data.get("species", [])]


@dataclass
class Filter:
    query: str = ""
    kind: str = "all"                # all | animal | plant
    regions: set[str] = field(default_factory=set)   # empty = all
    habitat: str = "all"             # all | one habitat key
    edibility: str = "all"           # all | yes | no

    def matches(self, sp: Species) -> bool:
        if self.kind != "all" and sp.kind != self.kind:
            return False
        if self.regions and not (self.regions & set(sp.regions)):
            return False
        if self.habitat != "all" and self.habitat not in sp.habitats:
            return False
        if self.edibility == "yes" and not sp.edible:
            return False
        if self.edibility == "no" and sp.edible:
            return False
        if self.query:
            q = self.query.lower().strip()
            hay = f"{sp.common_name}\n{sp.scientific_name}\n{sp.group}".lower()
            if q not in hay:
                return False
        return True


def apply_filter(species: Iterable[Species], f: Filter) -> list[Species]:
    return [s for s in species if f.matches(s)]
