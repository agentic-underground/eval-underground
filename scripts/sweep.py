#!/usr/bin/env python3
"""Refuse to commit or push anything that should not be public.

    scripts/sweep.py            the staged tree (every file in the index) and the commit identity
    scripts/sweep.py --history  every blob and every author/committer in the history (pre-push)

Generic patterns live here: email addresses, home-directory paths, private IP addresses, credential
shapes, .env files, and an author identity that is not the project's noreply one.

Terms that are private to a maintainer cannot live here — this file is public, and listing them would
publish them. Put them one per line (regex, case-insensitive) in a file outside the repository and
point at it with `git config sweep.denylist <path>`. If that is configured and the file is missing,
the sweep refuses: a denylist that silently vanished is a sweep that silently passes.
"""
import os
import re
import subprocess
import sys

NOREPLY = "noreply@agentic-underground.invalid"

GENERIC = {
    "email address": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "home-directory path": r"/(?:hom[e]|User[s])/[A-Za-z0-9._-]+",
    "private IPv4 address": r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b",
    "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "Hugging Face token": r"\bhf_[A-Za-z0-9]{30,}",
    "API key": r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
# Addresses that are public by construction: the project's noreply identity, and the noreply
# address of the Co-Authored-By trailer on agent-assisted commits.
ALLOWED_EMAILS = {NOREPLY, "noreply@anthropic.com"}
SECRET_FILES = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|id_[rd]sa.*|credentials\.json|\.netrc)$")

# A URL's host must be a public domain name. A single-label host, a bare IP address, or a name under
# a suffix that only resolves inside some network names a machine nobody outside it can reach —
# a package mirror in a lockfile is the usual way one gets in.
URL_HOST = re.compile(r"\b[a-z][a-z0-9+.-]*://(?:[^@/\s'\"<>]*@)?(\[[0-9a-f:]+\]|[^/\s:'\"<>?#)\]]+)", re.IGNORECASE)
PRIVATE_SUFFIXES = {"local", "lan", "internal", "home", "localdomain", "corp", "intranet", "private",
                    "localhost", "test"}


def private_host(host):
    h = host.lower().rstrip(".")
    if h.startswith("[") or re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", h):
        return "a bare IP address"
    if "." not in h:
        return "a single-label host"
    if h.rsplit(".", 1)[1] in PRIVATE_SUFFIXES:
        return f"a .{h.rsplit('.', 1)[1]} host"
    return None


def scan_hosts(name, text):
    hits = []
    for m in URL_HOST.finditer(text):
        why = private_host(m.group(1))
        if why:
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{name}:{line}: URL to {why}, not a public domain: {m.group(0)}")
    return hits


def git(*args, binary=False):
    out = subprocess.run(["git", *args], capture_output=True, check=True).stdout
    return out if binary else out.decode()


def denylist():
    path = subprocess.run(["git", "config", "sweep.denylist"], capture_output=True, text=True).stdout.strip()
    if not path:
        print("sweep: no private denylist configured (git config sweep.denylist <path>); generic checks only",
              file=sys.stderr)
        return {}
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        sys.exit(f"sweep: REFUSED — sweep.denylist points at {path}, which does not exist")
    terms = [ln.strip() for ln in open(path) if ln.strip() and not ln.startswith("#")]
    return {f"private term #{i}": t for i, t in enumerate(terms, 1)}


def scan(name, text, patterns):
    hits = []
    for label, pat in patterns.items():
        for m in re.finditer(pat, text, flags=re.IGNORECASE if label.startswith("private term") else 0):
            if label == "email address" and m.group(0).lower() in ALLOWED_EMAILS:
                continue
            line = text.count("\n", 0, m.start()) + 1
            # a private term's text is not echoed: the report is read in public logs too
            shown = "<hidden>" if label.startswith("private term") else m.group(0)
            hits.append(f"{name}:{line}: {label}: {shown}")
    return hits + scan_hosts(name, text)


def blob_text(data):
    return None if b"\0" in data[:8000] else data.decode("utf-8", "replace")


def identities_ok(idents):
    bad = []
    for who in idents:
        email = re.search(r"<([^>]*)>", who)
        if not email or email.group(1) != NOREPLY:
            bad.append(f"identity: {who.strip()} — set git config user.email {NOREPLY}")
    return bad


def staged(patterns):
    hits = []
    for path in git("diff", "--cached", "--name-only", "--diff-filter=A").splitlines():
        if SECRET_FILES.search(path):
            hits.append(f"{path}: a secret-shaped file is being added")
    for entry in git("ls-files", "-s", "-z").split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        hits += scan("(path)", path, patterns)
        text = blob_text(git("cat-file", "blob", meta.split()[1], binary=True))
        if text is not None:
            hits += scan(path, text, patterns)
    idents = [git("var", "GIT_AUTHOR_IDENT"), git("var", "GIT_COMMITTER_IDENT")]
    return hits + identities_ok(idents)


def history(patterns):
    hits, seen = [], set()
    for line in git("rev-list", "--all", "--objects").splitlines():
        sha, _, path = line.partition(" ")
        if sha in seen or git("cat-file", "-t", sha).strip() != "blob":
            continue
        seen.add(sha)
        hits += scan(f"(path {sha[:8]})", path, patterns)
        text = blob_text(git("cat-file", "blob", sha, binary=True))
        if text is not None:
            hits += scan(f"{path}@{sha[:8]}", text, patterns)
    for log in git("log", "--all", "--format=%an <%ae>%n%cn <%ce>%n%B%x00").split("\0"):
        lines = log.strip().splitlines()
        if len(lines) >= 2:
            hits += identities_ok(lines[:2])
            hits += scan("(commit message)", "\n".join(lines[2:]), patterns)
    return sorted(set(hits))


def main():
    patterns = {**GENERIC, **denylist()}
    hits = history(patterns) if "--history" in sys.argv else staged(patterns)
    if hits:
        print("sweep: REFUSED — this would make the following public:", file=sys.stderr)
        print("\n".join(f"  {h}" for h in hits), file=sys.stderr)
        return 1
    print("sweep: clean", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
