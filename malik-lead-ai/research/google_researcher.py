"""Milestone 2 — Google and Maps presence researcher."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .evidence import Evidence, EvidenceClass, ResourceStatus

logger = logging.getLogger(__name__)


@dataclass
class GoogleResearch:
    """Structured Google / Google Maps listing research for one lead."""

    google_maps_url: str | None
    rating: str | None
    review_count: str | None
    address: str | None
    category: str | None
    website_connection: str  # connected / not_observed / unknown
    other_listing_notes: str = ""
    status: str = ResourceStatus.UNKNOWN
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "google_maps_url": self.google_maps_url,
            "rating": self.rating,
            "review_count": self.review_count,
            "address": self.address,
            "category": self.category,
            "website_connection": self.website_connection,
            "other_listing_notes": self.other_listing_notes,
            "status": self.status,
            "evidence": [e.to_dict() for e in self.evidence],
        }


def research_google(
    google_maps_url: str | None,
    rating: str | None,
    review_count: str | None,
    address: str | None,
    category: str | None,
    website_url: str | None,
    discovered_maps_url: str | None = None,
) -> GoogleResearch:
    """Preserve and synthesize Google-related evidence from input and search discovery."""
    maps_url = google_maps_url or discovered_maps_url
    result = GoogleResearch(
        google_maps_url=maps_url,
        rating=rating,
        review_count=review_count,
        address=address,
        category=category,
        website_connection="unknown",
        status=ResourceStatus.FOUND if (maps_url or rating or review_count) else ResourceStatus.NOT_FOUND,
        evidence=[],
    )

    fields_provided = sum(
        1
        for v in (maps_url, rating, review_count, address, category)
        if v not in (None, "", "")
    )

    evidence_parts: list[str] = []
    if maps_url:
        evidence_parts.append("Google Maps URL supplied/discovered")
    if rating:
        evidence_parts.append(f"rating {rating}")
    if review_count:
        evidence_parts.append(f"review count {review_count}")
    if address:
        evidence_parts.append("address supplied")
    if category:
        evidence_parts.append(f"category {category!r}")

    result.evidence.append(
        Evidence(
            class_=EvidenceClass.VERIFIED_FACT if fields_provided > 0 else EvidenceClass.UNKNOWN,
            statement=(
                f"Google presence data: "
                + (", ".join(evidence_parts) if evidence_parts else "no Google-related fields identified")
            ),
            detail=f"fields_present={fields_provided}",
        )
    )

    # Website connection
    if website_url and maps_url:
        result.website_connection = "observed_in_input"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT,
                statement="Both a website URL and a Google Maps listing were identified.",
            )
        )
    elif website_url:
        result.website_connection = "not_observed"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement="A website was identified but no Google Maps listing was confirmed.",
            )
        )
    else:
        result.website_connection = "unknown"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement="No website URL was identified, so website-to-listing connection is unknown.",
            )
        )

    return result


__all__ = ["GoogleResearch", "research_google"]
