FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV SOCKET_HOST=0.0.0.0
ENV SOCKET_PORT=9999
ENV SOCKET_PROTOCOL=TCP
ENV DATABASE_URL=sqlite+aiosqlite:////data/temperature.db

EXPOSE 8000 9999

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
