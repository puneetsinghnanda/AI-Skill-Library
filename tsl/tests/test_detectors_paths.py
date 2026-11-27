"""Regression: file names in cited paths are not secrets (C1, HMS-11 companion check)."""

from tsl.harness import detectors

# The secrev feedback line that failed tsl-companion-check on every push to main: the quote
# above it says "PRIMARY KEY", and the migration name is long, mixed and high-entropy.
HMS11 = (
    "        {\n"
    '          "quote": "serial PRIMARY KEY",\n'
    '          "ref": "sample-system:db/migrations/20261016T090000__create_reference_lists.sql#L16"\n'
    "        },\n"
)


def _ent(text: str) -> list[detectors.Hit]:
    return [h for h in detectors.scan(text) if h.rule_id == "SEC-ENT-01"]


def test_cited_migration_path_near_primary_key_is_not_a_secret() -> None:
    assert not _ent(HMS11)


def test_bare_file_name_near_key_is_not_a_secret() -> None:
    assert not _ent("key column defined in 20261016T090000__create_reference_lists.sql\n")


def test_token_near_key_is_still_flagged() -> None:
    assert _ent("api key: Zx9Qw7Lm3Kp8Rt2Vb6Nc4Hd1Fg5Js0Ty\n")


def test_token_ending_a_sentence_is_still_flagged() -> None:
    assert _ent("the token is Zx9Qw7Lm3Kp8Rt2Vb6Nc4Hd1Fg5Js0Ty.\n")


def test_jwt_like_token_near_key_is_still_flagged() -> None:
    # Joined at run time so the repo's own gitleaks scan does not flag this fake.
    jwt = ".".join(
        ["ey" + "JhbGciOiJIUzI1NiJ9x7Q", "ey" + "JzdWIiOiIxMjM0NTY3ODkwIn0Zq9", "Kp8Rt2Vb6"]
    )
    assert _ent(f"signing key {jwt}\n")


# --- review of #63 (Gaurav): only real file names are skipped ------------------------------

TOK = "Zx9Qw7Lm3Kp8Rt2Vb6Nc4Hd1Fg5Js0Ty"


def test_token_followed_by_a_method_call_is_still_flagged() -> None:
    assert _ent(f"api key: {TOK}.trim()\n")


def test_token_as_a_host_name_is_still_flagged() -> None:
    assert _ent(f"secret at https://{TOK}.ngrok.io/x\n")


def test_token_before_a_new_sentence_is_still_flagged() -> None:
    assert _ent(f"the token is {TOK}.Use it once.\n")


def test_token_with_an_extension_but_no_path_shape_is_still_flagged() -> None:
    assert _ent(f"api key {TOK}.json\n")  # no `/` or `_`: not a file name


def test_long_extensions_in_cited_paths_are_not_secrets() -> None:
    for ext in ("properties", "sqlite3"):
        cite = f"sample-system:config/app_20261016T090000x9Kq.{ext}#L3"
        assert not _ent(f'"quote": "primary key", "ref": "{cite}"\n'), ext


# --- third review of #63 (Gaurav): pieces of a path are checked; prose is not an extension ----

MIG = "db/migrations/20261016T090000__create_reference_lists"


def test_secret_segment_of_a_url_ending_in_a_file_is_flagged() -> None:
    assert _ent(f"webhook key: https://hooks.example.com/services/{TOK}/payload.json\n")


def test_secret_before_a_file_name_suffix_is_flagged() -> None:
    assert _ent(f"api key in s3://bucket/{TOK}_dump.sql\n")


def test_prose_after_a_token_is_not_an_extension() -> None:
    assert _ent(f"the api key is ab_{TOK}.Go to settings\n")
    assert _ent(f"the api key is ab_{TOK}.Log in first\n")


def test_base64_secret_with_slashes_is_still_checked_whole() -> None:
    assert _ent("secret: Zx9Qw7Lm3/Kp8Rt2Vb6Nc4/Hd1Fg5Js0Ty9q\n")


def test_cited_file_names_in_more_shapes_are_not_secrets() -> None:
    for tail in (".sql.", ".sql;", ".sql>", ".sql}", ".sql?", ".sql|", ".sql.gz "):
        assert not _ent(f"primary key, created in {MIG}{tail}\n"), tail
    for name in ("x9Kq/20261016T090000__orders_api.spec.ts", "src/types/20261016T090000__api.d.ts"):
        assert not _ent(f'primary key "ref": "sample-system:{name}#L4"\n'), name
    assert not _ent("key in config/20261016T090000__settings.env.local\n")


def test_run_ids_inside_cited_paths_are_not_secrets() -> None:
    """Real companion lines (HMS-14, HMS-7): a run id stays whole when a path is split."""
    lines = (
        '      cites: ["runs/run_01M7HH0DM88V7JHMVZPSYX5BWE/ide-answers.md#a-07"]\n',
        '    cites: ["artifacts/HMS-7/run_01M6FXTGC048AXKA8X69ASS5QB/design.md#overview"]\n',
    )
    for line in lines:
        assert not _ent("signing key\n" + line), line
