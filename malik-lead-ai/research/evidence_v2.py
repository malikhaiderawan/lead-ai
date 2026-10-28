"""Standalone, immutable evidence contract; no fetching, inference, or persistence.

Retrieval rules (in precedence order): no attempt -> NOT_CHECKED; a transport
failure -> UNREACHABLE; HTTP 401/403/429 or an identified access wall -> BLOCKED;
404 -> NOT_FOUND for that URL only; usable 2xx content -> RETRIEVED. Everything
else is UNKNOWN, including unresolved redirects, other HTTP errors, unassessed
content, and probable JavaScript shells. No retrieval outcome implies a feature.

Callers supply timezone-aware timestamps and content signals. This module does
not detect walls/shells, validate network destinations, or verify quoted truth.
Absence requires an explicit supporting statement within exactly the assertion's
scope; a missing link, failed request, or unsuccessful search is insufficient.
Scope is caller-defined, never expanded to an entire business automatically.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


class RetrievalStatus(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    RETRIEVED = "RETRIEVED"
    NOT_FOUND = "NOT_FOUND"
    BLOCKED = "BLOCKED"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class FeatureStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PRESENT = "PRESENT"
    NOT_OBSERVED = "NOT_OBSERVED"
    VERIFIED_ABSENT = "VERIFIED_ABSENT"
    DISPUTED = "DISPUTED"


class TransportError(str, Enum):
    TIMEOUT = "TIMEOUT"
    DNS = "DNS"
    TLS = "TLS"
    CONNECTION = "CONNECTION"


class ContentSignal(str, Enum):
    UNASSESSED = "UNASSESSED"
    USABLE = "USABLE"
    LOGIN_WALL = "LOGIN_WALL"
    CAPTCHA = "CAPTCHA"
    CHALLENGE = "CHALLENGE"
    JAVASCRIPT_SHELL = "JAVASCRIPT_SHELL"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be nonblank text")


@dataclass(frozen=True)
class RetrievalResult:
    """One URL attempt, with derived status/reason that cannot be supplied.

``retrieved_at`` records the attempt time, including failed retrievals. No-attempt
records have no timestamp or response signals. Transport errors describe failures
before a usable response and cannot be combined with HTTP/content signals.
USABLE requires 2xx other than 204/205. Access-wall signals override HTTP 404:
an intercepted response does not establish a missing URL. HTTP 5xx is UNKNOWN,
since an HTTP response establishes reachability but not usable content.
"""

    source_url: str = ""
    retrieved_at: Optional[datetime] = None
    attempted: bool = False
    http_status: Optional[int] = None
    error: Optional[TransportError] = None
    content: ContentSignal = ContentSignal.UNASSESSED
    status: RetrievalStatus = field(init=False)
    reason: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.attempted) is not bool or not isinstance(self.source_url, str):
            raise ValueError("attempted must be bool; source_url must be text")
        if not isinstance(self.content, ContentSignal):
            raise ValueError("content must be a ContentSignal")
        if self.error is not None and not isinstance(self.error, TransportError):
            raise ValueError("error must be a TransportError")
        if self.http_status is not None and (
            type(self.http_status) is not int or not 100 <= self.http_status <= 599
        ):
            raise ValueError("http_status must be an integer from 100 to 599")
        if not self.attempted:
            if (self.retrieved_at is not None or self.http_status is not None
                    or self.error is not None or self.content != ContentSignal.UNASSESSED):
                raise ValueError("NOT_CHECKED cannot carry attempt/response signals")
            status, reason = RetrievalStatus.NOT_CHECKED, "not_attempted"
        else:
            _text(self.source_url, "source_url")
            if (not isinstance(self.retrieved_at, datetime)
                    or self.retrieved_at.utcoffset() is None):
                raise ValueError("attempts require a timezone-aware retrieved_at")
            if self.error is not None:
                if self.http_status is not None or self.content != ContentSignal.UNASSESSED:
                    raise ValueError("transport error conflicts with response signals")
                status, reason = RetrievalStatus.UNREACHABLE, self.error.value.lower()
            else:
                if self.content != ContentSignal.UNASSESSED and self.http_status is None:
                    raise ValueError("content signals require an HTTP response")
                if self.content == ContentSignal.USABLE and (
                    not 200 <= self.http_status < 300 or self.http_status in (204, 205)
                ):
                    raise ValueError("usable content requires a body-bearing 2xx response")
                if self.http_status in (401, 403, 429):
                    status, reason = RetrievalStatus.BLOCKED, "http_" + str(self.http_status)
                elif self.content in (ContentSignal.LOGIN_WALL, ContentSignal.CAPTCHA,
                                      ContentSignal.CHALLENGE):
                    status, reason = RetrievalStatus.BLOCKED, self.content.value.lower()
                elif self.http_status == 404:
                    status, reason = RetrievalStatus.NOT_FOUND, "url_http_404"
                elif self.content == ContentSignal.USABLE:
                    status, reason = RetrievalStatus.RETRIEVED, "usable_content"
                else:
                    status = RetrievalStatus.UNKNOWN
                    reason = ("javascript_shell" if self.content == ContentSignal.JAVASCRIPT_SHELL
                              else "unassessed_response" if self.http_status is not None
                              else "no_result")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True)
class EvidenceReference:
    """Scoped, caller-supplied evidence, tied to a URL and attempt timestamp.

