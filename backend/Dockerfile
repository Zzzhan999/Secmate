# 阿里云 ACR 云端构建机访问不了 Docker Hub 与 pypi.org，基础镜像和依赖都走国内镜像源
FROM docker.m.daocloud.io/library/python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY app ./app

EXPOSE 8000

# Render 等 PaaS 通过 $PORT 注入监听端口；本地 docker compose 未设置时回退 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
