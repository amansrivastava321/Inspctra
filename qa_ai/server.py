"""
server.py - Top-level entrypoint for the Inspectra product backend server.

Run:
    python -m qa_ai.server
    uvicorn qa_ai.server:app --host 127.0.0.1 --port 8765

Security:
- Binds to 127.0.0.1 only (never 0.0.0.0 by default).
- CORS restricted to localhost in the product app.
- No automatic launch: must be explicitly started.
"""
from __future__ import annotations

import logging

from qa_ai.product_backend.server import create_product_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# WSGI/ASGI app object — importable by uvicorn directly:
#   uvicorn qa_ai.server:app
app = create_product_app()

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("uvicorn is required: pip install uvicorn") from exc

    # Explicitly localhost-only — never expose to network without deliberate config change
    uvicorn.run(
        "qa_ai.server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info",
    )
