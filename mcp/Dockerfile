# wos-events MCP server. Build context: this mcp/ directory.
#   docker build -t wos-events-mcp mcp/
# Cloud Run sets PORT; the server reads MCP_PORT, falling back to PORT, then 8094.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_TRUST_PROXY=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wos_mcp ./wos_mcp

RUN useradd --system --uid 10001 --no-create-home mcp
USER mcp

EXPOSE 8094
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"MCP_PORT\") or os.getenv(\"PORT\") or 8094}/health',timeout=2)"
CMD ["python", "-m", "wos_mcp"]
