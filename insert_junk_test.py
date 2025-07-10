import json

TEST_ENTRIES = [
    {
        "title": "The Glitch", "year": "Unknown", "genre": "Sci-Fi", "poster": "N/A", "added_by": "admin"
    },
    {
        "title": "404: Not Found", "year": "", "genre": "Thriller", "poster": "N/A", "added_by": "admin"
    },
    {
        "title": "", "year": "2020", "genre": "Horror", "poster": "https://...", "added_by": "admin"
    },
    {
        "title": "The Thing (1982)", "year": "Unknown", "genre": "Unknown", "poster": "N/A", "added_by": "Unknown"
    },
]

# Inject these into a test category
category = "Horror"

with open("movies.json", "r") as f:
    data = json.load(f)

# If the category doesn't exist yet, create it
if category not in data:
    data[category] = []

# Append the test entries
data[category].extend(TEST_ENTRIES)

with open("movies.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"🧪 Injected {len(TEST_ENTRIES)} invalid test entries into '{category}'")