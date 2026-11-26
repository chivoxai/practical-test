"""Pydantic models for the public API plus internal data structures."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Platform names exactly as defined in the assessment, plus "Phone" for tel: links
# (the brief asks for phone numbers inside social_link but defines no platform name).
PlatformName = Literal[
    "Google",
    "LinkedIn",
    "X",
    "YouTube",
    "Instagram",
    "WhatsApp",
    "Facebook",
    "Email",
    "Threads",
    "Phone",
]


# --------------------------------------------------------------------------- #
# Public request / response
# --------------------------------------------------------------------------- #
class ProspectRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=300, examples=["Football lovers in Washington DC in USA"])

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("query is too short")
        if not any(ch.isalpha() for ch in v):
            raise ValueError("query must contain words")
        return v


class SocialLink(BaseModel):
    platform: PlatformName
    link: str


class Prospect(BaseModel):
    name: str = Field(..., min_length=1)
    location: Optional[str] = None
    social_link: List[SocialLink] = Field(default_factory=list)
    # Only present with ?include_evidence=true: match status (confirmed = evidence found,
    # likely = LLM-inferred), score, evidence and merge reasons.
    match: Optional[dict] = None


class ProspectResponse(BaseModel):
    success: bool
    query: str
    total_prospects: int
    prospects: List[Prospect]
    # Only filled on failures, or when ?debug=true is passed.
    error: Optional[str] = None
    debug: Optional[dict] = None

    def to_public(self) -> dict:
        """Spec-shaped JSON: optional keys are dropped when empty, `location` is kept."""
        data = self.model_dump()
        for k in ("error", "debug"):
            if data.get(k) is None:
                data.pop(k, None)
        for p in data["prospects"]:
            if p.get("match") is None:
                p.pop("match", None)
        return data


# --------------------------------------------------------------------------- #
# Internal: parsed query
# --------------------------------------------------------------------------- #
class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class ParsedQuery(BaseModel):
    interest: Optional[str] = None
    audience: Optional[str] = None
    location: Location = Field(default_factory=Location)
    target_type: Literal["individual", "business", "any"] = "individual"
    # Extra signals that drive search generation and relevance scoring.
    keywords: List[str] = Field(default_factory=list)         # interest synonyms, e.g. "soccer", "NFL"
    role_keywords: List[str] = Field(default_factory=list)    # e.g. "founder", "owner", "CEO"
    location_aliases: List[str] = Field(default_factory=list)  # e.g. "DC", "D.C.", "Washington, D.C."
    parsed_by: str = "heuristic"                              # "llm:<model>" | "heuristic"

    def interest_terms(self) -> List[str]:
        terms = [self.interest] if self.interest else []
        terms += self.keywords
        return _dedupe_terms(terms)

    def location_terms(self) -> List[str]:
        loc = self.location
        terms = [loc.city, loc.state] + list(self.location_aliases)
        return _dedupe_terms([t for t in terms if t])

    def country_terms(self) -> List[str]:
        from app.utils.normalizers import country_aliases

        return country_aliases(self.location.country)

    def location_label(self) -> Optional[str]:
        parts = [self.location.city or self.location.state, self.location.country]
        parts = [p for p in parts if p]
        return ", ".join(parts) if parts else None


def _dedupe_terms(terms: List[Optional[str]]) -> List[str]:
    out, seen = [], set()
    for t in terms:
        if not t:
            continue
        k = t.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(t.strip())
    return out
