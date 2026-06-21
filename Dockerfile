FROM python:3.11-slim

WORKDIR /app
COPY . /app
EXPOSE 8080
CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8080", "--db", "/app/data/mini_drop.sqlite3"]

