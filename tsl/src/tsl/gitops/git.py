"""Thin wrapper over the git command line (SDD-04 §2.2: no GitPython)."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import time
from pathlib import Path

from tsl.core import proc
from tsl.core.errors import TslError

# A git lock file older than this was left by a git command that died (D2).
STALE_GIT_LOCK_S = 120
# Left over from a sync that did not finish: not a network problem (D2).
REPAIR_HINT = (
    "A companion sync did not finish. /truminds:resume <run_id> (tsl state resume <run_id>) "
    "repairs it; tsl doctor --run shows what is left"
)
_LEFTOVER = ("index.lock", "rebase-merge", "rebase-apply", "rebase in progress", "middle of")


def _hint(text: str) -> str | None:
    """A cause-specific next step: None keeps E-GIT-01's network hint (fetch, push)."""
    low = text.lower()
    return REPAIR_HINT if any(k in low for k in _LEFTOVER) else None


class GitError(Exception):
    def __init__(self, op: str, detail: str, next_: str | None = None) -> None:
        super().__init__(f"git {op}: {detail}")
        self.op = op
        self.detail = detail
        self.next = next_

    def tsl(self) -> TslError:
        return TslError("E-GIT-01", op=self.op, detail=self.detail[:120], next=self.next)


def conflict_error(paths: list[str]) -> GitError:
    """Local edits that collide with what is on GitHub: say which file and how to keep GitHub's."""
    first = paths[0]
    return GitError(
        "pull",
        f"your local edits to {first} conflict with the version on GitHub",
        f"Keep GitHub's version: git checkout HEAD -- {first}; then git stash list and, if the "
        "entry is only that edit, git stash drop. Never edit runs/ files by hand",
    )


