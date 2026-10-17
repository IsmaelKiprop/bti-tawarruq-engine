"""Shared pytest configuration — isolate test DB and disable external mirrors."""

import os

# Must run before any tawarruq imports so engine binds to the test database.
os.environ["DATABASE_URL"] = "sqlite:///./tawarruq_test.db"
os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["SHARIAH_AUDIT_SERVICE_URL"] = ""
os.environ["AUTH_ENABLED"] = "false"
os.environ["OPS_SESSION_SECRET"] = "test-ops-session-secret"

from tawarruq.config import get_settings

get_settings.cache_clear()

