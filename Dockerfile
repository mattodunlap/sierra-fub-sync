# URL populator image for Fly.io.
# Runs the 60s FUB poll loop (url_populator.py) — no inbound service needed.
# webhook_handler.py is included as the shared library of URL/FUB helpers
# (and can be run instead via uvicorn if real-time webhooks are ever wanted).
FROM python:3.11-slim

WORKDIR /app

# Unbuffered stdout so background-task log lines show up in `fly logs` live
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webhook_handler.py url_populator.py ./

CMD ["python", "url_populator.py"]
