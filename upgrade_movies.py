import json
import os

CATEGORY_FILE = "categories.json"
MOVIE_DB_FILE = "movies.json"

# 💡 Patches missing fields for legacy entries
def fill_defaults(entry):
    return {
        "title": entry.get("title", "Untitled"),
        "year": entry.get("year", "Unknown Year"),
        "genre": entry.get("genre", "Unknown Genre"),
        "poster": entry.get("poster", "N/A"),
        "added_by": entry.get("added_by", "Unknown"),
    }

# 📖 Load the current list of categories
def load_categories():
    if not os.path.exists(CATEGORY_FILE):
        with open(CATEGORY_FILE, "w") as f:
            json.dump(["Horror"], f)  # Default fallback if category file doesn't exist
    with open(CATEGORY_FILE, "r") as f:
        return json.load(f)

def upgrade():
    if not os.path.exists(MOVIE_DB_FILE):
        print("❌ No movies.json file found to upgrade.")
        return

    with open(MOVIE_DB_FILE, "r") as f:
        data = json.load(f)

    # ✅ Already upgraded
    if isinstance(data, dict):
        print("✅ movies.json is already using the upgraded category format.")
        return

    # 🧪 Upgrade from flat list → category dict
    fallback_category = load_categories()[0]
    print(f"🔧 Detected legacy format. Upgrading movies to category: '{fallback_category}'")

    upgraded = {fallback_category: []}

    for entry in data:
        patched = fill_defaults(entry)
        upgraded[fallback_category].append(patched)

    with open(MOVIE_DB_FILE, "w") as f:
        json.dump(upgraded, f, indent=2)

    print(f"✅ Upgrade complete. {len(data)} entries moved to '{fallback_category}'.")

if __name__ == "__main__":
    upgrade()