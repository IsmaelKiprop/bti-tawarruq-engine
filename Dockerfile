FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/
COPY shariah-audit-service/ shariah-audit-service/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "tawarruq.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
