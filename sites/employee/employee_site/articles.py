from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from html import unescape
from pathlib import Path

import markdown

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "articles"

ARTICLE_INDEX: tuple[dict[str, object], ...] = (
    {
        "slug": "employment-rules",
        "title": "就業規則（抜粋）",
        "category": "人事",
        "tags": ("就業規則", "勤務時間", "休暇"),
        "summary": "勤務時間・休暇・服務規律の要点をまとめた抜粋版です。",
    },
    {
        "slug": "expense-reimbursement",
        "title": "経費精算ガイド",
        "category": "経理",
        "tags": ("経費精算", "領収書", "交通費"),
        "summary": "申請手順、領収書の要件、承認フローの流れを説明します。",
    },
    {
        "slug": "remote-work",
        "title": "リモートワーク規程",
        "category": "人事",
        "tags": ("リモートワーク", "在宅勤務", "セキュリティ"),
        "summary": "在宅勤務の申請条件と情報セキュリティ上の注意点です。",
    },
    {
        "slug": "it-support",
        "title": "IT サポート窓口",
        "category": "IT",
        "tags": ("IT", "パスワード", "端末"),
        "summary": "社内システム・端末に関する問い合わせ先と一次対応の手順です。",
    },
)


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    category: str
    tags: tuple[str, ...]
    summary: str
    body_html: str
    body_text: str


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _load_body(slug: str) -> tuple[str, str]:
    path = CONTENT_DIR / f"{slug}.md"
    if not path.is_file():
        return "<p>記事本文が見つかりません。</p>", ""
    raw = path.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        raw,
        extensions=["extra", "sane_lists", "tables", "nl2br"],
    )
    return body_html, _strip_html(body_html)


@lru_cache
def load_articles() -> tuple[Article, ...]:
    articles: list[Article] = []
    for meta in ARTICLE_INDEX:
        slug = str(meta["slug"])
        body_html, body_text = _load_body(slug)
        articles.append(
            Article(
                slug=slug,
                title=str(meta["title"]),
                category=str(meta["category"]),
                tags=tuple(str(t) for t in meta["tags"]),  # type: ignore[arg-type]
                summary=str(meta["summary"]),
                body_html=body_html,
                body_text=body_text,
            )
        )
    return tuple(articles)


def get_article(slug: str) -> Article | None:
    for article in load_articles():
        if article.slug == slug:
            return article
    return None


def search_articles(query: str) -> list[Article]:
    q = query.strip().lower()
    if not q:
        return []
    results: list[Article] = []
    for article in load_articles():
        haystack = " ".join(
            [
                article.title,
                article.summary,
                article.category,
                " ".join(article.tags),
                article.body_text,
            ]
        ).lower()
        if q in haystack:
            results.append(article)
    return results
