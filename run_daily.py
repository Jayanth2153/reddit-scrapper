"""
run_daily.py -- Scrapes Reddit, fetches human comments, generates humanized AI responses.

NO automated posting — all comments are for manual copy-paste from the dashboard.
Run: python run_daily.py
"""

import sys
from datetime import datetime
from pathlib import Path

from config import reddit as reddit_cfg, anthropic as anthropic_cfg, scraper as scraper_cfg
from rate_limiter import RateLimitManager
from reddit_client import RedditScraper
from claude_client import ClaudeCommentGenerator
import storage

KEYWORDS_FILE = Path("keywords.txt")
MAX_POSTS     = 10
TOP_COMMENTS  = 5
W = 70


def load_keywords() -> list:
    if not KEYWORDS_FILE.exists():
        return scraper_cfg.keywords
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    kws = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    print(f"[INFO]  Loaded {len(kws)} keywords")
    return kws


def main():
    print("=" * W)
    print("  REDDIT ENGAGEMENT SCRAPER  --  Manual posting mode")
    print(f"  {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print("  No automation -- copy comments from dashboard and post manually.")
    print("=" * W)

    keywords = load_keywords()
    if not keywords:
        print("[ERR]  No keywords found. Add some to keywords.txt.")
        sys.exit(1)

    rate_manager = (
        RateLimitManager()
        .register("reddit",    requests_per_minute=3,  burst_size=1)
        .register("anthropic", requests_per_minute=45, burst_size=5)
    )

    # STEP 1: Scrape posts
    print(f"\n{'-' * W}")
    print("  STEP 1  --  Scraping posts by keyword")
    print(f"{'-' * W}")

    already_scraped = storage.get_scraped_ids()
    print(f"  [INFO]  {len(already_scraped)} post IDs already processed — will skip them")

    scraper = RedditScraper(reddit_cfg, rate_manager)
    posts   = scraper.scrape(
        domain      = scraper_cfg.domain,
        subreddits  = scraper_cfg.subreddits,
        keywords    = keywords,
        max_posts   = MAX_POSTS * 3,   # fetch extra, then filter
        time_filter = "week",
        sort_by     = "top",
    )

    # Remove already-processed posts
    posts = [p for p in posts if p.id not in already_scraped]
    # Take best 10 by engagement score (already sorted by scraper)
    posts = posts[:MAX_POSTS]

    if not posts:
        print("[WARN]  No new posts found — all top posts already processed. Try again tomorrow.")
        sys.exit(0)

    print(f"\n  [OK]  {len(posts)} new posts scraped (skipped already-processed ones)")

    # STEP 2: Fetch human comments
    print(f"\n{'-' * W}")
    print("  STEP 2  --  Fetching human comments from posts")
    print(f"{'-' * W}")

    for post in posts:
        post.top_comments_human = scraper.fetch_top_comments(post, n=TOP_COMMENTS)

    total_human = sum(len(getattr(p, "top_comments_human", [])) for p in posts)
    print(f"\n  [OK]  {total_human} human comments fetched")

    # STEP 3: Generate humanized AI comments
    print(f"\n{'-' * W}")
    print("  STEP 3  --  Generating humanized comments with Claude")
    print(f"{'-' * W}")

    generator   = ClaudeCommentGenerator(anthropic_cfg, rate_manager)
    suggestions = generator.generate_batch(
        posts,
        domain    = scraper_cfg.domain,
        expertise = scraper_cfg.your_expertise,
    )

    # STEP 4: Save and mark IDs as processed
    storage.save_results(suggestions)
    storage.mark_scraped_ids([p.id for p in posts])

    insights = [
        {
            "id":               p.id,
            "title":            p.title,
            "subreddit":        p.subreddit,
            "permalink":        p.permalink,
            "author":           p.author,
            "keyword":          p.keyword,
            "score":            p.score,
            "num_comments":     p.num_comments,
            "engagement_score": p.engagement_score,
            "selftext":         p.selftext[:500],
            "scraped_at":       datetime.utcnow().isoformat(),
            "top_comments":     getattr(p, "top_comments_human", []),
        }
        for p in posts
    ]
    storage.save_insights(insights)

    ok_count   = sum(1 for s in suggestions if s.get("suggestion", {}) and s["suggestion"].get("comment"))
    fail_count = len(suggestions) - ok_count

    print(f"\n{'=' * W}")
    print(f"  RUN COMPLETE  --  {datetime.now().strftime('%Y-%m-%d  %H:%M')}")
    print(f"{'=' * W}")
    print(f"  [OK]   {ok_count} comments ready to copy & post manually")
    print(f"  [WARN] {fail_count} posts skipped (generation failed)")
    print(f"\n  Open dashboard:  http://localhost:8501")
    print(f"  Go to Comments Queue -- copy each comment -- open Reddit link -- paste")
    print(f"{'=' * W}\n")


if __name__ == "__main__":
    main()
