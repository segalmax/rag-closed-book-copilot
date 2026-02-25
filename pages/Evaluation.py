import json
import os
from collections import defaultdict

import openai
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from evaluation.eval import evaluate_answer, evaluate_retrieval_with_details, load_tests

load_dotenv(override=True)

RETRIEVAL_RESULTS_FILE = "evaluation/last_run_retrieval.json"
ANSWER_RESULTS_FILE = "evaluation/last_run_answer.json"

# Color coding thresholds - Retrieval
MRR_GREEN = 0.9
MRR_AMBER = 0.75
NDCG_GREEN = 0.9
NDCG_AMBER = 0.75
COVERAGE_GREEN = 90.0
COVERAGE_AMBER = 75.0

# Color coding thresholds - Answer (1-5 scale)
ANSWER_GREEN = 4.5
ANSWER_AMBER = 4.0

st.set_page_config(page_title="RAG Evaluation Dashboard", layout="wide")

def get_color(value: float, metric_type: str) -> str:
    """Get color based on metric value and type."""
    if metric_type == "mrr":
        if value >= MRR_GREEN: return "green"
        elif value >= MRR_AMBER: return "orange"
        else: return "red"
    elif metric_type == "ndcg":
        if value >= NDCG_GREEN: return "green"
        elif value >= NDCG_AMBER: return "orange"
        else: return "red"
    elif metric_type == "coverage":
        if value >= COVERAGE_GREEN: return "green"
        elif value >= COVERAGE_AMBER: return "orange"
        else: return "red"
    elif metric_type in ["accuracy", "completeness", "relevance"]:
        if value >= ANSWER_GREEN: return "green"
        elif value >= ANSWER_AMBER: return "orange"
        else: return "red"
    return "black"

def metric_card(label, value, metric_type, is_percentage=False, score_format=False):
    color = get_color(value, metric_type)
    if is_percentage:
        value_str = f"{value:.1f}%"
    elif score_format:
        value_str = f"{value:.2f}/5"
    else:
        value_str = f"{value:.4f}"
    
    st.markdown(f"""
    <div style="margin: 10px 0; padding: 15px; background-color: #f5f5f5; border-radius: 8px; border-left: 5px solid {color};">
        <div style="font-size: 14px; color: #666; margin-bottom: 5px;">{label}</div>
        <div style="font-size: 28px; font-weight: bold; color: {color};">{value_str}</div>
    </div>
    """, unsafe_allow_html=True)

