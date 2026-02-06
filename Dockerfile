FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY serp-to-context-api/ ./serp-to-context-api/

ENV PYTHONPATH=/app/serp-to-context-api

EXPOSE 8000

CMD ["uvicorn", "serp-to-context-api.main:app", "--host", "0.0.0.0", "--port", "8000"]
