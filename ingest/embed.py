import json
import datetime
import numpy as np
import faiss
import pathlib
import sentence_transformers
import argparse

# Configuration
CHUNKS_FILE = pathlib.Path("kb/processed/chunks.jsonl")
INDEX_FILE = pathlib.Path("kb/index.faiss")
META_FILE = pathlib.Path("kb/index_meta.json")
MODEL_NAME = 'mixedbread-ai/mxbai-embed-large-v1'

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-context", action="store_true", help="Disable contextual chunking (title prepending)")
    return parser.parse_args()

def load_chunks():
    path = CHUNKS_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run preprocess_kb.py first.")
    
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def main():
    args = parse_args()

    print(f"Loading chunks from {CHUNKS_FILE}...")
    try:
        chunks = load_chunks()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print(f"Loaded {len(chunks)} chunks.")

    print(f"Loading model '{MODEL_NAME}' from Hugging Face...")
    try:
        model = sentence_transformers.SentenceTransformer(MODEL_NAME)
    except Exception as e:
        print(f"Failed to download/load model: {e}")
        return
    
    print("Generating embeddings (this may take a moment)...")
    
    if args.no_context:
        print("Mode: Standard Chunking (Text only)")
        texts = [c["text"] for c in chunks]
    else:
        print("Mode: Contextual Chunking (Title > Section: Text)")
        texts = [f"{c['title']} > {c['section_title']}: {c['text']}" for c in chunks]

    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    # CAST TO FLOAT32 FOR FAISS
    embeddings = embeddings.astype(np.float32)
    
    # L2 normalize embeddings for Cosine Similarity search with IndexFlatIP
    faiss.normalize_L2(embeddings)
    
    dimension = embeddings.shape[1]
    print(f"Embedding dimension: {dimension}")

    print("Building FAISS index...")
    # IndexFlatIP = Exact search using Inner Product (Cosine Similarity since we normalized)
    index = faiss.IndexFlatIP(dimension) 
    index.add(embeddings)
    
    print(f"Index contains {index.ntotal} vectors.")

    print(f"Saving index to {INDEX_FILE}...")
    faiss.write_index(index, str(INDEX_FILE))
    
    print(f"Saving metadata to {META_FILE}...")
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    embed_manifest = {
        "model": MODEL_NAME,
        "dimension": dimension,
        "num_chunks": len(chunks),
        "contextual": not args.no_context,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    manifest_path = pathlib.Path("kb/embed_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(embed_manifest, f, indent=2)
    print(f"Saved embed manifest to {manifest_path}")

    print("Done!")

if __name__ == "__main__":
    main()
