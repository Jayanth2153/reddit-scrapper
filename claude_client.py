"""
claude_client.py — Generate contextual, authentic Reddit comments via Claude.

Each comment is analysed for strategy, tone, and estimated engagement before
being returned. Claude is instructed to be genuinely helpful — not promotional.
"""

import json
from typing import List, Optional

import anthropic as ant

from rate_limiter import RateLimitManager, exponential_backoff
from reddit_client import RedditPost


# ------------------------------------------------------------------ #
# System prompt
# ------------------------------------------------------------------ #

SYSTEM_PROMPT = """You are an expert community-engagement strategist who helps
professionals build authentic presence on Reddit.

Your job: craft a single, value-adding comment for the given post that helps
the OP or the wider community — and naturally positions the commenter as a
thoughtful expert in their domain.

Rules:
1. Add real value (insight, resource, lived experience, nuanced take).
2. Match the subreddit's tone — formal in r/MachineLearning, casual in r/Python.
3. Keep it concise and punchy. Reddit readers scroll fast.
4. Include a soft call-to-connect only when it fits naturally
   (e.g. "Happy to dig into this more if useful" — never salesy).
5. NEVER start with "Great post!" or any hollow opener.
6. NEVER be promotional or mention products/services.
7. Do not exceed 3 short paragraphs.

Return ONLY a JSON object (no markdown fences, no preamble):
{
  "comment":              "<the comment text — plain Reddit markdown>",
  "strategy":             "<one sentence: what engagement lever you used>",
  "tone":                 "technical | casual | professional | empathetic",
  "estimated_engagement": "low | medium | high",
  "best_time_to_post":    "<timing tip, e.g. 'post within 2 h of the OP for max visibility'>"
}"""


# ------------------------------------------------------------------ #
# Generator
# ------------------------------------------------------------------ #

class ClaudeCommentGenerator:

    def __init__(self, cfg, rate_manager: RateLimitManager):
        self._cfg  = cfg
        self._rl   = rate_manager
        self._ant  = ant.Anthropic(api_key=cfg.anthropic.api_key)

    # ---------------------------------------------------------------- #
    # Internal
    # ---------------------------------------------------------------- #

    def _build_prompt(self, post: RedditPost, domain: str, expertise: str) -> str:
        comments_block = ""
        if post.top_comments:
            snippets = "\n".join(f"  • {c[:300]}" for c in post.top_comments)
            comments_block = f"\nTop comments so far:\n{snippets}"

        return f"""Domain / niche:  {domain}
My expertise:    {expertise}

Reddit post
-----------
Subreddit:   r/{post.subreddit}
Title:       {post.title}
Body:        {post.selftext[:900] or '(link post – no body text)'}
Score:       {post.score} upvotes  |  {post.num_comments} comments  |  \
{post.upvote_ratio * 100:.0f}% upvoted
Flair:       {post.flair or 'none'}
Age:         {post.age_hours():.1f} h old
{comments_block}

Write the comment now. Return ONLY the JSON object — no extra text."""

    @exponential_backoff(max_retries=4, base_delay=2.0,
                         exceptions=(ant.APIStatusError, ant.APIConnectionError,
                                     ant.RateLimitError, Exception))
    def _call_api(self, prompt: str) -> dict:
        self._rl.wait("anthropic")
        msg = self._ant.messages.create(
            model      = self._cfg.anthropic.model,
            max_tokens = self._cfg.anthropic.max_tokens,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    # ---------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------- #

    def generate_comment(
        self,
        post: RedditPost,
        domain: str,
        expertise: str = "",
    ) -> Optional[dict]:
        """Generate one comment suggestion for a post. Returns None on failure."""
        try:
            return self._call_api(self._build_prompt(post, domain, expertise))
        except Exception as e:
            print(f"      ❌  Comment generation failed: {e}")
            return None

    def generate_batch(
        self,
        posts: List[RedditPost],
        domain: str,
        expertise: str = "",
    ) -> List[dict]:
        """
        Generate comments for every post in the list.
        Returns a list of dicts: {post: RedditPost, suggestion: dict | None}.
        """
        results = []
        for i, post in enumerate(posts, 1):
            print(f"\n  🤖  [{i}/{len(posts)}] \"{post.title[:60]}…\"")
            suggestion = self.generate_comment(post, domain, expertise)
            results.append({"post": post, "suggestion": suggestion})
        return results
