"""Thin wrapper over the git command line (SDD-04 §2.2: no GitPython)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tsl.core.errors import TslError


class GitError(Exception):
    def __init__(self, op: str, detail: str) -> None:
        super().__init__(f"git {op}: {detail}")
        self.op = op
        self.detail = detail

    def tsl(self) -> TslError:
        return TslError("E-GIT-01", op=self.op, detail=self.detail[:120])


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
            p = subprocess.run(
                ["git", *args],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                input=input_,
                env=self._env(),
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitError(args[0], type(exc).__name__) from exc
        if check and p.returncode != 0:
            lines = (p.stderr or p.stdout).strip().splitlines()
            raise GitError(args[0], lines[-1] if lines else f"exit {p.returncode}")
        return p

    def out(self, *args: str) -> str:
        return self.run(*args).stdout.strip()

    def ok(self, *args: str) -> bool:
        return self.run(*args, check=False).returncode == 0

    def raw(self, *args: str) -> bytes | None:
        try:
            p = subprocess.run(
                ["git", *args],
                cwd=self.cwd,
                capture_output=True,
                env=self._env(),
                timeout=60,
                check=False,
            )
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

    def rebase(self, onto: str) -> None:
        p = self.run("rebase", "-q", "--autostash", onto, check=False)
        if p.returncode != 0:
            self.run("rebase", "--abort", check=False)
            raise GitError("rebase", (p.stderr or "conflict").strip()[:120])

    def push(self, branch: str, remote_branch: str | None = None) -> bool:
        p = self.run(
            "push", "-q", "origin", f"{branch}:{remote_branch or branch}", check=False, timeout=60
        )
        return p.returncode == 0

    def drop_last_commit(self) -> None:
        self.run("reset", "-q", "--soft", "HEAD~1")
        self.run("reset", "-q")

    def sync_push(self, branch: str, retries: int = 3) -> bool:
        """Fetch, rebase, push; up to `retries` tries (SDD-12 §3.4). False when it still fails."""
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
            p = subprocess.run(
                ["git", *args],
                cwd=clone,
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
                check=False,
            )
            if p.returncode != 0:
                raise GitError(args[0], p.stderr.strip()[:120])
        return p.stdout.strip()
