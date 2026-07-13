FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY entrypoint.sh .

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
