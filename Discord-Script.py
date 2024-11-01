import discord
from discord.ext import commands
from discord.ui import Button, View

# Read the bot token from a file
bot_token_path = r'C:\Users\saved\PycharmProjects\discord-rich-presence\bot api'
with open(bot_token_path, 'r', encoding='utf-8') as file:
    bot_token = file.read().strip()

# Set up the bot with required intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enable member intents if you want to use UserSelect
bot = commands.Bot(command_prefix="!", intents=intents)

ROLE_ID = 1301973820223131718  # Replace with your role ID
THREAD_ID = 1301976838519652495  # Replace with your thread ID
CHANNEL_ID = 1280217973965197497  # Replace with your channel ID

# Define a view with buttons
class MyView(View):
    @discord.ui.button(label="Ping Tree", style=discord.ButtonStyle.primary)
    async def ping_tree(self, interaction: discord.Interaction, button: Button):
        print(f"Interaction: {interaction}")

        # Ensure the interaction is in a guild
        if not interaction.guild:
            await interaction.response.send_message("This button can only be used in a server.", ephemeral=True)
            return

        # Fetch the role by ID
        role = discord.utils.get(interaction.guild.roles, id=ROLE_ID)
        if role:
            thread = bot.get_channel(THREAD_ID)
            if isinstance(thread, discord.Thread):
                await thread.send(f"{role.mention} 🌲")
                await interaction.response.send_message("", ephemeral=True)  # Use ephemeral response to acknowledge

@bot.event
async def on_ready():
    print(f"Bot {bot.user} is ready and connected to Discord!")

    # Send a message to the specified channel with buttons
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        view = MyView()  # Create an instance of the view
        await channel.send("Hello, this is a message in the general channel! Select a channel or enter a message:", view=view)
    else:
        print("Channel not found.")

# Run the bot with your token
bot.run(bot_token)
