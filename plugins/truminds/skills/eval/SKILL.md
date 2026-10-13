---
name: eval
description: Run a skill's eval cases on this seat and record a signed eval result. Only when the user types /truminds:eval.
argument-hint: <skill> [version]
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write
---
Eval plan from tsl (do not edit):
!`tsl eval plan $0 --json`

If "ok" is false, show "message" and "next" to the user and stop.

The plan lists "data.cases", each with "id", "input_dir" and "output_path", inside a scratch work
folder that tsl created ("data.workdir"). Scratch folders never touch a real companion repo.

For each case, in order:
1. Use the skill named in "data.skill" on that case. Its input files are in "input_dir"; it must
   write exactly "output_path". If the post-write hook blocks the write, fix what it says and write again.
2. Run the `review` skill on "output_path".
3. Run `tsl eval check <skill> --case <id> --json` and show its one-line result.
   Never judge a case yourself; only tsl compares the output with the case's expectations.

When every case is done, run `tsl eval run <skill> --json` (add `--version <version>` if one was given).
It scores all cases with code, signs the eval result with your key and writes
evals/results/<version>.eval-result.json. Show "data.pass_rate", "data.passed" of "data.cases" and "next".
If it fails with E-EVAL-01, show which cases failed and stop. Never edit eval cases, expectations or results.
