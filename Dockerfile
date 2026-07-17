# Webhook handler image for Fly.io.
# The polling sync stays on GitHub Actions; only webhook_handler.py runs here.
FROM python:3.11-slim

WORKDIR /app

# Unbuffered stdout so background-task log lines show up in `fly logs` live
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webhook_handler.py .

EXPOSE 8080

CMD ["uvicorn", "webhook_handler:app", "--host", "0.0.0.0", "--port", "8080"]
