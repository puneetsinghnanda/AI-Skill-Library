"""Shell command shapes H7 needs: safe environment prefixes and read-only commands (SDD-03 §14).

The pre-tool hook classifies a Bash command when it sees all of it; the tool log keeps only its
first 80 characters plus the verdict. Anything this module cannot prove read-only is not.
"""

from __future__ import annotations

import fnmatch
import re

# Variables that may prefix a command without changing which program runs or what it may touch.
SAFE_ENV = frozenset(
    {"PYTHONIOENCODING", "PYTHONUTF8", "NO_COLOR", "FORCE_COLOR", "LANG", "LC_ALL", "TERM"}
)
_ASSIGN = re.compile(r"""([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|'[^']*'|[^\s'"]*)\s+""")

# Programs that only read files or repository history, with flags that would make them write.
READ_ONLY = frozenset(
    {
        "cat",
        "head",
        "tail",
        "ls",
        "grep",
        "rg",
        "wc",
        "find",
        "sort",
        "uniq",
        "diff",
        "stat",
        "file",
        "pwd",
        "git",
    }
)
GIT_READ = frozenset({"log", "show", "diff", "status", "rev-parse", "ls-files", "blame"})
_WRITING_FLAGS = {
    "find": ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fls"),
    "sort": ("-o", "--output"),
    "git": ("--output",),
    "rg": ("--pre",),
    "file": ("-C", "--compile"),
}
# Chaining, redirection, substitution and backgrounding all make a command more than one read.
_UNSAFE = (">", "<", ";", "&", "`", "$(", "\n", "\r")


# `cd <dir> &&` or `cd <dir>;` in front of a command only picks the folder it runs in.
_CD = re.compile(r"""cd\s+("[^"]*"|'[^']*'|[^\s;&|'"]+)\s*(?:&&|;)\s*""")


def strip_cd(cmd: str) -> str:
    """The command without leading `cd <dir> &&` / `cd <dir>;` parts."""
    rest = cmd.strip()
    while m := _CD.match(rest):
        rest = rest[m.end() :]
    return rest


def strip_safe_env(cmd: str) -> str | None:
    """The command without leading SAFE_ENV assignments; None when another variable is set."""
    rest = cmd.strip()
    while m := _ASSIGN.match(rest):
        if m.group(1) not in SAFE_ENV:
            return None
        rest = rest[m.end() :]
    return rest


def _git_sub(args: list[str]) -> str | None:
    """git's subcommand after its global options; None for -c, which can run a pager or alias."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-c" or args[i].startswith("-c"):
            return None
        i += 2 if args[i] == "-C" else 1
    return args[i] if i < len(args) else None


def bash_allowed(cmd: str, allowed: list[str]) -> bool:
    """True when the command, after `cd` and safe env prefixes, matches a Bash(...) tool or tsl."""
    body = strip_cd(cmd)
    body = strip_safe_env(body) or body
    pats = [a[5:-1] for a in allowed if a.startswith("Bash(") and a.endswith(")")] + ["tsl *"]
    return any(fnmatch.fnmatch(body, p) for p in pats)


def is_read_only(cmd: str) -> bool:
    """True only for a pipeline of known read-only programs with no writing flags."""
    body = strip_safe_env(strip_cd(cmd))
    if not body or any(u in body for u in _UNSAFE) or "||" in body:
        return False
    for segment in body.split("|"):
        words = segment.split()
        if not words or words[0] not in READ_ONLY:
            return False
        if words[0] == "git" and _git_sub(words[1:]) not in GIT_READ:
            return False
        if any(w.startswith(f) for f in _WRITING_FLAGS.get(words[0], ()) for w in words[1:]):
            return False
    return True
