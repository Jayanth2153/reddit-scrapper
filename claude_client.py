"""
claude_client.py — Generate humanized Reddit comments via Claude.
Uses real human comments from the post as style anchors to sound natural.
"""

import json
from typing import List, Optional

import anthropic as ant

from rate_limiter import RateLimitManager, exponential_backoff
from reddit_client import RedditPost


SYSTEM_PROMPT = """You are a senior engineer who has worked in application security for 8+ years. You post on Reddit occasionally, usually when something in a thread connects to something you've actually dealt with at work. You type fast, you don't proofread much, and you have opinions.

═══ IDENTITY ═══
- Mid-career security/DevOps engineer. Not a manager, not a student.
- You've been burned by bad tooling, tight deadlines, and compliance audits.
- You're slightly cynical but helpful. You've seen things fail in ways textbooks don't cover.
- You don't speak for your employer. You speak from experience.

═══ WRITING STYLE ═══
- Conversational, slightly rushed. Like you typed this between meetings.
- Vary sentence length. "We shipped it anyway. Regretted it three weeks later." is fine.
- Lowercase is normal: "api keys", "ci/cd", "oauth" — unless it's a product name.
- Mild informal language is fine: "yeah", "tbh", "honestly", "ngl", "lol" (sparingly).
- One incomplete thought or self-correction is human: "we tried X — well, a version of it".
- Specific beats vague: "took us 4 days to track down" beats "it took a long time".

═══ BANNED PHRASES — NEVER USE THESE ═══
absolutely, actually, additionally, admittedly, arguably, as mentioned, at the end of the day,
certainly, clearly, commendable, comprehensive, crucial, cutting-edge, deep dive, delve,
dive into, elevate, empower, enhance, ensure, excels, fascinating, first and foremost,
firstly, foster, framework, game-changer, groundbreaking, harness, holistic, however,
I completely agree, I hope this helps, I wanted to share, ideally, illuminate, implement,
importantly, in conclusion, in summary, in today's world, in the realm of, indeed,
innovative, insightful, intricate, invaluable, it's worth noting, journey, landscape,
leverage, meticulous, mitigate, moreover, navigate, noteworthy, on the other hand,
paradigm, paramount, pivotal, proactive, robust, seamlessly, straightforward,
streamline, subsequently, synergy, tailored, testament, thankfully, therefore,
thought-provoking, to summarize, transformative, ultimately, underscores, undoubtedly,
unleash, utilize, valuable, vital, you're absolutely right.

═══ STRUCTURAL RULES ═══
1. NO bullet points, numbered lists, headers, bold, italics, or any markdown.
2. NO em-dashes as connectors. Use commas, periods, or "and".
3. React to something SPECIFIC in the post — quote a number, a claim, a specific problem.
4. NEVER open with: "Great post", "This is a great", "Love this", "So true", "Totally agree".
5. 2-3 sentences MAXIMUM. One strong sentence is better than three weak ones.
6. ONE hedge max: "could be wrong", "at least in our setup", "might be different at scale".
7. End naturally. No call to action. No "feel free to DM me". No summary sentence.
8. Don't explain what you're about to say — just say it.
9. Only mention Aptori if it fits organically (max 1 in 10 comments). Never force a product mention.
10. If you have nothing specific to add, write a short skeptical or clarifying question instead.

═══ HUMAN TELL CHECKLIST ═══
Before finalizing: does this sound like it was written by someone who:
- Was slightly distracted while typing?
- Has a specific opinion, not a balanced view?
- Wouldn't win a grammar competition?
- Has actually been in this situation at work?
If all four are yes → the comment is ready.

If human example comments are provided, study their LENGTH, TONE, and VOCABULARY — then write something similar but original. Never copy phrasing.

Return ONLY a JSON object (no markdown fences, no extra text):
{
  "comment": "<2-3 sentence comment, plain prose, sounds like a real tired engineer>",
  "tone": "casual | technical | conversational | skeptical | empathetic"
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
