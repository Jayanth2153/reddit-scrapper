"""
main.py — Reddit Engagement Bot, powered by Claude AI.

Usage:
    1. Copy .env.example → .env and fill in your credentials.
    2. Tune the CONFIG block below to your domain and subreddits.
    3. Run:  python main.py
"""

import json
import csv
from datetime import datetime

from config import reddit as reddit_cfg, anthropic as anthropic_cfg, scraper as scraper_cfg
from rate_limiter import RateLimitManager
from reddit_client import RedditScraper, RedditPost
from claude_client import ClaudeCommentGenerator
from storage import get_today_commented_count


# ══════════════════════════════════════════════════════════════════════
# ❶  CONFIGURE YOUR BOT HERE
# ══════════════════════════════════════════════════════════════════════

DOMAIN         = scraper_cfg.domain
SUBREDDITS     = scraper_cfg.subreddits
KEYWORDS       = scraper_cfg.keywords
MY_EXPERTISE   = scraper_cfg.your_expertise

MIN_SCORE      = scraper_cfg.min_score
MIN_COMMENTS   = scraper_cfg.min_comments
MAX_POSTS      = scraper_cfg.max_posts
DAILY_LIMIT    = scraper_cfg.daily_scrape_limit
TIME_FILTER    = scraper_cfg.time_filter
SORT_BY        = scraper_cfg.sort_by
OUTPUT_FMT     = scraper_cfg.output_format

# ══════════════════════════════════════════════════════════════════════


def build_rate_manager() -> RateLimitManager:
    return (
        RateLimitManager()
        .register("reddit",    requests_per_minute=6, burst_size=1)
        .register("anthropic", requests_per_minute=45, burst_size=5)
    )


# ─────────────────────────────────────────────────────────────────────
# Pretty printer
# ─────────────────────────────────────────────────────────────────────

DIVIDER = "─" * 80

def print_results(results: list) -> None:
    print(f"\n\n{'═' * 80}")
    print("  🚀  REDDIT ENGAGEMENT REPORT")
    print(f"{'═' * 80}")

    for i, r in enumerate(results, 1):
        post: RedditPost = r["post"]
        sug: dict | None = r["suggestion"]

        print(f"\n  POST #{i}  ·  engagement score: {post.engagement_score:.3f}")
        print(f"  {post.title}")
        print(f"  r/{post.subreddit}  ·  ⬆ {post.score}  ·  💬 {post.num_comments}  "
              f"·  🏆 {post.num_awards}  ·  {post.age_hours():.1f} h old")
        print(f"  {post.permalink}")

        if sug:
            tone = sug.get("tone", "").upper()
            eng  = sug.get("estimated_engagement", "?").upper()
            print(f"\n  💡  SUGGESTED COMMENT  [{tone}  ·  est. engagement: {eng}]")
            for line in sug.get("comment", "").splitlines():
                print(f"     {line}")
            print(f"\n  📐  Strategy   : {sug.get('strategy', '')}")
            print(f"  ⏰  Timing tip  : {sug.get('best_time_to_post', '')}")
        else:
            print("  ❌  Comment generation failed for this post.")

        print(f"\n{DIVIDER}")


# ─────────────────────────────────────────────────────────────────────
# Export helpers
# ─────────────────────────────────────────────────────────────────────

FIELDS = [
    "post_title", "subreddit", "permalink", "score", "num_comments",
    "upvote_ratio", "num_awards", "age_hours", "engagement_score",
    "suggested_comment", "strategy", "tone", "estimated_engagement",
    "best_time_to_post",
]

def _flatten(r: dict) -> dict:
    p: RedditPost = r["post"]
    s: dict       = r["suggestion"] or {}
    return {
        "post_title":           p.title,
        "subreddit":            p.subreddit,
        "permalink":            p.permalink,
        "score":                p.score,
        "num_comments":         p.num_comments,
        "upvote_ratio":         p.upvote_ratio,
        "num_awards":           p.num_awards,
        "age_hours":            round(p.age_hours(), 1),
        "engagement_score":     p.engagement_score,
        "suggested_comment":    s.get("comment", ""),
        "strategy":             s.get("strategy", ""),
        "tone":                 s.get("tone", ""),
        "estimated_engagement": s.get("estimated_engagement", ""),
        "best_time_to_post":    s.get("best_time_to_post", ""),
    }

def export(results: list, fmt: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = [_flatten(r) for r in results]

    if fmt in ("json", "both"):
        path = f"reddit_engagement_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        print(f"\n  ✅  JSON  → {path}")

    if fmt in ("csv", "both"):
        path = f"reddit_engagement_{ts}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"  ✅  CSV   → {path}")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("🤖  Reddit Engagement Bot — powered by Claude AI")
    print(f"    Domain     : {DOMAIN}")
    print(f"    Subreddits : {', '.join(f'r/{s}' for s in SUBREDDITS)}")
    print(f"    Time filter: {TIME_FILTER}  ·  Sort: {SORT_BY}")
    print(f"    Target posts: top {MAX_POSTS}\n")

    # 1 — Rate limiter
    rate_manager = build_rate_manager()

    # 2 — Scrape
    print("━" * 50)
    print("STEP 1  Scraping Reddit …")
    print("━" * 50)
    scraper   = RedditScraper(reddit_cfg, rate_manager)
    posts     = scraper.scrape(
        domain       = DOMAIN,
        subreddits   = SUBREDDITS,
        keywords     = KEYWORDS,
        min_score    = MIN_SCORE,
        min_comments = MIN_COMMENTS,
        max_posts    = MAX_POSTS,
        time_filter  = TIME_FILTER,
        sort_by      = SORT_BY,
    )

    if not posts:
        print("\n⚠  No posts found. Try lowering min_score / min_comments "
              "or broadening your subreddit/keyword list.")
        return

    print(f"\n  ✅  Found {len(posts)} high-engagement posts.")

    # 3 — Generate comments
    print("\n" + "━" * 50)
    print("STEP 2  Generating comments with Claude …")
    print("━" * 50)
    generator = ClaudeCommentGenerator(anthropic_cfg, rate_manager)
    results   = generator.generate_batch(posts, DOMAIN, MY_EXPERTISE)

    # 4 — Display
    print_results(results)

    # 5 — Export
    export(results, OUTPUT_FMT)

    # 6 — Rate limiter status
    print("\n  📊  Rate limiter status:")
    for api, info in rate_manager.status().items():
        print(f"      {api:12s}: {info['tokens_available']} / {info['burst_size']} tokens")


if __name__ == "__main__":
    main()
