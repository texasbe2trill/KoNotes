"""Export insights to Markdown and plain text formats."""
from __future__ import annotations

from datetime import datetime

from models.insight import InsightCard


def export_insights_markdown(
    cards: list[InsightCard],
    *,
    title: str = "KoNotes Reading Intelligence",
) -> str:
    """Export a list of InsightCard objects to a Markdown document."""
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    # Group by category
    grouped: dict[str, list[InsightCard]] = {}
    for card in cards:
        grouped.setdefault(card.category, []).append(card)

    for category, category_cards in grouped.items():
        lines.append(f"## {category}")
        lines.append("")

        for card in category_cards:
            lines.append(f"### {card.title}")
            lines.append("")
            lines.append(f"**Summary:** {card.summary}")
            lines.append("")

            if card.body:
                lines.append(card.body)
                lines.append("")

            if card.evidence:
                lines.append("**Supporting evidence:**")
                lines.append("")
                for ev in card.evidence:
                    lines.append(f"- {ev.label}: {ev.value}")
                lines.append("")

            if card.recommendation:
                lines.append(f"**Recommendation:** {card.recommendation}")
                lines.append("")

            if card.related_books:
                lines.append(f"*Related books: {', '.join(card.related_books)}*")
                lines.append("")

            lines.append("---")
            lines.append("")

    lines.append("*Made with care for the Kobo community.*")
    return "\n".join(lines)


def export_insights_text(
    cards: list[InsightCard],
    *,
    title: str = "KoNotes Reading Intelligence",
) -> str:
    """Export insights as plain text."""
    lines: list[str] = []
    lines.append(title.upper())
    lines.append("=" * len(title))
    lines.append(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    for i, card in enumerate(cards, 1):
        lines.append(f"[{i}] {card.title}")
        lines.append(f"    Category: {card.category}")
        lines.append(f"    {card.summary}")
        if card.body:
            lines.append("")
            for body_line in card.body.split('\n'):
                lines.append(f"    {body_line}")
        if card.evidence:
            lines.append("")
            lines.append("    Evidence:")
            for ev in card.evidence:
                lines.append(f"      - {ev.label}: {ev.value}")
        if card.recommendation:
            lines.append(f"    Action: {card.recommendation}")
        lines.append("")

    lines.append("Made with care for the Kobo community.")
    return "\n".join(lines)


def export_single_card_markdown(card: InsightCard) -> str:
    """Export a single InsightCard to Markdown (for copy-friendly display)."""
    lines: list[str] = []
    lines.append(f"## {card.title}")
    lines.append(f"*{card.category}*")
    lines.append("")
    lines.append(card.summary)
    lines.append("")

    if card.body:
        lines.append(card.body)
        lines.append("")

    if card.evidence:
        lines.append("**Evidence:**")
        for ev in card.evidence:
            lines.append(f"- {ev.label}: {ev.value}")
        lines.append("")

    if card.recommendation:
        lines.append(f"**Next step:** {card.recommendation}")

    return "\n".join(lines)
