"""
higgsfield_client.py -- Higgsfield AI via the official CLI (no API key required).

Setup (one-time):
  npm install -g @higgsfield/cli   (already done)
  higgsfield auth login            <-- runs browser OAuth, takes 5 seconds

Confirmed models (from higgsfield model list):
  Image: text2image_soul_v2, gpt_image_2, flux_2, soul_cinematic, nano_banana_2
  Video: kling3_0, kling3_0_turbo, seedance_2_0, veo3, cinematic_studio_3_0
"""

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CREDITS_FILE = Path("higgsfield_credits.json")

CREDIT_COSTS = {
    "text2image_soul_v2": 4,
    "gpt_image_2":        6,
    "flux_2":             3,
    "soul_cinematic":     5,
    "nano_banana_2":      4,
    "kling3_0":          30,
    "kling3_0_turbo":    20,
    "seedance_2_0":      25,
    "veo3":              40,
    "cinematic_studio_3_0": 25,
}

TEXT_TO_IMAGE_MODELS = {
    "flux_2":             "FLUX.2 · 3 credits",
    "text2image_soul_v2": "Soul V2 · 4 credits",
    "nano_banana_2":      "Nano Banana Pro · 4 credits",
    "gpt_image_2":        "GPT Image 2 · 6 credits",
}

TEXT_TO_VIDEO_MODELS = {
    "kling3_0_turbo":       "Kling 3.0 Turbo · 20 credits",
    "cinematic_studio_3_0": "Cinematic Studio 3.0 · 25 credits",
    "seedance_2_0":         "Seedance 2.0 · 25 credits",
    "kling3_0":             "Kling v3.0 · 30 credits",
    "veo3":                 "Google Veo 3 · 40 credits",
}

# Rich model metadata for UI display
IMAGE_MODEL_META = {
    "flux_2": {
        "name": "FLUX.2",
        "credits": 3,
        "tag": "Best Value",
        "tag_color": "#10b981",
        "speed": "~25s",
        "desc": "Crisp, detailed, versatile. Excellent for community posts and infographics.",
        "reddit_fit": "Excellent for all Reddit post types",
        "quality_param": "resolution",
        "quality_options": ["1k", "2k"],
        "quality_default": "2k",
        "quality_labels": {"1k": "Standard (1k) · Save credits", "2k": "High Quality (2k) · Best detail"},
    },
    "text2image_soul_v2": {
        "name": "Soul V2",
        "credits": 4,
        "tag": "Flagship",
        "tag_color": "#E63946",
        "speed": "~45s",
        "desc": "Cinematic, editorial quality. Best for brand announcements and product visuals.",
        "reddit_fit": "Best for high-impact brand posts",
        "quality_param": "quality",
        "quality_options": ["1.5k", "2k"],
        "quality_default": "2k",
        "quality_labels": {"1.5k": "Standard (1.5k) · Save 1 credit", "2k": "High Quality (2k) · Best detail"},
    },
    "nano_banana_2": {
        "name": "Nano Banana Pro",
        "credits": 4,
        "tag": "Fastest",
        "tag_color": "#3b82f6",
        "speed": "~20s",
        "desc": "Fast generation with clean, sharp output. Great for rapid iteration.",
        "reddit_fit": "Great for quick mockups and drafts",
        "quality_param": "resolution",
        "quality_options": ["1k", "2k", "4k"],
        "quality_default": "2k",
        "quality_labels": {"1k": "Draft (1k) · Cheapest", "2k": "High Quality (2k) · Balanced", "4k": "Ultra (4k) · Maximum detail"},
    },
    "gpt_image_2": {
        "name": "GPT Image 2",
        "credits": 6,
        "tag": "Photorealistic",
        "tag_color": "#7c3aed",
        "speed": "~60s",
        "desc": "Photorealistic, highly detailed renders. Best for product showcases.",
        "reddit_fit": "Best for realistic/technical visuals",
        "quality_param": "quality",
        "quality_options": ["low", "medium", "high"],
        "quality_default": "high",
        "quality_labels": {"low": "Low · Fastest/cheapest", "medium": "Medium · Balanced", "high": "High · Best quality"},
    },
}

# Maps generic preset quality values → model-specific param value
_QUALITY_COMPAT = {
    "flux_2":             {"2k": "2k",   "1.5k": "1k", "1k": "1k", "high": "2k", "standard": "1k"},
    "text2image_soul_v2": {"2k": "2k",   "1.5k": "1.5k", "1k": "1.5k", "high": "2k", "standard": "1.5k"},
    "nano_banana_2":      {"2k": "2k",   "1.5k": "1k", "1k": "1k", "4k": "4k", "high": "4k", "standard": "2k"},
    "gpt_image_2":        {"2k": "high", "1.5k": "medium", "1k": "low", "high": "high", "medium": "medium", "low": "low", "standard": "medium"},
}

