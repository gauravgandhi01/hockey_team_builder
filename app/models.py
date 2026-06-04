from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SlotName = Literal["C", "W", "D", "G"]
DecadeLabel = Literal["1980s", "1990s", "2000s", "2010s", "2020s"]


class DrawRequest(BaseModel):
    openSlots: list[SlotName] = Field(min_length=1)
    excludeCandidateKeys: list[str] = Field(default_factory=list)
    hardMode: bool = False
    lockFranchiseAbbrev: str | None = None
    lockDecade: DecadeLabel | None = None
    excludePairKey: str | None = None


class LineupItem(BaseModel):
    slot: SlotName
    candidateKey: str


class GradeRequest(BaseModel):
    lineup: list[LineupItem]
