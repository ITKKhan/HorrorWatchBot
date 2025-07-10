import json
import os
from datetime import datetime
import getpass

LOG_FILE = "deduplication_log.txt"

def is_invalid_field(field):
    return not field or field.strip().lower() in {"", "unknown", "n/a"}

def is_valid_movie(movie):
    # Normalize fields for checking
    title = movie.get("title", "").strip().lower()
    year = movie.get("year", "").strip().lower()
    genre = movie.get("genre", "").strip().lower()
    poster = movie.get("poster", "").strip().lower()
    added_by = movie.get("added_by", "").strip().lower()

    # Reject if critical fields are missing or placeholder
    return all([
        title and title not in {"unknown", "n/a"},
        year and year not in {"unknown", "n/a"},
        genre and genre not in {"unknown", "n/a"},
        poster != "n/a",
        added_by and added_by != "unknown"
    ])

def deduplicate_and_validate(filepath="movies.json"):
    with open(filepath, "r") as f:
        data = json.load(f)

    username = getpass.getuser()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    removed_invalid = []
    removed_duplicates = []

    for watchparty in data:
        seen = set()
        cleaned = []

        for movie in data[watchparty]:
            key = (movie.get("title", "").lower().strip(), movie.get("year", "").strip())

            if not is_valid_movie(movie):
                removed_invalid.append((watchparty, movie))
                continue

            if key in seen:
                removed_duplicates.append((watchparty, movie))
                continue

            seen.add(key)
            cleaned.append(movie)

        data[watchparty] = cleaned

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    # 📓 Write to log file
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"\n--- Deduplication Run: {timestamp} by {username} ---\n")
        log.write(f"Removed {len(removed_duplicates)} duplicate(s) and {len(removed_invalid)} invalid movie(s).\n")

        if removed_duplicates:
            log.write("\n🗑️ Duplicates Removed:\n")
            for watchparty, movie in removed_duplicates:
                log.write(f" - [{watchparty}] {movie['title']} ({movie['year']})\n")

        if removed_invalid:
            log.write("\n❌ Invalid Movies Removed:\n")
            for watchparty, movie in removed_invalid:
                title = movie.get("title", "<no title>")
                year = movie.get("year", "<no year>")
                log.write(f" - [{watchparty}] {title} ({year}) — missing or malformed fields\n")

    print(f"✅ Cleaned {len(removed_duplicates)} duplicate(s) and {len(removed_invalid)} invalid movie(s). Log saved to {LOG_FILE}")

if __name__ == "__main__":
    print("🔍 Running deduplication and validation...")
    deduplicate_and_validate()