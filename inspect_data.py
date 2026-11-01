
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

for filename in ("users.csv", "accounts.csv"):
    path = DATA_DIR / filename

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    print(f"\n{filename}")
    print("Columns:", reader.fieldnames)
    print("Records:", len(rows))
    print("First record:", rows[0] if rows else "No records")
