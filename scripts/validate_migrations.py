from pathlib import Path

versions = sorted(Path("apps/api/migrations/versions").glob("*.py"))
assert versions, "at least one Alembic migration is required"
revisions = []
downs = []
for path in versions:
    text = path.read_text()
    assert "revision" in text and "def upgrade" in text and "def downgrade" in text, (
        f"invalid {path}"
    )
    ns = {}
    exec(compile(text, str(path), "exec"), ns)
    revisions.append(ns.get("revision"))
    downs.append(ns.get("down_revision"))
heads = set(revisions) - {d for d in downs if d}
assert len(heads) == 1, f"expected exactly one Alembic head, found {sorted(heads)}"
print(f"validated {len(versions)} Alembic migration(s); head={next(iter(heads))}")
