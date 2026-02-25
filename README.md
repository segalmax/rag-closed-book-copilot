# Closed-Book RAG Copilot

Streamlit RAG app for system-design Q&A with FAISS retrieval, OpenAI generation, and evaluation dashboards.

## Architecture

- `nginx` container binds host `:80` and reverse-proxies to `app:8501`
- `app` container runs Streamlit (`Chat.py`) and RAG pipeline (`rag.py`)
- `kb/` is mounted from host so FAISS artifacts persist and stay inspectable
- Hugging Face and Torch caches are mounted as Docker volumes to avoid repeated model downloads

## Repository Rules (public-safe)

- Commit source code, ingestion scripts, and `kb/raw/` content only if data license allows it
- Do not commit generated artifacts (`kb/index.faiss`, processed JSONL, visualizations, eval outputs)
- Do not commit `.env` or credentials

## Prerequisites

- Docker + Docker Compose plugin
- OpenAI API key

## Environment Setup

Create local env file:

```bash
cp .env.example .env
```

Set:

```dotenv
OPENAI_API_KEY=...
```

## Build Knowledge Base (fail-fast flow)

The app expects these files to exist:

- `kb/index.faiss`
- `kb/index_meta.json`
- `kb/embed_manifest.json`

Generate them before starting the app (containerized path):

```bash
docker compose build app
docker compose run --rm app python ingest/preprocess_kb.py
docker compose run --rm app python ingest/embed.py
```

If they are missing, the app exits with an explicit error.

## Run with Docker Compose

```bash
docker compose up --build -d
```

Open `http://localhost`.

Check logs:

```bash
docker compose logs -f app
docker compose logs -f nginx
```

Stop:

```bash
docker compose down
```

## Hugging Face Model Storage

- First model use downloads weights to disk cache inside the app container
- Cache is persisted by named volumes:
  - `hf_cache` -> `/root/.cache/huggingface`
  - `torch_cache` -> `/root/.cache/torch`
- These survive container recreation; remove only if you intentionally want a clean redownload

## EC2 Deployment (Nginx + app)

### 1) Provision VM

- Ubuntu EC2 instance
- Install Docker and Compose plugin
- Optional helper script: `bash deploy/ec2/bootstrap_ubuntu.sh`

### 2) Security Group rules

- Inbound `22` from your IP only
- Inbound `80` from `0.0.0.0/0`
- Inbound `443` from `0.0.0.0/0` only if HTTPS is enabled
- Do not expose `8501` publicly

### 3) Deploy

```bash
git clone <your-repo-url>
cd "RAG closed-book-copilot"
cp .env.example .env
# edit .env and set OPENAI_API_KEY
export OPENAI_API_KEY=...
bash deploy/ec2/deploy.sh
```

### 4) Verify

- `docker compose ps` shows both containers healthy/running
- `curl http://localhost/health` on EC2 returns `ok`
- Open `http://<EC2_PUBLIC_IP>` and run real queries

## Homework Submission Checklist

- Explain data source, chunking strategy, embedding model, and FAISS indexing
- Show at least 5 test questions and outputs
- Include at least 1 irrelevant question and system behavior
- Record short demo video:
  - open app on EC2 public endpoint
  - ask queries and show retrieved chunks + answer
  - briefly explain architecture (`Nginx -> Streamlit -> FAISS/OpenAI`)
  - show one edge case (missing/irrelevant context handling)

### Suggested 5 demo questions

1. "When should I prefer Redis over PostgreSQL for high-throughput workloads?"
2. "How does consistent hashing reduce rebalancing impact in distributed systems?"
3. "What trade-offs does CAP theorem force in a partitioned system?"
4. "When do I choose Kafka versus RabbitMQ for event-driven architecture?"
5. "How does API Gateway improve security and routing in microservices?"

Irrelevant test:

- "Who won the last FIFA World Cup?" (should respond that KB does not contain enough information)

### Evidence capture flow

1. Open `http://<EC2_PUBLIC_IP>` and run all 5 questions in the chat page.
2. Open the Evaluation page and run retrieval/answer evaluation on selected tests.
3. Save screenshots of:
   - retrieval context expander
   - generated answer
   - evaluation metrics panels
4. Record a short video that includes deployment URL, one relevant query, one irrelevant query, and architecture explanation.
