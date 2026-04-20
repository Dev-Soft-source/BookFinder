"""OpenAI vision helpers and Playwright Amazon-captcha automation."""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable, NamedTuple

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

load_dotenv()

# Stronger vision than mini; set OPENAI_VISION_MODEL=gpt-4o-mini to save cost.
DEFAULT_VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")

CAPTCHA_SYSTEM_PROMPT = """You solve Amazon-style 3×3 image CAPTCHAs.

Grid layout (the label you output is the small tile number 1–9):
  1 | 2 | 3   (top row)
  4 | 5 | 6   (middle)
  7 | 8 | 9   (bottom)

Rules:
- Each cell is a picture. Pick every tile whose IMAGE content matches the instruction (e.g. "Find all taxis" → every tile that clearly shows a taxi).
- The digit 1–9 on a tile identifies that tile for your answer; it is not "what the picture shows."
- Examine each of the nine tiles before deciding; be conservative if a cell is blurry.
- You MUST respond with one JSON object only — no markdown, no explanation outside JSON."""


def _captcha_user_prompt(instruction: str) -> str:
    return (
        f"Instruction (what to find in the pictures):\n{instruction.strip()}\n\n"
        "Respond with JSON only, in this exact shape:\n"
        '{"tile_numbers": [<integers 1-9 for matching tiles>]}\n'
        'Example: {"tile_numbers": [2, 5, 8]}\n'
        'If nothing matches: {"tile_numbers": []}'
    )


# --- Playwright: page URL and Amazon grid captcha ---

DEFAULT_URL = "https://bookfinder.com"

# Nine <button> nodes under the 320x320 puzzle <canvas> (a11y); scope to this canvas.
AMZN_PUZZLE_GRID = 'canvas[width="320"][height="320"]'


class ScreenPoint(NamedTuple):
    """Pixel coordinates on the primary display (origin top-left)."""

    x: int
    y: int


