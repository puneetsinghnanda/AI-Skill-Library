# Verifier container profiles (H3)

Each folder `<name>@<major>/` is one verifier profile: a `profile.yaml` (schema `verifier-profile.v1`) and the
`Dockerfile` of its image. `tsl verify` runs gate H3 for code steps with the profile named in `tsl.yaml`
`product_repos[].verifier_profile` (SDD-03 §4.5, §5.5).

| Profile | For | Image contents (pinned versions) | Named by |
| --- | --- | --- | --- |
| `node-22@1` | Node.js 22 projects | Node.js 22.11.0 on PostgreSQL 16.4 (bookworm), ESLint SARIF formatter 3.1.0, Semgrep 1.95.0, gitleaks 8.21.2 | Sample system (`examples/sample-system/companion-example/tsl.yaml`, SDD-06 §10.1) |
| `node-20@1` | Node.js 20 projects | Node.js 20.18.1 (bookworm), ESLint SARIF formatter 3.1.0, Semgrep 1.95.0, gitleaks 8.21.2 | SDD-03 §4.5, §5.5 example |
| `python-312@1` | Python 3.12 projects managed with uv | Python 3.12.7 (bookworm), uv 0.5.4, Ruff 0.7.4, Semgrep 1.95.0, gitleaks 8.21.2 | `verifier-profile.v1` sample |

Every profile has the steps `prepare`, `build`, `test`, `lint`, `sast`, `secrets` and `coverage`, because the
`implement`, `unit-test` and `test-automation` skills name them in their `checks.yaml` (`kind: container`).
The scanners follow SEC-01 §7.1 (gitleaks for secrets) and the SDD-03 §5.5 proposals (ESLint or Ruff, Semgrep);
the final choice stays with SEC-01 (SDD-03 OI-07).

## Image digests

Profiles reference images by digest only, never by tag. The registry is the GitHub Container Registry under
the repository owner, `ghcr.io/puneetsinghnanda/truminds/verifier-<name>` (OQ-10, decided by Puneet for the
test phase). Until a real digest is set, `image:` ends in the placeholder `@sha256:000…0`, and `tsl` refuses it
with E-H3-07 instead of pulling anything.

1. `.github/workflows/verifier-images.yml` runs on a push to `main` that touches `plugins/truminds/verifiers/**`
   or the workflow, or by hand (Actions → verifier-images → Run workflow). It lints each Dockerfile with
   hadolint, builds it, and pushes it with an SBOM as `:<major>` and `:<major>-<commit>`. It signs in with the
   workflow's own `GITHUB_TOKEN`, so there is no registry secret. On pull requests it builds without pushing.
2. The job summary prints one ready-to-paste line per profile: `image: ghcr.io/…@sha256:<digest>`.
3. A maintainer sets those lines in each `profile.yaml` in a reviewed PR (OPS-03 §2.1). CI never writes the
   digest itself.
4. Pulling: the packages are private by default. Either set each package to **Public** (GitHub → your profile
   → Packages → `truminds/verifier-<name>` → Package settings → Change visibility); the images hold only
   open-source tools. Or each tester runs `docker login ghcr.io` with a token that has `read:packages`.

## How tsl runs a step

`tsl/src/tsl/harness/verifier.py` (`docker_command`) runs every step in its own container:

```text
docker run --rm --network none --read-only --tmpfs /tmp --user 1000:1000 --cap-drop ALL \
  --security-opt no-new-privileges --cpus 2 --memory 4g --pids-limit 512 \
  -v <worktree>:/src:ro -v tsl-verifier-cache:/cache -v <out>:/out <image@digest> sh -c "<cmd>"
```

Only `prepare` runs without `--network none`, to reach the package registry. It copies the read-only source into
`/cache/w` and installs from the lock file there; the later steps work in `/cache/w` and write reports to `/out`.
Each image creates user 1000 and owns `/cache` and `/out` for it.

## Tests

`plugins/truminds/tests/test_verifiers.py` (run by `make test-plugin`) and `tsl/tests/test_docker.py`
(`make test-tsl`). Real image builds run only with a Docker daemon and `VERIFIER_BUILD=1`.

## Known limits

- The cache volume `tsl-verifier-cache` is shared, so `/cache/w` allows one H3 run at a time per machine.
- Semgrep's `p/default` ruleset is downloaded when the image is built; the image digest fixes that snapshot.
- `coverage` needs a project `coverage` script (Node) or `coverage` in the dev dependencies (Python). The sample
  system has no `coverage` script yet, so `ut.coverage-not-lower` fails there until one is added.
- `test` in the Node profiles is judged by exit code; the sample system's Vitest workspaces write no single JUnit file.
