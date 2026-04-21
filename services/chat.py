"""Chat service: builds reading-data context for the LLM conversation."""
from __future__ import annotations

from models.activity import ReadingSession
from models.book import Book
from models.insight import InsightCard
from models.recommendation import Recommendation
from services.hero_insight_engine import HeroInsight, generate_hero_insight
from services.recommendation_ranking import rank_recommendations
from services.recommender import generate_recommendations
from services.share_formatter import (
    APP_PUBLIC_URL,
    format_insight_for_bluesky,
    is_shareworthy,
)
from services.stats import LibraryStats, compute_stats
from services.streaks import ReadingStreaks, compute_streaks


def build_system_prompt(
    books: list[Book],
    stats: LibraryStats,
    streaks: ReadingStreaks,
    sessions: list[ReadingSession] | None = None,
    insights: list[InsightCard] | None = None,
    hero_insight: HeroInsight | None = None,
    recommendations: list[Recommendation] | None = None,
) -> str:
    """Build a system prompt that gives the LLM full reading-data context."""
    lines: list[str] = []

    lines.append(
        "You are a reading assistant for KoNotes, a tool that helps Kobo e-reader "
        "users understand their reading data. Answer questions about the user's "
        "library, annotations, reading habits, and books. Be concise and helpful. "
        "Use the data below to ground your answers.\n\n"
        "When the user asks for a shareable post, Bluesky post, or #booksky post, "
        "generate a concise, personal, non-spammy post using their actual insight "
        "data. End the post with: Discover your reading insights with #KoNotes #booksky "
        f"{APP_PUBLIC_URL} — keep the total under 300 characters. "
        "Focus on the feeling or meaning behind the reading, not raw stats."
    )
    lines.append("")

    # Hero reading pattern (deterministic top insight from overview)
    if hero_insight is not None:
        lines.append("## Hero Reading Pattern")
        lines.append(f"- Pattern: {hero_insight.title}")
        lines.append(f"- Summary: {hero_insight.summary}")
        for item in hero_insight.evidence[:4]:
            lines.append(f"- Evidence: {item}")
        if hero_insight.recommendation:
            lines.append(f"- Recommendation: {hero_insight.recommendation}")
        lines.append("")

    # Library overview
    lines.append("## Library Overview")
    lines.append(f"- Total books: {stats.total_books}")
    lines.append(f"- Total annotations: {stats.total_annotations}")
    lines.append(f"- Highlights: {stats.total_highlights}")
    lines.append(f"- Notes: {stats.total_notes}")
    lines.append(f"- Books completed: {stats.books_completed}")
    lines.append(f"- Books in progress: {stats.books_in_progress}")
    if stats.total_reading_time_sec > 0:
        hours = stats.total_reading_time_sec / 3600
        lines.append(f"- Total reading time: {hours:.1f} hours")
    if stats.avg_rating > 0:
        lines.append(f"- Average rating: {stats.avg_rating:.1f}/5 ({stats.books_with_ratings} rated)")
    lines.append("")

    # Streaks
    if streaks.active_days >= 2:
        lines.append("## Reading Streaks")
        lines.append(f"- Current streak: {streaks.current_streak} days")
        lines.append(f"- Longest streak: {streaks.longest_streak} days")
        lines.append(f"- Active days: {streaks.active_days}")
        lines.append(f"- Weekly consistency: {streaks.weekly_consistency:.0f}%")
        if streaks.most_active_day:
            lines.append(f"- Most active day of week: {streaks.most_active_day}")
        lines.append("")

    # Top authors
    if stats.top_authors:
        lines.append("## Top Authors")
        for author, count in stats.top_authors[:10]:
            lines.append(f"- {author}: {count} book(s)")
        lines.append("")

    # Shelves
    if stats.shelf_counts:
        lines.append("## Shelves")
        for name, count in stats.shelf_counts:
            lines.append(f"- {name}: {count} book(s)")
        lines.append("")

    # Per-book details
    lines.append("## Books")
    for book in books:
        parts = [f"**{book.title}**"]
        if book.author:
            parts.append(f"by {book.author}")
        meta: list[str] = []
        if book.read_percent is not None:
            meta.append(f"{book.read_percent:.0f}% read")
        hl = sum(1 for a in book.annotations if a.kind == "highlight")
        nt = sum(1 for a in book.annotations if a.kind == "note")
        if hl:
            meta.append(f"{hl} highlights")
        if nt:
            meta.append(f"{nt} notes")
        if book.rating:
            meta.append(f"rated {book.rating}/5")
        if book.time_spent_reading and book.time_spent_reading > 0:
            mins = book.time_spent_reading // 60
            meta.append(f"{mins} min reading time")
        if book.shelves:
            meta.append(f"shelves: {', '.join(book.shelves)}")
        line = " ".join(parts)
        if meta:
            line += f" ({', '.join(meta)})"
        lines.append(f"- {line}")

    lines.append("")

    # Key insights (if available)
    if insights:
        lines.append("## Key Insights About Your Reading")
        for card in insights[:10]:
            lines.append(f"- **{card.title}** ({card.category}): {card.summary}")
            if card.recommendation:
                lines.append(f"  - Recommendation: {card.recommendation}")
        shareworthy = [c for c in insights if is_shareworthy(c)]
        if shareworthy:
            lines.append(f"\n{len(shareworthy)} of these insights are share-worthy.")
        lines.append("")

    # Recommended next steps (deterministic, grounded in annotation data)
    if recommendations:
        lines.append("## Recommended Next Steps")
        lines.append(
            "Use these when the user asks what to revisit, finish, export, or compare."
        )
        for rec in recommendations[:6]:
            lines.append(f"- **{rec.title}** [{rec.kind}]: {rec.summary}")
            lines.append(f"  - Why: {rec.reason}")
            if rec.recommended_action:
                lines.append(f"  - Action: {rec.recommended_action}")
        lines.append("")

    # Sample highlights (up to 3 per book, 30 books max)
    sample_books = [b for b in books if b.annotations][:30]
    if sample_books:
        lines.append("## Sample Highlights & Notes")
        for book in sample_books:
            highlights = [a for a in book.annotations if a.kind == "highlight"][:3]
            notes = [a for a in book.annotations if a.kind == "note"][:2]
            if highlights or notes:
                lines.append(f"### {book.title}")
                for ann in highlights:
                    text = ann.text[:300]
                    ch = f" [{ann.chapter}]" if ann.chapter else ""
                    lines.append(f'- HL{ch}: "{text}"')
                for ann in notes:
                    text = ann.text[:300]
                    lines.append(f"- Note: {text}")
        lines.append("")

    return "\n".join(lines)