VIDEO_MODEL_META = {
    "kling3_0_turbo": {
        "name": "Kling 3.0 Turbo",
        "credits": 20,
        "tag": "Best Value",
        "tag_color": "#10b981",
        "speed": "~60s",
        "desc": "Smooth motion with great quality at lowest cost. Ideal for Reddit posts.",
        "reddit_fit": "Best cost-quality ratio for Reddit",
    },
    "cinematic_studio_3_0": {
        "name": "Cinematic Studio 3.0",
        "credits": 25,
        "tag": "Cinematic",
        "tag_color": "#E63946",
        "speed": "~90s",
        "desc": "Film-quality visuals with dramatic lighting and composition.",
        "reddit_fit": "Best for brand showcase videos",
    },
    "seedance_2_0": {
        "name": "Seedance 2.0",
        "credits": 25,
        "tag": "Dynamic",
        "tag_color": "#7c3aed",
        "speed": "~90s",
        "desc": "Dynamic movement and vivid colors. Great for action and tech demos.",
        "reddit_fit": "Best for fast-paced content",
    },
    "kling3_0": {
        "name": "Kling v3.0",
        "credits": 30,
        "tag": "Premium",
        "tag_color": "#f59e0b",
        "speed": "~2min",
        "desc": "Ultra-smooth motion with premium quality. Maximum detail retention.",
        "reddit_fit": "Premium quality brand content",
    },
    "veo3": {
        "name": "Google Veo 3",
        "credits": 40,
        "tag": "Flagship",
        "tag_color": "#E63946",
        "speed": "~3min",
        "desc": "State-of-the-art video generation. Commercial-grade output.",
        "reddit_fit": "Exceptional – use for hero content only",
    },
}

# Reddit-optimized format presets
REDDIT_POST_PRESETS = {
    "Square (1:1)":          {"aspect_ratio": "1:1",  "quality": "2k",   "label": "Universal · Best Engagement"},
    "Landscape (16:9)":      {"aspect_ratio": "16:9", "quality": "2k",   "label": "Standard · Desktop-first"},
    "Portrait (9:16)":       {"aspect_ratio": "9:16", "quality": "2k",   "label": "Mobile-first · Vertical"},
    "Medium (4:3)":          {"aspect_ratio": "4:3",  "quality": "2k",   "label": "Gallery · Banner"},
    "Draft Square (1:1)":    {"aspect_ratio": "1:1",  "quality": "1.5k", "label": "Save 1 credit · Test prompts"},
    "Draft Wide (16:9)":     {"aspect_ratio": "16:9", "quality": "1.5k", "label": "Save 1 credit · Test prompts"},
}

REDDIT_VIDEO_PRESETS = {
    "Standard (16:9 · 5s)":  {"aspect_ratio": "16:9", "duration": 5,  "label": "Desktop · Cheapest"},
    "Mobile (9:16 · 5s)":    {"aspect_ratio": "9:16", "duration": 5,  "label": "Vertical · Mobile Reddit"},
    "Square (1:1 · 5s)":     {"aspect_ratio": "1:1",  "duration": 5,  "label": "Universal · Square"},
    "Extended (16:9 · 10s)": {"aspect_ratio": "16:9", "duration": 10, "label": "More story · 2× cost"},
}

_CLI_CANDIDATES = [
    shutil.which("higgsfield"),
    shutil.which("higgsfield.cmd"),
    os.path.expanduser(r"~\AppData\Roaming\npm\higgsfield.cmd"),
    os.path.expanduser(r"~\AppData\Roaming\npm\higgsfield"),
    "/usr/local/bin/higgsfield",
]


def _find_cli() -> str | None:
    for c in _CLI_CANDIDATES:
        if c and os.path.isfile(c):
            return c
    return None


def _cli_available() -> bool:
    return _find_cli() is not None


def _build_env() -> dict:
    env   = os.environ.copy()
    extra = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        os.path.expanduser(r"~\AppData\Roaming\npm"),
    ]
    existing  = env.get("PATH", "")
    additions = ";".join(p for p in extra if p not in existing)
    if additions:
        env["PATH"] = additions + ";" + existing
    return env


