"""Typer layer only: parse arguments, call a service, print one envelope (SDD-04 §2.3, §3, §4).

`tsl hook <event>` and `tsl --version` are handled before Typer is imported (NFR-02, SDD-04 §11).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tsl import __version__


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["hook"] and len(args) >= 2:
        from tsl.hooks.dispatch import run

        out, code = run(args[1], sys.stdin.read())
        if out:
            sys.stdout.write(out + "\n")
        sys.exit(code)
    if args == ["--version"]:
        sys.stdout.write(f"tsl {__version__}\n")
        sys.exit(0)
    sys.exit(run_cli(args))


def run_cli(args: list[str]) -> int:
    import typer

    from tsl.cli import commands
    from tsl.cli.commands import app, render_error

    # --json, --no-color and -v are global and may appear anywhere (skills append --json).
    commands.FORCED["json"] = "--json" in args
    commands.FORCED["no_color"] = "--no-color" in args
    commands.FORCED["verbose"] = sum(a.count("v") for a in args if a in ("-v", "-vv"))
    args = [a for a in args if a not in ("--json", "--no-color", "-v", "-vv")]
    try:
        rv = app(args=args, standalone_mode=False, prog_name="tsl")
        return int(rv or 0)
    except typer.Exit as e:
        return int(e.exit_code)
    except typer.Abort:
        return 1
    except typer.TyperException as e:
        if type(e).__name__ == "NoArgsIsHelpError" and getattr(e, "ctx", None) is not None:
            sys.stdout.write(e.ctx.get_help() + "\n")  # type: ignore[attr-defined]
            return 0
        msg = e.format_message() if hasattr(e, "format_message") else str(e)
        return render_error("E-USE-01", msg, bool(commands.FORCED["json"]), args)


Fn = Callable[..., Any]
__all__ = ["Fn", "Path", "main", "run_cli"]