def build_context(
    books: list[Book],
    sessions: list[ReadingSession] | None = None,
    insights: list[InsightCard] | None = None,
) -> str:
    """Convenience wrapper: compute stats/streaks then build the system prompt."""
    stats = compute_stats(books)
    streaks = compute_streaks(books, sessions)
    hero_insight = generate_hero_insight(
        stats,
        books,
        longest_streak=streaks.longest_streak,
        total_reading_time_sec=stats.total_reading_time_sec,
    )
    all_recs = generate_recommendations(books, stats)
    recommendations = rank_recommendations(all_recs, max_results=6)
    return build_system_prompt(
        books,
        stats,
        streaks,
        sessions,
        insights,
        hero_insight=hero_insight,
        recommendations=recommendations,
    )


def format_insight_for_chat(card: InsightCard) -> str:
    """Format a single insight card for use in a chat response."""
    parts = [f"**{card.title}**", card.summary]
    if card.body:
        parts.append(card.body)
    if card.recommendation:
        parts.append(f"*Recommendation:* {card.recommendation}")
    if card.evidence:
        parts.append("Evidence:")
        for e in card.evidence[:5]:
            parts.append(f"  - {e.label}: {e.value}")
    return "\n".join(parts)


def generate_share_post(card: InsightCard) -> str:
    """Generate a Bluesky-ready post from an insight card."""
    return format_insight_for_bluesky(card)
