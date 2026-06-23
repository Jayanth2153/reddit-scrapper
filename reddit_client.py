"""
reddit_client.py — Reddit scraper using public RSS/Atom feeds (no auth needed).
"""

import time
import re
import html
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, timezone

from rate_limiter import RateLimitManager, exponential_backoff


ATOM_NS  = "http://www.w3.org/2005/Atom"
MEDIA_NS = "http://search.yahoo.com/mrss/"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})


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
    score:         int       = 100      # not available via RSS; default
    num_comments:  int       = 10       # not available via RSS; default
    upvote_ratio:  float     = 0.9      # not available via RSS; default
    num_awards:    int       = 0
    created_utc:   float     = 0.0
    permalink:     str       = ""
    author:        str       = "[unknown]"
    flair:         Optional[str] = None
    top_comments:  List[str] = field(default_factory=list)
    engagement_score: float  = 0.0
    keyword:       str       = ""       # keyword that surfaced this post

    def age_hours(self) -> float:
        return (time.time() - self.created_utc) / 3600


# ------------------------------------------------------------------ #
# Engagement scoring — weights informative/exclusive content higher
# ------------------------------------------------------------------ #

# Title/body phrases that signal a post shares original findings or experience
_INFO_SIGNALS = [
    "i built", "i made", "i created", "i wrote", "i found", "i discovered",
    "i tested", "i tried", "i spent", "i analyzed", "i compared", "i released",
    "we built", "we found", "we released", "we tested",
    "analysis", "benchmark", "benchmarks", "deep dive", "breakdown",
    "findings", "results", "research", "case study", "lessons learned",
    "review", "comparison", "tutorial", "guide", "how i", "my experience",
    "my journey", "sharing", "insight", "insights", "open source", "paper",
    "study", "dataset", "framework", "implementation", "behind the scenes",
    "i spent", "months", "years", "experiment", "proof of concept", "poc",
]

# Title phrases that indicate a generic help/advice request (lower priority)
_QUESTION_SIGNALS = [
    "what should", "which should", "should i", "can someone help",
    "help me", "anyone know", "is it worth", "how do i start",
    "where do i", "am i", "best way to", "recommend a", "looking for advice",
    "any suggestions", "total beginner", "complete beginner",
]


class EngagementScorer:
    def _info_score(self, p: RedditPost) -> float:
        combined = (p.title + " " + p.selftext).lower()
        title_l  = p.title.lower()

        hits = sum(1 for kw in _INFO_SIGNALS if kw in combined)
        score = min(1.0, hits / 3)  # 3+ keyword hits → max score

        # Penalise generic question posts with thin bodies
        is_question = title_l.strip().endswith("?") and len(p.selftext) < 120
        is_generic  = any(sig in title_l for sig in _QUESTION_SIGNALS)
        if is_question and is_generic:
            score *= 0.25
        elif is_question or is_generic:
            score *= 0.60

        return round(score, 4)

    def score_all(self, posts: List[RedditPost]) -> None:
        if not posts:
            return
        week_seconds = 7 * 24 * 3600
        now = time.time()
        for p in posts:
            recency    = 1.0 - min(1.0, (now - p.created_utc) / week_seconds)
            body_score = min(1.0, len(p.selftext) / 600)
            info       = self._info_score(p)
            p.engagement_score = round(0.30 * recency + 0.25 * body_score + 0.45 * info, 4)


# ------------------------------------------------------------------ #
# RSS helpers
# ------------------------------------------------------------------ #

def _strip_html(raw: str) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()


