"""
config.py — Load all settings from environment variables.
Copy .env.example to .env and fill in your credentials before running.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class RedditConfig:
    client_id: str     = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent: str    = os.getenv("REDDIT_USER_AGENT", "RedditEngagementBot/1.0")
    username: str      = os.getenv("REDDIT_USERNAME", "")
    password: str      = os.getenv("REDDIT_PASSWORD", "")


@dataclass
class AnthropicConfig:
    api_key: str          = os.getenv("ANTHROPIC_API_KEY", "")
    model: str            = "claude-sonnet-4-6"
    max_tokens: int       = 600
    requests_per_minute: int = 45   # Adjust to your tier


@dataclass
class ScraperConfig:
    # ----- Tune these to your domain -----
    domain: str                = "machine learning"
    subreddits: List[str]      = field(default_factory=lambda: [
        "MachineLearning", "learnmachinelearning", "mlops", "Python"
    ])
    keywords: List[str]        = field(default_factory=lambda: [
        "best practices", "help", "career", "advice", "tutorial"
    ])
    your_expertise: str        = "ML engineer with 5 years in production systems"

    # ----- Engagement thresholds -----
    min_score: int      = 10    # Minimum upvotes for a post to qualify
    min_comments: int   = 5     # Minimum comment count
    max_posts: int      = 10    # How many top posts to generate comments for

    # ----- Fetch settings -----
    time_filter: str    = "day"   # hour | day | week | month | year | all
    sort_by: str        = "hot"   # hot | new | top | rising

    # ----- Output -----
    output_format: str  = "json"  # json | csv | both


reddit    = RedditConfig()
anthropic = AnthropicConfig()
scraper   = ScraperConfig()