class Git:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["LC_ALL"] = "C"
        return env

    def run(
        self, *args: str, check: bool = True, input_: str | None = None, timeout: float = 60
    ) -> subprocess.CompletedProcess[str]:
        try:
            p = proc.run(
                ["git", *args], cwd=self.cwd, input_=input_, env=self._env(), timeout=timeout
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitError(args[0], type(exc).__name__) from exc
        if check and p.returncode != 0:
            text = (p.stderr or p.stdout).strip()
            lines = text.splitlines()
            raise GitError(args[0], lines[-1] if lines else f"exit {p.returncode}", _hint(text))
        return p

    def out(self, *args: str) -> str:
        return self.run(*args).stdout.strip()

    def ok(self, *args: str) -> bool:
        return self.run(*args, check=False).returncode == 0

    def raw(self, *args: str) -> bytes | None:
        try:
            p = proc.run(["git", *args], cwd=self.cwd, text=False, env=self._env(), timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return p.stdout if p.returncode == 0 else None

    # ---- queries
    def is_repo(self) -> bool:
        return self.ok("rev-parse", "--git-dir")

    def head(self) -> str:
        return self.out("rev-parse", "HEAD")

    def branch(self) -> str:
        return self.out("rev-parse", "--abbrev-ref", "HEAD")

    def has_remote(self, name: str = "origin") -> bool:
        return name in self.out("remote").split()

    def exists_at(self, ref: str, path: str) -> bool:
        return self.ok("cat-file", "-e", f"{ref}:{path}")

    def show(self, ref: str, path: str) -> bytes | None:
        return self.raw("show", f"{ref}:{path}")

    def resolve(self, ref: str) -> str | None:
        p = self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        return p.stdout.strip() if p.returncode == 0 else None

    def tree_of(self, ref: str) -> str:
        return self.out("rev-parse", f"{ref}^{{tree}}")

    def is_ancestor(self, a: str, b: str) -> bool:
        return self.ok("merge-base", "--is-ancestor", a, b)

    def ls_tree(self, commit: str, scope: str = ".") -> list[str]:
        args = ["ls-tree", "-r", "--name-only", "-z", commit]
        if scope not in (".", ""):
            args += ["--", scope]
        p = self.run(*args)
        return sorted(x for x in p.stdout.split("\0") if x)

    def rev_list_count(self, src: str, head: str, scope: str = ".") -> int:
        args = ["rev-list", "--count", "--first-parent", f"{src}..{head}"]
        if scope not in (".", ""):
            args += ["--", scope]
        return int(self.out(*args) or "0")

    def diff_names(self, a: str, b: str, scope: str = ".") -> list[str]:
        args = ["diff", "--name-only", a, b]
        if scope not in (".", ""):
            args += ["--", scope]
        return [x for x in self.out(*args).splitlines() if x]

    def diff_bytes(self, a: str, b: str) -> bytes:
        return self.raw("diff", "--binary", "--no-color", "--no-ext-diff", a, b) or b""

    def numstat(self, a: str, b: str) -> tuple[int, int, list[str]]:
        added = deleted = 0
        files: list[str] = []
        for line in self.out("diff", "--numstat", a, b).splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            files.append(parts[2])
            if parts[0] != "-":
                added += int(parts[0])
                deleted += int(parts[1])
        return added, deleted, files

    def is_tracked(self, rel: str) -> bool:
        return self.ok("ls-files", "--error-unmatch", "--", rel)

    def unpushed(self, branch: str, paths: list[str]) -> bool:
        if not self.has_remote():
            return True
        upstream = f"origin/{branch}"
        if self.resolve(upstream) is None:
            return True
        return bool(self.out("log", "--oneline", f"{upstream}..HEAD", "--", *paths))

    # ---- changes
    def mv(self, src: str, dst: str) -> None:
        (self.cwd / dst).parent.mkdir(parents=True, exist_ok=True)
        if self.is_tracked(src):
            self.run("mv", "-k", "--", src, dst)
        if (self.cwd / src).exists():
            shutil.move(str(self.cwd / src), str(self.cwd / dst))

    def commit(self, message: str, paths: list[str], trailer: str | None = None) -> str | None:
        if self.leftovers()["rebase"]:
            # A commit now would land on the half-finished rebase, and repairing it (rebase
            # --abort) would drop it. The files stay on disk; the repair commits them later.
            raise GitError("commit", "a companion sync did not finish", REPAIR_HINT)
        existing = [p for p in paths if (self.cwd / p).exists() or self.is_tracked(p)]
        if existing:
            self.run("add", "-A", "--", *existing)
            # machine-local files never enter history (SDD-02 §11.2, SDD-12 §3.1)
            self.run(
                "rm",
                "-q",
                "--cached",
                "--ignore-unmatch",
                "--",
                ":(glob)**/.local.lock",
                ":(glob).tsl/**",
                check=False,
            )
        if self.ok("diff", "--cached", "--quiet"):
            return None
        msg = message + (f"\n\n{trailer}" if trailer else "")
        self.run("commit", "-q", "-m", msg)
        return self.head()

    def fetch(self) -> None:
        self.run("fetch", "-q", "origin", timeout=60)

    def unmerged(self) -> list[str]:
        return self.run("diff", "--name-only", "--diff-filter=U", check=False).stdout.split()

    def rebase(self, onto: str) -> None:
        if left := self.unmerged():
            raise conflict_error(left)
        p = self.run("rebase", "-q", "--autostash", onto, check=False)
        if left := self.unmerged():  # the autostash did not re-apply cleanly
            raise conflict_error(left)
        if p.returncode != 0:
            self.run("rebase", "--abort", check=False)
            text = (p.stderr or "conflict").strip()
            # A rebase is local: whatever stopped it, the network is not the cause.
            raise GitError("rebase", text[:120], _hint(text) or REPAIR_HINT)

    # ---- repair (D2)
    def git_dir(self) -> Path:
        return Path(self.out("rev-parse", "--absolute-git-dir"))

    def leftovers(self) -> dict[str, str | float | None]:
        """What a git command that died left in the repo: a rebase still in progress (its
        branch), and the age in seconds of the index lock. Reads files only."""
        gd = self.git_dir()
        head: str | None = None
        for name in ("rebase-merge", "rebase-apply"):
            d = gd / name
            if d.is_dir():
                hp = d / "head-name"
                head = hp.read_text(encoding="utf-8").strip() if hp.is_file() else "?"
                break
        lock = gd / "index.lock"
        age = time.time() - lock.stat().st_mtime if lock.is_file() else None
        return {"rebase": head, "index_lock_age_s": age}

    def repair(self, branch: str) -> list[dict[str, str]]:
        """Undo what a killed sync left: a stale index lock, and tsl's own half-finished rebase
        of `branch` (git rebase --abort: the branch goes back to before the sync, local commits
        kept, the autostash put back). Returns what it repaired. A rebase of another branch is
        someone's own work: GitError, never touched."""
        done: list[dict[str, str]] = []
        left = self.leftovers()
        age = left["index_lock_age_s"]
        if isinstance(age, float) and age > STALE_GIT_LOCK_S:
            with contextlib.suppress(OSError):
                (self.git_dir() / "index.lock").unlink()
                done.append(
                    {
                        "what": "git-lock",
                        "detail": f"removed a git lock left {int(age)} s ago by a git "
                        "command that did not finish",
                    }
                )
        head = left["rebase"]
        if head:
            if head != f"refs/heads/{branch}":
                raise GitError(
                    "rebase",
                    f"a rebase of {head} is in progress in the companion repo",
                    "Finish it with git rebase --continue or stop it with git rebase --abort, "
                    "then repeat",
                )
            # rebase --abort resets the working tree: files tsl wrote after the sync died (a
            # state.json) would be lost. Keep them aside and put them back after. The run's own
            # .local.lock is never moved: the process that holds it may be this one.
            saved = bool(self.run("status", "--porcelain", check=False).stdout.strip()) and (
                self.run(
                    "stash",
                    "push",
                    "-q",
                    "--include-untracked",
                    "-m",
                    "tsl: files written during a half-finished sync",
                    "--",
                    ".",
                    ":(exclude,glob)**/.local.lock",
                    check=False,
                ).returncode
                == 0
            )
            p = self.run("rebase", "--abort", check=False)
            if p.returncode != 0:
                lines = (p.stderr or p.stdout).strip().splitlines()
                raise GitError(
                    "rebase",
                    "could not stop a half-finished sync: " + (lines[-1] if lines else "?"),
                    f"git -C {self.cwd} rebase --abort, then repeat",
                )
            done.append(
                {
                    "what": "rebase",
                    "detail": "stopped a companion sync (git rebase) that did not finish; "
                    "local commits and files are kept",
                }
            )
            if saved and self.run("stash", "pop", "-q", check=False).returncode != 0:
                self.run("reset", "-q", "--merge", check=False)  # no half-applied files
                done.append(
                    {
                        "what": "stash",
                        "detail": "files written during the half-finished sync did not fit "
                        "back; they are kept in git stash (tsl doctor --run shows it)",
                    }
                )
        return done

    def push(self, branch: str, remote_branch: str | None = None) -> bool:
        p = self.run(
            "push", "-q", "origin", f"{branch}:{remote_branch or branch}", check=False, timeout=60
        )
        return p.returncode == 0

    def drop_last_commit(self) -> None:
        self.run("reset", "-q", "--soft", "HEAD~1")
        self.run("reset", "-q")

    def sync_push(self, branch: str, retries: int = 3) -> bool:
        """Fetch, rebase, push; up to `retries` tries (SDD-12 §3.4). False when it still fails.
        A sync that a killed command left half-finished is repaired first (D2)."""
        try:
            self.repair(branch)
        except GitError:
            return False
        for _ in range(retries):
            try:
                self.fetch()
                if self.resolve(f"origin/{branch}") is not None:
                    self.rebase(f"origin/{branch}")
            except GitError:
                return False
            if self.push(branch):
                return True
        return False


def worktree_tree(clone: Path) -> str:
    """Tree object of the working tree (tracked + untracked), built in a temp index."""
    import tempfile

    g = Git(clone)
    with tempfile.TemporaryDirectory() as d:
        env_index = str(Path(d) / "index")
        env = g._env()
        env["GIT_INDEX_FILE"] = env_index
        for args in (["read-tree", "HEAD"], ["add", "-A"], ["write-tree"]):
            p = proc.run(["git", *args], cwd=clone, env=env, timeout=60)
            if p.returncode != 0:
                raise GitError(args[0], p.stderr.strip()[:120])
        return p.stdout.strip()
