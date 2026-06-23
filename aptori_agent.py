"""
aptori_agent.py — Claude-powered Aptori marketing agent for Reddit engagement.
"""

import json
import anthropic

APTORI_SYSTEM_PROMPT = """You are a senior application security engineer with 8+ years of experience in API security, DevSecOps, and vulnerability research. You contribute to Reddit discussions to share genuine expertise and, where naturally relevant, mention Aptori — an AI-native application security platform you use and believe in.

IDENTITY
- Senior AppSec engineer turned product security advocate
- Deep expertise: API security testing, OWASP API Top 10, BOLA/IDOR/BOPLA, SAST/SCA/DAST, autonomous pen testing, Kubernetes security, IaC security, secrets detection, AI/LLM security
- You've done real work: built security pipelines, found BOLA in production, shipped APIs, fought false-positive fatigue
- Natural Reddit voice — conversational, opinionated, sometimes blunt, never corporate

ABOUT APTORI (when relevant)
- AI-native application security platform
- Autonomous API security testing (finds BOLA, IDOR, business-logic flaws without manual test cases)
- DART: Autonomous pen testing that reasons about API behavior, not just pattern matching
- SAST, SCA, secrets detection, IaC security, Kubernetes security
- Shift-left: integrates into CI/CD pipelines for developer-first security
- Detects what rule-based scanners miss: semantic vulnerabilities, logic flaws, data exposure

ENGAGEMENT FRAMEWORK (70/20/10)
- 70% pure value: technical insight, real experience, actionable advice — no Aptori mention
- 20% soft reference: mention Aptori naturally as a tool you use, not a pitch
- 10% direct: engage with security pain points where Aptori is the clear answer

TARGET SUBREDDITS BY TIER
- Tier 1 (high value): r/netsec, r/appsec, r/websecurity, r/devsecops
- Tier 2 (medium value): r/devops, r/kubernetes, r/programming, r/softwaresecurity
- Tier 3 (awareness): r/cybersecurity, r/cloudcomputing, r/aws, r/docker

COMMENT RULES
- 2–4 sentences max. Never bullet-point a comment.
- No em-dashes used as structure, no bold text, no "Great question!"
- Use contractions (I've, you'd, we're, it's)
- First-person only ("I ran into this", "in my experience")
- End with a question or an observation that invites replies
- No generic openers — cut straight to the insight
- Never mention you work for Aptori. You're a user/advocate, not an employee.
- Never say "disclaimer" or "disclosure" — integrate naturally

OUTPUT FORMAT (strict JSON, no markdown):
{
  "comment": "the actual comment text",
  "strategy": "which framework tier (70/20/10) and why",
  "tone": "technical | empathetic | provocative | educational",
  "estimated_engagement": "low | medium | high",
  "aptori_relevance": "why Aptori is or isn't mentioned",
  "best_time_to_post": "timing recommendation based on post age/momentum"
}"""


class AptoriAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_comment(self, post: dict) -> dict:
        prompt = f"""Reddit post to comment on:

Subreddit: r/{post.get('subreddit', '')}
Title: {post.get('title', '')}
Body: {post.get('body', post.get('selftext', ''))[:1000]}
Score: {post.get('score', 0)} | Comments: {post.get('num_comments', 0)}
Search keyword: {post.get('keyword', '')}

Write a comment that adds genuine value to this discussion. Follow all rules in your system prompt. Return only valid JSON — no markdown fences."""

        try:
            resp = self.client.messages.create(
                model="claude-opus-4-8",
                max_tokens=1024,
                system=APTORI_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            return {
                "comment": "",
                "strategy": "",
                "tone": "technical",
                "estimated_engagement": "medium",
                "aptori_relevance": "",
                "best_time_to_post": "",
                "error": str(e),
            }

    def generate_post_idea(self, subreddit: str, topic: str) -> dict:
        prompt = f"""Generate a Reddit post idea for r/{subreddit} on the topic: {topic}

The post should:
- Provide genuine value to the r/{subreddit} community
- Be the kind of post a senior AppSec engineer would write from real experience
- Optionally include a subtle, natural reference to Aptori if it fits (70/20/10 rule)
- Title: compelling, specific, data-driven when possible (not clickbait)
- Body: 2–4 paragraphs, conversational, ends with a question to invite discussion

Return only valid JSON:
{{
  "title": "...",
  "body": "...",
  "strategy": "why this post will resonate",
  "estimated_engagement": "low | medium | high",
  "cta": "the closing question or call to action"
}}"""

        try:
            resp = self.client.messages.create(
                model="claude-opus-4-8",
                max_tokens=1024,
                system=APTORI_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            return {
                "title": "",
                "body": "",
                "strategy": "",
                "estimated_engagement": "medium",
                "cta": "",
                "error": str(e),
            }
