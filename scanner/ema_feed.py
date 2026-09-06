"""Pharma Radar — EMA primary regulatory feed."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from urllib.parse import urljoin

import requests

EMA_NEWS_RSS_URL = "https://www.ema.europa.eu/en/news.xml"
EMA_BASE_URL = "https://www.ema.europa.eu"
REQUEST_TIMEOUT = 20
USER_AGENT = "PharmaRadar/1.0"


def normalize_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


def normalize_date(value):
    if not value:
        return None
    text = normalize_text(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).isoformat()
        except ValueError:
            continue
    return text


def _field(fields, *names):
    for name in names:
        value = fields.get(name)
        if value:
            return value
    return ""


def build_ema_news_item(title, url, published_at=None, summary=""):
    title = normalize_text(title)
    url = urljoin(EMA_BASE_URL, normalize_text(url))
    summary = normalize_text(summary)
    item = {
        "source": "EMA",
        "source_type": "PRIMARY_REGULATORY",
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": normalize_date(published_at),
    }
    raw = "|".join((title, url, str(item["published_at"] or "")))
    item["item_id"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return item


def parse_ema_rss(xml_content, max_items=50):
    if not xml_content:
        return []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []
    results = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() != "item":
            continue
        fields = {}
        for child in list(node):
            key = child.tag.rsplit("}", 1)[-1].lower()
            fields[key] = normalize_text(child.text or "")
        title = _field(fields, "title")
        url = _field(fields, "link", "guid")
        if not title or not url:
            continue
        results.append(build_ema_news_item(
            title,
            url,
            _field(fields, "pubdate", "published", "date", "dc:date"),
            _field(fields, "description", "summary", "content"),
        ))
        if len(results) >= max_items:
            break
    return results


def get_ema_news(max_items=50):
    try:
        response = requests.get(
            EMA_NEWS_RSS_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/xml,text/xml"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"EMA FEED ERROR: {type(exc).__name__}: {exc}", flush=True)
        return []
    return parse_ema_rss(response.text, max_items=max_items)