def get_screen_center() -> ScreenPoint:
    """Center of the primary monitor in screen pixel coordinates."""
    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        w = int(user32.GetSystemMetrics(0))
        h = int(user32.GetSystemMetrics(1))
    else:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            w = int(root.winfo_screenwidth())
            h = int(root.winfo_screenheight())
        finally:
            root.destroy()
    return ScreenPoint(w // 2, h // 2)


def click_amzn_captcha_verify_button(page: Page, *, timeout_ms: float = 30_000) -> None:
    """Click Amazon captcha verify (``.amzn-captcha-verify-button``)."""
    page.locator(".amzn-captcha-verify-button").click(timeout=timeout_ms)


def click_confirm_button(page: Page, *, timeout_ms: float = 30_000) -> None:
    page.locator("#amzn-btn-verify-internal").click(timeout=timeout_ms)


def amzn_grid_buttons(page: Page):
    """Nine tile ``button`` elements for the 320x320 puzzle grid."""
    return page.locator(f"{AMZN_PUZZLE_GRID} button")


def _click_dom_invisible_button(locator: Locator, *, timeout_ms: float = 30_000) -> None:
    """DOM click when Playwright treats canvas a11y tiles as not visible."""
    locator.wait_for(state="attached", timeout=timeout_ms)
    locator.evaluate(
        """(el) => {
            el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            el.click();
        }"""
    )


def click_nth_canvas_button(
    page: Page,
    index: int,
    *,
    timeout_ms: float = 30_000,
) -> None:
    """Click ``index``-th puzzle tile under the grid (0-based)."""
    tiles = amzn_grid_buttons(page)
    tiles.first.wait_for(state="attached", timeout=timeout_ms)
    btn = tiles.nth(index)
    _click_dom_invisible_button(btn, timeout_ms=timeout_ms)


def click_amzn_grid_tile_by_label(page: Page, digit: str, *, timeout_ms: float = 30_000) -> None:
    """Click tile whose button shows ``digit`` (\"1\" … \"9\")."""
    canvas = page.locator(AMZN_PUZZLE_GRID).first
    canvas.wait_for(state="attached", timeout=timeout_ms)
    btn = canvas.get_by_role("button", name=digit, exact=True)
    _click_dom_invisible_button(btn, timeout_ms=timeout_ms)


def _human_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def get_captcha_instruction_text(page: Page, *, timeout_ms: float = 60_000) -> str:
    """Text inside puzzle ``<em>``; empty if not found."""
    try:
        page.locator(AMZN_PUZZLE_GRID).first.wait_for(state="attached", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        print("warning: 320x320 puzzle canvas did not appear in time.")

    em = page.locator("em").first
    try:
        em.wait_for(state="visible", timeout=timeout_ms)
        return em.inner_text().strip()
    except PlaywrightTimeoutError:
        print(
            "warning: no visible <em> instruction (wrong page, iframe, or captcha still loading)."
        )
        return ""


def run_post_load_captcha_and_screenshot(
    page: Page,
    *,
    screenshot_path: str = "center_320_screenshot.png",
    _round: int = 0,
    max_rounds: int = 3,
) -> None:
    """Screenshot, read instruction, OpenAI tile picks, click tiles, confirm; optional retry rounds."""
    _human_delay(3.0, 6.0)
    # Prefer element-based capture (page coordinates) over screen-center math for reliability.
    captured = False
    for loc in (
        page.locator(AMZN_PUZZLE_GRID).first,
        page.locator("canvas[width='320'][height='320']").first,
    ):
        try:
            loc.wait_for(state="visible", timeout=15_000)
            loc.screenshot(path=screenshot_path)
            captured = True
            print(f"Saved captcha canvas screenshot as {screenshot_path}")
            break
        except PlaywrightTimeoutError:
            continue

    if not captured:
        # Fallback: full-page screenshot is still better than bad monitor-space clipping.
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Saved full-page fallback screenshot as {screenshot_path}")

    text = get_captcha_instruction_text(page)
    words = re.findall(r"\b\w+\b", text)

    indexes_to_click = main(words, screenshot_path)
    print(f"indexes_to_click from vision: {indexes_to_click}")

    for i in indexes_to_click:
        click_nth_canvas_button(page, i)
        print(f"Clicked canvas button index {i}")
        _human_delay(0.5, 1.5)

    click_confirm_button(page)
    _human_delay(5.0, 8.0)

    if _round >= max_rounds:
        return
    if page.locator("#amzn-btn-verify-internal").count() > 0:
        print("Found #amzn-btn-verify-internal button; retrying captcha round.")
        run_post_load_captcha_and_screenshot(
            page,
            screenshot_path=screenshot_path,
            _round=_round + 1,
            max_rounds=max_rounds,
        )


MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

def _image_to_data_url(path: Path) -> str:
    mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
    b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def instruction_words_from_text(text: str) -> list[str]:
    """Tokenize like the ``<em>`` text from the captcha page (``re.findall(r'\\b\\w+\\b', text)``)."""
    return re.findall(r"\b\w+\b", text.strip())


def _ints_from_json_obj(data: dict[str, Any]) -> list[int] | None:
    for key in ("tile_numbers", "tiles", "numbers", "answer"):
        if key in data and isinstance(data[key], list):
            out: list[int] = []
            for x in data[key]:
                if isinstance(x, bool):
                    continue
                try:
                    n = int(x)
                except (TypeError, ValueError):
                    continue
                if 1 <= n <= 9:
                    out.append(n)
            return sorted(set(out))
    return None


def _parse_numbers_from_text(text: str) -> list[int]:
    text = text.strip()
    if not text:
        return []
    # Strip optional ```json ... ``` wrapper
    fence = re.match(r"^```(?:json)?\s*(.*)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            from_obj = _ints_from_json_obj(data)
            if from_obj is not None:
                return from_obj
        if isinstance(data, list):
            outl: list[int] = []
            for x in data:
                if isinstance(x, bool):
                    continue
                try:
                    outl.append(int(x))
                except (TypeError, ValueError):
                    continue
            return outl
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return [int(m) for m in re.findall(r"\b\d+\b", text)]

def get_numbers_from_image(
    image_path: str | Path,
    *,
    model: str | None = None,
    prompt: str | None = None,
    instruction_text: str | None = None,
) -> list[int]:
    """
    Upload an image to OpenAI (vision) and return integers found in the model output.

    With ``instruction_text``, uses a captcha-focused system prompt, JSON output,
    ``detail: high`` for the image, and ``temperature=0``. Default model is
    ``OPENAI_VISION_MODEL`` or ``gpt-4o`` (stronger than mini).

    Expects ``OPENAI_API_KEY`` in the environment or ``.env``.
    """
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or .env file."
        )

    effective_model = model or DEFAULT_VISION_MODEL

    default_prompt = (
        "Look at this image. Extract every standalone digit or whole number that "
        "matters for a puzzle or captcha (e.g. tile labels 1–9). "
        "Respond with ONLY a JSON array of integers in reading order "
        "(top-left to bottom-right for a grid), e.g. [3,5,9]. Use [] if none."
    )

    image_part = {
        "type": "image_url",
        "image_url": {"url": _image_to_data_url(path), "detail": "high"},
    }

    client = OpenAI()

    if instruction_text is not None and instruction_text.strip():
        user_body = _captcha_user_prompt(instruction_text)
        if prompt:
            user_body = f"{prompt}\n\n{user_body}"
        response = client.chat.completions.create(
            model=effective_model,
            messages=[
                {"role": "system", "content": CAPTCHA_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_body},
                        image_part,
                    ],
                },
            ],
            temperature=0,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
    else:
        user_text = prompt or default_prompt
        response = client.chat.completions.create(
            model=effective_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        image_part,
                    ],
                }
            ],
            temperature=0,
            max_tokens=400,
        )

    text = (response.choices[0].message.content or "").strip()
    return _parse_numbers_from_text(text)


