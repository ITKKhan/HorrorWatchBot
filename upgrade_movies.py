import json
import os

# 📂 Path to your existing movie list
MOVIE_DB_FILE = "movies.json"

# 🧱 Default category to assign to uncategorized entries
DEFAULT_CATEGORY = "Horror"

# 💡 Default metadata to patch in for missing fields
def fill_defaults(entry):
    return {
        "title": entry.get("title", "Untitled"),
        "year": entry.get("year", "Unknown Year"),
        "genre": entry.get("genre", "Unknown Genre"),
        "poster": entry.get("poster", "N/A"),
        "added_by": entry.get("added_by", "Unknown"),
    }

def upgrade():
    if not os.path.exists(MOVIE_DB_FILE):
        print("❌ No movies.json found!")
        return

    with open(MOVIE_DB_FILE, "r") as f:
        data = json.load(f)

    # 🧠 Detect if upgrade is needed (old format = list, new = dict by category)
    if isinstance(data, dict):
        print("✅ movies.json is already in the upgraded format.")
        return

    print(f"🔧 Found {len(data)} entries in legacy format. Upgrading...")

    upgraded = {DEFAULT_CATEGORY: []}

    for entry in data:
        patched = fill_defaults(entry)
        upgraded[DEFAULT_CATEGORY].append(patched)

    # 💾 Save back to file
    with open(MOVIE_DB_FILE, "w") as f:
        json.dump(upgraded, f, indent=2)

    print(f"✅ Upgrade complete! {len(data)} entries stored under '{DEFAULT_CATEGORY}'.")

if __name__ == "__main__":
    upgrade()