"""
scrape_insights.py — Scrape Reddit posts and fetch their best human comments.

Saves results to insights_data.json, displayed in the dashboard under
the Human Insights page.

Run:  python scrape_insights.py
"""

import sys
from datetime import datetime
from pathlib import Path

from config import reddit as reddit_cfg, scraper as scraper_cfg
from rate_limiter import RateLimitManager
from reddit_client import RedditScraper
import storage

KEYWORDS_FILE = Path("keywords.txt")
MAX_POSTS     = 20
TOP_COMMENTS  = 5

W = 70


def load_keywords() -> list:
    if not KEYWORDS_FILE.exists():
        return scraper_cfg.keywords
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    kws = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    print(f"[INFO]  Loaded {len(kws)} keywords from {KEYWORDS_FILE}")
    return kws


def main():
    print("=" * W)
    print("  INSIGHTS SCRAPER")
    print(f"  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print("=" * W)

    keywords = load_keywords()
    if not keywords:
        print("[ERR]  No keywords found. Add some to keywords.txt.")
        sys.exit(1)

    rate_manager = (
        RateLimitManager()
        .register("reddit", requests_per_minute=3, burst_size=1)
    )

    print(f"\n{'-' * W}")
    print("  STEP 1  --  Scraping posts by keyword")
    print(f"{'-' * W}")

    scraper = RedditScraper(reddit_cfg, rate_manager)
    posts   = scraper.scrape(
        domain      = scraper_cfg.domain,
        subreddits  = scraper_cfg.subreddits,
        keywords    = keywords,
        max_posts   = MAX_POSTS,
        time_filter = "week",
        sort_by     = "top",
    )

    if not posts:
        print("\n[WARN]  No posts found. Try expanding keywords or time_filter.")
        sys.exit(0)

    print(f"\n  [OK]  {len(posts)} posts to process\n")
    print(f"{'-' * W}")
    print("  STEP 2  --  Fetching top human comments per post")
    print(f"{'-' * W}")

    insights = []
    for i, post in enumerate(posts, 1):
        print(f"\n  [{i}/{len(posts)}] {post.title[:65]}")
        print(f"         r/{post.subreddit}  |  keyword: \"{post.keyword}\"")

        comments = scraper.fetch_top_comments(post, n=TOP_COMMENTS)
        print(f"         [OK]  {len(comments)} top comments fetched")

        insights.append({
            "id":               post.id,
            "title":            post.title,
            "subreddit":        post.subreddit,
            "permalink":        post.permalink,
            "author":           post.author,
            "keyword":          post.keyword,
            "score":            post.score,
            "num_comments":     post.num_comments,
            "engagement_score": post.engagement_score,
            "selftext":         post.selftext[:500],
            "scraped_at":       datetime.utcnow().isoformat(),
            "top_comments":     comments,
        })

    storage.save_insights(insights)

    total_comments = sum(len(p["top_comments"]) for p in insights)
    print(f"\n{'=' * W}")
    print(f"  DONE  --  {len(insights)} posts  |  {total_comments} human comments saved")
    print(f"  File:      insights_data.json")
    print(f"  Dashboard: http://localhost:8501  ->  Human Insights page")
    print(f"{'=' * W}\n")


if __name__ == "__main__":
    main()
