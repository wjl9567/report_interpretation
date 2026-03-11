# 报告AI解读系统 - 后端
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（可选，如需 psycopg2 等可取消注释）
# RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt aiosqlite

COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
