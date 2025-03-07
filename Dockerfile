FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# ENV OTEL_PYTHON_LOG_CORRELATION=true

# CMD ["opentelemetry-instrument", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]