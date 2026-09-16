"""Entry point for the AI DIGITAL BRAIN web application."""

from __future__ import annotations

import os

from app import create_app

app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = app.config.get("DEBUG", False)
    app.logger.info("Starting AI DIGITAL BRAIN on %s:%s", host, port)
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
