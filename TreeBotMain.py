import asyncio
import json
import logging
import random
import time
from collections import deque
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View


def get_bot_token():
    try:
        with open("token.txt", "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        raise ValueError("token.txt file not found. Please make sure it is in the same directory as the script.")

BOT_TOKEN = get_bot_token()

config = {
    "TEST_MODE": True,
    "COOLDOWN_SECONDS": 10,
    "BOT_TOKEN": BOT_TOKEN,
    "BANNED_USERS": []
}

config.update({
    "TOPIC_COOLDOWN_HOURS": 2,
    "TOPICS_FILE": "topics.txt"
})

ACTIVITIES = [
    discord.Game(name="Watering the tree 🌳"),
    discord.Game(name="Watching over the garden 🌻"),
    discord.Game(name="Shuffling leaves 🍂"),
    discord.Game(name="Getting pinged by HazardGoose 🏓"),
    discord.Game(name="Burning other trees 🔥"),
    discord.Game(name="Analyzing growth data 📈"),
    discord.Game(name="Checking soil moisture levels 💧"),
    discord.Game(name="Syncing with global tree network 🌎"),
    discord.Game(name="Running diagnostics on root network 💻")
]

@tasks.loop(seconds=30)
async def switch_activity():
    activity = random.choice(ACTIVITIES)
    await bot.change_presence(activity=activity)

def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f)

def load_config():
    try:
        with open('config.json', 'r') as f:
            loaded_config = json.load(f)
            config.update(loaded_config)
    except FileNotFoundError:
        save_config()
load_config()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('discord')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_role_id():
    return 1186948054838951976 if config["TEST_MODE"] else 1286817521952886854

def get_role_ids():
    return [
        1272788582691635211,
        1186948054838951976
    ]