def save_results(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_results(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

st.title("📊 RAG Evaluation Dashboard")
st.markdown("Select tests, run evals, then inspect details only when needed.")


def get_selected_tests():
    tests = load_tests()
    # Static base df - never rebuilt. Key accumulates edits on top.
    if "selector_base_df" not in st.session_state:
        st.session_state["selector_base_df"] = pd.DataFrame(
            [{"run": False, "question": t.question, "category": t.category} for t in tests]
        )
    edited_df = st.data_editor(
        st.session_state["selector_base_df"],
        key="tests_selector",
        use_container_width=True,
        hide_index=True,
        disabled=["question", "category"],
        column_config={
            "run": st.column_config.CheckboxColumn("Run"),
            "question": st.column_config.TextColumn("Question", width="large"),
            "category": st.column_config.TextColumn("Category", width="small"),
        },
    )
    selected_questions = set(edited_df.loc[edited_df["run"], "question"].tolist())
    selected_tests = [test for test in tests if test.question in selected_questions]
    st.caption(f"Selected {len(selected_tests)} / {len(tests)} tests")
    return selected_tests


with st.expander("Test Selection", expanded=False):
    selected_tests = get_selected_tests()

# RETRIEVAL SECTION
st.header("🔍 Retrieval Evaluation")

# Load existing results
retrieval_data = load_results(RETRIEVAL_RESULTS_FILE)

if st.button("Run Retrieval Evaluation", type="primary"):
    if not selected_tests:
        st.warning("Select at least one test in the table.")
        st.stop()
    total_mrr = 0.0
    total_ndcg = 0.0
    total_coverage = 0.0
    category_mrr = defaultdict(list)
    count = 0
    
    per_test_rows = []
    try:
        with st.status("Running retrieval evaluation...", expanded=True) as status:
            progress_bar = st.progress(0)

            for i, test in enumerate(selected_tests, start=1):
                result, retrieved_docs = evaluate_retrieval_with_details(test, k=5)
                prog_value = i / len(selected_tests)
                count += 1
                total_mrr += result.mrr
                total_ndcg += result.ndcg
                total_coverage += result.keyword_coverage

                category_mrr[test.category].append(result.mrr)
                per_test_rows.append({
                    "question": test.question,
                    "category": test.category,
                    "keywords": test.keywords,
                    "mrr": round(result.mrr, 4),
                    "ndcg": round(result.ndcg, 4),
                    "keyword_coverage": round(result.keyword_coverage, 1),
                    "keywords_found": f"{result.keywords_found}/{result.total_keywords}",
                    "retrieved_chunks": [
                        {
                            "title": doc.get("title", ""),
                            "section_title": doc.get("section_title", ""),
                            "doc_id": doc.get("doc_id", ""),
                            "score": round(doc.get("score", 0), 4),
                            "text": doc.get("text", ""),
                        }
                        for doc in retrieved_docs
                    ],
                })
                
                # Update status
                status.write(f"Evaluating: {test.question[:60]}...")
                progress_bar.progress(prog_value)

            progress_bar.empty()
            status.update(label="Retrieval Evaluation Complete!", state="complete", expanded=False)

        if count > 0:
            avg_mrr = total_mrr / count
            avg_ndcg = total_ndcg / count
            avg_coverage = total_coverage / count
            
            # Prepare data for saving/display
            category_data = []
            for category, mrr_scores in category_mrr.items():
                avg_cat_mrr = sum(mrr_scores) / len(mrr_scores)
                category_data.append({"Category": category, "Average MRR": avg_cat_mrr})
                
            retrieval_data = {
                "metrics": {
                    "mrr": avg_mrr,
                    "ndcg": avg_ndcg,
                    "coverage": avg_coverage,
                    "count": count
                },
                "category_data": category_data,
                "per_test": per_test_rows
            }
            save_results(retrieval_data, RETRIEVAL_RESULTS_FILE)
            st.rerun()
            
    except Exception as e:
        st.error(f"An error occurred during retrieval evaluation: {str(e)}")

if retrieval_data:
    metrics = retrieval_data["metrics"]
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Mean Reciprocal Rank (MRR)", metrics["mrr"], "mrr")
    with col2:
        metric_card("Normalized DCG (nDCG)", metrics["ndcg"], "ndcg")
    with col3:
        metric_card("Keyword Coverage", metrics["coverage"], "coverage", is_percentage=True)
        
    st.caption(f"Last run: {metrics['count']} tests evaluated")
    
    with st.expander("Retrieval Chart", expanded=False):
        df = pd.DataFrame(retrieval_data["category_data"])
        st.bar_chart(df, x="Category", y="Average MRR")
    per_test = retrieval_data.get("per_test", [])
    if per_test:
        with st.expander("Per-test retrieval results", expanded=False):
            table_df = pd.DataFrame([
                {
                    "question": row["question"],
                    "category": row["category"],
                    "keywords": ", ".join(row.get("keywords", [])),
                    "mrr": row["mrr"],
                    "ndcg": row["ndcg"],
                    "coverage_%": row["keyword_coverage"],
                    "keywords_found": row["keywords_found"],
                }
                for row in per_test
            ])
            st.dataframe(table_df, use_container_width=True, hide_index=True)
            selected_idx = st.selectbox(
                "Inspect retrieval test",
                range(len(per_test)),
                format_func=lambda i: per_test[i]["question"],
                key="inspect_retrieval_idx",
            )
            selected = per_test[selected_idx]
            st.markdown(f"**Expected keywords:** `{'`, `'.join(selected.get('keywords', []))}`")
            st.markdown("**Retrieved chunks:**")
            for i, chunk in enumerate(selected.get("retrieved_chunks", []), 1):
                kws = [kw.lower() for kw in selected.get("keywords", [])]
                hit = any(kw in chunk["text"].lower() for kw in kws)
                icon = "✅" if hit else "❌"
                with st.expander(f"{icon} #{i} — {chunk['title']} › {chunk['section_title']}  (score: {chunk['score']})"):
                    st.caption(chunk["doc_id"])
                    st.text(chunk["text"])
else:
    st.info("No retrieval evaluation results found. Click 'Run Retrieval Evaluation' to start.")

st.markdown("---")

# ANSWER SECTION
st.header("💬 Answer Evaluation")

# Load existing results
answer_data = load_results(ANSWER_RESULTS_FILE)

if st.button("Run Answer Evaluation", type="primary"):
    if not selected_tests:
        st.warning("Select at least one test in the table.")
        st.stop()
    total_accuracy = 0.0
    total_completeness = 0.0
    total_relevance = 0.0
    category_accuracy = defaultdict(list)
    count = 0

    per_test_rows = []
    try:
        with st.status("Running answer evaluation...", expanded=True) as status:
            progress_bar = st.progress(0)

            for i, test in enumerate(selected_tests, start=1):
                result, generated_answer, retrieved_docs = evaluate_answer(test)
                prog_value = i / len(selected_tests)
                count += 1
                total_accuracy += result.accuracy
                total_completeness += result.completeness
                total_relevance += result.relevance

                category_accuracy[test.category].append(result.accuracy)
                per_test_rows.append({
                    "question": test.question,
                    "category": test.category,
                    "keywords": test.keywords,
                    "accuracy": round(result.accuracy, 2),
                    "completeness": round(result.completeness, 2),
                    "relevance": round(result.relevance, 2),
                    "generated_answer": generated_answer,
                    "reference_answer": test.reference_answer,
                    "judge_feedback": result.feedback,
                    "retrieved_chunks": [
                        {
                            "title": doc.get("title", ""),
                            "section_title": doc.get("section_title", ""),
                            "doc_id": doc.get("doc_id", ""),
                            "score": round(doc.get("score", 0), 4),
                            "text": doc.get("text", ""),
                        }
                        for doc in retrieved_docs
                    ],
                })
                
                # Update status
                status.write(f"Evaluating: {test.question[:60]}...")
                progress_bar.progress(prog_value)

            progress_bar.empty()
            status.update(label="Answer Evaluation Complete!", state="complete", expanded=False)

        if count > 0:
            avg_accuracy = total_accuracy / count
            avg_completeness = total_completeness / count
            avg_relevance = total_relevance / count

            # Prepare data for saving/display
            category_data = []
            for category, accuracy_scores in category_accuracy.items():
                avg_cat_accuracy = sum(accuracy_scores) / len(accuracy_scores)
                category_data.append({"Category": category, "Average Accuracy": avg_cat_accuracy})
                
            answer_data = {
                "metrics": {
                    "accuracy": avg_accuracy,
                    "completeness": avg_completeness,
                    "relevance": avg_relevance,
                    "count": count
                },
                "category_data": category_data,
                "per_test": per_test_rows
            }
            save_results(answer_data, ANSWER_RESULTS_FILE)
            st.rerun()
            
    except openai.RateLimitError:
        st.error("⚠️ OpenAI API Quota Exceeded. Please check your billing details or try again later.")
        # Save partial results if any
        if count > 0:
             st.warning(f"Evaluation stopped early. Saved results for {count} tests.")
    except Exception as e:
        st.error(f"An error occurred during answer evaluation: {str(e)}")

if answer_data:
    metrics = answer_data["metrics"]
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Accuracy", metrics["accuracy"], "accuracy", score_format=True)
    with col2:
        metric_card("Completeness", metrics["completeness"], "completeness", score_format=True)
    with col3:
        metric_card("Relevance", metrics["relevance"], "relevance", score_format=True)
        
    st.caption(f"Last run: {metrics['count']} tests evaluated")

    with st.expander("Answer Chart", expanded=False):
        df = pd.DataFrame(answer_data["category_data"])
        st.bar_chart(df, x="Category", y="Average Accuracy")
    per_test = answer_data.get("per_test", [])
    if per_test:
        with st.expander("Per-test answer results", expanded=False):
            table_df = pd.DataFrame([
                {
                    "question": row["question"],
                    "category": row["category"],
                    "keywords": ", ".join(row.get("keywords", [])),
                    "accuracy": row["accuracy"],
                    "completeness": row["completeness"],
                    "relevance": row["relevance"],
                }
                for row in per_test
            ])
            st.dataframe(table_df, use_container_width=True, hide_index=True)
            selected_idx = st.selectbox(
                "Inspect answer test",
                range(len(per_test)),
                format_func=lambda i: per_test[i]["question"],
                key="inspect_answer_idx",
            )
            selected = per_test[selected_idx]
            st.markdown(f"**Expected keywords:** `{'`, `'.join(selected.get('keywords', []))}`")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Generated answer**")
                st.markdown(selected["generated_answer"])
            with col2:
                st.markdown("**Reference answer**")
                st.markdown(selected["reference_answer"])
            st.markdown(f"**Judge feedback:** {selected['judge_feedback']}")
            st.markdown("**Retrieved chunks:**")
            for i, chunk in enumerate(selected.get("retrieved_chunks", []), 1):
                with st.expander(f"#{i} — {chunk['title']} › {chunk['section_title']}  (score: {chunk['score']})"):
                    st.caption(chunk["doc_id"])
                    st.text(chunk["text"])
else:
    st.info("No answer evaluation results found. Click 'Run Answer Evaluation' to start.")