def _run(args: list, timeout: int = 300) -> tuple[str, str, int]:
    cli = _find_cli()
    if not cli:
        return "", "higgsfield CLI not found. Run: npm install -g @higgsfield/cli", 1
    try:
        result = subprocess.run(
            [cli] + args,
            capture_output=True, text=True, timeout=timeout,
            env=_build_env(),
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except FileNotFoundError:
        return "", f"CLI not found at {cli}", 1


def _extract_url(text: str) -> str:
    match = re.search(r"https://\S+\.(jpg|jpeg|png|webp|mp4|mov|gif)[\S]*", text, re.IGNORECASE)
    if match:
        return match.group(0).rstrip(".,)")
    match = re.search(r"https://\S+", text)
    return match.group(0).rstrip(".,)") if match else ""


class HiggsFieldClient:

    def __init__(self):
        self._log = self._load()

    # ── auth ─────────────────────────────────────────────────────────

    @property
    def configured(self) -> bool:
        if not _cli_available():
            return False
        out, err, rc = _run(["account", "status"])
        combined = (out + err).lower()
        return rc == 0 and "not authenticated" not in combined and "auth login" not in combined

    @property
    def cli_installed(self) -> bool:
        return _cli_available()

    def auth_status(self) -> dict:
        if not _cli_available():
            return {"authenticated": False, "error": "CLI not installed"}
        out, err, rc = _run(["account", "status"])
        combined = (out + err).lower()
        if rc == 0 and "not authenticated" not in combined and "auth login" not in combined:
            return {"authenticated": True, "info": out}
        return {"authenticated": False, "error": err or out or "Not logged in. Run: higgsfield auth login"}

    # ── persistence ──────────────────────────────────────────────────

    def _load(self) -> list:
        if not CREDITS_FILE.exists():
            return []
        try:
            return json.loads(CREDITS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self):
        CREDITS_FILE.write_text(
            json.dumps(self._log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── credit helpers ───────────────────────────────────────────────

    def credits_used_total(self) -> int:
        return sum(e.get("credits", 0) for e in self._log)

    def credits_used_today(self) -> int:
        today = datetime.utcnow().date().isoformat()
        return sum(
            e.get("credits", 0) for e in self._log
            if e.get("created_at", "").startswith(today)
        )

    def credit_history(self) -> list:
        return list(reversed(self._log))

    def estimate_credits(self, model_id: str, duration: int = 5) -> int:
        base = CREDIT_COSTS.get(model_id, 10)
        if model_id in TEXT_TO_VIDEO_MODELS:
            return base * max(1, duration // 5)
        return base

    # ── generation ───────────────────────────────────────────────────

    def generate_image(
        self,
        prompt:       str,
        model:        str = "flux_2",
        aspect_ratio: str = "16:9",
        quality:      str = "2k",
        topic:        str = "",
    ) -> dict:
        if not self.configured:
            return {"error": "Not authenticated. Run in terminal: higgsfield auth login"}

        # Resolve correct param name and value for this model
        meta       = IMAGE_MODEL_META.get(model, {})
        param_name = meta.get("quality_param", "quality")
        compat     = _QUALITY_COMPAT.get(model, {})
        param_val  = compat.get(quality, meta.get("quality_default", quality))

        args = [
            "generate", "create", model,
            "--prompt", prompt,
            "--aspect_ratio", aspect_ratio,
            f"--{param_name}", param_val,
            "--wait", "--json",
        ]
        out, err, rc = _run(args, timeout=300)

        credits = self.estimate_credits(model)
        if rc != 0:
            return {"error": err or out or "Generation failed"}

        result_url = _extract_url(out)
        request_id = ""
        try:
            data = json.loads(out)
            request_id = str(data.get("id", data.get("request_id", "")))
            result_url = result_url or data.get("url", "")
        except Exception:
            pass

        self._log.append({
            "type": "image", "model": model, "topic": topic,
            "prompt": prompt[:120], "credits": credits,
            "request_id": request_id, "status": "completed",
            "result_url": result_url,
            "created_at": datetime.utcnow().isoformat(),
        })
        self._save()
        return {"request_id": request_id, "status": "completed",
                "credits": credits, "url": result_url, "model": model}

    def generate_video(
        self,
        prompt:       str,
        model:        str = "kling3_0",
        duration:     int = 5,
        mode:         str = "pro",
        aspect_ratio: str = "16:9",
        image_path:   str = "",
        topic:        str = "",
    ) -> dict:
        if not self.configured:
            return {"error": "Not authenticated. Run in terminal: higgsfield auth login"}

        args = [
            "generate", "create", model,
            "--prompt", prompt,
            "--duration", str(duration),
            "--aspect_ratio", aspect_ratio,
            "--wait", "--json",
        ]
        # pass local image file for image-to-video if provided
        if image_path and os.path.isfile(image_path):
            args += ["--image", image_path]

        out, err, rc = _run(args, timeout=600)

        credits = self.estimate_credits(model, duration)
        if rc != 0:
            return {"error": err or out or "Generation failed"}

        result_url = _extract_url(out)
        request_id = ""
        try:
            data = json.loads(out)
            request_id = str(data.get("id", data.get("request_id", "")))
            result_url = result_url or data.get("url", "")
        except Exception:
            pass

        self._log.append({
            "type": "video", "model": model, "topic": topic,
            "prompt": prompt[:120], "credits": credits, "duration": duration,
            "request_id": request_id, "status": "completed",
            "result_url": result_url,
            "created_at": datetime.utcnow().isoformat(),
        })
        self._save()
        return {"request_id": request_id, "status": "completed",
                "credits": credits, "url": result_url, "model": model}

    def check_status(self, request_id: str) -> dict:
        out, err, rc = _run(["generate", "get", request_id, "--json"])
        if rc == 0 and out:
            try:
                data = json.loads(out)
                url  = data.get("url", _extract_url(out))
                stat = data.get("status", "completed")
                for entry in self._log:
                    if entry.get("request_id") == request_id:
                        entry["status"] = stat
                        if url:
                            entry["result_url"] = url
                self._save()
                return {"status": stat, "url": url, "request_id": request_id}
            except Exception:
                return {"status": "completed", "raw": out}
        return {"error": err or "Could not get status"}
