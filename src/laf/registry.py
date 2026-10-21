"""Sequence registry (config/sequences.toml)."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["dev", "test-pre", "test-post", "ambiguous"]


class Sequence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z]{2}[0-9a-z]{6,12}$")
    name: str
    role: Role
    catalog_min_mag: float = Field(ge=0.0, le=6.0)


def load_sequences(path: Path) -> list[Sequence]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    seqs = [Sequence.model_validate(s) for s in raw["sequence"]]
    ids = [s.id for s in seqs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate sequence ids in {path}")
    return seqs
