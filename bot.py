import discord
from discord import app_commands
from discord.ext import commands
import json, os, requests, asyncio
from dotenv import load_dotenv

#Environment and Setup
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

MOVIE_DB_FILE = "movies.json"
WATCHPARTY_FILE = "categories.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

#Helper Functions 
def load_watchparties():
    if not os.path.exists(WATCHPARTY_FILE):
        with open(WATCHPARTY_FILE, "w") as f:
            json.dump(["Horror", "Anime", "SciFi"], f)
    with open(WATCHPARTY_FILE, "r") as f:
        return json.load(f)

def save_watchparties(watchparties):
    with open(WATCHPARTY_FILE, "w") as f:
        json.dump(watchparties, f, indent=2)

def load_movie_db():
    if not os.path.exists(MOVIE_DB_FILE):
        with open(MOVIE_DB_FILE, "w") as f:
            json.dump({}, f)
    with open(MOVIE_DB_FILE, "r") as f:
        return json.load(f)

def save_movie_db(db):
    with open(MOVIE_DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

# On Ready Event
@bot.event
async def on_ready():
    print("🔥 on_ready fired!")
    synced = await bot.tree.sync()
    print(f"✅ Synced {len(synced)} slash command(s): {[cmd.name for cmd in synced]}")

# Mention-Handling Code for Discord Bot to handle @ request to explain functionality
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # If bot is mentioned directly
    if bot.user in message.mentions:
        await message.channel.send(
            f"👋 Hey **{message.author.display_name}**! I’m HorrorWatchBot 🎃, your watchparty companion.\n\n"
            f"Here’s what I can do:\n"
            f"• ➕ `/add_movie` to add films to your watchparty\n"
            f"• 📊 `/list_top10` to see the latest additions\n"
            f"• 🍿 More coming soon: ratings, suggestions, polls, and schedules!\n\n"
            f"Try typing `/` to view all commands or ask me what’s playing!"
        )
        await message.add_reaction("🎥")
   
    if message.content.startswith("/"):
        return

    await bot.process_commands(message)

# Discord Auto complete Command for Showing Top 10 Movie List
@bot.tree.command(name="list_top10", description="List the top 10 recent movies from a Watchparty 🎥")
@app_commands.describe(watchparty="Select a watchparty to view its top 10 movies")
async def list_top10(interaction: discord.Interaction, watchparty: str):
    db = load_movie_db()
    movies = db.get(watchparty)

    if not movies:
        await interaction.response.send_message(f"❌ No movies found in **{watchparty}**.", ephemeral=True)
        return

    top_movies = movies[-10:][::-1]  # Newest first

    response = "\n\n".join(
        f"🎬 **{m['title']}** ({m['year']})\nGenre: {m['genre']}\nAdded by: {m['added_by']}\n"
        f"{m['poster'] if m['poster'] != 'N/A' else '🖼️ No poster available'}"
        for m in top_movies
    )

    await interaction.response.send_message(response)

# Discord Auto complete Command for Top 10 List
@list_top10.autocomplete("watchparty")
async def autocomplete_watchparty_top(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=wp, value=wp)
        for wp in load_watchparties() if current.lower() in wp.lower()
    ]

