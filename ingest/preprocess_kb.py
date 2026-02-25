"""
Clean preprocessing for RAG using LangChain splitters.

Pipeline:
1) Parse markdown files + YAML frontmatter
2) Split into sections with MarkdownHeaderTextSplitter
3) Split sections into token-aware chunks with RecursiveCharacterTextSplitter
4) Write JSONL artifacts:
   - kb/processed/sections.jsonl
   - kb/processed/chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import tiktoken
import yaml
import langchain_text_splitters


DEFAULT_RAW_DIR = Path(__file__).parent.parent / "kb" / "raw"
DEFAULT_PROCESSED_DIR = Path(__file__).parent.parent / "kb" / "processed"


def parse_args():
    parser = argparse.ArgumentParser(description="Preprocess KB into sections and chunks")
    parser.add_argument("--raw_dir", default=str(DEFAULT_RAW_DIR), help="Input raw markdown root")
    parser.add_argument(
        "--processed_dir",
        default=str(DEFAULT_PROCESSED_DIR),
        help="Output directory for JSONL files",
    )
    parser.add_argument("--chunk_size", type=int, default=700, help="Chunk size in tokens")
    parser.add_argument("--chunk_overlap", type=int, default=120, help="Chunk overlap in tokens")
    parser.add_argument(
        "--encoding_name",
        default="cl100k_base",
        help="Tokenizer encoding name for chunk sizing",
    )
    return parser.parse_args()


def split_frontmatter_and_body(text: str):
    if not text.startswith("---\n"):
        raise ValueError("Missing YAML frontmatter start")
    _, rest = text.split("---\n", 1)
    frontmatter_text, body = rest.split("\n---\n", 1)
    return frontmatter_text, body


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_section_title(metadata: dict, fallback_title: str) -> tuple[str, int]:
    h1 = metadata.get("h1", "").strip()
    h2 = metadata.get("h2", "").strip()
    h3 = metadata.get("h3", "").strip()
    if h3:
        return h3, 3
    if h2:
        return h2, 2
    if h1:
        return h1, 1
    return fallback_title or "Untitled", 0


def get_section_path(metadata: dict, fallback_title: str) -> str:
    headers = [metadata.get("h1", "").strip(), metadata.get("h2", "").strip(), metadata.get("h3", "").strip()]
    headers = [h for h in headers if h]
    if headers:
        return " > ".join(headers)
    return fallback_title or "Untitled"


def build_splitters(chunk_size: int, chunk_overlap: int, encoding_name: str):
    section_splitter = langchain_text_splitters.MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    chunk_splitter = langchain_text_splitters.RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoding_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    return section_splitter, chunk_splitter


def iter_markdown_files(raw_dir: Path):
    files = sorted(raw_dir.rglob("*.md"))
    if not files:
        raise ValueError(f"No markdown files found under {raw_dir}")
    return files


def preprocess_file(path: Path, raw_dir: Path, section_splitter, chunk_splitter, encoder):
    text = path.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter_and_body(text)
    metadata = yaml.safe_load(fm_text) or {}
    body = normalize_text(body)

    doc_id = str(path.relative_to(raw_dir))
    title = str(metadata.get("title", "")).strip()
    url = str(metadata.get("url", "")).strip()

    section_docs = section_splitter.split_text(body)
    if not section_docs:
        raise ValueError(f"Section splitter produced no output for {path}")

    sections = []
    chunks = []
    for section_idx, section_doc in enumerate(section_docs, start=1):
        section_text = normalize_text(section_doc.page_content)
        if not section_text:
            continue

        section_title, section_level = get_section_title(section_doc.metadata, title)
        section_path = get_section_path(section_doc.metadata, title)
        section_id = f"{doc_id}::section-{section_idx:03d}"
        section_tokens = len(encoder.encode(section_text))

        sections.append(
            {
                "section_id": section_id,
                "doc_id": doc_id,
                "source_path": str(path),
                "url": url,
                "title": title,
                "section_title": section_title,
                "section_path": section_path,
                "section_level": section_level,
                "token_count": section_tokens,
                "text": section_text,
            }
        )

        chunk_docs = chunk_splitter.create_documents([section_text])
        for chunk_idx, chunk_doc in enumerate(chunk_docs, start=1):
            chunk_text = normalize_text(chunk_doc.page_content)
            if not chunk_text:
                continue
            chunk_id = f"{section_id}::chunk-{chunk_idx:03d}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "section_id": section_id,
                    "doc_id": doc_id,
                    "source_path": str(path),
                    "url": url,
                    "title": title,
                    "section_title": section_title,
                    "section_path": section_path,
                    "token_count": len(encoder.encode(chunk_text)),
                    "text": chunk_text,
                }
            )

    return sections, chunks


def write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    sections_file = processed_dir / "sections.jsonl"
    chunks_file = processed_dir / "chunks.jsonl"

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory not found: {raw_dir}")

    section_splitter, chunk_splitter = build_splitters(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        encoding_name=args.encoding_name,
    )
    encoder = tiktoken.get_encoding(args.encoding_name)

    all_sections = []
    all_chunks = []
    for md_file in iter_markdown_files(raw_dir):
        sections, chunks = preprocess_file(
            md_file,
            raw_dir,
            section_splitter,
            chunk_splitter,
            encoder,
        )
        all_sections.extend(sections)
        all_chunks.extend(chunks)

    write_jsonl(sections_file, all_sections)
    write_jsonl(chunks_file, all_chunks)

    print(f"Processed files: {len(iter_markdown_files(raw_dir))}")
    print(f"Sections: {len(all_sections)} -> {sections_file}")
    print(f"Chunks: {len(all_chunks)} -> {chunks_file}")
    if all_chunks:
        avg_tokens = sum(c["token_count"] for c in all_chunks) / len(all_chunks)
        print(f"Avg chunk tokens: {avg_tokens:.1f}")


if __name__ == "__main__":
    main()
