"""Feed hostname validation must deny special localhost names, even with explicit egress flags."""
import json

import pytest
from fastapi import HTTPException

from current.main import configured_feeds


@pytest.mark.parametrize("hostname", ["localhost", "LOCALHOST", "localhost.", "localhost.example.internal"])
def test_localhost_names_never_enter_feed_registry(monkeypatch, hostname):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({"news": f"https://{hostname}/rss"}))
    with pytest.raises(HTTPException) as err:
        configured_feeds()
    assert err.value.status_code == 503
