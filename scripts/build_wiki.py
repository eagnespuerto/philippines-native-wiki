"""Fetch Wikipedia summaries + Wikimedia Commons lead images for every entry
in `seed.SPECIES` and emit `data/species.json` plus compressed JPEGs under
`data/images/`.

Usage:
    python scripts/build_wiki.py [--only ID1,ID2]  [--force]

Options:
    --only  Rebuild only the listed species ids (comma-separated).
    --force Refetch even if data/species.json already has the entry.

The build is idempotent: re-running keeps existing images unless --force.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed import SPECIES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
IMAGE_DIR = DATA_DIR / "images"
SPECIES_JSON = DATA_DIR / "species.json"

USER_AGENT = (
    "PhilippinesNativeWikiBuild/1.0 "
    "(https://github.com/eagnespuerto/philippines-native-wiki; build script)"
)

MAX_IMAGE_BYTES = 1_000_000        # 1 MB
MAX_IMAGE_DIMENSION = 1200         # px on the long side
JPEG_QUALITY_START = 88
JPEG_QUALITY_MIN = 35
JPEG_QUALITY_STEP = 7

REQUEST_TIMEOUT = 30
POLITE_DELAY_SECONDS = 0.4


def ua_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    s.headers["Accept"] = "application/json"
    return s


def wiki_summary(session: requests.Session, title: str) -> dict[str, Any] | None:
    """Fetch the REST v1 summary for a Wikipedia article title."""
    slug = urllib.parse.quote(title.replace(" ", "_"), safe="_()")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    r = session.get(url, timeout=REQUEST_TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def commons_image_info(session: requests.Session, image_title: str) -> dict[str, Any]:
    """Look up author + license for a File: image via the MediaWiki API."""
    if not image_title.startswith("File:"):
        image_title = "File:" + image_title
    params = {
        "action": "query",
        "prop": "imageinfo",
        "iiprop": "extmetadata|url",
        "titles": image_title,
        "format": "json",
        "formatversion": "2",
    }
    url = "https://commons.wikimedia.org/w/api.php"
    r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    pages = data.get("query", {}).get("pages", [])
    if not pages or "imageinfo" not in pages[0]:
        return {}
    info = pages[0]["imageinfo"][0]
    meta = info.get("extmetadata", {})

    def val(key: str) -> str:
        v = meta.get(key, {}).get("value")
        if not v:
            return ""
        return re.sub(r"<[^>]+>", "", str(v)).strip()

    return {
        "url": info.get("url"),
        "artist": val("Artist"),
        "license": val("LicenseShortName") or val("License"),
        "credit": val("Credit"),
        "description": val("ImageDescription"),
    }


def compress_image(raw: bytes, out_path: Path) -> int:
    """Compress arbitrary image bytes to a JPEG under MAX_IMAGE_BYTES.

    Returns the final file size in bytes. Raises on failure.
    """
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        elif im.mode == "L":
            im = im.convert("RGB")

        w, h = im.size
        long_side = max(w, h)
        if long_side > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / long_side
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        quality = JPEG_QUALITY_START
        while True:
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
            size = buf.tell()
            if size <= MAX_IMAGE_BYTES or quality <= JPEG_QUALITY_MIN:
                out_path.write_bytes(buf.getvalue())
                return size
            quality -= JPEG_QUALITY_STEP


def download_image(session: requests.Session, url: str) -> bytes:
    r = session.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.content


def image_title_from_summary(summary: dict[str, Any]) -> str | None:
    """Extract the raw File: title of the lead image from a REST summary."""
    orig = summary.get("originalimage") or summary.get("thumbnail") or {}
    src = orig.get("source")
    if not src:
        return None
    # e.g. https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Foo.jpg/800px-Foo.jpg
    # or   https://upload.wikimedia.org/wikipedia/commons/a/aa/Foo.jpg
    m = re.search(r"/wikipedia/(?:commons|en)/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+?)(?:/\d+px-[^/]+)?$", src)
    if not m:
        return None
    return "File:" + urllib.parse.unquote(m.group(1))


def load_existing() -> dict[str, dict[str, Any]]:
    if not SPECIES_JSON.exists():
        return {}
    try:
        data = json.loads(SPECIES_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {e["id"]: e for e in data.get("species", [])}


def build(only: set[str] | None, force: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    session = ua_session()
    existing = load_existing()
    results: list[dict[str, Any]] = []
    warnings: list[str] = []

    for i, seed in enumerate(SPECIES, 1):
        sid = seed["id"]
        if only and sid not in only:
            if sid in existing:
                results.append(existing[sid])
            continue

        if not force and sid in existing and existing[sid].get("summary"):
            results.append(existing[sid])
            print(f"[{i:2d}/60] skip (cached) {sid}")
            continue

        title = seed["wikipediaTitle"]
        print(f"[{i:2d}/60] fetch {sid}  ({title})")
        record = {k: v for k, v in seed.items() if k != "wikipediaTitle"}

        try:
            summary = wiki_summary(session, title)
        except requests.RequestException as e:
            warnings.append(f"{sid}: summary request failed: {e}")
            summary = None

        if summary:
            record["summary"] = summary.get("extract", "").strip()
            record["wikipediaUrl"] = summary.get("content_urls", {}).get("desktop", {}).get("page") \
                or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"

            image_url = None
            orig = summary.get("originalimage") or summary.get("thumbnail")
            if orig:
                image_url = orig.get("source")

            if image_url:
                try:
                    raw = download_image(session, image_url)
                    img_path = IMAGE_DIR / f"{sid}.jpg"
                    size = compress_image(raw, img_path)
                    record["imageFile"] = f"images/{img_path.name}"
                    record["imageBytes"] = size

                    file_title = image_title_from_summary(summary)
                    if file_title:
                        time.sleep(POLITE_DELAY_SECONDS)
                        try:
                            info = commons_image_info(session, file_title)
                            credit_bits = [b for b in (info.get("artist"), info.get("license")) if b]
                            record["imageCredit"] = " / ".join(credit_bits) if credit_bits else "Wikimedia Commons"
                            record["imageSourceUrl"] = info.get("url") or image_url
                        except requests.RequestException as e:
                            warnings.append(f"{sid}: commons metadata failed: {e}")
                            record["imageCredit"] = "Wikimedia Commons"
                            record["imageSourceUrl"] = image_url
                    else:
                        record["imageCredit"] = "Wikimedia Commons"
                        record["imageSourceUrl"] = image_url
                except (requests.RequestException, OSError, Image.UnidentifiedImageError) as e:
                    warnings.append(f"{sid}: image handling failed: {e}")
                    record["imageFile"] = None
            else:
                warnings.append(f"{sid}: no image in summary payload")
                record["imageFile"] = None
        else:
            warnings.append(f"{sid}: Wikipedia article not found for '{title}'")
            record["summary"] = ""
            record["wikipediaUrl"] = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            record["imageFile"] = None

        results.append(record)
        time.sleep(POLITE_DELAY_SECONDS)

    # Preserve seed ordering
    seed_order = {s["id"]: i for i, s in enumerate(SPECIES)}
    results.sort(key=lambda r: seed_order.get(r["id"], 9999))

    SPECIES_JSON.write_text(
        json.dumps({"species": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Wrote {SPECIES_JSON} with {len(results)} species")
    print(f"Image dir: {IMAGE_DIR}")
    if warnings:
        print()
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", help="Comma-separated species ids to (re)build")
    p.add_argument("--force", action="store_true", help="Ignore cache and refetch")
    args = p.parse_args()

    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    build(only=only, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
