FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system findora && adduser --system --ingroup findora findora
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/uploads && chown -R findora:findora /app
USER findora
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && if [ \"$ENVIRONMENT\" = \"development\" ]; then python seed.py; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
