"""The first-party container must be local-only unless explicitly overridden."""

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def test_container_defaults_to_loopback_and_nonroot():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    commands = [
        line.removeprefix("CMD ").strip()
        for line in dockerfile.splitlines()
        if line.startswith("CMD ")
    ]
    assert len(commands) == 1
    cmd = json.loads(commands[0])
    assert cmd[:2] == ["uvicorn", "current.main:app"]
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "--port" in cmd
    assert "USER appuser" in dockerfile
    assert "RUN useradd --uid 10001 --create-home appuser" in dockerfile
    assert "COPY LICENSE ./" in dockerfile
