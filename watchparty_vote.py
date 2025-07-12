# Imports for Discord bot commands and random selection
import discord
from discord.ext import commands
import random
import json
from datetime import datetime

# Define the WatchpartyVote Cog
class WatchpartyVote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Predefined pool of horror movie titles to randomly sample from
        self.movie_pool = [
            "Alien", "The Thing", "Hereditary", "Get Out", "The Babadook",
            "Midsommar", "Us", "It Follows", "Scream", "The Exorcist"
        ]

        # Stores active voting sessions by message ID
        self.active_vote_session = {}  # Format: {message_id: {vote_id: movie_title}}

        # Tracks each user's selected vote IDs
        self.user_votes = {}  # Format: {user_id: [vote_id1, vote_id2, ...]}

        # Tallies total votes for each movie
        self.vote_tally = {}  # Format: {vote_id: vote_count}

    # Slash or prefix command to start a new vote session
    @commands.command(name="start_vote_session")
    async def start_vote_session(self, ctx):
        # Randomly select 5 movies from the pool
        selected = random.sample(self.movie_pool, 5)

        # Assign a three-digit vote ID to each selected movie
        movie_dict = {str(i+1).zfill(3): title for i, title in enumerate(selected)}

        # Create an embed message to show the voting options
        embed = discord.Embed(
            title="🎬 Watchparty Voting Session",
            description="Vote for up to 3 movies using number emojis below!",
            color=discord.Color.red()
        )

        # Add each movie to the embed with its vote ID
        for vid, title in movie_dict.items():
            embed.add_field(name=f"🆔 {vid}", value=title, inline=False)
            self.vote_tally[vid] = 0  # Initialize vote count

        # Send the embed to the channel and store the vote session
        vote_message = await ctx.send(embed=embed)
        self.active_vote_session[vote_message.id] = movie_dict

        # Add number emoji reactions for users to vote with
        emoji_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for emoji in emoji_list:
            await vote_message.add_reaction(emoji)

    # Event listener for when users add a reaction
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Skip if the reaction came from the bot itself
        if payload.user_id == self.bot.user.id:
            return

        # Get message and user info from the reaction payload
        msg_id = payload.message_id
        emoji = payload.emoji.name
        user_id = payload.user_id
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(msg_id)

        # Ignore reactions unrelated to active vote sessions
        if msg_id not in self.active_vote_session:
            return

        # Map emojis to vote IDs (fixed for 5 movies)
        emoji_map = {
            "1️⃣": "001", "2️⃣": "002", "3️⃣": "003", "4️⃣": "004", "5️⃣": "005"
        }

        vote_id = emoji_map.get(emoji)
        if not vote_id:
            return  # Ignore unrelated emoji reactions

        # Get or initialize the user's vote list
        self.user_votes.setdefault(user_id, [])

        # Don't count duplicate votes
        if vote_id in self.user_votes[user_id]:
            return

        # Enforce the vote cap of 3 movies per user
        if len(self.user_votes[user_id]) >= 3:
            try:
                await message.remove_reaction(payload.emoji, payload.member)
            except discord.Forbidden:
                 # Permission issue — silently fail or log
                print("⚠️ Bot lacks permission to remove reactions.")
            return

        # Register vote and update tally
        self.user_votes[user_id].append(vote_id)
        self.vote_tally[vote_id] += 1

    # Show results of the vote
    @commands.command(name="show_results")
    async def show_results(self, ctx):
        
        # Verify an active voting session exists
        if not self.active_vote_session:
            await ctx.send("❌ No active voting session found.")
            return

        # Grab the latest vote session's message ID
        msg_id = list(self.active_vote_session.keys())[-1]
        movies = self.active_vote_session[msg_id]

        # Calculate total vote count (prevent division by zero)
        total_votes = sum(self.vote_tally.values()) or 1

        results = []
        # Assemble result tuples with vote ID, title, count, and percentage
        for vote_id, title in movies.items():
            count = self.vote_tally.get(vote_id, 0)
            percent = int((count / total_votes) * 100)
            results.append((vote_id, title, count, percent))

        # Sort movies by vote count, descending
        results.sort(key=lambda x: x[2], reverse=True)

        # Extract top 3 movies
        top_3 = results[:3]

        # Basic tie breaker: randomize if all top 3 have same vote count
        if len(set(r[2] for r in top_3)) == 1:
            random.shuffle(top_3)

        # Create a visually styled embed message for results
        embed = discord.Embed(
            title="📊 Top 3 Watchparty Picks",
            description=f"Total Votes: {total_votes}",
            color=discord.Color.blue()
        )

        # Assign medals and add fields for each top movie
        medals = ["🥇", "🥈", "🥉"]
        for i, (vid, title, count, percent) in enumerate(top_3):
            embed.add_field(
                name=f"{medals[i]} {title}",
                value=f"🆔 {vid} — {percent}% ({count} votes)",
                inline=False
            )

        await ctx.send(embed=embed)

        # Store results for scheduling purposes
        await self.save_schedule("Horror", top_3)

    # Save Voting Results to a JSON file 
    async def save_schedule(self, category, top_3):
        schedule_path = "watchparty_schedule.json"

        try:
            # Load existing scheduling data from file
            with open(schedule_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            # Create new data structure if file doesn't exist
            data = {}

        formatted_top_3 = []
        # Format each top movie with default streaming platform set to N/A
        for vote_id, title, count, percent in top_3:
            formatted_top_3.append({
                "title": title,
                "votes": count,
                "percent": percent,
                "streaming": "N/A"
            })

        # Update the selected category with the new top 3 and metadata
        data[category] = {
            "day": self.get_day_for_category(category),
            "last_updated": datetime.utcnow().isoformat(),
            "top_3": formatted_top_3
        }

        # Write updated data back to the JSON file
        with open(schedule_path, "w") as f:
            json.dump(data, f, indent=4)

    # Day of the Week Mapping Helper
    def get_day_for_category(self, category):

        # Define day-of-week mapping for each watchparty genre
        category_days = {
            "Horror": "Friday",
            "Anime": "Tuesday",
            "SciFi": "Saturday"
        }

        # Return matched day or "TBD" if the category is new
        return category_days.get(category, "TBD")
    
    # Rest Watchparty votes
    @commands.command(name="reset_votes")
    async def reset_votes(self, ctx):
        """Resets all vote data for a clean session."""
        self.active_vote_session.clear()
        self.user_votes.clear()
        self.vote_tally.clear()
        await ctx.send("🧹 Voting data cleared. Ready for a new session!")

    #Schedule Watchparty Command
    @commands.command(name="schedule_watchparty")
    async def schedule_watchparty(self, ctx, category: str = "Horror"):
        """
        Reads the saved top 3 movies from the watchparty_schedule.json file
        and announces the upcoming Watchparty lineup for a given category.
        """

        import json

        schedule_path = "watchparty_schedule.json"

        try:
            # Open the JSON file that stores schedule data
            with open(schedule_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            # Inform user if no schedule data exists yet
            await ctx.send("⚠️ No schedule file found. Try running /show_results first.")
            return

        # Normalize category name capitalization
        category = category.capitalize()

        if category not in data:
            await ctx.send(f"❌ No schedule found for category: {category}")
            return

        schedule = data[category]
        top_3 = schedule.get("top_3", [])
        day = schedule.get("day", "TBD")
        last_updated = schedule.get("last_updated", "Unknown")

        # Create announcement embed
        embed = discord.Embed(
            title=f"📅 {category} Watchparty — Scheduled for {day}",
            description=f"Top 3 Picks Based on Votes\n_Last updated: {last_updated}_",
            color=discord.Color.purple()
        )

        # Add movie info (title, percent, vote count, streaming status)
        medals = ["🥇", "🥈", "🥉"]
        for i, movie in enumerate(top_3):
            title = movie["title"]
            votes = movie["votes"]
            percent = movie["percent"]
            streaming = movie.get("streaming", "N/A")
            embed.add_field(
                name=f"{medals[i]} {title}",
                value=f"{percent}% ({votes} votes)\n🛜 Streaming: {streaming}",
                inline=False
            )

        # Footer with scheduling guidance
        embed.set_footer(text="Get ready to queue it up! 🧟‍♂️🎥📺")

        await ctx.send(embed=embed)