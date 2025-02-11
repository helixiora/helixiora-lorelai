# Base image
FROM python:3.11 AS base
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config git wget libgl1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Web Production stage
FROM base AS web-production
EXPOSE 5000
RUN mkdir -p /usr/share/man/man1
RUN dpkg --print-architecture
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
# install gunicorn and dev requirements
RUN pip install --no-cache-dir -r requirements-web.txt
CMD ["gunicorn", "-w", "4", "-k", "gevent", "--timeout", "300", "-b", "0.0.0.0:5000", "--forwarded-allow-ips", "*", "run:app"]

# Web Development stage
FROM web-production AS web-development
COPY cert.pem key.pem ./
EXPOSE 22 5000
RUN pip install --no-cache-dir -r requirements-web.txt
CMD ["gunicorn", "-w", "4", "-k", "gevent", "--timeout", "300", "-b", "0.0.0.0:5000", "run:app", "--reload", "--certfile=cert.pem", "--keyfile=key.pem"]

# Worker Production stage
FROM base AS worker-production
RUN pip install --no-cache-dir -r requirements-worker.txt
ENTRYPOINT ["sh", "-c", "exec rq worker --url $REDIS_URL $LORELAI_RQ_QUEUES"]

# Worker Development stage
FROM worker-production AS worker-development
EXPOSE 22
RUN pip install --no-cache-dir -r requirements-worker.txt
ENTRYPOINT ["sh", "-c", "exec rq worker --url $REDIS_URL $LORELAI_RQ_QUEUES"]
