import json
import numpy as np
import faiss
import umap
import sklearn.decomposition
import plotly.express as px
import pandas as pd
from pathlib import Path
import argparse
import datetime

# Config
INDEX_FILE = Path("kb/index.faiss")
CHUNKS_FILE = Path("kb/processed/chunks.jsonl")
EMBED_CONFIG_FILE = Path("kb/embed_manifest.json")

def load_data():
    if not INDEX_FILE.exists() or not CHUNKS_FILE.exists():
        raise FileNotFoundError("Index or chunks not found.")
    if not EMBED_CONFIG_FILE.exists():
        raise FileNotFoundError("kb/embed_manifest.json not found. Re-run embed.py first.")

    index = faiss.read_index(str(INDEX_FILE))
    vectors = index.reconstruct_n(0, index.ntotal)

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]

    with open(EMBED_CONFIG_FILE, "r", encoding="utf-8") as f:
        embed_manifest = json.load(f)

    return vectors, chunks, embed_manifest

def extract_category(doc_id):
    # doc_id example: "learn/system-design/key-technologies/redis.md"
    # We want "redis" or the title
    path = Path(doc_id)
    return path.stem.replace("-", " ").title() # e.g. "redis.md" -> "Redis"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", type=str, default="default", help="Short description tag for filename")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Create output directory
    viz_dir = Path("kb/visualizations")
    viz_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = viz_dir / f"viz_{timestamp}_{args.tag}.html"

    print("Loading data...")
    vectors, chunks, embed_manifest = load_data()
    print(f"Loaded {len(vectors)} vectors.")

    print("Running UMAP dimensionality reduction (to 3D)...")
    reducer = umap.UMAP(n_components=3, random_state=42, metric='cosine')
    projections = reducer.fit_transform(vectors)

    pca = sklearn.decomposition.PCA(n_components=3, random_state=42)
    projections = pca.fit_transform(projections)

    print("Preparing plot...")
    data = []
    for i, chunk in enumerate(chunks):
        category = extract_category(chunk["doc_id"])
        text_snippet = chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
        data.append({
            "x": projections[i, 0],
            "y": projections[i, 1],
            "z": projections[i, 2],
            "Title": chunk["title"],
            "Category": category,
            "Snippet": text_snippet,
            "DocID": chunk["doc_id"]
        })

    df = pd.DataFrame(data)

    dimension = vectors.shape[1]
    num_chunks = len(chunks)
    contextual = embed_manifest.get("contextual", True)
    model_name = embed_manifest["model"]

    subtitle = (
        f"Model: {model_name} | Dims: {dimension} | "
        f"Chunks: {num_chunks} | Contextual: {'Yes' if contextual else 'No'}"
    )

    print("Generating interactive 3D plot...")
    fig = px.scatter_3d(
        df,
        x='x', y='y', z='z',
        color='Category',
        hover_data=["Title", "DocID", "Snippet"],
        title=f"RAG Clusters ({args.tag})<br><sup>{subtitle}</sup>",
        opacity=0.7,
        size_max=10,
        color_discrete_sequence=px.colors.qualitative.Dark24,
    )
    fig.update_traces(marker=dict(size=4))

    # Fixed camera so initial view is same across all visualizations
    fig.update_layout(
        scene=dict(
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.2),
                center=dict(x=0, y=0, z=0),
                up=dict(x=0, y=0, z=1),
            )
        )
    )

    print(f"Saving to {output_filename}...")
    fig.write_html(str(output_filename))

    metadata = {
        "tag": args.tag,
        "timestamp": timestamp,
        "html_file": output_filename.name,
        "model": model_name,
        "dimension": dimension,
        "num_chunks": num_chunks,
        "contextual": contextual,
        "embed_timestamp": embed_manifest.get("timestamp", "unknown"),
    }
    json_filename = viz_dir / f"viz_{timestamp}_{args.tag}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Done! Open {output_filename} in your browser.")
    print(f"Metadata saved to {json_filename}")

if __name__ == "__main__":
    main()
