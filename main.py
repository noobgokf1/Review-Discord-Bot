import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput, View, Select, Button
import sqlite3
from dotenv import load_dotenv
import os

load_dotenv()  
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

conn = sqlite3.connect('reviews.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS reviews (
                reviewer_id TEXT,
                reviewee_id TEXT,
                rating INTEGER,
                review TEXT,
                guild_id TEXT,
                guild_name TEXT,
                FOREIGN KEY (reviewer_id) REFERENCES users (user_id),
                FOREIGN KEY (reviewee_id) REFERENCES users (user_id)
            )''')

conn.commit()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

async def add_user_to_db(user_id, username):
    c.execute('INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()

class ReviewModal(Modal, title="Submit Review"):
    review_text = TextInput(label="Your Review", style=discord.TextStyle.long, placeholder="Type your review here...", required=True)

    def __init__(self, reviewer_id, reviewee_id, rating, guild_id, guild_name):
        super().__init__()
        self.reviewer_id = reviewer_id
        self.reviewee_id = reviewee_id
        self.rating = rating
        self.guild_id = guild_id
        self.guild_name = guild_name

    async def on_submit(self, interaction: discord.Interaction):
        review = self.review_text.value
        c.execute('INSERT INTO reviews (reviewer_id, reviewee_id, rating, review, guild_id, guild_name) VALUES (?, ?, ?, ?, ?, ?)',
                  (self.reviewer_id, self.reviewee_id, self.rating, review, self.guild_id, self.guild_name))
        conn.commit()
        await interaction.response.send_message(f"Review submitted for {interaction.guild.get_member(int(self.reviewee_id)).name} with {self.rating} ⭐", ephemeral=True)

@bot.tree.command(name="setup")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    roles = [f"{i} ⭐" for i in range(1, 6)]

    gold_orange_color = discord.Colour.from_str("#FFAA00")
    
    for role in roles:
        if not discord.utils.get(guild.roles, name=role):
            await guild.create_role(name=role, color=gold_orange_color)
    await interaction.response.send_message("Server has been set up", ephemeral=True)

@bot.tree.command(name="review")
async def rate(interaction: discord.Interaction, user: discord.User):
    reviewer_id = interaction.user.id
    reviewee_id = user.id
    guild_id = str(interaction.guild.id) 
    guild_name = interaction.guild.name 

    if reviewer_id == reviewee_id:
        await interaction.response.send_message("You cannot review yourself!", ephemeral=True)
        return

    await add_user_to_db(reviewer_id, str(interaction.user))
    await add_user_to_db(reviewee_id, str(user))

    c.execute('SELECT rating, review FROM reviews WHERE reviewer_id = ? AND reviewee_id = ?', (reviewer_id, reviewee_id))
    result = c.fetchone()

    if result:
        embed = discord.Embed(title="Review Exists", description=f"You've already reviewed {user.name}.", color=0xffc107)
        embed.add_field(name="Your Review", value=f"Rating: {result[0]} ⭐\nReview: {result[1]}")
        remove_button = Button(label="Remove Review", style=discord.ButtonStyle.red)

        async def remove_review(interaction):
            c.execute('DELETE FROM reviews WHERE reviewer_id = ? AND reviewee_id = ?', (reviewer_id, reviewee_id))
            conn.commit()
            await interaction.response.send_message(f"Your review for {user.name} has been removed.", ephemeral=True)

        remove_button.callback = remove_review
        view = View()
        view.add_item(remove_button)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    else:
        embed = discord.Embed(title="Rate User", description=f"Rate {user.name} from 1 to 5 stars.", color=0x99FF99)
        rating_select = Select(placeholder="Choose a rating", options=[discord.SelectOption(label=f"{i} ⭐", value=str(i)) for i in range(1, 6)])

        async def submit_rating(interaction):
            rating = int(rating_select.values[0])
            await interaction.response.send_modal(ReviewModal(reviewer_id, reviewee_id, rating, guild_id, guild_name))

        rating_select.callback = submit_rating
        view = View()
        view.add_item(rating_select)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="profile")
async def profile(interaction: discord.Interaction, user: discord.User):
    c.execute('SELECT reviewer_id, rating, review FROM reviews WHERE reviewee_id = ?', (user.id,))
    reviews = c.fetchall()

    if not reviews:
        await interaction.response.send_message(f"{user.name} has no reviews yet.", ephemeral=True)
        return

    c.execute('SELECT AVG(rating) FROM reviews WHERE reviewee_id = ?', (user.id,))
    avg_rating = c.fetchone()[0]
    if avg_rating is not None:
        avg_rating = round(avg_rating, 1)
    else:
        avg_rating = 0.0

    pages = [reviews[i:i+2] for i in range(0, len(reviews), 2)]
    page = 0

    async def update_embed(page):
        embed = discord.Embed(title=f"{user.name}'s Profile ({len(reviews)} reviews)", description=f"Average Rating: {avg_rating} ⭐", color=0x00ff00)
        for review in pages[page]:
            reviewer_id, rating, review_text = review
            c.execute("SELECT username FROM users WHERE user_id = ?", (reviewer_id,))
            reviewer_username = c.fetchone()
            reviewer_name = reviewer_username[0] if reviewer_username else 'Unknown'
            embed.add_field(name=f"Reviewer: {reviewer_name}", value=f"Rating: {rating} ⭐\nReview: {review_text}", inline=False)
        return embed

    embed = await update_embed(page)
    next_button = Button(label="Next", style=discord.ButtonStyle.primary)
    prev_button = Button(label="Previous", style=discord.ButtonStyle.primary)

    async def next_page(interaction):
        nonlocal page
        if page < len(pages) - 1:
            page += 1
        embed = await update_embed(page)
        await interaction.response.edit_message(embed=embed, view=view)

    async def prev_page(interaction):
        nonlocal page
        if page > 0:
            page -= 1
        embed = await update_embed(page)
        await interaction.response.edit_message(embed=embed, view=view)

    next_button.callback = next_page
    prev_button.callback = prev_page
    view = View()
    view.add_item(prev_button)
    view.add_item(next_button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        print("Slash commands have been synced.")
        activity = discord.Game(name="/review")
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception as e:
        print(f"Failed to sync commands: {e}")

bot.run(TOKEN)
