import subprocess
from pathlib import Path

from laf import path_guard as G

PATTERNS = G.frozen_patterns(Path(".github/frozen-paths.txt"))


def test_direct_pushes_of_code_are_flagged_and_data_runs_ops_docs_pass():
    assert G.push_violations([("M", "src/laf/etas.py")], True, PATTERNS)
    assert G.push_violations([("A", "config/sequences_new.toml")], True, PATTERNS)
    ok = [("A", "runs/x/results.jsonl"), ("M", "results/e3.csv"), ("M", "ops/windows-queue.md")]
    ok += [("A", "data/raw/new/x.csv"), ("M", "docs/adr/0013-data-splits.md")]
    ok += [("A", "figures/f.png"), ("M", "data/processed/S/items.jsonl")]
    ok += [("M", "notebooks/public/explorer_e3.csv")]
    assert G.push_violations(ok, True, PATTERNS) == []
    assert G.push_violations([("M", "docs/preregistration.md")], True, PATTERNS)


def test_frozen_paths_need_the_override_label():
    ch = [("M", "prompts/system_p1.txt")]
    assert G.pr_violations(ch, True, PATTERNS, override=False)
    assert G.pr_violations(ch, True, PATTERNS, override=True) == []
    assert G.pr_violations([("M", "src/laf/etas.py")], True, PATTERNS, override=False) == []
    for p in ("src/laf/analysis.py", "docs/preregistration.md", "src/laf/path_guard.py"):
        assert G.pr_violations([("M", p)], True, PATTERNS, override=False), p


def test_raw_data_is_immutable_and_the_manifest_append_only():
    for s in ("M", "D"):
        assert G.pr_violations([(s, "data/raw/oaf/x.json")], True, PATTERNS, False)
        assert G.push_violations([(s, "data/raw/oaf/x.json")], True, PATTERNS)
        assert G.pr_violations([(s, "data/raw/oaf/x.json")], True, PATTERNS, override=True)
    assert G.pr_violations([("A", "data/raw/oaf/new.json")], True, PATTERNS, False) == []
    assert G.manifest_append_only("a\nb\n", "a\nb\nc\n")
    assert not G.manifest_append_only("a\nb\n", "a\nc\n")
    assert not G.manifest_append_only("a\nb\n", "a\n")
    assert G.push_violations([("M", "data/manifest.jsonl")], False, PATTERNS)
    assert G.pr_violations([("M", "data/manifest.jsonl")], False, PATTERNS, override=True)


def test_pr_command_on_a_real_repository(tmp_path, monkeypatch):
    import os

    for var in [v for v in os.environ if v.startswith("GIT_")]:  # e.g. set by pre-commit hooks
        monkeypatch.delenv(var)

    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data/manifest.jsonl").write_text("a\n")
    (tmp_path / "data/raw/x.csv").write_text("1\n")
    (tmp_path / "prompts/p.txt").write_text("p\n")
    git("add", ".")
    git("commit", "-qm", "base")
    (tmp_path / "data/manifest.jsonl").write_text("a\nb\n")
    (tmp_path / "data/raw/y.csv").write_text("2\n")
    git("add", ".")
    git("commit", "-qm", "append data")
    frozen = tmp_path / "frozen.txt"
    frozen.write_text("prompts/*\n")
    monkeypatch.chdir(tmp_path)
    assert G.main(["pr", "--frozen", str(frozen), "HEAD~1", "HEAD"]) == 0
    (tmp_path / "prompts/p.txt").write_text("changed\n")
    (tmp_path / "data/raw/x.csv").write_text("changed\n")
    git("commit", "-qam", "edit frozen and raw")
    assert G.main(["pr", "--frozen", str(frozen), "HEAD~1", "HEAD"]) == 1
    assert G.main(["pr", "--frozen", str(frozen), "HEAD~1", "HEAD", "--override"]) == 1  # raw
    git("revert", "--no-edit", "HEAD")
    (tmp_path / "prompts/p.txt").write_text("changed\n")
    git("commit", "-qam", "edit frozen only")
    assert G.main(["pr", "--frozen", str(frozen), "HEAD~1", "HEAD", "--override"]) == 0
    head = git("rev-parse", "HEAD").stdout.decode().strip()
    assert G.main(["push", "--frozen", str(frozen), head]) == 1
    (tmp_path / "data/raw/tab\tname.csv").write_text("x\n")  # quoted by git without -z
    git("add", ".")
    git("commit", "-qm", "odd name")
    (tmp_path / "data/raw/tab\tname.csv").write_text("y\n")
    git("commit", "-qam", "edit odd name")
    assert G.main(["pr", "--frozen", str(frozen), "HEAD~1", "HEAD"]) == 1
