import json
import traceback
import webbrowser
import streamlit as st
import rag
from pathlib import Path
from ingest.stats import compute_stats

# Config
VIZ_DIR = Path("kb/visualizations")

# Page Setup
st.set_page_config(page_title="Closed-Book Copilot", layout="wide")
st.title("Closed-Book System Design Copilot")


def load_viz_history():
    if not VIZ_DIR.exists():
        return []
    json_files = sorted(VIZ_DIR.glob("viz_*.json"), reverse=True)  # newest first
    history = []
    for jf in json_files:
        with open(jf, encoding="utf-8") as f:
            meta = json.load(f)
        html_path = VIZ_DIR / meta["html_file"]
        if html_path.exists():
            history.append({"meta": meta, "html_path": html_path.resolve()})
    return history


# --- Sidebar ---
with st.sidebar:
    st.header("Settings")
    st.markdown("---")
    k_retrieval = st.slider("Chunks to retrieve (k)", 1, 20, 5)
    model_choice = st.selectbox("LLM Model", ["gpt-4o", "gpt-3.5-turbo"])

    st.markdown("---")
    st.subheader("Embedding Visualizations")

    history = load_viz_history()
    if not history:
        st.caption("No visualizations found. Run `visualize/plot_embeddings.py` first.")
    else:
        options = [f"{h['meta']['timestamp'][:16].replace('T', ' ')} — {h['meta']['tag']}" for h in history]
        selected_idx = st.selectbox("Select run", range(len(options)), format_func=lambda i: options[i])
        selected = history[selected_idx]
        meta = selected["meta"]

        st.markdown(
            f"| | |\n"
            f"|---|---|\n"
            f"| **Model** | `{meta['model']}` |\n"
            f"| **Dims** | {meta['dimension']} |\n"
            f"| **Chunks** | {meta['num_chunks']} |\n"
            f"| **Contextual** | {'Yes' if meta['contextual'] else 'No'} |\n"
            f"| **Embedded** | {meta.get('embed_timestamp', 'N/A')[:16].replace('T', ' ')} |"
        )

        if st.button("Open in browser"):
            webbrowser.open(f"file://{selected['html_path']}")


# --- Load Resources (Cached) ---
@st.cache_resource
def load_resources():
    return rag.load_resources()


with st.spinner("Loading Knowledge Base..."):
    try:
        index, chunks, embed_model = load_resources()
    except Exception:
        st.error("Failed to load knowledge base")
        st.code(traceback.format_exc())
        st.stop()

# --- KB Stats ---
kb_stats = compute_stats(chunks)
with st.expander("Knowledge Base Stats"):
    st.markdown(
        f"| | |\n"
        f"|---|---|\n"
        f"| **Total Documents** | {kb_stats['total_docs']} |\n"
        f"| **Total Chunks** | {kb_stats['total_chunks']} |\n"
        f"| **Total Tokens** | {kb_stats['total_tokens']:,} |\n"
        f"| **Avg Tokens/Chunk** | {kb_stats['avg_tokens_per_chunk']:.1f} |"
    )
    st.markdown("**Per-document:**")
    st.dataframe(
        kb_stats["rows"],
        column_config={"Title": st.column_config.TextColumn("Title", width="medium")},
        use_container_width=True,
        hide_index=True,
    )

# --- Main App ---
query = st.text_input("Ask a question about System Design:")

if query:
    try:
        # 1. Retrieve
        retrieved_chunks = rag.retrieve(query, k=k_retrieval, resources=(index, chunks, embed_model))

        # 2. Display Sources
        with st.expander(f"View Retrieved Context ({len(retrieved_chunks)} chunks)"):
            for i, chunk in enumerate(retrieved_chunks):
                st.markdown(f"**{i+1}. {chunk['title']}** (Score: {chunk['score']:.4f})")
                st.caption(f"Path: {chunk['doc_id']}")
                st.text(chunk['text'])
                st.divider()

        # 3. Call LLM
        st.markdown("### Answer")
        response_placeholder = st.empty()
        full_response = ""

        response = rag.generate_answer(query, retrieved_chunks, model=model_choice, stream=True)

        for chunk in response:
            content = chunk.choices[0].delta.content or ""
            full_response += content
            response_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)
    except Exception:
        st.error("Runtime error")
        st.code(traceback.format_exc())
