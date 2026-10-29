"""CI path guard (docs/factory.md, Brakes). Standard library only: the workflow runs the copy of
this file from the base branch, so a pull request cannot loosen its own check.

    python path_guard.py push SHA...                    commits pushed outside a merged PR
    python path_guard.py pr --frozen F BASE HEAD [--override]
"""

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

CODE_PREFIXES = ("src/", "tests/", "notebooks/", "prompts/", "config/")
GENERATED = ("notebooks/public/",)  # explorer data tables written by `laf figures`
RAW = "data/raw/"
MANIFEST = "data/manifest.jsonl"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

Change = tuple[str, str]  # (git status letter, path)


def frozen_patterns(path: Path) -> list[str]:
    lines = (x.strip() for x in path.read_text(encoding="utf-8").splitlines())
    return [x for x in lines if x and not x.startswith("#")]


def manifest_append_only(old: str, new: str) -> bool:
    return new.startswith(old)


def _data_violations(changes: list[Change], manifest_ok: bool) -> list[str]:
    out = [f"{s} {p}: raw data is immutable" for s, p in changes if p.startswith(RAW) and s != "A"]
    if not manifest_ok:
        out.append(f"{MANIFEST}: lines may only be appended")
    return out


def push_violations(changes: list[Change], manifest_ok: bool) -> list[str]:
    """A direct push: code paths go through pull requests; raw data and manifest rules hold."""
    code = [
        f"{s} {p}: code changes go through a pull request"
        for s, p in changes
        if p.startswith(CODE_PREFIXES) and not p.startswith(GENERATED)
    ]
    return code + _data_violations(changes, manifest_ok)


def pr_violations(
    changes: list[Change], manifest_ok: bool, patterns: list[str], override: bool
) -> list[str]:
    """A pull request: frozen paths, raw data and the manifest need the override label."""
    if override:
        return []
    frozen = [
        f"{s} {p}: frozen path (label frozen-override)"
        for s, p in changes
        if any(fnmatch.fnmatch(p, pat) for pat in patterns)
    ]
    return frozen + _data_violations(changes, manifest_ok)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _changes(a: str, b: str) -> list[Change]:
    out = _git("diff", "--name-status", "--no-renames", a, b)
    return [(s[0], p) for s, p in (line.split("\t", 1) for line in out.splitlines() if line)]


def _parent(sha: str) -> str:
    """First parent, or the empty tree for a root commit."""
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{sha}^"], capture_output=True)
    return f"{sha}^" if r.returncode == 0 else EMPTY_TREE


def _manifest_ok(a: str, b: str) -> bool:
    def show(rev: str) -> str:
        r = subprocess.run(["git", "show", f"{rev}:{MANIFEST}"], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""

    return manifest_append_only(show(a), show(b))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="path_guard")
    sub = p.add_subparsers(dest="cmd", required=True)
    pu = sub.add_parser("push")
    pu.add_argument("shas", nargs="*")
    pr = sub.add_parser("pr")
    pr.add_argument("base")
    pr.add_argument("head")
    pr.add_argument("--override", action="store_true")
    pr.add_argument("--frozen", type=Path, default=Path(".github/frozen-paths.txt"))
    a = p.parse_args(argv)
    found = []
    if a.cmd == "push":
        for sha in a.shas:
            parent = _parent(sha)
            v = push_violations(_changes(parent, sha), _manifest_ok(parent, sha))
            found += [f"{sha[:9]} {x}" for x in v]
    else:
        changes = _changes(a.base, a.head)
        found = pr_violations(
            changes, _manifest_ok(a.base, a.head), frozen_patterns(a.frozen), a.override
        )
    for v in found:
        print(f"::error::{v}")
    print(f"path guard: {len(found)} violation(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
