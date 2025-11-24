# ========================================
# Stage 1: Builder (Python 3.11 Slim)
# ========================================
FROM python:3.11-slim AS builder

ARG VERSION=unknown
ARG FINGERPRINT=unknown

# Labels
LABEL version=$VERSION
LABEL fingerprint=$FINGERPRINT
LABEL description="Download Manager for Anna's Archive"
LABEL maintainer="Zelest Carlyone"

WORKDIR /opt/stacks

# Install dependencies into /install (distroless compatible layout)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


RUN rm -rf ./requirements.txt


# Copy application files
COPY src ./src
COPY VERSION .
COPY web ./web
COPY files ./files

# ========================================
# Stage 2: Distroless Runtime (Python 3)
# ========================================
FROM gcr.io/distroless/python3-debian12

ARG VERSION=unknown
ARG FINGERPRINT=unknown

# Labels
LABEL version=$VERSION
LABEL fingerprint=$FINGERPRINT

WORKDIR /opt/stacks

# Set Python path to find installed packages
ENV PYTHONPATH="/opt/stacks/src:/usr/local/lib/python3.11/site-packages"

# Bring in installed Python packages + app
COPY --from=builder /install /usr/local
COPY --from=builder /opt/stacks /opt/stacks

EXPOSE 7788

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD ["/usr/bin/python3", "-c", "import urllib.request, json, sys; r=json.load(urllib.request.urlopen('http://127.0.0.1:7788/api/health')); sys.exit(0 if r.get('status')=='ok' else 1)"]

ENTRYPOINT ["/usr/bin/python3", "-m", "stacks.main"]