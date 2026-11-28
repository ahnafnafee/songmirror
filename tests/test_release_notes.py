"""Release metadata integration tests with disposable Git histories."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest


RELEASE_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "release_notes.py"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "release-test@example.invalid")
    git(tmp_path, "config", "user.name", "Release Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    git(tmp_path, "config", "tag.gpgSign", "false")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    git(tmp_path, "add", "pyproject.toml")
    git(tmp_path, "commit", "-m", "chore: create project")
    git(tmp_path, "switch", "-c", "feat/release-notes")
    notes = tmp_path / ".github" / "release-notes"
    notes.mkdir(parents=True)
    shutil.copyfile(RELEASE_SCRIPT, notes.parent / RELEASE_SCRIPT.name)
    (notes / "spotify.md").write_text(
        "# Better Shazam to Spotify playlist imports\n\nImport a Shazam CSV into Spotify.\n",
        encoding="utf-8",
    )
    git(tmp_path, "add", ".github")
    git(tmp_path, "commit", "-m", "feat: improve Spotify imports")
    git(tmp_path, "switch", "main")
    git(tmp_path, "merge", "--no-ff", "-m", "feat: introduce automated releases", "feat/release-notes")
    return tmp_path


def metadata(repo, revision="HEAD"):
    body, output = repo / "notes.out", repo / "metadata.out"
    output.unlink(missing_ok=True)
    subprocess.run(
        [sys.executable, str(RELEASE_SCRIPT), revision, "--notes", str(body), "--output", str(output)],
        cwd=repo, check=True,
    )
    values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    return values, body.read_text(encoding="utf-8")


def test_first_release_uses_project_version_and_curated_headline(repo):
    values, body = metadata(repo)
    assert values == {
        "tag": "v0.1.0",
        "title": "SongMirror v0.1.0 — Better Shazam to Spotify playlist imports",
        "previous_tag": "",
    }
    assert body == "Import a Shazam CSV into Spotify.\n"


def test_versions_follow_mainline_and_use_the_highest_bump_in_a_merge(repo):
    git(repo, "tag", "v0.1.0")
    git(repo, "commit", "--allow-empty", "-m", "fix(spotify): preserve album credits (#123)")
    patch_commit = git(repo, "rev-parse", "HEAD")
    assert metadata(repo)[0]["tag"] == "v0.1.1"
    git(repo, "switch", "-c", "feat/import-search")
    git(repo, "commit", "--allow-empty", "-m", "feat: add album search")
    git(repo, "commit", "--allow-empty", "-m", "feat: filter recordings by venue")
    git(repo, "switch", "main")
    git(repo, "merge", "--no-ff", "-m", "Merge pull request #124", "-m", "feat: expand import search",
        "feat/import-search")
    assert metadata(repo)[0]["tag"] == "v0.2.0"
    git(repo, "tag", "v0.2.0")
    git(repo, "commit", "--allow-empty", "-m", "fix: replace obsolete playlist identifiers",
        "-m", "BREAKING CHANGE: playlist identifiers have changed.")
    assert metadata(repo)[0]["tag"] == "v1.0.0"
    values, body = metadata(repo, patch_commit)
    assert values == {
        "tag": "v0.1.1",
        "title": "SongMirror v0.1.1 — Preserve album credits",
        "previous_tag": "v0.1.0",
    }
    assert "(#123)" not in body and "Shazam CSV" not in body
