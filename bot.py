import discord
from discord import app_commands
from discord.ext import commands
import json, os, requests, asyncio
from dotenv import load_dotenv
from watchparty_vote import WatchpartyVote

#Environment and Setup
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

MOVIE_DB_FILE = "movies.json"
WATCHPARTY_FILE = "categories.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

    # Load your WatchpartyVote Cog properly
    await bot.add_cog(WatchpartyVote(bot))

    # Optionally sync app commands here if you're mixing slash and prefix
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

#Error Visibility for silent command errors
@bot.event
async def on_command_error(ctx, error):
    print(f"Command error: {error}")

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
# Slash Command to Add a Movie to a Watchparty
@bot.tree.command(name="add_movie", description="Search and add one or more movies to a watchparty 🎞️")
@app_commands.describe(
    watchparty="Choose a watchparty category",
    movie_title="Enter the movie title to search for"
)
async def slash_add_movie(interaction: discord.Interaction, watchparty: str, movie_title: str):
    await interaction.response.defer(thinking=True)

    # 🔍 Step 1: Use OMDb Search Mode (`s`) to find possible matches
    params = {"s": movie_title, "apikey": OMDB_API_KEY}
    response = requests.get("http://www.omdbapi.com/", params=params)
    search_results = response.json().get("Search", [])

    # 🔁 Step 2: Fallback to exact title lookup if no results
    if not search_results:
        params = {"t": movie_title, "apikey": OMDB_API_KEY}
        response = requests.get("http://www.omdbapi.com/", params=params)
        data = response.json()

        if data.get("Response") == "False":
            await interaction.followup.send(f"❌ Couldn't find anything for '{movie_title}'.")
            return

        # ✅ Add exact match directly
        await insert_movie(interaction, watchparty, data)
        return

    # 🎞️ Step 3: Show numbered list of options
    msg = f"🔍 Found multiple matches for **{movie_title}**:\n\n"
    for i, m in enumerate(search_results[:5], 1):
        msg += f"{i}. {m['Title']} ({m['Year']})\n"

    msg += (
        "\nReply with the number(s) to add:\n"
        "• Use formats like `1`, `1 2`, `1,3`, or `1 and 3`\n"
        "• Type `all` to add every listed result\n"
        "• Type `cancel` to abort"
    )
    await interaction.followup.send(msg)

    # 🧠 Step 4: Define check for reply input
    def check(msg):
        return (
            msg.author == interaction.user and
            msg.channel == interaction.channel
        )

    try:
        reply_msg = await bot.wait_for("message", timeout=30.0, check=check)
        user_input = reply_msg.content.strip().lower()

        if user_input == "cancel":
            await interaction.followup.send("❎ Addition cancelled.")
            return

        # 🔎 Step 5: Parse input into selected indexes
        import re
        if user_input == "all":
            selected_indexes = list(range(1, min(6, len(search_results) + 1)))
        else:
            raw = re.findall(r"\d+", user_input)
            selected_indexes = [int(r) for r in raw if 1 <= int(r) <= len(search_results[:5])]

        if not selected_indexes:
            await interaction.followup.send("❌ Couldn't interpret your selection. Try `/add_movie` again.")
            return

    except asyncio.TimeoutError:
        await interaction.followup.send("⏰ Timed out — try `/add_movie` again.")
        return

    # 📦 Step 6: Fetch full metadata and insert each movie
    success_list = []
    for i in selected_indexes:
        chosen = search_results[i - 1]
        imdb_id = chosen["imdbID"]
        params = {"i": imdb_id, "apikey": OMDB_API_KEY}
        final = requests.get("http://www.omdbapi.com/", params=params).json()

        if final.get("Response") == "True":
            await insert_movie(interaction, watchparty, final)
            success_list.append(f"✅ {final['Title']} ({final['Year']})")

    # 📝 Step 7: Recap what was added
    if success_list:
        await interaction.followup.send(
            "**Added the following movies:**\n" + "\n".join(success_list)
        )
    else:
        await interaction.followup.send("❌ No movies were successfully added.")

# Discord Auto complete Command for Watchparty Add Movies
@slash_add_movie.autocomplete("watchparty")
async def autocomplete_watchparty_add(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=wp, value=wp)
        for wp in load_watchparties() if current.lower() in wp.lower()
    ]

# Remove Movie from List. Admin can remove all, where basic users remove ones they added. 
@bot.tree.command(name="remove_movie", description="Choose and remove one or more movie versions 🗑️")
@app_commands.describe(
    watchparty="Select a watchparty category",
    movie_title="Enter the title of the movie to remove"
)
async def remove_movie(interaction: discord.Interaction, watchparty: str, movie_title: str):
    await interaction.response.defer(thinking=True)

    db = load_movie_db()
    user_name = interaction.user.name
    is_admin = interaction.user.guild_permissions.administrator

    if watchparty not in db:
        await interaction.followup.send(f"❌ Watchparty '{watchparty}' doesn't exist.")
        return

    # 🔍 Match movies by title and permission
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

    # 🎞️ Present numbered list to user
    msg = f"🔍 Found multiple versions of **{movie_title}** in **{watchparty}**:\n\n"
    for i, m in enumerate(matches, 1):
        msg += f"{i}. {m['title']} ({m['year']}) — added by {m['added_by']}\n"

    msg += (
        "\nReply with the number(s) to remove:\n"
        "• `1`, `1 2`, `1,2`, `1 and 2` all work\n"
        "• Type `all` to remove every match\n"
        "• Type `cancel` to abort"
    )
    await interaction.followup.send(msg)

    # 🧠 Check function for user reply
    def check(msg):
        return (
            msg.author == interaction.user and
            msg.channel == interaction.channel
        )

    try:
        reply_msg = await bot.wait_for("message", timeout=30.0, check=check)
        user_input = reply_msg.content.strip().lower()

        if user_input == "cancel":
            await interaction.followup.send("❎ Removal cancelled.")
            return

        # 🎛️ Parse user input with regex
        import re
        if user_input == "all":
            selected_indexes = list(range(1, len(matches) + 1))
        else:
            raw = re.findall(r"\d+", user_input)
            selected_indexes = [int(r) for r in raw if 1 <= int(r) <= len(matches)]

        if not selected_indexes:
            await interaction.followup.send("❌ Couldn't interpret your selection. Please try again.")
            return

    except asyncio.TimeoutError:
        await interaction.followup.send("⏰ Timed out — try `/remove_movie` again.")
        return

    # 🗑️ Remove only selected items
    to_remove = [matches[i - 1] for i in selected_indexes]
    db[watchparty] = [m for m in db[watchparty] if m not in to_remove]
    save_movie_db(db)

    titles = ", ".join([f"**{m['title']}** ({m['year']})" for m in to_remove])
    await interaction.followup.send(f"✅ Removed {len(to_remove)} item(s): {titles}")

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
@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")