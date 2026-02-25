import json
import os
from pathlib import Path
import faiss
import numpy as np
import sentence_transformers
import openai
import dotenv

# Config
BASE_DIR = Path(__file__).parent
INDEX_FILE = BASE_DIR / "kb/index.faiss"
META_FILE = BASE_DIR / "kb/index_meta.json"
EMBED_CONFIG_FILE = BASE_DIR / "kb/embed_manifest.json"
MODEL_NAME = 'mixedbread-ai/mxbai-embed-large-v1'

# Global state
_index = None
_chunks = None
_embed_model = None

def load_resources():
    """Load and cache resources (FAISS index, chunks, embedding model)."""
    global _index, _chunks, _embed_model
    if _index is not None:
        return _index, _chunks, _embed_model

    if not INDEX_FILE.exists() or not META_FILE.exists():
        raise FileNotFoundError("Knowledge base not found. Run ingest pipeline first.")

    # Check manifest
    if EMBED_CONFIG_FILE.exists():
        embed_manifest = json.loads(EMBED_CONFIG_FILE.read_text())
        if embed_manifest["model"] != MODEL_NAME:
             raise RuntimeError(f"Model mismatch: index was built with '{embed_manifest['model']}' but app is configured to use '{MODEL_NAME}'.")

    print("Loading FAISS index...")
    _index = faiss.read_index(str(INDEX_FILE))
    
    print("Loading metadata...")
    with open(META_FILE, "r", encoding="utf-8") as f:
        _chunks = json.load(f)
        
    print("Loading embedding model...")
    _embed_model = sentence_transformers.SentenceTransformer(MODEL_NAME)
    
    # Load OpenAI key
    dotenv.load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
         raise RuntimeError("Missing OPENAI_API_KEY in .env")
    openai.api_key = os.environ.get("OPENAI_API_KEY")

    return _index, _chunks, _embed_model

def retrieve(query, k=5, resources=None):
    """Retrieve relevant chunks for a query."""
    if resources:
        index, chunks, embed_model = resources
    else:
        index, chunks, embed_model = load_resources()
    
    query_text = f"Represent this sentence for searching relevant passages: {query}"
    query_vector = embed_model.encode([query_text], convert_to_numpy=True)
    query_vector = np.asarray(query_vector, dtype=np.float32)
    faiss.normalize_L2(query_vector)
    
    distances, indices = index.search(query_vector, k)
    
    retrieved_chunks = []
    for i, idx in enumerate(indices[0]):
        if idx == -1: continue
        chunk = chunks[idx].copy() # Copy to avoid modifying global state
        # Add score to chunk for reference
        chunk['score'] = float(distances[0][i])
        retrieved_chunks.append(chunk)
        
    return retrieved_chunks

def format_context(retrieved_chunks):
    """Format chunks into a context string."""
    context_text = ""
    for i, chunk in enumerate(retrieved_chunks):
        context_text += f"Source {i+1} ({chunk['title']}):\n{chunk['text']}\n\n"
    return context_text

def generate_answer(query, retrieved_chunks, model="gpt-4o", stream=True):
    """Generate an answer using OpenAI."""
    context_text = format_context(retrieved_chunks)

    system_prompt = (
        "You are a helpful expert System Design assistant. "
        "You answer questions based ONLY on the provided context. "
        "If the answer is not in the context, say \"I don't have enough information in my knowledge base to answer that.\" "
        "Do not use outside knowledge. "
        "Cite your sources if possible (e.g. 'According to the Redis article...')."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}"},
    ]

    return openai.chat.completions.create(
        model=model,
        messages=messages,
        stream=stream,
    )
