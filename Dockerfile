# Base image
FROM python:3.11-slim as base
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Web Production stage
FROM base as web-production
EXPOSE 5000
# install flyway
ENV FLYWAY_VERSION=10.13.0
RUN apt-get install -y --no-install-recommends openjdk-17-jre-headless wget
RUN wget -qO- https://repo1.maven.org/maven2/org/flywaydb/flyway-commandline/${FLYWAY_VERSION}/flyway-commandline-${FLYWAY_VERSION}-linux-x64.tar.gz | tar xvz -C /usr/local/bin
RUN ln -s /usr/local/bin/flyway-${FLYWAY_VERSION}/flyway /usr/local/bin/flyway
RUN chmod +x /usr/local/bin/flyway
RUN flyway -v
# install gunicorn
RUN pip install --no-cache-dir -r requirements-web.txt
CMD ["gunicorn", "-w", "4", "-k", "gevent", "--timeout", "300", "-b", "0.0.0.0:5000", "run:app"]

# Development stage
FROM web-production as web-development
COPY cert.pem key.pem ./
EXPOSE 22 5000
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["gunicorn", "-w", "4", "-k", "gevent", "--timeout", "300", "-b", "0.0.0.0:5000", "run:app", "--reload", "--certfile=cert.pem", "--keyfile=key.pem"]

# Worker Production stage
FROM base as worker-production
RUN pip install --no-cache-dir -r requirements-worker.txt
ENTRYPOINT exec rq worker --url $REDIS_URL

# Worker Development stage
FROM worker-production as worker-development
EXPOSE 22
RUN pip install --no-cache-dir -r requirements-dev.txt
ENTRYPOINT exec rq worker --url $REDIS_URL