``explicit_absence`` means the statement explicitly supports absence within
``scope``. It must not be set merely because a feature was not observed.
Failed attempts may be referenced with an empty statement, but cannot support
feature claims. Reference IDs are caller-owned; no files are read to resolve them.
"""

    reference_id: str
    retrieval: RetrievalResult
    scope: str
    statement: str = ""
    explicit_absence: bool = False

    def __post_init__(self) -> None:
        _text(self.reference_id, "reference_id")
        _text(self.scope, "scope")
        if not isinstance(self.retrieval, RetrievalResult):
            raise ValueError("retrieval must be a RetrievalResult")
        if not isinstance(self.statement, str) or type(self.explicit_absence) is not bool:
            raise ValueError("statement must be text; explicit_absence must be bool")
        if self.retrieval.status != RetrievalStatus.RETRIEVED:
            if self.statement or self.explicit_absence:
                raise ValueError("failed/unassessed retrieval cannot support a statement")
        if self.explicit_absence:
            _text(self.statement, "explicit absence statement")


@dataclass(frozen=True)
class FeatureAssertion:
    """A feature claim, independent of retrieval status; default is UNKNOWN.

Non-UNKNOWN claims require same-scope, usable, nonblank evidence. NOT_OBSERVED
means only that the stated inspection did not observe the feature. VERIFIED_ABSENT
requires exclusively explicit absence evidence. DISPUTED requires at least two
distinct references; the caller's reason must explain their conflict. No automatic
conflict resolution, staleness policy, scoring, or business-wide inference occurs.
"""

    feature: str
    reason: str
    status: FeatureStatus = FeatureStatus.UNKNOWN
    scope: str = ""
    evidence: Tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _text(self.feature, "feature")
        _text(self.reason, "reason")
        if not isinstance(self.status, FeatureStatus) or not isinstance(self.scope, str):
            raise ValueError("status must be FeatureStatus; scope must be text")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(ref, EvidenceReference) for ref in self.evidence
        ):
            raise ValueError("evidence must be a tuple of EvidenceReference objects")
        if len({ref.reference_id for ref in self.evidence}) != len(self.evidence):
            raise ValueError("evidence reference IDs must be unique")
        if self.evidence or self.status != FeatureStatus.UNKNOWN:
            _text(self.scope, "scope")
            if any(ref.scope != self.scope for ref in self.evidence):
                raise ValueError("evidence scope must exactly match assertion scope")
        if self.status == FeatureStatus.UNKNOWN:
            return
        if not self.evidence:
            raise ValueError("feature claims require supporting evidence")
        for ref in self.evidence:
            if ref.retrieval.status != RetrievalStatus.RETRIEVED:
                raise ValueError("feature claims require usable retrieved evidence")
            _text(ref.statement, "supporting statement")
        if self.status == FeatureStatus.VERIFIED_ABSENT:
            if not all(ref.explicit_absence for ref in self.evidence):
                raise ValueError("VERIFIED_ABSENT requires explicit scoped absence evidence")
        elif self.status in (FeatureStatus.PRESENT, FeatureStatus.NOT_OBSERVED):
            if any(ref.explicit_absence for ref in self.evidence):
                raise ValueError("explicit absence conflicts with this assertion status")
        elif self.status == FeatureStatus.DISPUTED and len(self.evidence) < 2:
            raise ValueError("DISPUTED requires at least two distinct evidence references")
