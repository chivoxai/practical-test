"""Internal data structures passed between pipeline stages (not part of the public API)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str = ""
    position: int = 0
    query: str = ""
    backend: str = ""


@dataclass
class RawProfile:
    """One public profile/page found on one platform. Every URL here was returned by a
    search index, an official API, or a link published on the prospect's own page —
    URLs are never constructed from names."""

    platform: str                      # one of the assessment platform names
    url: str                           # canonical URL
    name: Optional[str] = None
    handle: Optional[str] = None
    kind: str = "unknown"              # person | business | unknown
    title: str = ""
    snippet: str = ""
    bio: str = ""                      # official API description / website text excerpt
    source: str = ""                   # e.g. "serper", "youtube_api", "website:acme.com"
    query: str = ""                    # search query that produced it
    country_code: Optional[str] = None # e.g. from YouTube channel metadata
    emails: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    whatsapp: Set[str] = field(default_factory=set)
    linked_urls: Set[str] = field(default_factory=set)  # canonical URLs this profile links to

    def text(self) -> str:
        return " \n ".join(x for x in (self.name or "", self.title, self.snippet, self.bio) if x)


@dataclass
class Candidate:
    """A consolidated prospect: one or more RawProfiles believed to be the same entity."""

    profiles: List[RawProfile]
    name: str = ""
    location: Optional[str] = None
    score: float = 0.0
    status: str = "rejected"          # confirmed | likely | possible | rejected
    evidence: List[str] = field(default_factory=list)
    merge_reasons: List[str] = field(default_factory=list)
    signals: Dict[str, bool] = field(default_factory=dict)

    def platforms(self) -> List[str]:
        return sorted({p.platform for p in self.profiles})

    def text(self) -> str:
        return " \n ".join(p.text() for p in self.profiles)

    def emails(self) -> Set[str]:
        return set().union(*(p.emails for p in self.profiles)) if self.profiles else set()

    def phones(self) -> Set[str]:
        return set().union(*(p.phones for p in self.profiles)) if self.profiles else set()

    def whatsapp(self) -> Set[str]:
        return set().union(*(p.whatsapp for p in self.profiles)) if self.profiles else set()
