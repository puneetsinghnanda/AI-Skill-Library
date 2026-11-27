"""C1: only a code citation of a known product repo is exempt from SEC-ENT-01 as a whole.

`<repo>:<path>.<ext>#<anchor>` with a repo the caller names: directories are checked whole and
the file name piece by piece; every other token is checked exactly as before. Cases include
every example from the #63 reviews.
"""

from tsl.harness import detectors

REPOS = frozenset({"sample-system"})
TOK = "Zx9Qw7Lm3Kp8Rt2Vb6Nc4Hd1Fg5Js0Ty"
MIG = "sample-system:db/migrations/20261016T090000__create_reference_lists.sql#L16"


def _ent(text: str, repos: frozenset[str] = REPOS) -> list[detectors.Hit]:
    return [h for h in detectors.scan(text, cite_repos=repos) if h.rule_id == "SEC-ENT-01"]


# --- the false positive this fixes -------------------------------------------------------------


def test_cited_migration_near_primary_key_is_not_a_secret() -> None:
    """The HMS-11 secrev line that failed tsl-companion-check on every push to main."""
    assert not _ent(f'"quote": "serial PRIMARY KEY",\n"ref": "{MIG}"\n')


def test_other_cite_shapes_of_a_known_repo_are_not_secrets() -> None:
    for cite in (
        "sample-system:web/x9Kq/20261016T090000__orders_api.spec.ts#L4",
        "sample-system:src/types/20261016T090000__api.d.ts#L4",
        "sample-system:config/app_20261016T090000x9Kq.properties#L3",
        "sample-system:db/migrations/20261016T090100__create_doctors.sql#L1-L9",
    ):
        assert not _ent(f'primary key, "ref": "{cite}"\n'), cite


def test_without_repo_names_the_scanner_is_unchanged() -> None:
    """Callers that pass no repo names (validate, context build, tickets) see no exemption."""
    assert _ent(f'"quote": "serial PRIMARY KEY", "ref": "{MIG}"\n', frozenset())


# --- secrets are still found -------------------------------------------------------------------


def test_secrets_outside_cites_are_flagged_as_before() -> None:
    cases = (
        f"api key: {TOK}.trim()",
        f"secret at https://{TOK}.ngrok.io/x",
        f"the token is {TOK}.Use it once.",
        f"webhook key: https://hooks.example.com/services/{TOK}/payload.json",
        f"the api key is ab_{TOK}.Go to settings",
        f"api key in s3://bucket/{TOK}_dump.sql",
        "secret …/s/Zx9Qw7Lm3Kp8Rt2V_b6Nc4Hd1Fg5Js0Ty/payload.json",
        "token /d/Zx9Qw7Lm3Kp8Rt2V-b6Nc4Hd1Fg5Js0Ty.json",
        "api key https://Zx9Qw7Lm3Kp8Rt2V-b6Nc4Hd1Fg5Js0Ty.example.sh",
        "secret: Zx9Qw7Lm3/Kp8Rt2Vb6Nc4/Hd1Fg5Js0Ty9q",
    )
    for text in cases:
        assert _ent(text + "\n"), text


def test_a_secret_shaped_as_a_cite_is_still_flagged() -> None:
    cases = (
        f"api key sample-system:{TOK}/x.json#L1",  # secret as a directory of a known repo
        f"api key sample-system:a/{TOK}.ts#L1",  # secret as the file name
        f"api key sample-system:a/{TOK}_x.ts#L1",  # secret as a piece of the file name
        "api key sample-system:a/Zx9Qw7Lm3Kp8Rt2V_b6Nc4Hd1Fg5Js0Ty.ts#L1",  # name with `_`
        f"api key https:{TOK}/x.sql#L1",  # not a product repo
        f"api key other-repo:a/{TOK}.ts#L1",  # not a product repo
        f"api key https://{TOK}/x.sql#L1",  # a URL, not a cite
        f"api key sample-system:a/{TOK}+x.ts#L2",  # base64 characters
        f"api key sample-system:a/{TOK}.ts",  # no anchor: not a cite
        f"api key sample-system:a/{TOK}.TS#L1",  # upper-case extension: not a cite
        f"api key xsample-system:a/{TOK}.ts#L1",  # repo name must start the word
    )
    for text in cases:
        assert _ent(text + "\n"), text


# --- no new false positives --------------------------------------------------------------------


def test_run_ids_in_paths_are_not_secrets() -> None:
    for line in (
        'cites: ["runs/run_01M7HH0DM88V7JHMVZPSYX5BWE/ide-answers.md#a-07"] key',
        'cites: ["artifacts/HMS-7/run_01M6FXTGC048AXKA8X69ASS5QB/design.md#overview"] key',
        "key sample-system:runs/HMS-7_run_01M6FXTGC048AXKA8X69ASS5QB.json#L1",
    ):
        assert not _ent(line + "\n"), line


def test_path_words_are_not_the_keyword_for_a_cite() -> None:
    """The keyword search skips the whole token, so `add_api_key` in a cite is not `key`."""
    assert not _ent("see sample-system:db/migrations/add_api_key/x9Kq_20261016T090000.sql#L1\n")


# --- round 5 (approved review of cd98a65) ------------------------------------------------------


def test_a_secret_split_across_a_cite_path_is_flagged() -> None:
    """Short random pieces joined: the whole secret, not each piece, is what is checked."""
    for cite in (
        "sample-system:Zx9Qw7Lm3K/p8Rt2Vb6Nc/4Hd1Fg5Js0T.json#L1",
        "sample-system:Zx9Qw7Lm3K_p8Rt2Vb6Nc/docs/4Hd1Fg5Js0T.md#L1",
        "sample-system:a/Zx9Qw7Lm3K-p8Rt2Vb6Nc-4Hd1Fg5Js0T/b.py#L1",
    ):
        assert _ent(f"secret key {cite}\n"), cite


def test_the_reported_span_hash_clears_a_cite_finding() -> None:
    """--show-allow-hashes hashes text[start:end]; that hash must clear the finding, ids or not."""
    import hashlib

    ulid = "evt_01M6FXTGC048AXKA8X69ASS5QB"
    text = f"secret key sample-system:db/{ulid}_{TOK}.json#L1\n"
    hits = _ent(text)
    assert hits
    allow = frozenset(hashlib.sha256(text[h.start : h.end].encode()).hexdigest() for h in hits)
    assert not [
        h for h in detectors.scan(text, allow, cite_repos=REPOS) if h.rule_id == "SEC-ENT-01"
    ]


def test_cites_in_markdown_emphasis_tables_and_angle_brackets() -> None:
    for wrap in ("**{}**", "| {} |", "|{}|", "<{}>", "*{}*"):
        assert not _ent("primary key " + wrap.format(MIG) + "\n"), wrap


def test_more_source_extensions_and_extensionless_files() -> None:
    for cite in (
        "sample-system:web/src/components/20261016T090000__orders_panel.vue#L4",
        "sample-system:native/src/20261016T090000__crc_table.c#L4",
        "sample-system:ios/App/20261016T090000__session_store.swift#L4",
        "sample-system:infra/images/20261016T090000__api_worker/Dockerfile#L4",
    ):
        assert not _ent(f"primary key {cite}\n"), cite


def test_an_extensionless_name_must_be_a_known_one() -> None:
    assert _ent(f"secret key sample-system:infra/{TOK}#L4\n")