class TopicManager:
    def __init__(self, cooldown_hours: int):
        self.used_topics = deque(maxlen=1000)
        self.cooldown_seconds = cooldown_hours * 3600

    def load_topics(self) -> list[str]:
        try:
            with open(config["TOPICS_FILE"], 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.error(f"Topics file {config['TOPICS_FILE']} not found")
            return []

    def get_available_topics(self) -> list[str]:
        current_time = time.time()
        while self.used_topics and current_time - self.used_topics[0][1] > self.cooldown_seconds:
            self.used_topics.popleft()

        recent_topics = {topic for topic, _ in self.used_topics}

        all_topics = self.load_topics()
        return [topic for topic in all_topics if topic not in recent_topics]

    def get_random_topic(self) -> tuple[str, bool]:
        available_topics = self.get_available_topics()

        if not available_topics:
            all_topics = self.load_topics()
            if not all_topics:
                return "No topics available in topics.txt", False

            topic = random.choice(all_topics)
            reused = True
        else:
            topic = random.choice(available_topics)
            reused = False

        self.used_topics.append((topic, time.time()))
        return topic, reused

bot.topic_manager = TopicManager(config["TOPIC_COOLDOWN_HOURS"])

async def has_required_role(interaction: discord.Interaction):
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        member = await interaction.guild.fetch_member(interaction.user.id)

    if not any(role.id in get_role_ids() for role in member.roles):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return False
    return True

THREAD_ID = 1286821326778011790
CHANNEL_ID = 1272801417047834654

REQUIRED_ROLE = 1186948054838951976

def get_test_mode_message():
    return " [I AM IN TEST MODE, PING ME FOR TESTING ☺]" if config["TEST_MODE"] else ""

class ConfirmView(View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)
        self.value = None
        self.message = None

    async def on_timeout(self):
        await self.delete_confirmation_message()
        self.stop()

    async def delete_confirmation_message(self):
        if self.message:
            try:
                await self.message.delete()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                pass

    @discord.ui.button(label="Confirm Ping", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        self.value = True
        self.stop()
        logger.info(f"{interaction.user.name} confirm")
        await self.delete_confirmation_message()
        await interaction.followup.send("Pinged Tree Role!", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        self.value = False
        self.stop()
        logger.info(f"{interaction.user.name} cancel")
        await self.delete_confirmation_message()
        await interaction.followup.send("Cancelled", ephemeral=True)

class PingButton(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.previous_confirmation_messages = {}
        self.cooldowns = {}

    @discord.ui.button(label="Ping Tree Role", style=discord.ButtonStyle.danger, custom_id="ping_tree_button")
    async def ping_tree(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.defer(ephemeral=True)
            logger.info(f"{interaction.user.name} ping")

            if interaction.user.id in config["BANNED_USERS"]:
                logger.warning(f"Banned: {interaction.user.name} tried to use button")
                await interaction.followup.send("You are banned from treebot ☻", ephemeral=True)
                return

            current_time = datetime.now()
            user_id = interaction.user.id
            if user_id in self.cooldowns:
                time_diff = (current_time - self.cooldowns[user_id]).total_seconds()
                if time_diff < config["COOLDOWN_SECONDS"]:
                    remaining = round(config["COOLDOWN_SECONDS"] - time_diff)
                    await interaction.followup.send(
                        f"Please wait {remaining} seconds before using this button again.",
                        ephemeral=True
                    )
                    return

            if not interaction.guild:
                logger.warning(f"User {interaction.user.name} attempted to use button outside server")
                await interaction.followup.send("This button can only be used in a server.", ephemeral=True)
                return

            role = interaction.guild.get_role(get_role_id())
            thread = bot.get_channel(THREAD_ID)

            if not role or not thread:
                logger.error(f"Role or thread not found for user {interaction.user.name}")
                await interaction.followup.send("Role or thread not found.", ephemeral=True)
                return

            if user_id in self.previous_confirmation_messages:
                try:
                    await self.previous_confirmation_messages[user_id].delete_confirmation_message()
                except:
                    pass

            view = ConfirmView()
            confirmation_message = await interaction.followup.send(
                f"Are you sure you want to ping the role?{get_test_mode_message()}",
                view=view,
                ephemeral=True
            )
            view.message = confirmation_message
            self.previous_confirmation_messages[user_id] = view
            await view.wait()

            if view.value:
                self.cooldowns[user_id] = current_time
                await thread.send(f"{role.mention} 🌲 Pinged by {interaction.user.name}!{get_test_mode_message()}")

        except discord.errors.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"Error for user {interaction.user.name}: {str(e)}")
            try:
                await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
            except:
                pass

    async def cleanup_cooldowns(self):
        current_time = datetime.now()
        self.cooldowns = {
            user_id: timestamp
            for user_id, timestamp in self.cooldowns.items()
            if (current_time - timestamp).total_seconds() < config["COOLDOWN_SECONDS"]
        }

async def update_button_message():
    if hasattr(bot, 'ping_button_message'):
        try:
            await bot.ping_button_message.edit(
                content=f"Click this button to ping @tree role when the tree needs watering!{get_test_mode_message()}",
                view=PingButton()
            )
        except Exception as e:
            logger.error(f"Error updating button message: {str(e)}")

async def check_roles(interaction: discord.Interaction):
    if not has_required_role(interaction.user):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return False
    return True

@bot.tree.command(name="topic", description="Get a random discussion topic")
async def get_topic(interaction: discord.Interaction):
    try:
        topic, _ = bot.topic_manager.get_random_topic()

        await interaction.response.send_message(f"{topic}")

        logger.info(f"{interaction.user.name} used topic")

    except Exception as e:
        logger.error(f"Error in topic command: {str(e)}")
        await interaction.response.send_message(
            "An error occurred while getting a topic. Please try again.",
            ephemeral=True
        )

@bot.tree.command(name="toggletestmode", description="Toggle test mode on/off")
async def toggle_test_mode(interaction: discord.Interaction):
    if not await has_required_role(interaction):
        logger.info(f"{interaction.user.name} attempted: toggletestmode")
        if not interaction.response.is_done():
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    config["TEST_MODE"] = not config["TEST_MODE"]
    save_config()
    mode_status = "enabled" if config["TEST_MODE"] else "disabled"

    logger.info(f"{interaction.user.name} set toggletestmod: {mode_status}")

    await update_button_message()

    if not interaction.response.is_done():
        await interaction.response.send_message(f"Test mode {mode_status}", ephemeral=False)

@bot.tree.command(name="ban", description="Ban a user from using the tree bot")
async def ban_user(interaction: discord.Interaction, user: discord.User):
    if not await has_required_role(interaction):

        logger.info(f"{interaction.user.name} attempted: ban {user.name}")

        if not interaction.response.is_done():
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if user.id not in config["BANNED_USERS"]:
        config["BANNED_USERS"].append(user.id)
        save_config()

        logger.info(f"{interaction.user.name} banned {user.name}")

        if not interaction.response.is_done():
            await interaction.response.send_message(f"Banned {user.name} from using the tree bot", ephemeral=False)
    else:
        logger.info(f"{interaction.user.name} tried to ban {user.name}, but they are already banned.")

        if not interaction.response.is_done():
            await interaction.response.send_message(f"{user.name} is already banned", ephemeral=False)

@bot.tree.command(name="unban", description="Unban a user from the tree bot")
async def unban_user(interaction: discord.Interaction, user: discord.User):
    if not await has_required_role(interaction):
        logger.info(f"{interaction.user.name} attempted: unban {user.name}")

        if not interaction.response.is_done():
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if user.id in config["BANNED_USERS"]:
        config["BANNED_USERS"].remove(user.id)
        save_config()

        logger.info(f"{interaction.user.name} unbanned {user.name}")

        if not interaction.response.is_done():
            await interaction.response.send_message(f"Unbanned {user.name} from the tree bot", ephemeral=False)
    else:
        logger.info(f"{interaction.user.name} tried to unban {user.name}, but they are not banned.")

        if not interaction.response.is_done():
            await interaction.response.send_message(f"{user.name} is not banned", ephemeral=False)

@bot.tree.command(name="listbanned", description="List all banned users")
async def list_banned(interaction: discord.Interaction):
    logger.info(f"{interaction.user.name} used listbanned")

    if not config["BANNED_USERS"]:
        await interaction.response.send_message("No users are currently banned", ephemeral=False)
        return

    banned_users = []
    for user_id in config["BANNED_USERS"]:
        try:
            user = await bot.fetch_user(user_id)
            banned_users.append(f"- {user.name} ({user_id})")
        except:
            banned_users.append(f"- Unknown User ({user_id})")

    await interaction.response.send_message(
        "Banned users:\n" + "\n".join(banned_users),
        ephemeral=False
    )

@bot.event
async def on_ready():
    if not switch_activity.is_running():
        switch_activity.start()

    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s) globally")

        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
    except Exception as e:
        logger.error(f"Error syncing commands: {str(e)}")

    bot.add_view(PingButton())

    if not check_connection.is_running():
        check_connection.start()

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        existing_button = None
        async for message in channel.history(limit=100):
            if message.author == bot.user and "Click this button to ping @tree role" in message.content:
                existing_button = message
                break

        if existing_button:
            bot.ping_button_message = existing_button
            await update_button_message()
        else:
            async for message in channel.history(limit=100):
                if message.author == bot.user:
                    await message.delete()

            bot.ping_button_message = await channel.send(
                f"Click this button to ping @tree role when the tree needs watering!{get_test_mode_message()}",
                view=PingButton()
            )
            logger.info("New ping button message created")
    if not switch_activity.is_running():
        switch_activity.start()
    print("Bot is ready")

@tasks.loop(seconds=30)
async def check_connection():
    try:
        if bot.is_closed():
            logger.warning("Bot connection is closed, attempting to reconnect")
            return

        if bot.latency > 1.0:
            logger.warning(f"High latency detected: {bot.latency:.2f}s")
            return

        channel = bot.get_channel(CHANNEL_ID)
        if channel and hasattr(bot, 'ping_button_message'):
            try:
                message = await channel.fetch_message(bot.ping_button_message.id)
                if not message.components:
                    await message.edit(view=PingButton())
                    logger.info("Restored button view to existing message")
            except discord.NotFound:
                logger.info("Ping button message not found, creating new one")
                bot.ping_button_message = await channel.send(
                    f"Click this button to ping @tree role when the tree needs watering!{get_test_mode_message()}",
                    view=PingButton()
                )
            except Exception as e:
                logger.error(f"Error in check_connection: {str(e)}")

    except Exception as e:
        logger.error(f"Connection check error: {str(e)}")

@check_connection.before_loop
async def before_check_connection():
    await bot.wait_until_ready()

@check_connection.after_loop
async def after_check_connection():
    if check_connection.is_being_cancelled():
        logger.info("Bot stopped, cleaning up...")

@bot.event
async def on_resumed():
    logger.info("Bot resumed connection")
    await asyncio.sleep(1)
    if hasattr(bot, 'ping_button_message'):
        try:
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.fetch_message(bot.ping_button_message.id)
        except (discord.NotFound, discord.HTTPException):
            bot.ping_button_message = await channel.send(
                f"Click this button to ping @tree role when the tree needs watering!{get_test_mode_message()}",
                view=PingButton()
            )
            logger.info("Recreated button message after resume")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}: {args} {kwargs}")

@bot.event
async def on_command(ctx):
    logger.info(f"{ctx.author} used command: {ctx.command}")

async def cleanup():
    if check_connection.is_running():
        check_connection.cancel()

    if switch_activity.is_running():
        switch_activity.cancel()

    try:
        if not bot.is_closed():
            await bot.close()
    except Exception as e:
        logger.error(f"Error during bot cleanup: {str(e)}")

    if hasattr(bot, 'session') and not bot.session.closed:
        await bot.session.close()

    await asyncio.sleep(0.25)

async def main():
    bot.session = aiohttp.ClientSession()

    while True:
        try:
            bot.reconnect = True
            if hasattr(bot, 'ws') and bot.ws:
                bot.ws._max_heartbeat_timeout = 120.0

            await bot.start(config["BOT_TOKEN"])

        except discord.errors.LoginFailure:
            logger.error("Invalid token")
            await cleanup()
            break

        except (discord.errors.ConnectionClosed,
                discord.errors.GatewayNotFound,
                discord.errors.HTTPException) as e:
            logger.error(f"Connection error: {str(e)}")
            await cleanup()
            await asyncio.sleep(10)
            continue

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {str(e)}")
            await cleanup()
            await asyncio.sleep(10)
            continue

        await asyncio.sleep(10)

    await cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup())
        loop.close()