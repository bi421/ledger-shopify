import inspect
from unittest.mock import ANY

import httpx
import pytest


if "app" not in inspect.signature(httpx.AsyncClient.__init__).parameters:
    _async_client_init = httpx.AsyncClient.__init__

    def _async_client_init_with_app(self, *args, app=None, transport=None, **kwargs):
        if app is not None and transport is None:
            transport = httpx.ASGITransport(app=app)
        return _async_client_init(self, *args, transport=transport, **kwargs)

    httpx.AsyncClient.__init__ = _async_client_init_with_app


pytest.any = ANY


def pytest_configure():
    try:
        from src.trueroas.api.routes.autonomous import limiter

        limiter.enabled = False
    except Exception:
        pass
