# NginxForge - zero-dependency nginx configuration auditor
#
#   docker build -t nginxforge:1.0.0 .
#   docker run --rm -v "$PWD/conf.d:/conf" nginxforge:1.0.0 audit /conf
#   docker run --rm -v "$PWD/conf.d:/conf" nginxforge:1.0.0 audit /conf --format sarif
FROM python:3.12-alpine

LABEL org.opencontainers.image.title="NginxForge" \
      org.opencontainers.image.description="Zero-dependency, offline-first nginx config parser, auditor, fixer and generator" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY nginxforge ./nginxforge

RUN pip install --no-cache-dir .

# Run as a non-root user: the tool only ever reads configs unless --apply is passed.
RUN adduser -D -u 10001 nginxforge && mkdir -p /conf && chown nginxforge /conf
USER nginxforge
WORKDIR /conf

ENTRYPOINT ["nginxforge"]
CMD ["--help"]
