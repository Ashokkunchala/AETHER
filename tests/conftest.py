"""Keep HTTP tests independent without disabling production protections."""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def isolated_http_rate_buckets():
    """A TestClient's repeated synthetic IP must not charge later tests' budget."""
    from app.middleware.rate_limit import ApiRateLimitMiddleware

    for name in ('app.main', 'app.main_enhanced'):
        module = sys.modules.get(name)
        current = getattr(getattr(module, 'app', None), 'middleware_stack', None)
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, ApiRateLimitMiddleware):
                with current._lock:
                    current._events.clear()
            current = getattr(current, 'app', None)


@pytest.fixture
def manual_scheduler(monkeypatch):
    """HTTP management tests dispatch explicitly; scheduler tests run real loops."""
    async def no_background_polling(self):
        pass

    monkeypatch.setattr('app.scheduler.ScheduleRunner.start', no_background_polling)
