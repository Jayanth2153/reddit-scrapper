"""
storage.py — Lightweight JSON-based storage for dashboard data.
Persists scraped posts, generated comments, and post ideas.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

DB_FILE       = "dashboard_data.json"
INSIGHTS_FILE = "insights_data.json"


def _load() -> dict:
    if not os.path.exists(DB_FILE):
        return {"posts": [], "comments": [], "post_ideas": []}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_results(results: List[dict]):
    data = _load()
    ts = datetime.utcnow().isoformat()
    for r in results:
        post = r["post"]
        suggestion = r.get("suggestion") or {}

        post_entry = {
            "id":               post.id if hasattr(post, "id") else post.get("id"),
            "title":            post.title if hasattr(post, "title") else post.get("title"),
            "subreddit":        str(post.subreddit) if hasattr(post, "subreddit") else post.get("subreddit"),
            "score":            post.score if hasattr(post, "score") else post.get("score", 0),
            "num_comments":     post.num_comments if hasattr(post, "num_comments") else post.get("num_comments", 0),
            "upvote_ratio":     post.upvote_ratio if hasattr(post, "upvote_ratio") else post.get("upvote_ratio", 0),
            "engagement_score": post.engagement_score if hasattr(post, "engagement_score") else post.get("engagement_score", 0),
            "permalink":        post.permalink if hasattr(post, "permalink") else post.get("permalink", ""),
            "author":           str(post.author) if hasattr(post, "author") else post.get("author", ""),
            "scraped_at":       ts,
            "status":           "commented" if suggestion else "skipped",
        }

        existing_ids = {p["id"] for p in data["posts"]}
        if post_entry["id"] not in existing_ids:
            data["posts"].append(post_entry)

        if suggestion:
            comment_entry = {
                "post_id":              post_entry["id"],
                "post_title":           post_entry["title"],
                "subreddit":            post_entry["subreddit"],
                "permalink":            post_entry["permalink"],
                "comment":              suggestion.get("comment", ""),
                "strategy":             suggestion.get("strategy", ""),
                "tone":                 suggestion.get("tone", ""),
                "estimated_engagement": suggestion.get("estimated_engagement", "medium"),
                "aptori_relevance":     suggestion.get("aptori_relevance", ""),
                "best_time_to_post":    suggestion.get("best_time_to_post", ""),
                "keyword":              getattr(post, "keyword", "") if hasattr(post, "keyword") else "",
                "generated_at":         ts,
                "posted":               False,
            }
            data["comments"].append(comment_entry)

    _save(data)


def save_post_idea(subreddit: str, topic: str, idea: dict):
    data = _load()
    data["post_ideas"].append({
        "subreddit":            subreddit,
        "topic":                topic,
        "title":                idea.get("title", ""),
        "body":                 idea.get("body", ""),
        "strategy":             idea.get("strategy", ""),
        "estimated_engagement": idea.get("estimated_engagement", ""),
        "cta":                  idea.get("cta", ""),
        "generated_at":         datetime.utcnow().isoformat(),
        "posted":               False,
    })
    _save(data)


def get_all() -> dict:
    return _load()


def save_insights(insights: list) -> None:
    """Upsert posts-with-human-comments into insights_data.json."""
    existing    = get_insights()
    existing_ids = {p["id"] for p in existing}
    for item in insights:
        if item["id"] not in existing_ids:
            existing.append(item)
            existing_ids.add(item["id"])
        else:
            # Refresh existing entry
            for i, e in enumerate(existing):
                if e["id"] == item["id"]:
                    existing[i] = item
                    break
    with open(INSIGHTS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def get_insights() -> list:
    if not os.path.exists(INSIGHTS_FILE):
        return []
    with open(INSIGHTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def mark_comment_posted(index: int):
    data = _load()
    if 0 <= index < len(data["comments"]):
        data["comments"][index]["posted"] = True
        _save(data)


def mark_post_idea_posted(index: int):
    data = _load()
    if 0 <= index < len(data["post_ideas"]):
        data["post_ideas"][index]["posted"] = True
        _save(data)



# ── Accounts ──────────────────────────────────────────────────────────────────

ACCOUNTS_FILE      = "accounts.json"
KEYWORDS_DATA_FILE = "keywords_data.json"
SETTINGS_FILE      = "app_settings.json"


def get_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {"theme": "dark"}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_accounts() -> list:
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_accounts(accounts: list):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)


def add_account(account: dict):
    accounts = get_accounts()
    accounts.append(account)
    save_accounts(accounts)


def update_account(username: str, updates: dict):
    accounts = get_accounts()
    for i, acc in enumerate(accounts):
        if acc.get("username") == username:
            accounts[i].update(updates)
            break
    save_accounts(accounts)


def delete_account(username: str):
    accounts = [a for a in get_accounts() if a.get("username") != username]
    save_accounts(accounts)


# ── Keywords data ─────────────────────────────────────────────────────────────

def get_keywords_data() -> list:
    if not os.path.exists(KEYWORDS_DATA_FILE):
        return []
    with open(KEYWORDS_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_keywords_data(kw_data: list):
    with open(KEYWORDS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(kw_data, f, indent=2, ensure_ascii=False)


def init_keywords_data() -> list:
    """Bootstrap keywords_data.json from keywords.txt if not yet created."""
    existing = get_keywords_data()
    if existing:
        return existing
    kw_file = Path("keywords.txt")
    keywords = []
    if kw_file.exists():
        for line in kw_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line)
    data = [
        {
            "keyword": kw, "status": "active",
            "posts_found": 0, "quality_score": 0, "last_scan": "",
        }
        for kw in keywords
    ]
    save_keywords_data(data)
    return data


# ── Comment extended fields ───────────────────────────────────────────────────

def update_comment_by_post_id(post_id: str, updates: dict):
    data = _load()
    updated = False
    for i, c in enumerate(data["comments"]):
        if c.get("post_id") == post_id:
            data["comments"][i].update(updates)
            updated = True
    if updated:
        _save(data)


def get_publishing_tracker() -> list:
    """Return comments enriched with default publishing fields."""
    data = _load()
    out = []
    for c in data["comments"]:
        out.append({
            "post_id":             c.get("post_id", ""),
            "post_title":          c.get("post_title", ""),
            "subreddit":           c.get("subreddit", ""),
            "permalink":           c.get("permalink", ""),
            "comment":             c.get("comment", ""),
            "tone":                c.get("tone", ""),
            "keyword":             c.get("keyword", ""),
            "generated_at":        c.get("generated_at", ""),
            "posted":              c.get("posted", False),
            "comment_status":      c.get("comment_status", "draft"),
            "account_used":        c.get("account_used", ""),
            "verification_status": c.get("verification_status", "pending"),
            "verified_at":         c.get("verified_at", ""),
            "verification_reason": c.get("verification_reason", ""),
        })
    return out


def seed_demo_data():
    """Populate with realistic demo data so dashboard renders without credentials."""
    data = _load()
    if data["posts"]:
        return

    from datetime import timedelta

    posts = [
        {"id": "abc1", "title": "How do you secure REST APIs in CI/CD pipelines?", "subreddit": "devops", "score": 342, "num_comments": 87, "upvote_ratio": 0.96, "engagement_score": 0.871, "permalink": "https://reddit.com/r/devops/abc1", "author": "user_devops_pro", "scraped_at": (datetime.utcnow() - timedelta(hours=3)).isoformat(), "status": "commented"},
        {"id": "abc2", "title": "OWASP API Top 10 — which ones do you actually encounter?", "subreddit": "netsec", "score": 210, "num_comments": 63, "upvote_ratio": 0.94, "engagement_score": 0.743, "permalink": "https://reddit.com/r/netsec/abc2", "author": "sec_researcher_42", "scraped_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(), "status": "commented"},
        {"id": "abc3", "title": "Frustrated with false positives from our DAST tool", "subreddit": "appsec", "score": 189, "num_comments": 54, "upvote_ratio": 0.91, "engagement_score": 0.698, "permalink": "https://reddit.com/r/appsec/abc3", "author": "appsec_lead", "scraped_at": (datetime.utcnow() - timedelta(hours=8)).isoformat(), "status": "commented"},
        {"id": "abc4", "title": "GraphQL API security — best practices thread", "subreddit": "graphql", "score": 156, "num_comments": 41, "upvote_ratio": 0.93, "engagement_score": 0.612, "permalink": "https://reddit.com/r/graphql/abc4", "author": "graphql_fan", "scraped_at": (datetime.utcnow() - timedelta(hours=10)).isoformat(), "status": "skipped"},
        {"id": "abc5", "title": "Is automated pen testing for APIs actually reliable?", "subreddit": "cybersecurity", "score": 134, "num_comments": 38, "upvote_ratio": 0.89, "engagement_score": 0.581, "permalink": "https://reddit.com/r/cybersecurity/abc5", "author": "pentester_dev", "scraped_at": (datetime.utcnow() - timedelta(hours=12)).isoformat(), "status": "commented"},
        {"id": "abc6", "title": "Broken object level authorization — how do you test for it?", "subreddit": "appsec", "score": 98, "num_comments": 29, "upvote_ratio": 0.92, "engagement_score": 0.498, "permalink": "https://reddit.com/r/appsec/abc6", "author": "bola_hunter", "scraped_at": (datetime.utcnow() - timedelta(hours=14)).isoformat(), "status": "commented"},
    ]

    comments = [
        {"post_id": "abc1", "post_title": "How do you secure REST APIs in CI/CD pipelines?", "subreddit": "devops", "permalink": "https://reddit.com/r/devops/abc1", "keyword": "API security testing", "comment": "The biggest shift we've seen is moving from perimeter testing to continuous API validation in the pipeline itself. Static analysis catches syntax issues but misses business-logic flaws entirely — like an endpoint that returns data for the wrong user if you swap an ID.\n\nWhat's worked well: contract testing (OpenAPI specs as a source of truth) + automated fuzz testing on every PR. The key is keeping the feedback loop under 5 minutes or devs ignore it.\n\nCurious what your current gate looks like — are you blocking merges on security findings or just alerting?", "strategy": "Lead with insight on logic bugs vs syntax bugs, end with question to drive replies", "tone": "technical", "estimated_engagement": "high", "aptori_relevance": "Positions semantic API testing as the missing piece in CI/CD security", "best_time_to_post": "Post within 1h of OP for max visibility", "generated_at": (datetime.utcnow() - timedelta(hours=3)).isoformat(), "posted": True},
        {"post_id": "abc2", "post_title": "OWASP API Top 10 — which ones do you actually encounter?", "subreddit": "netsec", "permalink": "https://reddit.com/r/netsec/abc2", "keyword": "OWASP API security top 10", "comment": "BOLA (Broken Object Level Authorization) by a massive margin in my experience. It's embarrassing how often you find endpoints that trust client-supplied IDs without verifying the requester owns that resource. The reason it's so prevalent: it's invisible to scanners. You need to understand the intended access model to know it's broken.\n\nBroken authentication is #2 but usually caught earlier. Excessive data exposure is sneaky — often a frontend-driven API that was never meant to be used directly.\n\nWhat sector are you testing in? The mix shifts a lot between fintech vs. healthtech vs. consumer SaaS.", "strategy": "Share concrete hierarchy from experience, prompt sector-specific discussion", "tone": "technical", "estimated_engagement": "high", "aptori_relevance": "Establishes authority on logic-based vulnerabilities that Aptori specializes in", "best_time_to_post": "Post in the first 2h — thread is gaining traction", "generated_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(), "posted": True},
        {"post_id": "abc3", "post_title": "Frustrated with false positives from our DAST tool", "subreddit": "appsec", "permalink": "https://reddit.com/r/appsec/abc3", "keyword": "automated security scanning", "comment": "This is the core problem with rule-based DAST — it doesn't understand context. It sees a SQL-shaped input going into a parameterized query and flags it anyway because it pattern-matched, not because it reasoned about the code path.\n\nThe false-positive rate usually gets worse as your API surface grows because the tool has no memory of what it already validated.\n\nHave you tried tuning the scanner's confidence thresholds, or has it gotten to the point where the team just ignores the report entirely? The latter is more dangerous than the false positives themselves.", "strategy": "Validate the pain empathetically, diagnose the root cause, end with a sharp question", "tone": "empathetic", "estimated_engagement": "high", "aptori_relevance": "Directly addresses the problem Aptori solves — semantic understanding vs rule matching", "best_time_to_post": "Post now — high engagement window", "generated_at": (datetime.utcnow() - timedelta(hours=8)).isoformat(), "posted": False},
        {"post_id": "abc5", "post_title": "Is automated pen testing for APIs actually reliable?", "subreddit": "cybersecurity", "permalink": "https://reddit.com/r/cybersecurity/abc5", "keyword": "autonomous penetration testing", "comment": "Reliable for what matters. Automated tools are excellent at finding injection flaws, misconfigurations, and known CVE patterns consistently and at scale.\n\nWhere they fall short: chained attack paths, business-logic abuse, and anything requiring lateral reasoning across multiple endpoints.\n\nThe most productive setup I've seen: automated testing in CI catches the obvious stuff fast, human pentesters focus their time on logic and privilege escalation. Automation as a floor, not a ceiling.", "strategy": "Give a nuanced both-sides answer that builds credibility", "tone": "professional", "estimated_engagement": "medium", "aptori_relevance": "Primes audience for AI-assisted testing that bridges the gap", "best_time_to_post": "Post within 3h of OP", "generated_at": (datetime.utcnow() - timedelta(hours=12)).isoformat(), "posted": False},
        {"post_id": "abc6", "post_title": "Broken object level authorization — how do you test for it?", "subreddit": "appsec", "permalink": "https://reddit.com/r/appsec/abc6", "keyword": "BOLA broken object level authorization", "comment": "BOLA is hard to test systematically because you need two things: a map of which objects belong to which users, and the ability to swap IDs and check whether the server enforces ownership.\n\nPractical approach: capture authenticated sessions for 2+ test users, replay each user's requests substituting the other user's resource IDs, flag any 200 response that returns data.\n\nAre you testing a public API or internal microservices? The attack surface differs quite a bit.", "strategy": "Give actionable methodology, show technical depth, end with scoping question", "tone": "technical", "estimated_engagement": "high", "aptori_relevance": "Demonstrates expertise in the exact vulnerability class Aptori detects autonomously", "best_time_to_post": "Post within 1h — active discussion thread", "generated_at": (datetime.utcnow() - timedelta(hours=14)).isoformat(), "posted": True},
    ]

    post_ideas = [
        {"subreddit": "devops", "topic": "API security in CI/CD", "title": "We audited 50 APIs in CI/CD pipelines — here's what we found (and what traditional DAST missed)", "body": "Over the past few months we ran API security assessments on ~50 production APIs.\n\nThe finding that surprised us most: **~60% of critical findings were business-logic vulnerabilities** that rule-based scanners had a 0% detection rate for.\n\nHappy to share more specifics if useful. What's the weirdest API vulnerability you've caught in a pipeline?", "strategy": "Data-driven post with concrete findings builds credibility", "estimated_engagement": "high", "cta": "Happy to share more specifics if useful", "generated_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(), "posted": False},
        {"subreddit": "netsec", "topic": "OWASP API Top 10 detection gaps", "title": "OWASP API Top 10: which items are actually detectable by automated tools (and which aren't)?", "body": "Been thinking about this after a few conversations with security teams frustrated by their DAST coverage.\n\nThe top two (BOLA and Broken Auth) are also the most common and highest severity. Feels like the tooling gap is exactly where it hurts most.\n\nAnyone found automated approaches that work well for BOLA specifically?", "strategy": "Educational breakdown with a clear gap that invites discussion", "estimated_engagement": "high", "cta": "Anyone found automated approaches that work well for BOLA specifically?", "generated_at": (datetime.utcnow() - timedelta(hours=5)).isoformat(), "posted": False},
    ]

    data["posts"]      = posts
    data["comments"]   = comments
    data["post_ideas"] = post_ideas
    _save(data)
