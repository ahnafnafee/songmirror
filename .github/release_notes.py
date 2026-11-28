"""Generate a mainline release version and its opening notes from Git history."""

import argparse
from pathlib import Path
import re
import subprocess
import tomllib


SCRIPT = ".github/release_notes.py"
NOTES = ".github/release-notes"
SUBJECT = re.compile(r"^(\w+)(?:\([^)]+\))?(!)?:\s+(.+)$")
BREAKING = re.compile(r"(?:^|\n)BREAKING[ -]CHANGE:\s+")
MERGE = re.compile(r"^Merge pull request #\d+\b")
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def git(*arguments):
    return subprocess.check_output(
        ["git", *arguments], encoding="utf-8", errors="replace",
    ).strip()


def commits(revision_range):
    return git("log", "--format=%B", "-z", revision_range).split("\0")


def subject_of(message):
    subject, _, body = message.partition("\n")
    if MERGE.match(subject):
        return next((item.strip() for item in body.splitlines() if item.strip()), "")
    return "" if subject.startswith("Merge ") else subject


def bump(version, messages):
    subjects = [SUBJECT.fullmatch(subject_of(message)) for message in messages]
    major, minor, patch = version
    if any(BREAKING.search(message) for message in messages) or any(
        match and match[2] for match in subjects
    ):
        return major + 1, 0, 0
    if any(match and match[1] == "feat" for match in subjects):
        return major, minor + 1, 0
    return major, minor, patch + 1


def tag_of(version):
    return "v" + ".".join(map(str, version))


def release_history(revision):
    additions = git(
        "log", "--first-parent", "--diff-merges=first-parent", "--reverse",
        "--diff-filter=A", "--format=%H", revision, "--", SCRIPT,
    ).splitlines()
    if not additions:
        raise SystemExit("The release generator must be committed in mainline history.")
    first = additions[0]
    initial = tomllib.loads(git("show", f"{first}:pyproject.toml"))["project"]["version"]
    match = VERSION.fullmatch(initial)
    if not match:
        raise SystemExit(f"Expected major.minor.patch in the initial pyproject.toml, got {initial}")
    version = tuple(map(int, match.groups()))
    history = [(first, tag_of(version))]
    parent = first
    for commit in git("rev-list", "--first-parent", "--reverse", f"{first}..{revision}").splitlines():
        version = bump(version, commits(f"{parent}..{commit}"))
        history.append((commit, tag_of(version)))
        parent = commit
    return history


def previous_release(history):
    # An out-of-order build may see a tag for a newer commit. Only use the
    # expected tags of earlier mainline commits as changelog start points.
    tags = {}
    refs = git("for-each-ref", "--format=%(refname:short) %(objectname) %(*objectname)", "refs/tags")
    for ref in refs.splitlines():
        name, direct, *peeled = ref.split()
        tags[name] = peeled[0] if peeled else direct
    for commit, tag in reversed(history[:-1]):
        if tags.get(tag) == commit:
            return commit, tag
    return git("rev-parse", f"{history[0][0]}^1"), ""


def note_fragments(base, revision):
    changed = git("diff", "--diff-filter=A", "--name-only", "-z", base, revision, "--", NOTES)
    fragments = []
    for path in changed.split("\0"):
        if not path.endswith(".md"):
            continue
        text = git("show", f"{revision}:{path}")
        headline, _, body = text.partition("\n")
        if not headline.startswith("# ") or not body.strip():
            raise SystemExit(f"{path} needs a level-one heading and a release note.")
        fragments.append((headline[2:].strip(), body.strip()))
    return fragments


def default_notes(tag, messages):
    priorities = {"feat": 0, "fix": 1, "perf": 2}
    changes = {}
    for message in messages:
        subject = subject_of(message)
        if subject:
            match = SUBJECT.fullmatch(subject)
            name = match[3] if match else subject
            name = re.sub(r"\s+\(#\d+\)$", "", name).strip()
            if name:
                name = name[0].upper() + name[1:]
                changes.setdefault(name, priorities.get(match[1], 3) if match else 3)
    ordered = sorted(changes, key=changes.get)
    if not ordered:
        return "Project maintenance", f"SongMirror {tag} rolls up the latest maintenance changes."
    highlights = "\n".join(f"- {name}" for name in ordered[:5])
    return ordered[0], f"SongMirror {tag} includes these updates.\n\n{highlights}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    history = release_history(args.revision)
    revision, tag = history[-1]
    base, previous_tag = previous_release(history)
    fragments = note_fragments(base, revision)
    if fragments:
        headline, lead = fragments[0]
        notes = "\n\n".join([lead, *(f"## {title}\n\n{body}" for title, body in fragments[1:])])
    else:
        headline, notes = default_notes(tag, commits(f"{base}..{revision}"))
    headline = " ".join(headline.replace("`", "").split())
    title = f"SongMirror {tag} — {headline}"
    args.notes.write_text(notes + "\n", encoding="utf-8")
    with args.output.open("a", encoding="utf-8") as output:
        print(f"tag={tag}\ntitle={title}\nprevious_tag={previous_tag}", file=output)
    print(tag)


if __name__ == "__main__":
    main()
