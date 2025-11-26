# ========================================
# Stage 1: Builder
# ========================================
FROM python:3.11-slim AS builder

WORKDIR /opt/stacks

# Install PEX
RUN pip install --no-cache-dir pex

# Copy project files
COPY requirements.txt .
COPY VERSION .
COPY src ./src
COPY web ./web
COPY files ./files

# Install dependencies into deps/
RUN pip install --no-cache-dir -r requirements.txt -t deps

# Build the PEX
RUN pex \
    --disable-cache \
    -m stacks.main \
    --sources-directory ./src \
    -D ./deps \
    -o stacks.pex

# Cleanup: remove everything except the PEX and runtime files
RUN rm -rf deps src web/scss requirements.txt

# ========================================
# Stage 2: Distroless Python3
# ========================================
FROM gcr.io/distroless/python3

ARG VERSION=unknown
ARG FINGERPRINT=unknown

LABEL version=$VERSION \ 
    fingerprint=$FINGERPRINT \ 
    description="Download Manager for Anna's Archive" \ 
    maintainer="Zelest Carlyone"

WORKDIR /opt/stacks

# Set PROJECT_ROOT for the application
ENV STACKS_PROJECT_ROOT=/opt/stacks

# Copy application and files
COPY --from=builder /opt/stacks/ /opt/stacks/

EXPOSE 7788

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["/usr/bin/python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7788/api/health')"]

ENTRYPOINT ["/usr/bin/python3", "/opt/stacks/stacks.pex"]
