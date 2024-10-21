#!/usr/bin/env python3

"""Main application file for the Flask app."""

from app.factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run(ssl_context=("cert.pem", "key.pem"))
