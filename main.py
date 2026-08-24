"""Convenience ASGI entry point for running CodeX from the project root."""

from backend.main import app, create_app

__all__ = ["app", "create_app"]
