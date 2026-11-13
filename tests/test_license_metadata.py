"""The Current source distribution declares its individual MIT license."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_repository_license_is_present_and_complete():
    content = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert content.startswith("MIT License\n\nCopyright (c) 2026 GoreeCloud")
    assert "Permission is hereby granted, free of charge" in content
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in content


def test_package_and_container_include_license():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["license"] == "MIT"
    assert metadata["project"]["license-files"] == ["LICENSE"]
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY LICENSE ./" in dockerfile
