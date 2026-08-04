from pathlib import Path

files = sorted(Path("apps/api/migrations").glob("*.sql"))
assert files, "at least one migration is required"
names = [path.name.split("_", 1)[0] for path in files]
assert len(names) == len(set(names)), "duplicate migration sequence"
for path in files:
    text = path.read_text()
    assert "-- outcomeos:up" in text and "-- outcomeos:down" in text, f"invalid {path}"
print(f"validated {len(files)} migration(s)")
