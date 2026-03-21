"""
Global Analysis State Management

Used for maintaining global information during two-pass analysis, ensuring terminology consistency and avoiding duplicate suggestions
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnalysisState:
    """Global analysis state

    Tracks information throughout the document analysis process:
    - Terms and their usage locations
    - Issues found (for deduplication)
    - Issue statistics per category
    - Summaries per section
    """

    # Terms found and their usage
    terminology: Dict[str, List[str]] = field(default_factory=dict)
    # term -> list of locations where it appears

    # Issues found summary (for deduplication)
    found_issues: Dict[str, Set[str]] = field(default_factory=dict)
    # (category, rule_id) -> {location descriptions}

    # Issue statistics per category
    issue_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Section-level summaries
    section_summaries: Dict[str, str] = field(default_factory=dict)
    # section_title -> summary_text

    # Raw summaries from scan phase (unparsed)
    raw_summaries: Dict[str, str] = field(default_factory=dict)
    # section_title -> raw JSON string

    def add_term(self, term: str, location: str) -> None:
        """Add term and its location"""
        if term not in self.terminology:
            self.terminology[term] = []
        self.terminology[term].append(location)
        logger.debug(f"Added term: {term} @ {location}")

    def add_issue(self, category: str, rule_id: str, location: str) -> None:
        """Add found issue"""
        key = f"{category}_{rule_id}"
        if key not in self.found_issues:
            self.found_issues[key] = set()
        self.found_issues[key].add(location)
        self.issue_counts[category] += 1
        logger.debug(f"Added issue: {category}.{rule_id} @ {location}")

    def is_duplicate_issue(self, category: str, rule_id: str, location: str) -> bool:
        """Check if duplicate issue"""
        key = f"{category}_{rule_id}"
        if key in self.found_issues:
            # Check if near same location
            return any(
                self._locations_close(location, existing)
                for existing in self.found_issues[key]
            )
        return False

    def _locations_close(self, loc1: str, loc2: str, threshold: int = 50) -> bool:
        """Determine if two location descriptions are close"""
        # Simplified implementation: check string similarity
        if loc1 == loc2:
            return True
        if loc2 in loc1 or loc1 in loc2:
            return True
        return False

    def get_summary_for_prompt(self) -> str:
        """Generate state summary for prompt"""
        summary_parts = []

        # Terminology summary
        if self.terminology:
            summary_parts.append("## Terminology Found So Far")
            for term, locations in list(self.terminology.items())[:20]:  # Limit count
                summary_parts.append(f"- {term}: used in {len(locations)} location(s)")
            if len(self.terminology) > 20:
                summary_parts.append(f"- ... and {len(self.terminology) - 20} more terms")

        # Found issues summary
        if self.issue_counts and sum(self.issue_counts.values()) > 0:
            summary_parts.append("\n## Issues Found So Far")
            for category, count in sorted(self.issue_counts.items()):
                if count > 0:
                    summary_parts.append(f"- {category}: {count} issues")

        return "\n".join(summary_parts) if summary_parts else ""

    def get_statistics(self) -> Dict[str, any]:
        """Get statistics"""
        return {
            "total_terms": len(self.terminology),
            "total_issues": sum(self.issue_counts.values()),
            "categories_with_issues": len([k for k, v in self.issue_counts.items() if v > 0]),
            "sections_scanned": len(self.raw_summaries)
        }
