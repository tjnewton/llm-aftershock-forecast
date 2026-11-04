"""Shared fixtures."""

import subprocess

import pytest


@pytest.fixture
def worktree(tmp_path, monkeypatch):
    """A clone of a local bare repository: the live branch's worktree with its origin."""
    import os

    for var in [v for v in os.environ if v.startswith("GIT_")]:  # e.g. set by pre-commit hooks
        monkeypatch.delenv(var)
    origin, wt = tmp_path / "origin.git", tmp_path / "wt"

    def git(*a, cwd=wt):
        return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                              text=True).stdout.strip()  # fmt: skip

    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(wt)], check=True, capture_output=True)
    for k, v in (
        ("user.email", "t@example.invalid"),
        ("user.name", "t"),
        ("core.hooksPath", "/dev/null"),
    ):
        git("config", k, v)
    git("checkout", "-q", "-b", "live-test")
    (wt / "README.md").write_text("live-test\n")
    git("add", "README.md")
    git("commit", "-qm", "start")
    git("push", "-q", "-u", "origin", "live-test")
    return wt, origin, git