def _tag(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _parse_comment_entries(xml_text: str) -> List[dict]:
    """Parse a subreddit comments Atom feed (/r/sub/comments/.rss)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    comments = []
    for entry in root.findall(_tag(ATOM_NS, "entry")):
        link_el = entry.find(_tag(ATOM_NS, "link"))
        link    = link_el.get("href", "") if link_el is not None else ""

        author_el = entry.find(f".//{_tag(ATOM_NS, 'name')}")
        author    = (author_el.text or "[unknown]").strip() if author_el is not None else "[unknown]"
        author    = re.sub(r"^/?u/", "", author)

        content_el = entry.find(_tag(ATOM_NS, "content"))
        body_raw   = (content_el.text or "") if content_el is not None else ""
        body       = _strip_html(body_raw)[:1500].strip()

        if len(body) < 40 or body in ("[deleted]", "[removed]"):
            continue

        comments.append({
            "author":    author,
            "body":      body,
            "score":     0,   # RSS feed does not expose vote counts
            "permalink": link,
        })
    return comments


def _parse_entries(xml_text: str) -> List[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    posts = []
    for entry in root.findall(_tag(ATOM_NS, "entry")):
        link_el = entry.find(_tag(ATOM_NS, "link"))
        link    = link_el.get("href", "") if link_el is not None else ""

        m_id  = re.search(r"/comments/([a-z0-9]+)/", link)
        m_sub = re.search(r"/r/(\w+)/",              link)
        if not m_id or not m_sub:
            continue

        title_el = entry.find(_tag(ATOM_NS, "title"))
        title    = (title_el.text or "").strip() if title_el is not None else ""

        author_el = entry.find(f".//{_tag(ATOM_NS, 'name')}")
        author    = (author_el.text or "[unknown]").strip() if author_el is not None else "[unknown]"

        updated_el = entry.find(_tag(ATOM_NS, "updated"))
        updated    = (updated_el.text or "").strip() if updated_el is not None else ""

        content_el = entry.find(_tag(ATOM_NS, "content"))
        body_raw   = (content_el.text or "") if content_el is not None else ""
        body       = _strip_html(body_raw)[:1200]

        posts.append({
            "id":        m_id.group(1),
            "subreddit": m_sub.group(1),
            "title":     title,
            "selftext":  body,
            "permalink": link,
            "author":    author.lstrip("/u/"),
            "created":   _parse_date(updated),
        })
    return posts


# ------------------------------------------------------------------ #
# Reddit client
# ------------------------------------------------------------------ #

class RedditScraper:

    BASE = "https://www.reddit.com"

    def __init__(self, cfg, rate_manager: RateLimitManager):
        self._rl     = rate_manager
        self._scorer = EngagementScorer()
        print("[OK]  Using Reddit public RSS feeds (no login required)")

    def _get_rss(self, url: str, params: dict = None) -> List[dict]:
        self._rl.wait("reddit")
        resp = SESSION.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return _parse_entries(resp.text)

    @exponential_backoff(max_retries=3, base_delay=2.0, exceptions=(Exception,))
    def _fetch_sorted(self, sub: str, sort: str, limit: int) -> List[dict]:
        return self._get_rss(f"{self.BASE}/r/{sub}/{sort}.rss", {"limit": limit})

    @exponential_backoff(max_retries=3, base_delay=2.0, exceptions=(Exception,))
    def _search(self, query: str, sub: Optional[str], time_filter: str, limit: int) -> List[dict]:
        if sub:
            url = f"{self.BASE}/r/{sub}/search.rss"
            params = {"q": query, "restrict_sr": "true", "t": time_filter, "limit": limit}
        else:
            url = f"{self.BASE}/search.rss"
            params = {"q": query, "t": time_filter, "limit": limit}
        return self._get_rss(url, params)

    @staticmethod
    def _to_post(d: dict) -> RedditPost:
        return RedditPost(
            id          = d["id"],
            title       = d["title"],
            selftext    = d["selftext"],
            url         = d["permalink"],
            subreddit   = d["subreddit"],
            created_utc = d["created"],
            permalink   = d["permalink"],
            author      = d["author"],
        )

    # ---------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------- #

    def fetch_top_comments(self, post: "RedditPost", n: int = 5) -> list:
        """
        Fetch recent human comments for a post via the subreddit comments RSS feed.
        The feed is fetched once per subreddit and cached for the lifetime of this
        scraper instance, so multiple posts from the same sub share one HTTP request.
        """
        if not hasattr(self, "_comment_cache"):
            self._comment_cache: Dict[str, List[dict]] = {}

        sub = post.subreddit.lower()

        if sub not in self._comment_cache:
            try:
                self._rl.wait("reddit")
                url  = f"{self.BASE}/r/{sub}/comments/.rss"
                resp = SESSION.get(url, params={"limit": 100}, timeout=15)
                resp.raise_for_status()
                self._comment_cache[sub] = _parse_comment_entries(resp.text)
                print(f"      [RSS]  Fetched {len(self._comment_cache[sub])} recent comments for r/{sub}")
            except Exception as e:
                print(f"      [WARN]  Could not fetch comments feed for r/{sub}: {e}")
                self._comment_cache[sub] = []

        matched = [
            c for c in self._comment_cache[sub]
            if f"/comments/{post.id}/" in c.get("permalink", "")
        ]
        return matched[:n]

    def scrape(
        self,
        domain:       str,
        subreddits:   List[str],
        keywords:     List[str],
        min_score:    int  = 10,
        min_comments: int  = 5,
        max_posts:    int  = 10,
        time_filter:  str  = "week",
        sort_by:      str  = "top",
    ) -> List[RedditPost]:
        seen: Dict[str, RedditPost] = {}
        target_subs = {s.lower().lstrip("r/").strip() for s in subreddits}

        # Phase 1 — per-keyword search in r/all, filtered to target subreddits
        # This is the primary mode: find posts that match what the user cares about
        for kw in keywords[:8]:   # cap at 8 keywords to avoid rate limit pile-up
            print(f"\n  [KW]  Keyword: \"{kw}\"")
            try:
                results = self._search(kw, None, time_filter, limit=50)
                added = 0
                for d in results:
                    if d["subreddit"].lower() in target_subs and d["id"] not in seen:
                        post = self._to_post(d)
                        post.keyword = kw
                        seen[d["id"]] = post
                        added += 1
                print(f"        {added} new posts found")
            except Exception as e:
                print(f"      [WARN]  {e}")

        # Phase 2 — top feed fallback for 2 subreddits if we need more posts
        if len(seen) < max_posts:
            for sub in subreddits[:2]:
                clean = sub.lstrip("r/").strip()
                print(f"\n  [RSS]  r/{clean}  fallback top feed")
                try:
                    for d in self._fetch_sorted(clean, sort_by, limit=50):
                        if d["id"] not in seen:
                            post = self._to_post(d)
                            post.keyword = domain
                            seen[d["id"]] = post
                    print(f"         {len(seen)} unique posts so far")
                except Exception as e:
                    print(f"      [WARN]  {e}")

        posts = list(seen.values())
        print(f"\n  [INFO]  {len(posts)} posts collected before quality filter")

        # Drop zero-body pure question posts
        posts = [
            p for p in posts
            if not (
                len(p.selftext) < 60
                and p.title.strip().endswith("?")
                and any(sig in p.title.lower() for sig in _QUESTION_SIGNALS)
            )
        ]
        print(f"  [INFO]  {len(posts)} posts after quality filter")

        if not posts:
            return []

        self._scorer.score_all(posts)
        posts.sort(key=lambda p: p.engagement_score, reverse=True)
        return posts[:max_posts]
