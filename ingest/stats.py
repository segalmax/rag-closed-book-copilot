import json
from pathlib import Path
from collections import defaultdict

CHUNKS_FILE = Path("kb/processed/chunks.jsonl")
SECTIONS_FILE = Path("kb/processed/sections.jsonl")


def compute_stats(chunks, sections=None):
    """Pure function: chunks -> stats dict. Chunks from chunks.jsonl or index_meta.json.
    If sections (list of section dicts with doc_id) is provided, use it for section count;
    otherwise derive from unique section_id in chunks (sections with ≥1 chunk)."""
    doc_stats = defaultdict(lambda: {"title": "Unknown", "section_count": 0, "chunks": 0, "chunk_tokens": []})
    for c in chunks:
        doc_id = c.get("doc_id", "unknown")
        doc_stats[doc_id]["chunks"] += 1
        doc_stats[doc_id]["chunk_tokens"].append(c.get("token_count", 0))
        doc_stats[doc_id]["title"] = c.get("title", "Unknown")

    if sections:
        for s in sections:
            doc_stats[s.get("doc_id", "unknown")]["section_count"] += 1
    else:
        section_ids_by_doc = defaultdict(set)
        for c in chunks:
            sid = c.get("section_id")
            if sid:
                section_ids_by_doc[c.get("doc_id", "unknown")].add(sid)
        for doc_id, sids in section_ids_by_doc.items():
            doc_stats[doc_id]["section_count"] = len(sids)
    rows = []
    for doc_id, s in doc_stats.items():
        toks = s["chunk_tokens"]
        total_tok = sum(toks)
        avg_tok = total_tok / len(toks) if toks else 0
        rows.append({
            "File": doc_id.split("/")[-1],
            "Title": s["title"],
            "Sections": s["section_count"],
            "Chunks": s["chunks"],
            "Total Tok": total_tok,
            "Avg Tok/Chunk": round(avg_tok, 1),
            "Max Tok": max(toks) if toks else 0,
        })
    rows.sort(key=lambda x: x["Total Tok"], reverse=True)
    total_chunks = sum(r["Chunks"] for r in rows)
    total_tokens = sum(r["Total Tok"] for r in rows)
    return {
        "rows": rows,
        "total_docs": len(rows),
        "total_chunks": total_chunks,
        "total_tokens": total_tokens,
        "avg_tokens_per_chunk": total_tokens / total_chunks if total_chunks else 0,
    }


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    if not CHUNKS_FILE.exists():
        print("Processed files not found. Run preprocess_kb.py first.")
        return

    chunks_data = load_jsonl(CHUNKS_FILE)
    sections_data = load_jsonl(SECTIONS_FILE) if SECTIONS_FILE.exists() else None
    stats = compute_stats(chunks_data, sections=sections_data)

    # Print markdown table manually to avoid pandas dep
    headers = ["File", "Title", "Sections", "Chunks", "Total Tok", "Avg Tok/Chunk", "Max Tok"]
    widths = [30, 40, 10, 8, 10, 15, 8]
    
    # Format header
    header_str = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, widths)) + " |"
    separator_str = "| " + " | ".join("-" * w for w in widths) + " |"
    
    print(header_str)
    print(separator_str)
    
    for row in stats["rows"]:
        title = str(row["Title"])
        title = title[:37] + "..." if len(title) > 37 else title
        vals = [
            str(row["File"]),
            title,
            str(row["Sections"]),
            str(row["Chunks"]),
            str(row["Total Tok"]),
            str(row["Avg Tok/Chunk"]),
            str(row["Max Tok"])
        ]
        line = "| " + " | ".join(f"{v:<{w}}" for v, w in zip(vals, widths)) + " |"
        print(line)

    print("\n--- Global Stats ---")
    print(f"Total Documents: {stats['total_docs']}")
    print(f"Total Chunks: {stats['total_chunks']}")
    print(f"Total Tokens: {stats['total_tokens']}")
    print(f"Avg Tokens per Chunk: {stats['avg_tokens_per_chunk']:.1f}")

if __name__ == "__main__":
    main()
