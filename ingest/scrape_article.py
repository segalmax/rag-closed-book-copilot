"""
Extract clean markdown text from a URL and save to kb/raw/<url-path>.md
mirroring the URL path structure, e.g.:
  https://www.hellointerview.com/learn/system-design/in-a-hurry/introduction
  → kb/raw/learn/system-design/in-a-hurry/introduction.md
"""
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import trafilatura


KB_RAW_DIR = Path(__file__).parent.parent / "kb" / "raw"


def parse_args():
    p = argparse.ArgumentParser(description="Scrape article text to KB markdown")
    p.add_argument("--url", required=True, help="Article URL to scrape")
    return p.parse_args()


def path_from_url(url: str) -> Path:
    parts = urlparse(url).path.strip("/").split("/")
    return KB_RAW_DIR.joinpath(*parts[:-1]) / f"{parts[-1]}.md"


def extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def clean_markdown(markdown: str) -> str:
    """Remove common nav/footer noise lines left by trafilatura."""
    noise = {"Search", "⌘K", "Mark as read", "On This Page", "Schedule a mock interview",
             "Your account is free and you can post anonymously if you choose."}
    lines = markdown.splitlines()
    cleaned = [l for l in lines if l.strip() not in noise]
    return "\n".join(cleaned).strip()


def fetch_markdown(url: str):
    html = trafilatura.fetch_url(url)
    if not html:
        raise ValueError(f"Failed to fetch HTML from {url}")

    markdown = trafilatura.extract(html, output_format="markdown", include_tables=True,
                                   favor_precision=True)
    if not markdown:
        raise ValueError(f"trafilatura returned empty content for {url}")

    markdown = clean_markdown(markdown)
    title = extract_title(markdown)
    return title, markdown


def build_frontmatter(url: str, title: str) -> str:
    return (
        f"---\n"
        f"url: {url}\n"
        f"title: {title}\n"
        f"scraped_at: {datetime.utcnow().isoformat()}Z\n"
        f"---\n\n"
    )


def save(out_path: Path, content: str) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    args = parse_args()
    url = args.url
    out_path = path_from_url(url)

    print(f"Fetching: {url}")
    title, markdown = fetch_markdown(url)

    content = build_frontmatter(url, title) + markdown
    out_path = save(out_path, content)

    print(f"Saved to: {out_path}")
    print(f"\n--- Preview (first 800 chars) ---\n{content[:800]}")


if __name__ == "__main__":
    main()
