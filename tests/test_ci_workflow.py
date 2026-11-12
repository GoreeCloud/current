"""Regression gate for Current's reviewed immutable CI action references."""

from pathlib import Path
import re

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
APPROVED = {
    "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
}


def test_ci_actions_are_reviewed_immutable_commits():
    text = WORKFLOW.read_text(encoding="utf-8")
    references = re.findall(r"^\s*-\s*uses:\s*([^\s#]+)", text, flags=re.MULTILINE)
    assert len(references) == 2
    assert set(references) == APPROVED
    for ref in references:
        assert re.fullmatch(r"[a-z0-9_-]+/[a-z0-9_-]+@[0-9a-f]{40}", ref)


def test_ci_is_read_only_and_bounded():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in text
    assert "runs-on: ubuntu-24.04" in text
    assert "timeout-minutes: 10" in text
