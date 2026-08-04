from pathlib import Path


ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def environment_keys() -> list[str]:
    return [
        line.partition("=")[0]
        for line in ENV_EXAMPLE.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    ]


def test_environment_example_has_no_merge_conflict_markers() -> None:
    contents = ENV_EXAMPLE.read_text()
    assert not any(marker in contents for marker in CONFLICT_MARKERS)


def test_environment_example_defines_each_setting_once() -> None:
    keys = environment_keys()
    assert len(keys) == len(set(keys))


def test_environment_example_covers_runnable_services() -> None:
    assert {
        "APP_ENV",
        "DATABASE_URL",
        "NEXT_PUBLIC_API_URL",
        "POSTGRES_DB",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "WORKER_POLL_INTERVAL_SECONDS",
    } <= set(environment_keys())
