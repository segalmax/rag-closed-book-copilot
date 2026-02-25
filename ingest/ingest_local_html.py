"""
Convert locally saved .html files into KB markdown.

Usage: python ingest/ingest_local_html.py
"""
from pathlib import Path
import trafilatura

from scrape_article import KB_RAW_DIR, extract_title, save

DOWNLOADS = Path("/Users/segalmax/Downloads")
KB_BASE = "learn/system-design"

# filename prefix → (section, slug, url-path)
MAPPING = [
    ("API Gateway Deep Dive",          "key-technologies", "api-gateway"),
    ("Cassandra Deep Dive",            "key-technologies", "cassandra"),
    ("Consistent Hashing",             "core-concepts",    "consistent-hashing"),
    ("Database Indexing",              "core-concepts",    "db-indexing"),
    ("DynamoDB Deep Dive",             "key-technologies", "dynamodb"),
    ("Elasticsearch Deep Dive",        "key-technologies", "elasticsearch"),
    ("Flink Deep Dive",                "key-technologies", "flink"),
    ("Kafka Deep Dive",                "key-technologies", "kafka"),
    ("Numbers to Know",                "core-concepts",    "numbers-to-know"),
    ("PostgreSQL Deep Dive",           "key-technologies", "postgresql"),
    ("Real-time Updates Pattern",      "patterns",         "realtime-updates"),
    ("Redis Deep Dive",                "key-technologies", "redis"),
    ("Sharding in System Design",      "core-concepts",    "sharding"),
    ("Vector Databases Deep Dive",     "advanced-topics",  "vector-databases"),
    ("ZooKeeper Deep Dive",            "key-technologies", "zookeeper"),
]

BASE_URLS = {
    "core-concepts":    "https://www.hellointerview.com/learn/system-design/core-concepts",
    "key-technologies": "https://www.hellointerview.com/learn/system-design/key-technologies",
    "patterns":         "https://www.hellointerview.com/learn/system-design/patterns",
    "advanced-topics":  "https://www.hellointerview.com/learn/system-design/advanced-topics",
}


def find_html_file(prefix: str) -> Path:
    for html_file in DOWNLOADS.glob("*.html"):
        if html_file.name.startswith(prefix):
            return html_file
    raise FileNotFoundError(f"No HTML file starting with: {prefix!r}")


def html_to_markdown(html_path: Path) -> tuple:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    markdown = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        favor_precision=True,
    )
    if not markdown:
        raise ValueError(f"trafilatura returned empty content for {html_path.name}")
    title = extract_title(markdown)
    return title, markdown.strip()


def kb_path(section: str, slug: str) -> Path:
    return KB_RAW_DIR / KB_BASE / section / f"{slug}.md"


def build_frontmatter(url: str, title: str) -> str:
    from datetime import datetime
    return (
        f"---\n"
        f"url: {url}\n"
        f"title: {title}\n"
        f"free: true\n"
        f"scraped_at: {datetime.utcnow().isoformat()}Z\n"
        f"---\n\n"
    )


def main():
    for prefix, section, slug in MAPPING:
        html_file = find_html_file(prefix)
        title, markdown = html_to_markdown(html_file)
        url = f"{BASE_URLS[section]}/{slug}"
        content = build_frontmatter(url, title) + markdown
        out_path = kb_path(section, slug)
        save(out_path, content)
        print(f"OK  {section}/{slug}.md  ({len(markdown)} chars)")


if __name__ == "__main__":
    main()
