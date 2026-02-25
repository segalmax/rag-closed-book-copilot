FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.lock.txt

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "Chat.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
