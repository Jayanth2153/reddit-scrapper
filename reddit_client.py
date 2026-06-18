"""
reddit_client.py — Reddit scraper and engagement scoring.

Uses PRAW (Python Reddit API Wrapper) with OAuth2 authentication.
All API calls are guarded by the shared RateLimitManager so we never
exceed Reddit's 60 req/min limit for OAuth clients.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict

import praw
import praw.exceptions

from rate_limiter import RateLimitManager, exponential_backoff


# ------------------------------------------------------------------ #
# Data model
# ------------------------------------------------------------------ #

@dataclass
class RedditPost:
    id:            str
    title:         str
    selftext:      str
    url:           str
    subreddit:     str
    score:         int
    num_comments:  int
    upvote_ratio:  float
    num_awards:    int
    created_utc:   float
    permalink:     str
    author:        str
    flair:         Optional[str]
    top_comments:  List[str]       = field(default_factory=list)
    engagement_score: float        = 0.0

    def age_hours(self) -> float:
        return (time.time() - self.created_utc) / 3600


# ------------------------------------------------------------------ #
# Engagement scoring
# ------------------------------------------------------------------ #

class EngagementScorer:
    """
    Weighted, normalised engagement score in [0, 1].

    Weights (sum to 1.0):
      score         35 %  — upvotes signal broad reach
      comments      30 %  — discussion signals depth of engagement
      upvote_ratio  20 %  — quality signal (not just controversial)
      awards        10 %  — community endorsement
      recency        5 %  — fresher posts have more engagement headroom
    """

    WEIGHTS = dict(score=0.35, comments=0.30, ratio=0.20, awards=0.10, recency=0.05)

    def score_all(self, posts: List[RedditPost]) -> None:
        """Mutate each post in-place, setting engagement_score."""
        if not posts:
            return

        max_score    = max(p.score        for p in posts) or 1
        max_comments = max(p.num_comments for p in posts) or 1
        max_awards   = max(p.num_awards   for p in posts) or 1
        week_seconds = 7 * 24 * 3600

        for p in posts:
            recency = 1.0 - min(1.0, (time.time() - p.created_utc) / week_seconds)
            p.engagement_score = round(
                self.WEIGHTS["score"]    * (p.score        / max_score)    +
                self.WEIGHTS["comments"] * (p.num_comments / max_comments) +
                self.WEIGHTS["ratio"]    * p.upvote_ratio                  +
                self.WEIGHTS["awards"]   * (p.num_awards   / max_awards)   +
                self.WEIGHTS["recency"]  * recency,
                4
            )


# ------------------------------------------------------------------ #
# Reddit client
# ------------------------------------------------------------------ #

class RedditScraper:

    def __init__(self, cfg, rate_manager: RateLimitManager):
        self._cfg  = cfg
        self._rl   = rate_manager
        self._r    = praw.Reddit(
            client_id     = cfg.reddit.client_id,
            client_secret = cfg.reddit.client_secret,
            user_agent    = cfg.reddit.user_agent,
            username      = cfg.reddit.username,
            password      = cfg.reddit.password,
        )
        self._scorer = EngagementScorer()
        me = self._r.user.me()
        print(f"✅  Authenticated as u/{me}")

    # ---------------------------------------------------------------- #
    # Internal helpers (rate-limited + retried)
    # ---------------------------------------------------------------- #

    @exponential_backoff(max_retries=4, base_delay=2.0,
                         exceptions=(praw.exceptions.PRAWException, Exception))
    def _fetch_sorted(self, sub_name: str, sort: str,
                      time_filter: str, limit: int) -> list:
        self._rl.wait("reddit")
        sub = self._r.subreddit(sub_name)
        fetchers = {
            "hot":    lambda: sub.hot(limit=limit),
            "top":    lambda: sub.top(time_filter=time_filter, limit=limit),
            "rising": lambda: sub.rising(limit=limit),
            "new":    lambda: sub.new(limit=limit),
        }
        return list(fetchers.get(sort, fetchers["hot"])())

    @exponential_backoff(max_retries=4, base_delay=2.0,
                         exceptions=(praw.exceptions.PRAWException, Exception))
    def _search(self, query: str, sub_name: Optional[str],
                time_filter: str, limit: int) -> list:
        self._rl.wait("reddit")
        target = self._r.subreddit(sub_name or "all")
        return list(target.search(query, time_filter=time_filter, limit=limit))

    @exponential_backoff(max_retries=3, base_delay=2.0,
                         exceptions=(praw.exceptions.PRAWException, Exception))
    def _top_comments(self, submission, n: int = 3) -> List[str]:
        self._rl.wait("reddit")
        submission.comment_sort = "top"
        submission.comments.replace_more(limit=0)
        out = []
        for c in list(submission.comments)[:n]:
            if hasattr(c, "body") and len(c.body) < 600:
                out.append(c.body)
        return out

    # ---------------------------------------------------------------- #
    # Conversion helper
    # ---------------------------------------------------------------- #

    @staticmethod
    def _to_post(s) -> RedditPost:
        return RedditPost(
            id           = s.id,
            title        = s.title,
            selftext     = (s.selftext or "")[:1200],
            url          = s.url,
            subreddit    = str(s.subreddit),
            score        = s.score,
            num_comments = s.num_comments,
            upvote_ratio = s.upvote_ratio,
            num_awards   = s.total_awards_received,
            created_utc  = s.created_utc,
            permalink    = f"https://reddit.com{s.permalink}",
            author       = str(s.author) if s.author else "[deleted]",
            flair        = s.link_flair_text,
        )

    # ---------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------- #

    def scrape(
        self,
        domain:       str,
        subreddits:   List[str],
        keywords:     List[str],
        min_score:    int  = 10,
        min_comments: int  = 5,
        max_posts:    int  = 10,
        time_filter:  str  = "day",
        sort_by:      str  = "hot",
    ) -> List[RedditPost]:
        """
        Collect posts, deduplicate, filter by engagement, rank, and return
        the top `max_posts` results with their top comments loaded.
        """
        seen: Dict[str, tuple] = {}   # id → (RedditPost, raw_submission)

        # Fetch sorted posts from each subreddit
        for sub in subreddits:
            clean = sub.lstrip("r/").strip()
            print(f"\n  📡  r/{clean}  (sort={sort_by})")
            try:
                for s in self._fetch_sorted(clean, sort_by, time_filter, limit=50):
                    if s.id not in seen:
                        seen[s.id] = (self._to_post(s), s)
            except Exception as e:
                print(f"      ⚠  {e}")

            # Also search by keyword within each subreddit
            for kw in keywords:
                q = f"{domain} {kw}"
                print(f"  🔍  r/{clean} → \"{q}\"")
                try:
                    for s in self._search(q, clean, time_filter, limit=25):
                        if s.id not in seen:
                            seen[s.id] = (self._to_post(s), s)
                except Exception as e:
                    print(f"      ⚠  {e}")

        # Global search if no subreddits given
        if not subreddits:
            for kw in keywords:
                q = f"{domain} {kw}"
                print(f"  🔍  all → \"{q}\"")
                try:
                    for s in self._search(q, None, time_filter, limit=30):
                        if s.id not in seen:
                            seen[s.id] = (self._to_post(s), s)
                except Exception as e:
                    print(f"      ⚠  {e}")

        # Filter by minimum engagement
        candidates = [
            (p, s) for p, s in seen.values()
            if p.score >= min_score and p.num_comments >= min_comments
        ]
        print(f"\n  📊  {len(candidates)} posts pass the engagement threshold "
              f"(min score={min_score}, min comments={min_comments})")

        if not candidates:
            return []

        # Score and sort
        posts = [p for p, _ in candidates]
        self._scorer.score_all(posts)
        posts.sort(key=lambda p: p.engagement_score, reverse=True)
        top = posts[:max_posts]

        # Enrich top posts with real comment context
        sub_map = {p.id: s for p, s in candidates}
        for i, post in enumerate(top[:5]):   # comments only for top 5
            print(f"  💬  Loading comments for post {i+1}: \"{post.title[:55]}…\"")
            try:
                post.top_comments = self._top_comments(sub_map[post.id])
            except Exception as e:
                print(f"      ⚠  {e}")

        return top