# Add Movie with Search and Fallback of Search parameters
@bot.tree.command(name="add_movie", description="Add a movie to your Watchparty 🏠")
@app_commands.describe(watchparty="Choose a watchparty", movie_title="Enter the movie title")
async def slash_add_movie(interaction: discord.Interaction, watchparty: str, movie_title: str):
    await interaction.response.defer(thinking=True)

    # Search using "s"
    params = {"s": movie_title, "apikey": OMDB_API_KEY}
    response = requests.get("http://www.omdbapi.com/", params=params)
    search_results = response.json().get("Search", [])

    # Fallback if nothing found
    if not search_results:
        print("🔄 Falling back to exact lookup")
        params = {"t": movie_title, "apikey": OMDB_API_KEY}
        response = requests.get("http://www.omdbapi.com/", params=params)
        data = response.json()

        if data.get("Response") == "False":
            await interaction.followup.send(f"❌ Couldn't find anything for '{movie_title}'.")
            return

        await insert_movie(interaction, watchparty, data)
        return

    # Show user options
    choices = []
    for i, result in enumerate(search_results[:5], 1):
        title = result.get("Title", "Unknown")
        year = result.get("Year", "Unknown")
        poster = result.get("Poster", "🖼️ No poster")
        choices.append(f"{i}. **{title}** ({year})\n{poster}")

    await interaction.followup.send(
        "🔍 Found multiple matches! Reply with the number of your pick:\n\n" + "\n\n".join(choices)
    )

    # Await reply
    def check(m): return (
        m.author == interaction.user and
        m.channel == interaction.channel and
        m.content.isdigit() and
        1 <= int(m.content) <= len(search_results[:5])
    )
    try:
        msg = await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏰ Timed out—try again.")
        return

    chosen = search_results[int(msg.content) - 1]
    imdb_id = chosen["imdbID"]
    params = {"i": imdb_id, "apikey": OMDB_API_KEY}
    final = requests.get("http://www.omdbapi.com/", params=params).json()

    if final.get("Response") == "False":
        await interaction.followup.send("😞 Couldn't load full details.")
        return

    await insert_movie(interaction, watchparty, final)   

# Discord Auto complete Command for Watchparty Add Movies
@slash_add_movie.autocomplete("watchparty")
async def autocomplete_watchparty(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=wp, value=wp)
        for wp in load_watchparties() if current.lower() in wp.lower()
    ]

# Remove Movie from List. Admin can remove all, where basic users remove ones they added. 
@bot.tree.command(name="remove_movie", description="Remove a movie you've added, or others if you're an admin 🗑️")
@app_commands.describe(
    watchparty="Select a watchparty category",
    movie_title="Enter the title of the movie to remove"
)
async def remove_movie(interaction: discord.Interaction, watchparty: str, movie_title: str):
    await interaction.response.defer(thinking=True)

    db = load_movie_db()

    if watchparty not in db:
        await interaction.followup.send(f"❌ Watchparty '{watchparty}' doesn't exist.")
        return

    user_name = interaction.user.name
    is_admin = interaction.user.guild_permissions.administrator

    # Look for matching titles
    matches = [
        m for m in db[watchparty]
        if m.get("title", "").lower().strip() == movie_title.lower().strip()
        and (m.get("added_by") == user_name or is_admin)
    ]

    if not matches:
        await interaction.followup.send(
            f"🙅 No removable matches found for '{movie_title}' in **{watchparty}**."
        )
        return

    # Remove matches
    db[watchparty] = [m for m in db[watchparty] if m not in matches]
    save_movie_db(db)

    # Feedback
    removed_titles = ", ".join([f"**{m['title']}** ({m['year']})" for m in matches])
    await interaction.followup.send(
        f"🗑️ Removed {len(matches)} movie(s) from **{watchparty}**:\n{removed_titles}"
    )

# Discord Auto complete Command for Watchparty Remove Movies
@remove_movie.autocomplete("watchparty")
async def autocomplete_watchparty_remove(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=wp, value=wp)
        for wp in load_watchparties() if current.lower() in wp.lower()
    ]

# Insert Movie Helper
async def insert_movie(interaction, watchparty, data):
    db = load_movie_db()

    movie = {
        "title": data.get("Title", "Untitled"),
        "year": data.get("Year", "Unknown"),
        "genre": data.get("Genre", "Unknown"),
        "poster": data.get("Poster", "N/A"),
        "added_by": interaction.user.name
    }

    if watchparty not in db:
        db[watchparty] = []

    title_norm = movie["title"].lower().strip()
    year_norm = movie["year"].strip()
    if (title_norm, year_norm) in {
        (entry["title"].lower().strip(), entry["year"].strip()) for entry in db[watchparty]
    }:
        await interaction.followup.send(
            f"⚠️ **{movie['title']}** ({movie['year']}) is already in **{watchparty}**!"
        )
        return

    db[watchparty].append(movie)
    save_movie_db(db)

    await interaction.followup.send(
        f"✅ **{movie['title']}** ({movie['year']}) added to **{watchparty}** by **{movie['added_by']}**\n"
        f"Genre: {movie['genre']}\n"
        f"{movie['poster'] if movie['poster'] != 'N/A' else '🖼️ No poster available'}"
    )    

# Bot Run
bot.run(DISCORD_TOKEN)