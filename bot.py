import discord
from discord.ext import commands
import json
import os
import requests               # 🔍 Used to contact the OMDb API
from dotenv import load_dotenv

# 🔐 Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

MOVIE_DB_FILE = "movies.json"
if not os.path.exists(MOVIE_DB_FILE):
    with open(MOVIE_DB_FILE, "w") as f:
        json.dump([], f)

@bot.event
async def on_ready():
    print(f"{bot.user} is channeling horror metadata... 👁️📼")

# 🎬 Multi-step add_movie flow: ask for category first, then title
@bot.command(name="add_movie")
async def add_movie(ctx):
    """
    Step 1: Ask for category
    Step 2: Ask for movie title
    Step 3: Fetch metadata and save under category
    """

    def check_author(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # Ask for category
    await ctx.send("📂 Which watchparty category is this for? (e.g. Horror, Anime, SciFi)")

    try:
        category_msg = await bot.wait_for("message", timeout=30.0, check=check_author)
        category = category_msg.content.strip().title()  # Format it nicely
    except asyncio.TimeoutError:
        await ctx.send("⏳ Timed out waiting for category. Try again later.")
        return

    # Ask for movie title
    await ctx.send(f"🎥 Great! Now tell me the movie title to add to **{category}**")

    try:
        title_msg = await bot.wait_for("message", timeout=60.0, check=check_author)
        title = title_msg.content.strip()
    except asyncio.TimeoutError:
        await ctx.send("⏳ Timed out waiting for movie title. Try again later.")
        return

    # Fetch from OMDb API
    params = {"t": title, "apikey": OMDB_API_KEY}
    response = requests.get("http://www.omdbapi.com/", params=params)
    data = response.json()

    if data.get("Response") == "False":
        await ctx.send(f"😞 Couldn't find a movie called '{title}'.")
        return

    # Create movie object
    movie = {
        "title": data.get("Title", "Untitled"),
        "year": data.get("Year", "Unknown"),
        "genre": data.get("Genre", "Unknown"),
        "poster": data.get("Poster", "N/A"),
        "added_by": ctx.author.name
    }

    # Load and update movies.json
    with open(MOVIE_DB_FILE, "r") as f:
        movie_db = json.load(f)

    if category not in movie_db:
        movie_db[category] = []

    movie_db[category].append(movie)

    with open(MOVIE_DB_FILE, "w") as f:
        json.dump(movie_db, f, indent=2)

    # Confirmation message
    await ctx.send(
        f"✅ **{movie['title']}** ({movie['year']}) added to **{category}** by **{movie['added_by']}**\n"
        f"Genre: {movie['genre']}\n"
        f"{movie['poster'] if movie['poster'] != 'N/A' else '🖼️ No poster available'}"
    )

# 📋 Command: /list_movies [optional_category]
@bot.command(name="list_movies")
async def list_movies(ctx, *, category=None):
    """
    Lists movies from the JSON file.
    If category is provided, shows only that section.
    """
    # Open the movie database
    with open(MOVIE_DB_FILE, "r") as f:
        data = json.load(f)

    # If using new format (dict by category), handle accordingly
    if isinstance(data, dict):
        # If user requests a category
        if category:
            category = category.strip().title()  # e.g., "horror" → "Horror"
            movies = data.get(category)
            if not movies:
                await ctx.send(f"😕 No movies found in the **{category}** category.")
                return
        else:
            # No category specified—combine all movies
            movies = []
            for cat, entries in data.items():
                for m in entries:
                    m["watchparty"] = cat
                    movies.append(m)
    else:
        # Legacy format fallback
        movies = data

    if not movies:
        await ctx.send("📂 The movie list is empty.")
        return

    # 💬 Build the response text
    response = "🎃 **HorrorWatch Queue** 🎬\n\n"
    for idx, m in enumerate(movies, 1):
        title = m.get("title", "Untitled")
        year = m.get("year", "Unknown Year")
        genre = m.get("genre", None)
        watchparty = m.get("watchparty", None)

    response += f"**{idx}. {title}** ({year})\n"
    if genre:
        response += f"   _{genre}_\n"
    if watchparty:
        response += f"   Category: `{watchparty}`\n"
    response += "\n"

    # Split message if too long for Discord
    if len(response) > 2000:
        await ctx.send("📄 Movie list too long! Consider filtering by category.")
    else:
        await ctx.send(response)

# 🧃 Launch the bot!
bot.run(DISCORD_TOKEN)
