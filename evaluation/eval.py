import sys
import math
import json
from pathlib import Path
from pydantic import BaseModel, Field
import openai
from dotenv import load_dotenv

# Add parent directory to path to import rag
sys.path.append(str(Path(__file__).parent.parent))
import rag

load_dotenv(override=True)

MODEL = "gpt-4o"

class RetrievalEval(BaseModel):
    """Evaluation metrics for retrieval performance."""
    mrr: float = Field(description="Mean Reciprocal Rank - average across all keywords")
    ndcg: float = Field(description="Normalized Discounted Cumulative Gain (binary relevance)")
    keywords_found: int = Field(description="Number of keywords found in top-k results")
    total_keywords: int = Field(description="Total number of keywords to find")
    keyword_coverage: float = Field(description="Percentage of keywords found")

class AnswerEval(BaseModel):
    """LLM-as-a-judge evaluation of answer quality."""
    feedback: str = Field(description="Concise feedback on the answer quality.")
    accuracy: float = Field(description="How factually correct is the answer? 1-5 scale.")
    completeness: float = Field(description="How complete is the answer? 1-5 scale.")
    relevance: float = Field(description="How relevant is the answer? 1-5 scale.")

class TestQuestion(BaseModel):
    question: str
    keywords: list[str]
    reference_answer: str
    category: str

def load_tests(path="evaluation/tests.jsonl"):
    tests = []
    with open(path, "r") as f:
        for line in f:
            tests.append(TestQuestion(**json.loads(line)))
    return tests

def calculate_mrr(keyword: str, retrieved_docs: list) -> float:
    keyword_lower = keyword.lower()
    for rank, doc in enumerate(retrieved_docs, start=1):
        if keyword_lower in doc['text'].lower():
            return 1.0 / rank
    return 0.0

def calculate_dcg(relevances: list[int], k: int) -> float:
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        dcg += relevances[i] / math.log2(i + 2)
    return dcg

def calculate_ndcg(keyword: str, retrieved_docs: list, k: int = 10) -> float:
    keyword_lower = keyword.lower()
    relevances = [1 if keyword_lower in doc['text'].lower() else 0 for doc in retrieved_docs[:k]]
    dcg = calculate_dcg(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = calculate_dcg(ideal_relevances, k)
    return dcg / idcg if idcg > 0 else 0.0

def _build_retrieval_eval(test: TestQuestion, retrieved_docs: list, k: int) -> RetrievalEval:
    mrr_scores = [calculate_mrr(kw, retrieved_docs) for kw in test.keywords]
    avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0.0
    
    ndcg_scores = [calculate_ndcg(kw, retrieved_docs, k) for kw in test.keywords]
    avg_ndcg = sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else 0.0
    
    keywords_found = sum(1 for score in mrr_scores if score > 0)
    total_keywords = len(test.keywords)
    keyword_coverage = (keywords_found / total_keywords * 100) if total_keywords > 0 else 0.0
    
    return RetrievalEval(
        mrr=avg_mrr,
        ndcg=avg_ndcg,
        keywords_found=keywords_found,
        total_keywords=total_keywords,
        keyword_coverage=keyword_coverage
    )

def evaluate_retrieval(test: TestQuestion, k: int = 5) -> RetrievalEval:
    retrieved_docs = rag.retrieve(test.question, k=k)
    return _build_retrieval_eval(test, retrieved_docs, k)

def evaluate_retrieval_with_details(test: TestQuestion, k: int = 5) -> tuple[RetrievalEval, list]:
    retrieved_docs = rag.retrieve(test.question, k=k)
    result = _build_retrieval_eval(test, retrieved_docs, k)
    return result, retrieved_docs

def evaluate_answer(test: TestQuestion) -> tuple[AnswerEval, str, list]:
    retrieved_docs = rag.retrieve(test.question, k=5)
    response = rag.generate_answer(test.question, retrieved_docs, model=MODEL, stream=False)
    generated_answer = response.choices[0].message.content

    judge_messages = [
        {"role": "system", "content": "You are an expert evaluator assessing the quality of answers."},
        {"role": "user", "content": f"""
Question: {test.question}
Generated Answer: {generated_answer}
Reference Answer: {test.reference_answer}

Evaluate the generated answer on:
1. Accuracy (1-5): Factual correctness.
2. Completeness (1-5): Addressing all aspects.
3. Relevance (1-5): Directness.

Provide scores and feedback.
"""}
    ]

    judge_response = openai.beta.chat.completions.parse(
        model=MODEL,
        messages=judge_messages,
        response_format=AnswerEval
    )
    
    return judge_response.choices[0].message.parsed, generated_answer, retrieved_docs

def evaluate_all_retrieval(limit=None, include_details=False):
    tests = load_tests()
    if limit:
        tests = tests[:limit]
    total = len(tests)
    for i, test in enumerate(tests):
        if include_details:
            result, retrieved_docs = evaluate_retrieval_with_details(test)
            details = {
                "retrieved_titles": [doc.get("title", "") for doc in retrieved_docs],
                "retrieved_doc_ids": [doc.get("doc_id", "") for doc in retrieved_docs],
            }
            yield test, result, (i + 1) / total, details
        else:
            result = evaluate_retrieval(test)
            yield test, result, (i + 1) / total

def evaluate_all_answers(limit=None, include_details=False):
    tests = load_tests()
    if limit:
        tests = tests[:limit]
    total = len(tests)
    for i, test in enumerate(tests):
        result, generated_answer, retrieved_docs = evaluate_answer(test)
        if include_details:
            details = {
                "generated_answer": generated_answer,
                "judge_feedback": result.feedback,
                "retrieved_titles": [doc.get("title", "") for doc in retrieved_docs],
                "retrieved_doc_ids": [doc.get("doc_id", "") for doc in retrieved_docs],
            }
            yield test, result, (i + 1) / total, details
        else:
            yield test, result, (i + 1) / total