def tile_labels_to_click_indexes(tile_labels: Iterable[Any]) -> list[int]:
    """Turn model tile NUMBERS (1–9 on buttons) into 0-based ``indexes_to_click`` for Playwright ``.nth(i)``."""
    indexes: list[int] = []
    for raw in tile_labels:
        try:
            if isinstance(raw, str):
                raw = raw.strip()
            n = int(raw)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 9:
            indexes.append(n - 1)
    return sorted(set(indexes))

def main(
    words: list[str],
    image: str | Path,
    *,
    model: str | None = None,
) -> list[int]:
    """
    Vision step: ``words`` from captcha ``<em>``; returns 0-based indices for ``click_nth_canvas_button``.
    """
    if not words:
        return []
    instruction = " ".join(words)
    labels = get_numbers_from_image(
        image,
        model=model,
        instruction_text=instruction,
    )
    return tile_labels_to_click_indexes(labels)

def cli() -> None:
    parser = argparse.ArgumentParser(description="Extract numbers from an image via OpenAI vision.")
    parser.add_argument("image", type=Path, help="Path to an image file (png, jpg, webp, ...)")
    parser.add_argument(
        "--model",
        default=None,
        metavar="NAME",
        help=(
            "Vision model (default: OPENAI_VISION_MODEL env or gpt-4o — use gpt-4o-mini for cheaper runs)"
        ),
    )
    parser.add_argument(
        "--phrase",
        default=None,
        metavar="TEXT",
        help=(
            "Captcha instruction (same as page <em> text). "
            "Tokenized like the runner; stdout is 0-based tile indexes for Playwright .nth(i)."
        ),
    )
    args = parser.parse_args()

    image_path = args.image.expanduser()
    if not image_path.is_file():
        print(f"error: image not found: {image_path}", file=sys.stderr)
        raise SystemExit(1)

    phrase = (args.phrase or "").strip()
    try:
        if phrase:
            words = instruction_words_from_text(phrase)
            indexes = main(words, image_path, model=args.model)
            print(", ".join(map(str, indexes)))
        else:
            numbers = get_numbers_from_image(image_path, model=args.model)
            print(json.dumps(numbers))
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except RateLimitError as e:
        print("error: OpenAI rate limit or quota exceeded.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        raise SystemExit(1) from e
    except APIStatusError as e:
        print(f"error: OpenAI API {e.status_code}: {e.message}", file=sys.stderr)
        raise SystemExit(1) from e
    except APIConnectionError as e:
        print("error: could not reach OpenAI API.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        raise SystemExit(1) from e
