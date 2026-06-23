"""
claude_client.py — Generate humanized Reddit comments via Claude.
Uses real human comments from the post as style anchors to sound natural.
"""

import json
from typing import List, Optional

import anthropic as ant

from rate_limiter import RateLimitManager, exponential_backoff
from reddit_client import RedditPost


SYSTEM_PROMPT = """You are a real person on Reddit who works in application security. You have hands-on experience with API security testing, DevSecOps, and vulnerability management. You comment like a normal engineer, not like a marketer or AI assistant.

HARD RULES — breaking any makes the comment unusable:
1. NO bullet points, numbered lists, or dashes — flowing prose only.
2. NO em-dashes as structural dividers. Use commas or short sentences instead.
3. NO bold, no headers, no formatting of any kind.
4. Use contractions naturally: don't, it's, I've, you'd, that's, isn't, didn't.
5. React to something SPECIFIC in the post — a number, a claim, a problem. Never open generically.
6. NEVER start with: "Great post", "This is interesting", "Totally agree", "Fascinating", "Excellent".
7. Use "I" — "I ran into this at work", "when we tested X...", "in my experience..."
8. 2-3 sentences MAX. Shorter is better. Reddit readers scroll fast.
9. ONE casual hedge is fine: "could be wrong but", "might depend on your stack", "at least in our env"
10. End naturally — no CTA, no summary, no "hope this helps".
11. Match the vocabulary of the subreddit — r/devops tone differs from r/netsec.
12. Only mention Aptori if it fits organically (max 1 in 10 comments). Never force it.

If human example comments are provided, study their LENGTH, TONE, and VOCABULARY — then write something similar but original.

Return ONLY a JSON object (no markdown fences, no extra text):
{
  "comment": "<2-3 sentence comment, plain prose, sounds like a real engineer typing fast>",
  "tone": "casual | technical | conversational | empathetic"
}"""


class ClaudeCommentGenerator:

    def __init__(self, cfg, rate_manager: RateLimitManager):
        self._cfg = cfg
        self._rl  = rate_manager
        self._ant = ant.Anthropic(api_key=cfg.api_key)

    def _build_prompt(self, post: RedditPost, domain: str, expertise: str) -> str:
        # Use real human comments from the post as style anchors
        human_cmts = getattr(post, "top_comments_human", None) or []
        human_block = ""
        if human_cmts:
            snippets = "\n".join(
                f'  u/{c["author"]}: "{c["body"][:220]}"'
                for c in human_cmts[:3]
            )
            human_block = (
                f"\nReal human comments already on this post "
                f"(study their tone, length, and vocabulary — DO NOT copy them directly):\n"
                f"{snippets}\n"
            )

        return f"""Domain:    {domain}
Expertise: {expertise}
Keyword:   {post.keyword or domain}

Reddit post
-----------
Subreddit: r/{post.subreddit}
Title:     {post.title}
Body:      {post.selftext[:800] or '(link post)'}
Score:     {post.score} upvotes  |  {post.num_comments} comments  |  {post.upvote_ratio*100:.0f}% upvoted
Age:       {post.age_hours():.1f}h old
{human_block}
Write the comment now. Return ONLY the JSON."""

    @exponential_backoff(max_retries=4, base_delay=2.0,
                         exceptions=(ant.APIStatusError, ant.APIConnectionError,
                                     ant.RateLimitError, Exception))
    def _call_api(self, prompt: str) -> dict:
        self._rl.wait("anthropic")
        msg = self._ant.messages.create(
            model      = self._cfg.model,
            max_tokens = self._cfg.max_tokens,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def generate_comment(self, post: RedditPost, domain: str,
                         expertise: str = "") -> Optional[dict]:
        try:
            return self._call_api(self._build_prompt(post, domain, expertise))
        except Exception as e:
            print(f"      [ERR]  Comment generation failed: {e}")
            return None

    def generate_batch(self, posts: List[RedditPost], domain: str,
                       expertise: str = "") -> List[dict]:
        results = []
        for i, post in enumerate(posts, 1):
            human_count = len(getattr(post, "top_comments_human", []))
            print(f"\n  [AI]  [{i}/{len(posts)}] \"{post.title[:58]}...\"")
            if human_count:
                print(f"         Using {human_count} human comments as style reference")
            suggestion = self.generate_comment(post, domain, expertise)
            results.append({"post": post, "suggestion": suggestion})
        return results
