"""
dashboard.py — Aptori Reddit Engagement Console
Dark enterprise SaaS dashboard for API security community engagement.
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests as _requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from storage import (
    get_all, get_insights, get_accounts, save_accounts,
    add_account, update_account, delete_account,
    get_keywords_data, save_keywords_data, init_keywords_data,
    update_comment_by_post_id, delete_comment_by_post_id,
    get_settings, save_settings, save_results,
)
from higgsfield_client import (
    HiggsFieldClient, TEXT_TO_IMAGE_MODELS, TEXT_TO_VIDEO_MODELS,
    IMAGE_MODEL_META, VIDEO_MODEL_META, REDDIT_POST_PRESETS, REDDIT_VIDEO_PRESETS,
)
from config import anthropic as anthropic_cfg, scraper as scraper_cfg
from rate_limiter import RateLimitManager
from reddit_client import RedditPost
from claude_client import ClaudeCommentGenerator

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aptori Reddit Engagement Console",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme ────────────────────────────────────────────────────────────────────
app_settings  = get_settings()
_theme        = app_settings.get("theme", "dark")

_DARK_VARS = """
:root {
    --c-bg:      #0a0e1a;
    --c-card:    #1a2235;
    --c-row:     #111827;
    --c-b1:      #1e2d45;
    --c-b2:      #2d3748;
    --c-t1:      #f1f5f9;
    --c-t1b:     #e2e8f0;
    --c-t2:      #9ca3af;
    --c-t3:      #6b7280;
    --c-input:   #1e293b;
    --c-iborder: #334155;
    --c-link:    #93c5fd;
    --c-sbg:     #111827;
}"""

_LIGHT_VARS = """
:root {
    --c-bg:      #f8fafc;
    --c-card:    #ffffff;
    --c-row:     #f1f5f9;
    --c-b1:      #e2e8f0;
    --c-b2:      #cbd5e1;
    --c-t1:      #0f172a;
    --c-t1b:     #1e293b;
    --c-t2:      #475569;
    --c-t3:      #94a3b8;
    --c-input:   #ffffff;
    --c-iborder: #cbd5e1;
    --c-link:    #2563eb;
    --c-sbg:     #f1f5f9;
}"""

_SYSTEM_VARS = """
:root {
    --c-bg:#0a0e1a;--c-card:#1a2235;--c-row:#111827;--c-b1:#1e2d45;
    --c-b2:#2d3748;--c-t1:#f1f5f9;--c-t1b:#e2e8f0;--c-t2:#9ca3af;
    --c-t3:#6b7280;--c-input:#1e293b;--c-iborder:#334155;
    --c-link:#93c5fd;--c-sbg:#111827;
}
@media (prefers-color-scheme: light) {
    :root {
        --c-bg:#f8fafc;--c-card:#ffffff;--c-row:#f1f5f9;--c-b1:#e2e8f0;
        --c-b2:#cbd5e1;--c-t1:#0f172a;--c-t1b:#1e293b;--c-t2:#475569;
        --c-t3:#94a3b8;--c-input:#ffffff;--c-iborder:#cbd5e1;
        --c-link:#2563eb;--c-sbg:#f1f5f9;
    }
}"""

_THEME_VARS = {"dark": _DARK_VARS, "light": _LIGHT_VARS, "system": _SYSTEM_VARS}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
{_THEME_VARS.get(_theme, _DARK_VARS)}

/* ── Reset ── */
#MainMenu, footer, header {{ visibility: hidden; }}
.stDeployButton {{ display: none; }}

/* ── App shell ── */
.stApp {{ background-color: var(--c-bg) !important; }}
.main .block-container {{
    max-width: 1280px;
    padding: 2rem 2.5rem 3rem;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background: var(--c-sbg) !important;
    border-right: 1px solid var(--c-b1);
    padding-top: 0;
}}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 0; }}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{ color: var(--c-t1b); }}
[data-testid="stSidebar"] .stCaption {{ color: var(--c-t3) !important; }}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {{
    display: block;
    padding: 9px 14px !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    color: var(--c-t2) !important;
    transition: background .12s, color .12s;
    cursor: pointer;
    margin-bottom: 2px;
}}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {{
    background: var(--c-b1) !important;
    color: var(--c-t1) !important;
}}

/* ── Inputs & selects ── */
input, textarea {{
    background-color: var(--c-input) !important;
    color: var(--c-t1) !important;
    border: 1px solid var(--c-iborder) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    transition: border-color .15s;
}}
input:focus, textarea:focus {{
    border-color: #E63946 !important;
    box-shadow: 0 0 0 2px rgba(230,57,70,.15) !important;
}}
textarea {{ resize: vertical !important; }}
[data-baseweb="select"] {{ background-color: var(--c-input) !important; border-radius: 8px !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div {{ color: var(--c-t1) !important; }}
[data-baseweb="popover"] {{ background-color: var(--c-input) !important; border: 1px solid var(--c-iborder) !important; border-radius: 10px !important; }}
li[role="option"] {{ background-color: var(--c-input) !important; color: var(--c-t1) !important; }}
li[role="option"]:hover {{ background-color: var(--c-b1) !important; }}

/* ── Buttons ── */
.stButton > button {{
    background-color: var(--c-input) !important;
    color: var(--c-t1) !important;
    border: 1px solid var(--c-iborder) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 16px !important;
    transition: all .15s !important;
}}
.stButton > button:hover {{
    background-color: var(--c-b1) !important;
    border-color: var(--c-t2) !important;
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg,#E63946,#c62333) !important;
    border: none !important;
    color: #fff !important;
    font-weight: 600 !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: linear-gradient(135deg,#f04554,#d42535) !important;
    box-shadow: 0 4px 12px rgba(230,57,70,.4) !important;
    transform: translateY(-1px);
}}

/* ── Tabs ── */
[data-baseweb="tab-list"] {{
    background-color: transparent !important;
    border-bottom: 1px solid var(--c-b1) !important;
    gap: 4px;
}}
[data-baseweb="tab"] {{
    color: var(--c-t3) !important;
    background: transparent !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    border-radius: 6px 6px 0 0 !important;
}}
[data-baseweb="tab"]:hover {{ color: var(--c-t1b) !important; background: var(--c-b1) !important; }}
[aria-selected="true"][data-baseweb="tab"] {{
    color: #E63946 !important;
    border-bottom: 2px solid #E63946 !important;
    background: transparent !important;
    font-weight: 600 !important;
}}

/* ── Expander ── */
[data-testid="stExpander"] {{
    background-color: var(--c-card) !important;
    border: 1px solid var(--c-b1) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 6px rgba(0,0,0,.12);
    margin-bottom: 10px !important;
    overflow: hidden;
}}
details summary {{
    color: var(--c-t1b) !important;
    font-weight: 500 !important;
    padding: 12px 16px !important;
}}
details summary:hover {{ background: var(--c-b1) !important; }}

/* ── Metric cards ── */
[data-testid="metric-container"] {{
    background: var(--c-card) !important;
    border: 1px solid var(--c-b1) !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,.14);
    transition: transform .15s, box-shadow .15s;
}}
[data-testid="metric-container"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,.22);
}}
[data-testid="stMetricLabel"] div {{ color: var(--c-t2) !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: .07em; }}
[data-testid="stMetricValue"] div {{ color: var(--c-t1) !important; font-size: 28px !important; font-weight: 800 !important; }}
[data-testid="stMetricDelta"] div {{ font-size: 12px !important; }}

/* ── Alerts ── */
[data-testid="stAlert"] {{ border-radius: 10px !important; border-left-width: 3px !important; }}
.stInfo  {{ background: rgba(59,130,246,.08) !important; border-left-color: #3b82f6 !important; }}
.stSuccess {{ background: rgba(16,185,129,.08) !important; border-left-color: #10b981 !important; }}
.stWarning {{ background: rgba(245,158,11,.08) !important; border-left-color: #f59e0b !important; }}
.stError {{ background: rgba(239,68,68,.08) !important; border-left-color: #ef4444 !important; }}

/* ── Code ── */
pre, code {{
    background: var(--c-input) !important;
    color: var(--c-link) !important;
    border-radius: 8px !important;
    font-size: 12px !important;
}}
.stCode > div {{ border-radius: 10px !important; border: 1px solid var(--c-iborder) !important; }}

/* ── HR ── */
hr {{ border-color: var(--c-b1) !important; margin: 20px 0 !important; }}

/* ── Caption & small text ── */
.stCaption, small, .stCaption p {{ color: var(--c-t3) !important; font-size: 12px !important; }}

/* ── Markdown ── */
.stMarkdown p, .stMarkdown li {{ color: var(--c-t1b); line-height: 1.65; }}
.stMarkdown h3, .stMarkdown h4 {{ color: var(--c-t1); }}

/* ── Spinner ── */
.stSpinner > div {{ border-top-color: #E63946 !important; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: var(--c-bg); }}
::-webkit-scrollbar-thumb {{ background: var(--c-b2); border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--c-t3); }}

/* ── Download button ── */
.stDownloadButton > button {{
    background-color: var(--c-input) !important;
    color: var(--c-t1) !important;
    border: 1px solid var(--c-iborder) !important;
    border-radius: 8px !important;
}}

/* ── Responsive ── */
@media (max-width: 900px) {{
    .main .block-container {{ padding: 1rem 1rem 2rem !important; }}
    [data-testid="stHorizontalBlock"] > div {{ min-width: 48% !important; flex: 1 1 48% !important; }}
}}
@media (max-width: 600px) {{
    .main .block-container {{ padding: 0.5rem 0.5rem 1.5rem !important; }}
    [data-testid="stHorizontalBlock"] > div {{ min-width: 100% !important; flex: 1 1 100% !important; }}
}}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

APTORI_RED   = "#E63946"
APTORI_BLUE  = "#3b82f6"
APTORI_GREEN = "#10b981"

_BADGE_COLORS = {
    "active":         ("#10b981", "#10b98120"),
    "paused":         ("#6b7280", "#6b728020"),
    "draft":          ("#6b7280", "#6b728020"),
    "ready":          ("#3b82f6", "#3b82f620"),
    "copied":         ("#7c3aed", "#7c3aed20"),
    "posted":         ("#f59e0b", "#f59e0b20"),
    "verified_pass":  ("#10b981", "#10b98120"),
    "verified_fail":  ("#ef4444", "#ef444420"),
    "needs_rewrite":  ("#f97316", "#f9731620"),
    "pass":           ("#10b981", "#10b98120"),
    "fail":           ("#ef4444", "#ef444420"),
    "pending":        ("#f59e0b", "#f59e0b20"),
    "review":         ("#7c3aed", "#7c3aed20"),
    "live":           ("#10b981", "#10b98120"),
    "low":            ("#10b981", "#10b98120"),
    "medium":         ("#f59e0b", "#f59e0b20"),
    "high":           ("#ef4444", "#ef444420"),
    "banned":         ("#ef4444", "#ef444420"),
}

def badge(text: str, key: str = "") -> str:
    k   = (key or text).lower().replace(" ", "_")
    fg, bg = _BADGE_COLORS.get(k, ("#9ca3af", "#9ca3af20"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 10px;'
        f'border-radius:20px;font-size:11px;font-weight:700;'
        f'border:1px solid {fg}55;white-space:nowrap;letter-spacing:.02em">{text}</span>'
    )

def card(content: str, border_color: str = "var(--c-b1)", top_color: str = "", shadow: bool = True) -> str:
    top = f"border-top:3px solid {top_color};" if top_color else ""
    sh  = "box-shadow:0 2px 10px rgba(0,0,0,.14);" if shadow else ""
    return (
        f'<div style="background:var(--c-card);border:1px solid {border_color};'
        f'border-radius:14px;padding:20px 24px;margin-bottom:14px;{top}{sh}">'
        f'{content}</div>'
    )

def metric_card(label: str, value, sub: str = "", color: str = APTORI_RED) -> str:
    return (
        f'<div style="background:var(--c-card);border:1px solid var(--c-b1);'
        f'border-top:3px solid {color};border-radius:14px;padding:18px 20px;'
        f'box-shadow:0 2px 10px rgba(0,0,0,.12);height:100%">'
        f'<div style="color:var(--c-t3);font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:8px">{label}</div>'
        f'<div style="color:var(--c-t1);font-size:28px;font-weight:800;line-height:1;margin-bottom:4px">{value}</div>'
        f'<div style="color:var(--c-t3);font-size:12px">{sub}</div>'
        f'</div>'
    )

def section_header(title: str, subtitle: str = "") -> str:
    sub_html = f'<div style="color:var(--c-t3);font-size:13px;margin-top:4px">{subtitle}</div>' if subtitle else ""
    return (
        f'<div style="margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--c-b1)">'
        f'<h1 style="color:var(--c-t1);font-size:26px;font-weight:800;margin:0;letter-spacing:-.5px">{title}</h1>'
        f'{sub_html}</div>'
    )

def info_row(label: str, value: str, value_color: str = "var(--c-t1)") -> str:
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:8px 0;border-bottom:1px solid var(--c-b1)">'
        f'<span style="color:var(--c-t3);font-size:12px">{label}</span>'
        f'<span style="color:{value_color};font-size:13px;font-weight:600">{value}</span>'
        f'</div>'
    )

def intent_score(post: dict) -> int:
    s = min(post.get("score", 0) / 300.0, 1.0) * 35
    c = min(post.get("num_comments", 0) / 80.0, 1.0) * 35
    e = post.get("engagement_score", 0.5) * 30
    return min(max(int(s + c + e), 10), 99)

def comment_quality(comment: dict) -> int:
    body  = comment.get("body", "")
    lscore = min(len(body) / 300.0, 1.0) * 40
    terms  = ["api","security","vulnerability","auth","test","endpoint","token","owasp"]
    tscore = min(sum(1 for t in terms if t in body.lower()) / 3.0, 1.0) * 40
    return min(int(20 + lscore + tscore), 99)

def status_label(s: str) -> str:
    return {
        "draft": "Draft", "ready": "Ready", "copied": "Copied",
        "posted": "Posted", "verified_pass": "Live",
        "verified_fail": "Not Found", "needs_rewrite": "Needs Rewrite",
    }.get(s, s.title())

def parse_credits(info: str) -> str:
    m = re.search(r"([\d,]+)\s+credits", info)
    return m.group(1).replace(",", "") if m else "—"

def ts_ago(iso: str) -> str:
    if not iso:
        return "never"
    try:
        dt   = datetime.fromisoformat(iso)
        diff = datetime.utcnow() - dt
        h    = int(diff.total_seconds() // 3600)
        if h < 1:    return f"{int(diff.total_seconds()//60)}m ago"
        if h < 24:   return f"{h}h ago"
        return f"{h//24}d ago"
    except Exception:
        return iso[:10]

# ── Aptori brand prompts ──────────────────────────────────────────────────────
APTORI_IMG_PROMPTS = [
    "Professional illustration for Aptori, AI-native API security platform, sleek dark blue and electric purple tones, glowing security shield with AI circuit patterns, enterprise software aesthetic",
    "Aptori autonomous API security testing, cinematic dramatic lighting, abstract code flows morphing into shield icons, deep navy background, electric blue accent lines, photorealistic 3D render",
    "Aptori catching API vulnerabilities in real-time, hacker terminal on left, Aptori dashboard on right, split editorial style, professional tech illustration",
    "Aptori DevSecOps integration, modern flat illustration, CI/CD pipeline with Aptori blocking threats before production, corporate pitch-deck quality, muted blues and whites",
]
APTORI_VID_PROMPTS = [
    "Cinematic slow zoom into Aptori dashboard glowing with live security alerts, teal and purple light trails, professional product demo atmosphere",
    "Time-lapse API traffic patterns morphing into security graphs, dark moody background, Aptori logo appears, tech commercial style",
]

# ── Comment generation helpers ────────────────────────────────────────────────

def _make_rate_manager() -> RateLimitManager:
    return (
        RateLimitManager()
        .register("reddit",    requests_per_minute=6,  burst_size=1)
        .register("anthropic", requests_per_minute=45, burst_size=5)
    )

def fetch_post_from_url(url: str) -> dict:
    """Fetch a Reddit post via the public JSON API (no auth needed)."""
    clean = url.strip().rstrip("/")
    if "?" in clean:
        clean = clean[:clean.index("?")]
    if not clean.endswith(".json"):
        clean += ".json"
    resp = _requests.get(
        clean,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AptoriBot/1.0)"},
        timeout=12,
    )
    resp.raise_for_status()
    listing = resp.json()
    pd = listing[0]["data"]["children"][0]["data"]
    permalink = f"https://www.reddit.com{pd['permalink']}"
    return {
        "id":           pd["id"],
        "title":        pd.get("title", ""),
        "selftext":     pd.get("selftext", ""),
        "subreddit":    pd.get("subreddit", ""),
        "score":        pd.get("score", 0),
        "num_comments": pd.get("num_comments", 0),
        "upvote_ratio": pd.get("upvote_ratio", 0.9),
        "permalink":    permalink,
        "author":       str(pd.get("author", "[unknown]")),
        "created_utc":  pd.get("created_utc", time.time()),
        "keyword":      "",
    }

def generate_comment_for_post(post_dict: dict) -> dict | None:
    """Call Claude to generate a humanized comment for a post dict."""
    post_obj = RedditPost(
        id           = post_dict["id"],
        title        = post_dict["title"],
        selftext     = post_dict.get("selftext", ""),
        url          = post_dict["permalink"],
        subreddit    = post_dict["subreddit"],
        score        = post_dict.get("score", 0),
        num_comments = post_dict.get("num_comments", 0),
        upvote_ratio = post_dict.get("upvote_ratio", 0.9),
        created_utc  = post_dict.get("created_utc", time.time()),
        permalink    = post_dict["permalink"],
        author       = post_dict.get("author", "[unknown]"),
        keyword      = post_dict.get("keyword", scraper_cfg.domain),
    )
    rm  = _make_rate_manager()
    gen = ClaudeCommentGenerator(anthropic_cfg, rm)
    return gen.generate_comment(post_obj, scraper_cfg.domain, scraper_cfg.your_expertise)

# ── Data load ─────────────────────────────────────────────────────────────────
data       = get_all()
insights   = get_insights()
kw_data    = init_keywords_data()
accounts   = get_accounts()
all_posts  = data.get("posts", [])

hf         = HiggsFieldClient()
hf_auth    = hf.auth_status()
hf_ready   = hf_auth.get("authenticated", False)
hf_info    = hf_auth.get("info", "")
hf_credits = parse_credits(hf_info)

# Compute pipeline counts
comments_all   = data.get("comments", [])
pending_cmts   = [c for c in comments_all if not c.get("posted")]
posted_cmts    = [c for c in comments_all if c.get("posted")]
verified_pass  = [c for c in comments_all if c.get("verification_status") == "pass"]
verified_fail  = [c for c in comments_all if c.get("verification_status") == "fail"]
high_intent    = [p for p in insights if intent_score(p) >= 60]

# ── Sidebar ───────────────────────────────────────────────────────────────────
NAV_ITEMS = [
    "Dashboard",
    "Keyword Monitor",
    "Post Discovery",
    "Comment Studio",
    "Content Studio",
    "Higgsfield Credits",
    "Accounts Manager",
    "Settings",
]

with st.sidebar:
    # Brand header
    st.markdown(
        '<div style="padding:20px 16px 16px">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">'
        '<div style="width:32px;height:32px;background:linear-gradient(135deg,#E63946,#c62333);'
        'border-radius:8px;display:flex;align-items:center;justify-content:center;'
        'color:#fff;font-size:16px;font-weight:900">A</div>'
        '<div>'
        '<div style="color:#E63946;font-size:16px;font-weight:800;letter-spacing:-.3px;line-height:1">Aptori Bot</div>'
        '<div style="color:var(--c-t3);font-size:10px;letter-spacing:.04em">Reddit Engagement Console</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr style="margin:0 0 8px;border-color:var(--c-b1)">', unsafe_allow_html=True)

    page = st.radio(
        "nav", NAV_ITEMS,
        label_visibility="collapsed",
        key="sidebar_nav",
    )

    st.markdown('<hr style="margin:8px 0;border-color:var(--c-b1)">', unsafe_allow_html=True)

    # Status section
    st.markdown(
        f'<div style="padding:0 4px">'
        f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px">Pipeline</div>'
        f'<div style="display:flex;flex-direction:column;gap:6px">'
        + info_row("Posts scraped", str(len(insights)))
        + info_row("Comments ready", str(len(pending_cmts)), "#3b82f6")
        + info_row("Posted", str(len(posted_cmts)), "#10b981")
        + info_row("Verified live", str(len(verified_pass)), "#10b981")
        + f'</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr style="margin:10px 0;border-color:var(--c-b1)">', unsafe_allow_html=True)

    # Credits section
    st.markdown(
        f'<div style="padding:0 4px">'
        f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Higgsfield</div>'
        f'<div style="color:var(--c-t1);font-size:24px;font-weight:800;line-height:1">{hf_credits}'
        f'<span style="color:var(--c-t3);font-size:12px;font-weight:400"> credits</span></div>'
        f'<div style="color:var(--c-t3);font-size:11px;margin-top:2px">{hf.credits_used_total()} used this session</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr style="margin:10px 0;border-color:var(--c-b1)">', unsafe_allow_html=True)

    if st.button("Refresh Data", use_container_width=True):
        st.rerun()

# =============================================================================
# PAGE 1 — DASHBOARD (OVERVIEW)
# =============================================================================
if page == "Dashboard":
    st.markdown(section_header("Dashboard", "Aptori Reddit Engagement Intelligence — overview of your engagement pipeline"), unsafe_allow_html=True)

    # KPI cards
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Posts Found",       len(insights),      f"{len(high_intent)} high-intent"), unsafe_allow_html=True)
    c2.markdown(metric_card("Comments Ready",    len(pending_cmts),  "awaiting manual post",  "#7c3aed"), unsafe_allow_html=True)
    c3.markdown(metric_card("Manually Posted",   len(posted_cmts),   f"{len(verified_pass)} verified live", "#10b981"), unsafe_allow_html=True)
    c4.markdown(metric_card("Credits Used",      hf.credits_used_total(), f"{hf_credits} remaining", "#f59e0b"), unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5.markdown(metric_card("High-Intent Threads", len(high_intent),   "score >= 60%",     "#3b82f6"), unsafe_allow_html=True)
    c6.markdown(metric_card("Pending Review",      len(pending_cmts),  "needs posting",    "#f97316"), unsafe_allow_html=True)
    c7.markdown(metric_card("Verified Pass",       len(verified_pass), "confirmed live",   "#10b981"), unsafe_allow_html=True)
    c8.markdown(metric_card("Verified Fail",       len(verified_fail), "not found",        "#ef4444"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Pipeline
    disc   = len(insights)
    qual   = len(high_intent)
    gen    = len(comments_all)
    rev    = len(pending_cmts)
    post   = len(posted_cmts)
    ver    = len(verified_pass)

    st.markdown(
        '<div style="background:var(--c-row);border:1px solid var(--c-b1);border-radius:12px;padding:20px 24px;margin-bottom:20px">'
        '<div style="color:var(--c-t2);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px">Engagement Pipeline</div>'
        '<div style="display:flex;align-items:center;gap:0;flex-wrap:wrap">'
        + "".join([
            f'<div style="flex:1;text-align:center;padding:12px 8px;background:var(--c-card);border-radius:10px;margin:2px">'
            f'<div style="color:var(--c-t1);font-size:22px;font-weight:800">{n}</div>'
            f'<div style="color:var(--c-t2);font-size:11px;margin-top:4px">{lbl}</div></div>'
            f'{"" if i == 5 else "<div style=color:#475569;font-size:20px;padding:0 4px>›</div>"}'
            for i, (n, lbl) in enumerate([
                (disc,"Discovered"),(qual,"Qualified"),(gen,"Generated"),
                (rev,"In Review"),(post,"Posted"),(ver,"Verified"),
            ])
        ])
        + '</div></div>',
        unsafe_allow_html=True,
    )

    # Today's recommended threads
    th1, th2, th3 = st.columns([3, 2, 2])
    th1.markdown('<h3 style="color:var(--c-t1);font-weight:700;margin:0">Today\'s Recommended Threads</h3>', unsafe_allow_html=True)
    dash_timeline = th2.selectbox(
        "Timeline", ["Last 24 hours", "Last 6 hours", "Last 3 days", "All time"],
        index=0, key="dash_timeline", label_visibility="collapsed",
    )
    dash_fetch = th3.button("Fetch New Posts", key="dash_fetch", use_container_width=True)
    if dash_fetch:
        with st.spinner("Fetching fresh posts..."):
            try:
                r = subprocess.run(["python", "run_daily.py"], cwd=str(Path.cwd()),
                                   capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    st.success("Done!")
                    st.rerun()
                else:
                    st.error(f"Scraper error:\n{r.stderr[-400:]}")
            except Exception as e:
                st.error(str(e))

    dash_age_map = {"Last 6 hours": 6, "Last 24 hours": 24, "Last 3 days": 72, "All time": 99999}
    dash_max_h = dash_age_map.get(dash_timeline, 24)
    _now = datetime.utcnow()
    def _dash_age(p):
        try:
            return (_now - datetime.fromisoformat(p.get("scraped_at","").rstrip("Z"))).total_seconds()/3600
        except Exception:
            return 99999
    top_posts = sorted(
        [p for p in insights if _dash_age(p) <= dash_max_h],
        key=intent_score, reverse=True
    )[:6]

    st.markdown("<br>", unsafe_allow_html=True)
    if not top_posts:
        st.info("No posts in this time window — click **Fetch New Posts** or widen the timeline.")
    else:
        for i in range(0, len(top_posts), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j >= len(top_posts):
                    break
                p   = top_posts[i + j]
                isc = intent_score(p)
                color = "#10b981" if isc >= 75 else "#f59e0b" if isc >= 50 else "#6b7280"
                has_comment = any(c.get("post_id") == p.get("id") for c in comments_all)
                with col:
                    st.markdown(
                        f'<div style="background:var(--c-row);border:1px solid var(--c-b1);border-left:3px solid {color};'
                        f'border-radius:10px;padding:16px;margin-bottom:12px">'
                        f'<div style="color:var(--c-t2);font-size:11px">r/{p.get("subreddit","")} · {badge("Aptori match","active")}</div>'
                        f'<div style="color:var(--c-t1);font-weight:600;font-size:14px;margin:8px 0 4px;line-height:1.4">{p.get("title","")[:70]}</div>'
                        f'<div style="display:flex;gap:12px;color:var(--c-t2);font-size:12px;margin-bottom:10px">'
                        f'<span>↑ {p.get("score",0)}</span><span>💬 {p.get("num_comments",0)}</span>'
                        f'<span>Intent: <b style="color:{color}">{isc}%</b></span></div>'
                        f'<div style="display:flex;gap:8px;align-items:center">'
                        f'{"" + badge("Reply Ready","ready") if has_comment else badge("No Reply","draft")}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                    c_a, c_b = col.columns(2)
                    if c_a.button("Open Reddit", key=f"dash_open_{i+j}", use_container_width=True):
                        st.markdown(f'<script>window.open("{p.get("permalink","#")}")</script>', unsafe_allow_html=True)
                    if c_b.button("Comment Studio", key=f"dash_studio_{i+j}", use_container_width=True):
                        st.session_state["sidebar_nav"] = "Comment Studio"
                        st.session_state["studio_post_id"] = p.get("id", "")
                        st.rerun()

# =============================================================================
# PAGE 2 — KEYWORD MONITOR
# =============================================================================
elif page == "Keyword Monitor":
    st.markdown(section_header("Keyword Monitor", "Track and manage keywords used to discover relevant Reddit posts"), unsafe_allow_html=True)

    # Add keyword
    with st.expander("+ Add Keyword", expanded=False):
        new_kw = st.text_input("New keyword", placeholder="e.g. API security testing", key="new_kw_input")
        if st.button("Add", key="add_kw_btn", type="primary"):
            if new_kw.strip():
                kd = get_keywords_data()
                if not any(k["keyword"].lower() == new_kw.strip().lower() for k in kd):
                    kd.append({"keyword": new_kw.strip(), "status": "active",
                               "posts_found": 0, "quality_score": 0, "last_scan": ""})
                    save_keywords_data(kd)
                    # Also append to keywords.txt
                    kw_file = Path("keywords.txt")
                    with open(kw_file, "a", encoding="utf-8") as f:
                        f.write(f"\n{new_kw.strip()}")
                    st.success(f"Added: {new_kw.strip()}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Keyword already exists.")

    # Compute posts-per-keyword from insights
    kw_counts: dict = {}
    for ins in insights:
        kw = ins.get("keyword", "")
        kw_counts[kw] = kw_counts.get(kw, 0) + 1

    kw_data_fresh = get_keywords_data()

    # Update posts_found from live data
    for kd in kw_data_fresh:
        kd["posts_found"] = kw_counts.get(kd["keyword"], kd.get("posts_found", 0))

    st.markdown(
        '<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 1fr;'
        'gap:0;background:var(--c-card);border:1px solid var(--c-b2);border-radius:10px;overflow:hidden;margin-bottom:4px">'
        + "".join(
            f'<div style="padding:10px 14px;color:var(--c-t2);font-size:11px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.07em;border-bottom:1px solid #2d3748">{h}</div>'
            for h in ["Keyword", "Status", "Posts Found", "Quality Score", "Last Scan", "Actions"]
        )
        + '</div>',
        unsafe_allow_html=True,
    )

    for idx, kd in enumerate(kw_data_fresh):
        kw    = kd.get("keyword", "")
        st_   = kd.get("status", "active")
        pf    = kd.get("posts_found", 0)
        qs    = kd.get("quality_score", 0)
        ls    = ts_ago(kd.get("last_scan", ""))
        b_clr = "#10b981" if st_ == "active" else "#6b7280"

        col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 1])
        col1.markdown(f'<div style="color:var(--c-t1);font-size:13px;padding:8px 0">{kw}</div>', unsafe_allow_html=True)
        col2.markdown(badge(st_.title(), st_), unsafe_allow_html=True)
        col3.markdown(f'<div style="color:var(--c-t1);font-size:13px;padding:8px 0">{pf}</div>', unsafe_allow_html=True)
        col4.markdown(f'<div style="color:var(--c-t1);font-size:13px;padding:8px 0">{qs}%</div>' if qs else '<div style="color:var(--c-t3);font-size:13px;padding:8px 0">—</div>', unsafe_allow_html=True)
        col5.markdown(f'<div style="color:var(--c-t2);font-size:12px;padding:8px 0">{ls}</div>', unsafe_allow_html=True)
        with col6:
            toggle = "Pause" if st_ == "active" else "Resume"
            if st.button(toggle, key=f"kw_tog_{idx}", use_container_width=True):
                new_st = "paused" if st_ == "active" else "active"
                kw_data_fresh[idx]["status"] = new_st
                save_keywords_data(kw_data_fresh)
                st.rerun()
        st.markdown('<hr style="margin:4px 0;border-color:#1e2d45">', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Scan Now (background)", type="primary", use_container_width=True):
            subprocess.Popen(["python", "run_daily.py"], cwd=str(Path.cwd()))
            st.success("Scan started in background. Refresh in ~2 minutes.")
    with c2:
        if st.button("Export Keywords CSV", use_container_width=True):
            csv = "keyword,status,posts_found,quality_score,last_scan\n"
            csv += "\n".join(
                f'"{k["keyword"]}",{k["status"]},{k.get("posts_found",0)},{k.get("quality_score",0)},{k.get("last_scan","")}'
                for k in kw_data_fresh
            )
            st.download_button("Download CSV", csv, "keywords.csv", "text/csv", key="kw_csv")

# =============================================================================
# PAGE 3 — POST DISCOVERY
# =============================================================================
elif page == "Post Discovery":
    st.markdown(section_header("Post Discovery", "Fresh Reddit posts discovered by keyword — fetch new posts, review, send to Comment Studio"), unsafe_allow_html=True)

    # ── Toolbar ──────────────────────────────────────────────────────────────
    tb1, tb2, tb3 = st.columns([2, 2, 4])
    run_discovery = tb1.button("Fetch Fresh Posts Now", type="primary", use_container_width=True, key="pd_run")
    age_filter    = tb2.selectbox(
        "Age", ["Last 6 hours", "Last 24 hours", "Last 3 days", "All time"],
        index=1, key="pd_age", label_visibility="collapsed",
    )

    if run_discovery:
        with st.spinner("Fetching fresh posts from Reddit with all keywords — takes ~2 min..."):
            try:
                result = subprocess.run(
                    ["python", "run_daily.py"],
                    cwd=str(Path.cwd()),
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0:
                    st.success("Done! Scroll down to see fresh posts.")
                    st.rerun()
                else:
                    st.error(f"Scraper error:\n{result.stderr[-600:]}")
            except subprocess.TimeoutExpired:
                st.error("Timed out — Reddit may be rate-limiting. Try again in a few minutes.")
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Filter by age ─────────────────────────────────────────────────────────
    age_hours_map = {"Last 6 hours": 6, "Last 24 hours": 24, "Last 3 days": 72, "All time": 99999}
    max_hours = age_hours_map.get(age_filter, 24)
    now_utc = datetime.utcnow()

    def _post_age_h(p):
        ts = p.get("scraped_at", "")
        if not ts:
            return 99999
        try:
            dt = datetime.fromisoformat(ts.rstrip("Z"))
            return (now_utc - dt).total_seconds() / 3600
        except Exception:
            return 99999

    fresh = [p for p in insights if _post_age_h(p) <= max_hours]
    fresh = sorted(fresh, key=lambda p: p.get("scraped_at", ""), reverse=True)

    # ── Keyword filter ────────────────────────────────────────────────────────
    kws_present = sorted({p.get("keyword", "") for p in fresh if p.get("keyword")})
    if kws_present:
        sel_kw_pd = st.selectbox("Filter by keyword", ["All keywords"] + kws_present, key="pd_kw")
        if sel_kw_pd != "All keywords":
            fresh = [p for p in fresh if p.get("keyword") == sel_kw_pd]

    # ── Keyword coverage badges ───────────────────────────────────────────────
    if fresh:
        kw_counts: dict = {}
        for p in fresh:
            k = p.get("keyword", "—")
            kw_counts[k] = kw_counts.get(k, 0) + 1
        badges_html = " ".join(
            f'<span style="background:var(--c-b1);color:var(--c-link);font-size:11px;'
            f'font-weight:600;padding:3px 10px;border-radius:20px">'
            f'{kw} <span style="color:var(--c-t3)">({n})</span></span>'
            for kw, n in sorted(kw_counts.items(), key=lambda x: -x[1])
        )
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 4px">{badges_html}</div>',
            unsafe_allow_html=True,
        )

    commented_ids_pd = {c.get("post_id") for c in comments_all}
    st.caption(f"{len(fresh)} fresh posts")

    if not fresh:
        st.markdown(
            '<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:14px;'
            'padding:48px;text-align:center;margin-top:20px">'
            '<div style="font-size:36px;margin-bottom:12px">🔍</div>'
            '<div style="color:var(--c-t1);font-size:16px;font-weight:600;margin-bottom:8px">No fresh posts yet</div>'
            '<div style="color:var(--c-t3);font-size:13px">Click <b>Fetch Fresh Posts Now</b> above to search Reddit using all your keywords.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for p in fresh:
            pid       = p.get("id", "")
            has_cmt   = pid in commented_ids_pd
            kw        = p.get("keyword", "")
            sub       = p.get("subreddit", "")
            link      = p.get("permalink", "#")
            full_url  = link if link.startswith("http") else f"https://reddit.com{link}"
            ts_raw    = p.get("scraped_at", "")
            try:
                age_h = _post_age_h(p)
                age_label = f"{int(age_h)}h ago" if age_h < 48 else f"{int(age_h/24)}d ago"
            except Exception:
                age_label = ""

            cmt_ready_badge = (
                '<span style="background:#10b98122;color:#10b981;font-size:10px;'
                'padding:2px 8px;border-radius:4px;font-weight:600">Comment Ready</span>'
            ) if has_cmt else ""
            selftext_snippet = (
                f'<div style="color:var(--c-t3);font-size:12px;margin-top:6px;line-height:1.5">'
                f'{p["selftext"][:160]}...</div>'
            ) if p.get("selftext") else ""
            st.markdown(
                f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:12px;'
                f'padding:16px 20px;margin-bottom:12px">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">'
                f'<div style="flex:1;min-width:0">'
                f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px">'
                f'<span style="color:var(--c-link);font-size:12px;font-weight:600">r/{sub}</span>'
                f'<span style="color:var(--c-t3);font-size:11px">↑ {p.get("score",0)}</span>'
                f'<span style="color:var(--c-t3);font-size:11px">💬 {p.get("num_comments",0)}</span>'
                f'<span style="background:var(--c-b1);color:var(--c-t2);font-size:10px;padding:2px 7px;border-radius:4px">{kw}</span>'
                f'<span style="color:var(--c-t3);font-size:10px">{age_label}</span>'
                f'{cmt_ready_badge}'
                f'</div>'
                f'<div style="color:var(--c-t1);font-size:14px;font-weight:600;line-height:1.4">{p.get("title","")}</div>'
                f'{selftext_snippet}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            ba1, ba2 = st.columns([1, 5])
            ba1.markdown(
                f'<a href="{full_url}" target="_blank" style="display:block;background:#E63946;color:#fff;'
                f'padding:7px 14px;border-radius:8px;font-size:12px;font-weight:600;text-decoration:none;text-align:center">Open Reddit</a>',
                unsafe_allow_html=True,
            )
            if ba2.button("Send to Comment Studio", key=f"pd_studio_{pid}", use_container_width=False):
                st.session_state["sidebar_nav"] = "Comment Studio"
                st.session_state["studio_post_id"] = pid
                st.rerun()
            st.markdown('<hr style="border-color:var(--c-b1);margin:4px 0 8px">', unsafe_allow_html=True)

# =============================================================================
# PAGE 5 — COMMENT STUDIO
# =============================================================================
elif page == "Comment Studio":
    st.markdown(section_header("Comment Studio", "Top scraped posts with Claude-generated humanized comments — copy, post, confirm."), unsafe_allow_html=True)

    # ── Toolbar ──────────────────────────────────────────────────────────────
    tb1, tb2, tb3 = st.columns([2, 2, 4])
    run_scraper = tb1.button("Fetch 10 Fresh Posts", type="primary", use_container_width=True, key="cs_run_scraper")
    show_filter = tb2.selectbox("Filter", ["All", "Not Posted", "Posted", "Pass", "Fail"], key="cs_filter", label_visibility="collapsed")

    if run_scraper:
        with st.spinner("Scraping Reddit and generating comments with Claude — this takes ~2 minutes..."):
            try:
                result = subprocess.run(
                    ["python", "run_daily.py"],
                    cwd=str(Path.cwd()),
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode == 0:
                    st.success("Done! Scroll down to see your 10 fresh posts.")
                    st.rerun()
                else:
                    st.error(f"Scraper error:\n{result.stderr[-800:]}")
            except subprocess.TimeoutExpired:
                st.error("Timed out after 5 minutes. Reddit may be rate-limiting — try again in a few minutes.")
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Load data ─────────────────────────────────────────────────────────────
    data_cs      = get_all()
    insight_map  = {p.get("id",""): p for p in insights}

    # Build unified post list: comments are the source of truth
    # Each comment entry is one card (most recent comment per post_id)
    seen_pids = set()
    cs_items  = []
    for c in reversed(data_cs.get("comments", [])):
        pid = c.get("post_id","")
        if not pid or pid in seen_pids:
            continue
        seen_pids.add(pid)
        post_info = insight_map.get(pid, {})
        cs_items.append({
            "post_id":    pid,
            "title":      c.get("post_title","") or post_info.get("title","(no title)"),
            "subreddit":  c.get("subreddit","")  or post_info.get("subreddit",""),
            "permalink":  c.get("permalink","")  or post_info.get("permalink",""),
            "score":      post_info.get("score", 0),
            "num_comments": post_info.get("num_comments", 0),
            "keyword":    c.get("keyword",""),
            "comment":    c.get("comment",""),
            "tone":       c.get("tone",""),
            "generated_at": c.get("generated_at",""),
            "posted":     c.get("posted", False),
            "comment_status": c.get("comment_status","draft"),
            "verification_status": c.get("verification_status","pending"),
        })

    # Apply filter
    if show_filter == "Not Posted":
        cs_items = [x for x in cs_items if not x["posted"]]
    elif show_filter == "Posted":
        cs_items = [x for x in cs_items if x["posted"]]
    elif show_filter == "Pass":
        cs_items = [x for x in cs_items if x["verification_status"] == "pass"]
    elif show_filter == "Fail":
        cs_items = [x for x in cs_items if x["verification_status"] == "fail"]

    if not cs_items:
        st.markdown(
            '<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:14px;'
            'padding:48px;text-align:center;margin-top:20px">'
            '<div style="font-size:40px;margin-bottom:12px">📭</div>'
            '<div style="color:var(--c-t1);font-size:16px;font-weight:600;margin-bottom:8px">No posts yet</div>'
            '<div style="color:var(--c-t3);font-size:13px">Click <b>Fetch 10 Fresh Posts</b> above to scrape Reddit and generate humanized comments.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div style="color:var(--c-t3);font-size:12px;margin-bottom:16px">{len(cs_items)} post{"s" if len(cs_items)!=1 else ""}</div>', unsafe_allow_html=True)

        for idx, item in enumerate(cs_items):
            pid      = item["post_id"]
            cmt_text = item["comment"]
            posted   = item["posted"]
            vst      = item["verification_status"]
            cst      = item["comment_status"]
            tone     = item["tone"]
            full_url = item["permalink"] if item["permalink"].startswith("http") else f"https://reddit.com{item['permalink']}"

            # Pre-compute snippets to avoid nested f-strings
            tone_badge = (
                f'<span style="background:#1e3050;color:#93c5fd;font-size:10px;font-weight:600;'
                f'padding:2px 8px;border-radius:20px">{tone.title()}</span>'
            ) if tone else ""

            # Status colors
            vst_color = "#10b981" if vst == "pass" else "#ef4444" if vst == "fail" else "#6b7280"
            vst_label = "PASS" if vst == "pass" else "FAIL" if vst == "fail" else "PENDING"
            posted_color = "#10b981" if posted else "#6b7280"

            st.markdown(
                f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:16px;'
                f'margin-bottom:20px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.12)">'

                # ── Post header ──
                f'<div style="padding:16px 20px;border-bottom:1px solid var(--c-b1);'
                f'display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">'
                f'<div style="flex:1;min-width:0">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">'
                f'<span style="background:var(--c-b1);color:var(--c-t2);font-size:10px;font-weight:700;'
                f'padding:2px 8px;border-radius:4px">#{idx+1}</span>'
                f'<span style="color:var(--c-t2);font-size:12px">r/{item["subreddit"]}</span>'
                f'<span style="color:var(--c-t3);font-size:11px">↑ {item["score"]}</span>'
                f'<span style="color:var(--c-t3);font-size:11px">💬 {item["num_comments"]}</span>'
                f'{tone_badge}'
                f'</div>'
                f'<div style="color:var(--c-t1);font-size:14px;font-weight:700;line-height:1.4">{item["title"]}</div>'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:8px;flex-shrink:0;flex-wrap:wrap">'
                f'<span style="color:{posted_color};font-size:11px;font-weight:700">{"● POSTED" if posted else "○ NOT POSTED"}</span>'
                f'<span style="background:{vst_color}22;color:{vst_color};font-size:11px;font-weight:700;'
                f'padding:3px 10px;border-radius:20px">{vst_label}</span>'
                f'<a href="{full_url}" target="_blank" style="background:#E63946;color:#fff;padding:6px 14px;'
                f'border-radius:8px;font-size:12px;font-weight:600;text-decoration:none">Open Reddit</a>'
                f'</div>'
                f'</div>'

                # ── Comment body ──
                f'<div style="padding:16px 20px;border-bottom:1px solid var(--c-b1)">'
                f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.1em;margin-bottom:10px">Claude-Generated Comment</div>'
                f'<div style="background:var(--c-row);border-radius:10px;padding:14px 16px;'
                f'font-size:13px;line-height:1.75;color:var(--c-t1b);white-space:pre-wrap">{cmt_text}</div>'
                f'<div style="color:var(--c-t3);font-size:11px;margin-top:8px">'
                f'{len(cmt_text)} chars · {len(cmt_text.split())} words</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Action buttons ──
            b1, b2, b3, b4, b5, b6 = st.columns([2, 2, 1, 1, 2, 1])

            if b1.button("Copy Comment", key=f"cs_copy_{pid}", type="primary", use_container_width=True):
                update_comment_by_post_id(pid, {"comment_status": "copied"})
                st.code(cmt_text, language=None)

            if b2.button("Mark as Posted", key=f"cs_post_{pid}", use_container_width=True):
                update_comment_by_post_id(pid, {"posted": True, "comment_status": "posted"})
                st.success("Marked as posted!")
                st.rerun()

            if b3.button("Pass", key=f"cs_pass_{pid}", use_container_width=True):
                update_comment_by_post_id(pid, {
                    "verification_status": "pass",
                    "verified_at": datetime.utcnow().isoformat(),
                })
                st.rerun()

            if b4.button("Fail", key=f"cs_fail_{pid}", use_container_width=True):
                update_comment_by_post_id(pid, {
                    "verification_status": "fail",
                    "verified_at": datetime.utcnow().isoformat(),
                })
                st.rerun()

            if b5.button("Regenerate", key=f"cs_regen_{pid}", use_container_width=True):
                post_for_regen = insight_map.get(pid, {
                    "id": pid, "title": item["title"], "selftext": "",
                    "permalink": item["permalink"], "subreddit": item["subreddit"],
                    "score": item["score"], "num_comments": item["num_comments"],
                    "upvote_ratio": 0.9, "created_utc": time.time(),
                    "author": "", "keyword": item["keyword"],
                })
                with st.spinner("Regenerating..."):
                    try:
                        new_sug = generate_comment_for_post(post_for_regen)
                        if new_sug:
                            update_comment_by_post_id(pid, {
                                "comment": new_sug.get("comment",""),
                                "tone": new_sug.get("tone",""),
                                "verification_status": "pending",
                            })
                            st.success("Regenerated!")
                            st.rerun()
                        else:
                            st.error("Claude returned nothing — check ANTHROPIC_API_KEY in .env")
                    except Exception as e:
                        st.error(f"Error: {e}")

            if b6.button("Remove", key=f"cs_remove_{pid}", use_container_width=True,
                         help="Delete this comment — frees slot for a new post"):
                delete_comment_by_post_id(pid)
                st.rerun()

# =============================================================================
# PAGE 6 — CONTENT STUDIO (HIGGSFIELD)
# =============================================================================
elif page == "Content Studio":
    st.markdown(section_header("Content Studio", "Generate Reddit-ready post images and videos with Higgsfield AI"), unsafe_allow_html=True)

    # ── Auth status bar ──────────────────────────────────────────────────────
    if not hf_ready:
        st.warning("Not authenticated with Higgsfield CLI. Run `higgsfield auth login` in your terminal, then refresh this page.")
        st.code("higgsfield auth login", language="bash")
    else:
        st.markdown(
            f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:12px;'
            f'padding:12px 18px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between">'
            f'<div style="display:flex;align-items:center;gap:12px">'
            f'<span style="width:8px;height:8px;background:#10b981;border-radius:50%;display:inline-block;box-shadow:0 0 6px #10b981"></span>'
            f'<span style="color:var(--c-t1);font-size:13px;font-weight:600">Higgsfield CLI Authenticated</span>'
            f'<span style="color:var(--c-t2);font-size:12px">{hf_info}</span>'
            f'</div>'
            f'<div style="color:var(--c-t3);font-size:12px">{hf_credits} credits available</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── KPI row ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(metric_card("Credits Available",  hf_credits or "—",             "ultra plan",        "#10b981"), unsafe_allow_html=True)
    k2.markdown(metric_card("Used Today",         hf.credits_used_today(),       "resets midnight",   "#f59e0b"), unsafe_allow_html=True)
    k3.markdown(metric_card("Used Total",         hf.credits_used_total(),       "this session",      "#E63946"), unsafe_allow_html=True)
    k4.markdown(metric_card("Posts Generated",    len(hf.credit_history()),      "all time",          "#7c3aed"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_img, tab_vid, tab_ideas = st.tabs(["Post Image", "Post Video", "Content Ideas"])

    # =========================================================================
    # TAB 1 — POST IMAGE
    # =========================================================================
    with tab_img:
        st.markdown("<br>", unsafe_allow_html=True)
        main_col, side_col = st.columns([3, 1], gap="large")

        with main_col:
            # Model selector cards
            st.markdown(
                '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px">Choose Model</div>',
                unsafe_allow_html=True,
            )
            _img_model_keys = list(IMAGE_MODEL_META.keys())
            _img_cols = st.columns(len(_img_model_keys))
            _selected_img_model = st.session_state.get("cs_img_model_id", "flux_2")

            for _mi, (_mk, _mc) in enumerate(IMAGE_MODEL_META.items()):
                _is_sel = _selected_img_model == _mk
                _border = f"border:2px solid #E63946;" if _is_sel else f"border:1px solid var(--c-b1);"
                _bg     = "background:rgba(230,57,70,.08);" if _is_sel else "background:var(--c-card);"
                _img_cols[_mi].markdown(
                    f'<div style="{_bg}{_border}border-radius:12px;padding:14px;text-align:center;cursor:pointer;'
                    f'box-shadow:0 2px 8px rgba(0,0,0,.1)">'
                    f'<div style="background:{_mc["tag_color"]}22;color:{_mc["tag_color"]};font-size:10px;'
                    f'font-weight:700;padding:2px 8px;border-radius:20px;display:inline-block;margin-bottom:8px">{_mc["tag"]}</div>'
                    f'<div style="color:var(--c-t1);font-size:13px;font-weight:700;margin-bottom:4px">{_mc["name"]}</div>'
                    f'<div style="color:#f59e0b;font-size:18px;font-weight:800;margin-bottom:2px">{_mc["credits"]}</div>'
                    f'<div style="color:var(--c-t3);font-size:10px">credits · {_mc["speed"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if _img_cols[_mi].button(_mc["name"], key=f"sel_img_model_{_mk}", use_container_width=True):
                    st.session_state["cs_img_model_id"] = _mk
                    st.rerun()

            model_id  = st.session_state.get("cs_img_model_id", "flux_2")
            _meta     = IMAGE_MODEL_META.get(model_id, {})

            # Selected model info bar
            st.markdown(
                f'<div style="background:var(--c-row);border:1px solid var(--c-b1);border-radius:10px;'
                f'padding:12px 16px;margin:16px 0;display:flex;gap:24px;flex-wrap:wrap">'
                f'<span style="color:var(--c-t3);font-size:12px">Model: <b style="color:var(--c-t1)">{_meta.get("name","")}</b></span>'
                f'<span style="color:var(--c-t3);font-size:12px">Cost: <b style="color:#f59e0b">{_meta.get("credits",0)} credits</b></span>'
                f'<span style="color:var(--c-t3);font-size:12px">Speed: <b style="color:var(--c-t1b)">{_meta.get("speed","")}</b></span>'
                f'<span style="color:var(--c-t3);font-size:12px">Reddit: <b style="color:#10b981">{_meta.get("reddit_fit","")}</b></span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Reddit format presets
            st.markdown(
                '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Reddit Format Presets</div>',
                unsafe_allow_html=True,
            )
            _preset_names = list(REDDIT_POST_PRESETS.keys())
            _preset_cols  = st.columns(len(_preset_names))
            _sel_preset   = st.session_state.get("cs_img_preset", "")
            for _pi, _pname in enumerate(_preset_names):
                _pdata = REDDIT_POST_PRESETS[_pname]
                _is_draft = "Draft" in _pname
                _pbg = "background:var(--c-b1);" if _is_draft else "background:var(--c-card);"
                _preset_cols[_pi].markdown(
                    f'<div style="{_pbg}border:1px solid var(--c-b1);border-radius:8px;padding:8px 6px;text-align:center">'
                    f'<div style="color:var(--c-t1);font-size:11px;font-weight:600;margin-bottom:2px">{_pname}</div>'
                    f'<div style="color:var(--c-t3);font-size:10px">{_pdata["label"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if _preset_cols[_pi].button("Use", key=f"preset_img_{_pi}", use_container_width=True):
                    st.session_state["cs_img_preset"] = _pname
                    st.rerun()

            # Compute active preset values
            _active_preset = REDDIT_POST_PRESETS.get(st.session_state.get("cs_img_preset",""), {})
            _default_ar    = _active_preset.get("aspect_ratio", "16:9")
            _default_q     = _active_preset.get("quality", "2k")

            st.markdown("<br>", unsafe_allow_html=True)

            # Prompt
            st.markdown('<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Prompt</div>', unsafe_allow_html=True)
            quick = st.selectbox("Quick Aptori prompt", ["— write custom prompt —"] + APTORI_IMG_PROMPTS, key="cs_img_quick", label_visibility="collapsed")
            _prompt_default = "" if quick == "— write custom prompt —" else quick
            prompt = st.text_area(
                "Post image prompt",
                value=st.session_state.get("cs_img_prompt", _prompt_default) or _prompt_default,
                height=110,
                key="cs_img_prompt",
                placeholder="Describe your Reddit post image — be specific about style, subject, and mood…",
                label_visibility="collapsed",
            )

            # Format controls
            st.markdown("<br>", unsafe_allow_html=True)
            fc1, fc2, fc3 = st.columns([1, 1, 2])
            _ar_opts   = ["16:9","9:16","1:1","4:3","3:2"]
            aspect     = fc1.selectbox("Aspect ratio", _ar_opts,
                                       index=_ar_opts.index(_default_ar) if _default_ar in _ar_opts else 0,
                                       key="cs_img_ar")
            _q_opts    = _meta.get("quality_options", ["2k", "1.5k"])
            _q_labels  = _meta.get("quality_labels", {o: o for o in _q_opts})
            _q_default = _meta.get("quality_default", _q_opts[0])
            _q_display = [_q_labels.get(o, o) for o in _q_opts]
            _q_sel_lbl = fc2.selectbox("Quality / Resolution", _q_display, key="cs_img_q",
                                       help="Quality options vary per model. Lower = fewer credits, great for testing.")
            quality    = _q_opts[_q_display.index(_q_sel_lbl)]
            topic      = fc3.text_input("Topic tag (for your records)", "Aptori brand", key="cs_img_topic")

        with side_col:
            st.markdown("<br>", unsafe_allow_html=True)
            # Credit preview
            _est = _meta.get("credits", 0) if "_meta" in dir() else 0
            _rem = int(hf_credits or 0) - _est if hf_credits and str(hf_credits).isdigit() else "—"
            st.markdown(
                f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:14px;'
                f'padding:20px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-bottom:16px">'
                f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">After Generation</div>'
                f'<div style="color:#f59e0b;font-size:13px;margin-bottom:4px">Cost: {_est} credits</div>'
                f'<div style="color:var(--c-t1);font-size:28px;font-weight:800;margin:8px 0;line-height:1">{_rem}</div>'
                f'<div style="color:var(--c-t3);font-size:12px">credits remaining</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Quality guide
            st.markdown(
                '<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:14px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.1)">'
                '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Reddit Quality Guide</div>'
                + info_row("Square (1:1)", "Best engagement")
                + info_row("Landscape (16:9)", "Standard desktop")
                + info_row("Portrait (9:16)", "Mobile-first")
                + info_row("2k quality", "Publish-ready")
                + info_row("1.5k quality", "Drafts & testing")
                + '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        gen_col, _ = st.columns([2, 3])
        if gen_col.button("Generate Post Image", type="primary", disabled=not hf_ready, key="cs_gen_img", use_container_width=True):
            if not prompt.strip():
                st.error("Enter a prompt to generate a post image.")
            else:
                with st.spinner(f"Generating with {_meta.get('name','model')} — {_meta.get('speed','~45s')}…"):
                    res = hf.generate_image(prompt=prompt, model=model_id, aspect_ratio=aspect, quality=quality, topic=topic)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.success(f"Post image generated — {res['credits']} credits used.")
                    if res.get("url"):
                        st.markdown("<br>", unsafe_allow_html=True)
                        ri1, ri2 = st.columns([2, 1])
                        ri1.image(res["url"], caption=f"{aspect} · {quality} · {_meta.get('name','')}", use_container_width=True)
                        with ri2:
                            st.markdown(
                                f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:12px;padding:16px">'
                                f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Post Details</div>'
                                + info_row("Format", f"{aspect}")
                                + info_row("Quality", quality)
                                + info_row("Model", _meta.get("name",""))
                                + info_row("Credits used", str(res["credits"]))
                                + f'</div>',
                                unsafe_allow_html=True,
                            )
                            st.code(res["url"], language=None)
                            st.caption("Copy URL above to download/share this image.")
                    st.rerun()

    # =========================================================================
    # TAB 2 — POST VIDEO
    # =========================================================================
    with tab_vid:
        st.markdown("<br>", unsafe_allow_html=True)
        vid_main, vid_side = st.columns([3, 1], gap="large")

        with vid_main:
            # Video model cards
            st.markdown(
                '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px">Choose Model</div>',
                unsafe_allow_html=True,
            )
            _vid_model_keys = list(VIDEO_MODEL_META.keys())
            _vcols = st.columns(len(_vid_model_keys))
            _sel_vid_model = st.session_state.get("cs_vid_model_id", "kling3_0_turbo")

            for _vi, (_vk, _vc) in enumerate(VIDEO_MODEL_META.items()):
                _is_vsel = _sel_vid_model == _vk
                _vborder = f"border:2px solid #E63946;" if _is_vsel else f"border:1px solid var(--c-b1);"
                _vbg     = "background:rgba(230,57,70,.08);" if _is_vsel else "background:var(--c-card);"
                _vcols[_vi].markdown(
                    f'<div style="{_vbg}{_vborder}border-radius:12px;padding:12px 8px;text-align:center;'
                    f'box-shadow:0 2px 8px rgba(0,0,0,.1)">'
                    f'<div style="background:{_vc["tag_color"]}22;color:{_vc["tag_color"]};font-size:9px;'
                    f'font-weight:700;padding:2px 6px;border-radius:20px;display:inline-block;margin-bottom:6px">{_vc["tag"]}</div>'
                    f'<div style="color:var(--c-t1);font-size:12px;font-weight:700;margin-bottom:3px">{_vc["name"]}</div>'
                    f'<div style="color:#f59e0b;font-size:16px;font-weight:800;margin-bottom:2px">{_vc["credits"]}</div>'
                    f'<div style="color:var(--c-t3);font-size:10px">per 5s · {_vc["speed"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if _vcols[_vi].button(_vc["name"], key=f"sel_vid_model_{_vk}", use_container_width=True):
                    st.session_state["cs_vid_model_id"] = _vk
                    st.rerun()

            vid_id   = st.session_state.get("cs_vid_model_id", "kling3_0_turbo")
            _vmeta   = VIDEO_MODEL_META.get(vid_id, {})

            # Model info bar
            st.markdown(
                f'<div style="background:var(--c-row);border:1px solid var(--c-b1);border-radius:10px;'
                f'padding:12px 16px;margin:14px 0;display:flex;gap:24px;flex-wrap:wrap">'
                f'<span style="color:var(--c-t3);font-size:12px">Model: <b style="color:var(--c-t1)">{_vmeta.get("name","")}</b></span>'
                f'<span style="color:var(--c-t3);font-size:12px">Reddit: <b style="color:#10b981">{_vmeta.get("reddit_fit","")}</b></span>'
                f'<span style="color:var(--c-t3);font-size:12px">Speed: <b style="color:var(--c-t1b)">{_vmeta.get("speed","")}</b></span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Reddit video presets
            st.markdown(
                '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Reddit Format Presets</div>',
                unsafe_allow_html=True,
            )
            _vpnames = list(REDDIT_VIDEO_PRESETS.keys())
            _vpcols  = st.columns(len(_vpnames))
            for _vpi, _vpname in enumerate(_vpnames):
                _vpdata = REDDIT_VIDEO_PRESETS[_vpname]
                _vpcols[_vpi].markdown(
                    f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:8px;padding:8px 6px;text-align:center">'
                    f'<div style="color:var(--c-t1);font-size:11px;font-weight:600;margin-bottom:2px">{_vpname}</div>'
                    f'<div style="color:var(--c-t3);font-size:10px">{_vpdata["label"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if _vpcols[_vpi].button("Use", key=f"preset_vid_{_vpi}", use_container_width=True):
                    st.session_state["cs_vid_preset"] = _vpname
                    st.rerun()

            _vpreset   = REDDIT_VIDEO_PRESETS.get(st.session_state.get("cs_vid_preset",""), {})
            _def_var   = _vpreset.get("aspect_ratio", "16:9")
            _def_vdur  = _vpreset.get("duration", 5)

            st.markdown("<br>", unsafe_allow_html=True)

            # Prompt
            st.markdown('<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Prompt</div>', unsafe_allow_html=True)
            quick_v = st.selectbox("Quick video prompt", ["— write custom prompt —"] + APTORI_VID_PROMPTS, key="cs_vid_quick", label_visibility="collapsed")
            _vprompt_def = "" if quick_v == "— write custom prompt —" else quick_v
            vid_prompt = st.text_area(
                "Video prompt",
                value=_vprompt_def,
                height=100,
                key="cs_vid_prompt",
                placeholder="Describe the video scene, motion, style, mood…",
                label_visibility="collapsed",
            )

            # Format controls
            st.markdown("<br>", unsafe_allow_html=True)
            vf1, vf2, vf3 = st.columns([1, 1, 2])
            _ar_options  = ["16:9","9:16","1:1"]
            _dur_idx     = [5, 10].index(_def_vdur) if _def_vdur in [5, 10] else 0
            duration     = vf1.selectbox("Duration", [5, 10], index=_dur_idx, key="cs_vid_dur",
                                         format_func=lambda d: f"{d}s", help="5s = cheapest. 10s = 2× credits.")
            vid_ar       = vf2.selectbox("Aspect ratio", _ar_options,
                                         index=_ar_options.index(_def_var) if _def_var in _ar_options else 0,
                                         key="cs_vid_ar")
            vid_topic    = vf3.text_input("Topic tag", "Aptori promo", key="cs_vid_topic")

            st.caption("Optional: provide a local image file to animate (image-to-video)")
            img_path = st.text_input("Image file path", key="cs_vid_img", placeholder=r"C:\Users\lalit\Downloads\aptori.png", label_visibility="collapsed")

        with vid_side:
            st.markdown("<br>", unsafe_allow_html=True)
            _vest  = hf.estimate_credits(vid_id, duration) if "vid_id" in dir() else 0
            _vrem  = int(hf_credits or 0) - _vest if hf_credits and str(hf_credits).isdigit() else "—"
            st.markdown(
                f'<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:14px;'
                f'padding:20px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-bottom:16px">'
                f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">After Generation</div>'
                f'<div style="color:#f59e0b;font-size:13px;margin-bottom:4px">Cost: {_vest} credits</div>'
                f'<div style="color:var(--c-t1);font-size:28px;font-weight:800;margin:8px 0;line-height:1">{_vrem}</div>'
                f'<div style="color:var(--c-t3);font-size:12px">credits remaining</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="background:var(--c-card);border:1px solid var(--c-b1);border-radius:14px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.1)">'
                '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Reddit Video Guide</div>'
                + info_row("16:9 landscape", "Desktop posts")
                + info_row("9:16 portrait", "Mobile/vertical")
                + info_row("5 seconds", "Cheapest option")
                + info_row("10 seconds", "2× cost, more depth")
                + info_row("Max file size", "1 GB for Reddit")
                + '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        vgen_col, _ = st.columns([2, 3])
        if vgen_col.button("Generate Post Video", type="primary", disabled=not hf_ready, key="cs_gen_vid", use_container_width=True):
            if not vid_prompt.strip():
                st.error("Enter a video prompt.")
            else:
                with st.spinner(f"Generating with {_vmeta.get('name','model')} — {_vmeta.get('speed','~2min')}…"):
                    res = hf.generate_video(prompt=vid_prompt, model=vid_id, duration=duration, aspect_ratio=vid_ar, image_path=img_path.strip() if img_path else "", topic=vid_topic)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.success(f"Video generated — {res['credits']} credits used.")
                    if res.get("url"):
                        st.video(res["url"])
                        st.code(res["url"], language=None)
                        st.caption("Download this video and upload it to Reddit as a video post.")
                    st.rerun()

    # =========================================================================
    # TAB 3 — CONTENT IDEAS
    # =========================================================================
    with tab_ideas:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px">Top Reddit Threads — Use as Prompt Inspiration</div>',
            unsafe_allow_html=True,
        )
        if not insights:
            st.info("Run the scraper to pull in Reddit discussions and generate content ideas.")
        else:
            for p in sorted(insights, key=intent_score, reverse=True)[:15]:
                isc = intent_score(p)
                iclr = "#10b981" if isc >= 70 else "#f59e0b" if isc >= 45 else "#ef4444"
                _has_p_url = p.get("permalink","")
                _pfull_url = f"https://reddit.com{_has_p_url}" if _has_p_url and not _has_p_url.startswith("http") else _has_p_url
                with st.expander(f"[{isc}%] r/{p.get('subreddit','')}  ·  {p.get('title','')[:70]}", expanded=False):
                    st.markdown(
                        f'<div style="display:flex;gap:16px;align-items:center;margin-bottom:12px">'
                        f'<a href="{_pfull_url}" target="_blank" style="color:var(--c-link);font-size:13px">Open Reddit thread</a>'
                        f'<span style="color:var(--c-t3);font-size:12px">↑{p.get("score",0)} · 💬{p.get("num_comments",0)}</span>'
                        f'<span style="color:{iclr};font-size:12px;font-weight:700">Intent {isc}%</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    _sug_img = f"Professional Aptori post image: {p.get('title','')[:80]}, dark enterprise SaaS style, API security theme, cinematic quality"
                    _sug_vid = f"Cinematic video about: {p.get('title','')[:80]}, Aptori brand, teal and dark blue tones, dramatic lighting"
                    st.markdown(
                        f'<div style="background:var(--c-row);border-radius:10px;padding:14px;margin-bottom:8px">'
                        f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Suggested Post Image Prompt</div>'
                        f'<div style="color:var(--c-t1b);font-size:13px;line-height:1.5">{_sug_img}</div>'
                        f'</div>'
                        f'<div style="background:var(--c-row);border-radius:10px;padding:14px">'
                        f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Suggested Video Prompt</div>'
                        f'<div style="color:var(--c-t1b);font-size:13px;line-height:1.5">{_sug_vid}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    _ic1, _ic2 = st.columns(2)
                    if _ic1.button("Use as Image Prompt", key=f"idea_img_{p.get('id','')}"):
                        st.session_state["cs_img_prompt"] = _sug_img
                        st.session_state["sidebar_nav"]   = "Content Studio"
                        st.rerun()
                    if _ic2.button("Use as Video Prompt", key=f"idea_vid_{p.get('id','')}"):
                        st.session_state["cs_vid_prompt"] = _sug_vid
                        st.session_state["sidebar_nav"]   = "Content Studio"
                        st.rerun()

# =============================================================================
# PAGE 8 — HIGGSFIELD CREDITS
# =============================================================================
elif page == "Higgsfield Credits":
    st.markdown(section_header("Higgsfield Credits", "Track credit usage across all AI generations"), unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Credits Available",   hf_credits or "—",              "from your plan",    "#10b981"), unsafe_allow_html=True)
    c2.markdown(metric_card("Used This Session",   hf.credits_used_total(),        "",                  "#E63946"), unsafe_allow_html=True)
    c3.markdown(metric_card("Used Today",          hf.credits_used_today(),        "",                  "#f59e0b"), unsafe_allow_html=True)
    c4.markdown(metric_card("Generations Logged",  len(hf.credit_history()),       "",                  "#7c3aed"), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div style="color:var(--c-t1);font-weight:700;font-size:18px;margin-bottom:12px">Download History</div>', unsafe_allow_html=True)

    history = hf.credit_history()
    if not history:
        st.info("No generations logged yet. Use Content Studio to generate images or videos.")
    else:
        img_history = [e for e in history if e.get("type","").lower() in ("image","text_to_image","img")]
        vid_history = [e for e in history if e.get("type","").lower() in ("video","text_to_video","vid")]
        other_history = [e for e in history if e not in img_history and e not in vid_history]

        tab_img_h, tab_vid_h = st.tabs([
            f"Images ({len(img_history)})",
            f"Videos ({len(vid_history) + len(other_history)})",
        ])

        def _render_history_table(entries):
            if not entries:
                st.caption("Nothing here yet.")
                return
            st.markdown(
                '<div style="display:grid;grid-template-columns:1.4fr 1.2fr 1fr 1fr 2fr;'
                'background:var(--c-card);border:1px solid var(--c-b2);border-radius:10px 10px 0 0;padding:10px 14px">'
                + "".join(f'<div style="color:var(--c-t2);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em">{h}</div>'
                          for h in ["Date", "Model", "Credits", "Status", "Prompt"])
                + '</div>',
                unsafe_allow_html=True,
            )
            for entry in entries:
                created = entry.get("created_at","")[:16].replace("T"," ")
                model   = entry.get("model","?").split("/")[-1]
                creds   = entry.get("credits", 0)
                status_ = entry.get("status","?")
                prompt  = entry.get("prompt","")[:55]
                url     = entry.get("result_url","")
                s_color = "#10b981" if status_ == "completed" else "#f59e0b"
                st.markdown(
                    f'<div style="display:grid;grid-template-columns:1.4fr 1.2fr 1fr 1fr 2fr;'
                    f'background:var(--c-row);border:1px solid var(--c-b1);border-top:none;padding:10px 14px">'
                    f'<div style="color:var(--c-t2);font-size:12px">{created}</div>'
                    f'<div style="color:var(--c-t1);font-size:12px">{model}</div>'
                    f'<div style="color:#f59e0b;font-size:13px;font-weight:700">{creds}</div>'
                    f'<div style="color:{s_color};font-size:12px">{status_.title()}</div>'
                    f'<div style="color:var(--c-t2);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
                    f'{prompt}{"…" if len(entry.get("prompt","")) > 55 else ""}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if url:
                    dl_col, _ = st.columns([1, 5])
                    dl_col.markdown(
                        f'<div style="background:var(--c-bg);border:1px solid var(--c-b1);border-top:none;padding:6px 14px">'
                        f'<a href="{url}" target="_blank" style="color:var(--c-link);font-size:11px;font-weight:600">Download / View</a>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        with tab_img_h:
            _render_history_table(img_history)

        with tab_vid_h:
            _render_history_table(vid_history + other_history)

# =============================================================================
# PAGE 9 — ACCOUNTS MANAGER
# =============================================================================
elif page == "Accounts Manager":
    st.markdown(section_header("Accounts Manager", "Manage Reddit accounts used for manual engagement — no automation"), unsafe_allow_html=True)

    st.markdown(
        '<div style="background:var(--c-card);border:1px solid var(--c-b2);border-left:3px solid #f59e0b;'
        'border-radius:10px;padding:14px 18px;margin-bottom:20px">'
        '<div style="color:#f59e0b;font-weight:700;margin-bottom:4px">Manual posting only</div>'
        '<div style="color:var(--c-t1b);font-size:13px">All posting is done manually by you. No automation touches Reddit accounts. '
        'These account profiles are for your reference and tracking only.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.expander("+ Add Reddit Account", expanded=False):
        a1, a2 = st.columns(2)
        new_uname  = a1.text_input("Reddit username", placeholder="u/AptoriOfficial", key="acc_uname")
        new_pwd    = a2.text_input("Reddit password", type="password", placeholder="stored locally only", key="acc_pwd")
        a3, a4 = st.columns(2)
        new_role   = a3.selectbox("Role", ["Brand","Founder","Thought Leadership","Community","Personal"], key="acc_role")
        new_risk   = a4.selectbox("Risk level", ["Low","Medium","High"], key="acc_risk")
        a5, a6 = st.columns(2)
        new_tone   = a5.text_input("Tone", "Professional, helpful, technical", key="acc_tone")
        new_email  = a6.text_input("Email (optional)", placeholder="linked email", key="acc_email")
        new_rules  = st.text_area("Posting rules", "No spammy CTA. Always add value first. Mention Aptori only when relevant.", height=80, key="acc_rules")
        new_notes  = st.text_input("Notes", key="acc_notes")
        st.caption("Credentials stored locally only — never sent anywhere. Use them to log in manually via the button below each account.")

        if st.button("Add Account", type="primary", key="acc_add_btn"):
            if new_uname.strip():
                import base64 as _b64
                _enc_pwd = _b64.b64encode(new_pwd.encode()).decode() if new_pwd else ""
                add_account({
                    "username":   new_uname.strip().lstrip("u/"),
                    "password":   _enc_pwd,
                    "email":      new_email.strip(),
                    "role": new_role, "tone": new_tone, "risk": new_risk,
                    "rules": new_rules, "notes": new_notes,
                    "status": "active", "last_used": "", "posts_made": 0,
                    "verified_pass": 0, "verified_fail": 0,
                })
                st.success(f"Added u/{new_uname.strip()}")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Enter a username.")

    accts = get_accounts()
    if not accts:
        st.info("No accounts added yet. Add your Reddit accounts above.")
    else:
        for acc in accts:
            uname  = acc.get("username","")
            role   = acc.get("role","")
            status_a = acc.get("status","active")
            risk   = acc.get("risk","Low")
            pm     = acc.get("posts_made", 0)
            vp     = acc.get("verified_pass", 0)
            lu     = acc.get("last_used","") or "Never"

            with st.expander(f"u/{uname}  ·  {role}  ·  {badge(status_a, status_a)}", expanded=False):
                import base64 as _b64
                _stored_pwd_b64 = acc.get("password", "")
                _plain_pwd = _b64.b64decode(_stored_pwd_b64).decode() if _stored_pwd_b64 else ""
                _has_pwd = bool(_plain_pwd)

                # ── Reddit login panel ────────────────────────────────────────
                _email_block = (
                    f'<div><div style="color:var(--c-t3);font-size:10px;margin-bottom:2px">EMAIL</div>'
                    f'<div style="color:var(--c-t2);font-size:13px">{acc.get("email","")}</div></div>'
                ) if acc.get("email") else ""
                st.markdown(
                    f'<div style="background:var(--c-row);border:1px solid var(--c-b1);border-radius:12px;'
                    f'padding:16px 20px;margin-bottom:16px">'
                    f'<div style="color:var(--c-t3);font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.1em;margin-bottom:12px">Reddit Login</div>'
                    f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:12px">'
                    f'<div>'
                    f'<div style="color:var(--c-t3);font-size:10px;margin-bottom:2px">USERNAME</div>'
                    f'<div style="color:var(--c-t1);font-size:14px;font-weight:700">u/{uname}</div>'
                    f'</div>'
                    f'<div>'
                    f'<div style="color:var(--c-t3);font-size:10px;margin-bottom:2px">PASSWORD</div>'
                    f'<div style="color:var(--c-t1);font-size:14px;font-weight:700">{"••••••••" if _has_pwd else "—"}</div>'
                    f'</div>'
                    f'{"<div><div style=\\"color:var(--c-t3);font-size:10px;margin-bottom:2px\\">EMAIL</div><div style=\\"color:var(--c-t2);font-size:13px\\">" + acc.get("email","") + "</div></div>" if acc.get("email") else ""}'
                    f'</div>'
                    f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                    f'<a href="https://www.reddit.com/login" target="_blank" '
                    f'style="background:#FF4500;color:#fff;padding:8px 18px;border-radius:8px;'
                    f'font-size:13px;font-weight:700;text-decoration:none">Open Reddit Login</a>'
                    f'<a href="https://www.reddit.com/user/{uname}" target="_blank" '
                    f'style="background:var(--c-b1);color:var(--c-link);padding:8px 16px;border-radius:8px;'
                    f'font-size:13px;font-weight:600;text-decoration:none">View Profile</a>'
                    f'<a href="https://www.reddit.com/submit" target="_blank" '
                    f'style="background:var(--c-b1);color:var(--c-t2);padding:8px 16px;border-radius:8px;'
                    f'font-size:13px;font-weight:600;text-decoration:none">Submit Post</a>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Show credentials to copy (reveal password for login)
                if _has_pwd:
                    if st.button("Show credentials to copy", key=f"acc_show_{uname}"):
                        st.session_state[f"show_creds_{uname}"] = True
                    if st.session_state.get(f"show_creds_{uname}"):
                        cr1, cr2 = st.columns(2)
                        cr1.text_input("Username", value=uname, key=f"acc_cu_{uname}", disabled=True)
                        cr2.text_input("Password", value=_plain_pwd, key=f"acc_cp_{uname}", type="default")
                        st.caption("Copy these into the Reddit login form above. Click away to hide.")
                        if st.button("Hide", key=f"acc_hide_{uname}"):
                            st.session_state[f"show_creds_{uname}"] = False
                            st.rerun()

                # ── Stats ─────────────────────────────────────────────────────
                ca, cb, cc, cd = st.columns(4)
                ca.markdown(metric_card("Posts Made",    pm,      "", "#3b82f6"), unsafe_allow_html=True)
                cb.markdown(metric_card("Verified Pass", vp,      "", "#10b981"), unsafe_allow_html=True)
                cc.markdown(metric_card("Risk Level",    risk,    "", "#f59e0b"), unsafe_allow_html=True)
                cd.markdown(metric_card("Last Used",     lu[:10], "", "#7c3aed"), unsafe_allow_html=True)

                st.markdown("---")
                st.markdown(f'**Tone:** {acc.get("tone","")}')
                st.markdown(f'**Posting rules:** {acc.get("rules","")}')
                if acc.get("notes"):
                    st.caption(f'Notes: {acc["notes"]}')

                col_p, col_d = st.columns([1, 4])
                toggle_lbl = "Pause" if status_a == "active" else "Resume"
                if col_p.button(toggle_lbl, key=f"acc_tog_{uname}"):
                    update_account(uname, {"status": "paused" if status_a == "active" else "active"})
                    st.rerun()
                if col_d.button("Delete Account", key=f"acc_del_{uname}"):
                    delete_account(uname)
                    st.rerun()

# =============================================================================
# PAGE 10 — SETTINGS
# =============================================================================
elif page == "Settings":
    st.markdown(section_header("Settings", "Configure appearance, keywords, credentials, and system commands"), unsafe_allow_html=True)

    tab_appearance, tab_kw, tab_creds, tab_cmds = st.tabs(["Appearance", "Keywords", "Credentials", "Commands"])

    with tab_appearance:
        st.markdown("**Theme**")
        st.caption("Controls the color scheme of the dashboard.")
        _current_theme = app_settings.get("theme", "dark")
        _theme_options = ["Dark", "Light", "System"]
        _theme_index   = {"dark": 0, "light": 1, "system": 2}.get(_current_theme, 0)
        _selected = st.radio(
            "Appearance mode",
            _theme_options,
            index=_theme_index,
            key="settings_theme",
            label_visibility="collapsed",
        )
        _selected_key = _selected.lower()
        if st.button("Apply Theme", type="primary", key="apply_theme"):
            _new_settings = {**app_settings, "theme": _selected_key}
            save_settings(_new_settings)
            # Update config.toml so Streamlit's native widgets match the theme
            _toml_dark = (
                '[theme]\nbase = "dark"\nprimaryColor = "#E63946"\n'
                'backgroundColor = "#0a0e1a"\nsecondaryBackgroundColor = "#111827"\n'
                'textColor = "#f1f5f9"\nfont = "sans serif"\n\n'
                '[server]\nrunOnSave = false\n'
            )
            _toml_light = (
                '[theme]\nbase = "light"\nprimaryColor = "#E63946"\n'
                'backgroundColor = "#f8fafc"\nsecondaryBackgroundColor = "#f1f5f9"\n'
                'textColor = "#0f172a"\nfont = "sans serif"\n\n'
                '[server]\nrunOnSave = false\n'
            )
            # System uses dark as the Streamlit base (CSS media query handles the switch)
            _toml_map = {"dark": _toml_dark, "light": _toml_light, "system": _toml_dark}
            Path(".streamlit/config.toml").write_text(
                _toml_map[_selected_key], encoding="utf-8"
            )
            st.success(f"{_selected} theme applied. The page will reload.")
            st.rerun()

        st.markdown("---")
        st.markdown("**Preview**")
        _prev_dark  = "**Dark** — deep navy background, light text, high contrast for extended use."
        _prev_light = "**Light** — white background, dark text, easy to read in bright environments."
        _prev_sys   = "**System** — follows your OS/browser preference automatically."
        st.info({"dark": _prev_dark, "light": _prev_light, "system": _prev_sys}[_selected_key])

    with tab_kw:
        st.markdown("**Edit keywords.txt**")
        kw_file = Path("keywords.txt")
        kw_content = kw_file.read_text(encoding="utf-8") if kw_file.exists() else ""
        edited_kw = st.text_area("keywords.txt", value=kw_content, height=300, key="settings_kw")
        if st.button("Save Keywords", type="primary", key="settings_kw_save"):
            kw_file.write_text(edited_kw, encoding="utf-8")
            # Re-sync keywords_data.json
            existing_kd = {k["keyword"]: k for k in get_keywords_data()}
            new_lines   = [l.strip() for l in edited_kw.splitlines() if l.strip() and not l.startswith("#")]
            new_kd      = [existing_kd.get(kw, {"keyword":kw,"status":"active","posts_found":0,"quality_score":0,"last_scan":""}) for kw in new_lines]
            save_keywords_data(new_kd)
            st.success("Keywords saved.")

    with tab_creds:
        st.markdown("**Higgsfield CLI auth status**")
        if hf_ready:
            st.success(f"Authenticated: {hf_info}")
        else:
            st.warning("Not authenticated.")
            st.code("higgsfield auth login", language="bash")
            st.caption("Run in terminal — opens browser OAuth, no API key needed.")

        st.markdown("---")
        st.markdown("**Anthropic API**")
        ak = os.getenv("ANTHROPIC_API_KEY","")
        if ak and not ak.startswith("your_"):
            st.success("Anthropic API key configured.")
        else:
            st.error("ANTHROPIC_API_KEY not set in .env")

    with tab_cmds:
        st.markdown("**Run commands**")
        st.code("python run_daily.py", language="bash")
        st.caption("Scrape posts and generate humanized comments (takes 2-5 min)")
        st.code("python scrape_insights.py", language="bash")
        st.caption("Scrape insights only (no AI generation)")
        st.code("streamlit run dashboard.py", language="bash")
        st.caption("Launch this dashboard")
        st.code("higgsfield auth login", language="bash")
        st.caption("Re-authenticate Higgsfield CLI")
        st.markdown("---")
        st.markdown("**Storage files**")
        for f in ["dashboard_data.json","insights_data.json","higgsfield_credits.json","accounts.json","keywords_data.json"]:
            exists = Path(f).exists()
            size   = Path(f).stat().st_size if exists else 0
            col_a, col_b = st.columns([2, 1])
            col_a.markdown(f'<span style="color:{"#10b981" if exists else "#ef4444"}">{f}</span>', unsafe_allow_html=True)
            col_b.caption(f"{size:,} bytes" if exists else "not found")
