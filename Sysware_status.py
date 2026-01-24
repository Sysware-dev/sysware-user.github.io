# sysware_status.py
import discord
from discord.ext import commands, tasks
import datetime
import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("STATUS_CHANNEL_ID", "1460911777939194081"))
STATUS_MESSAGE_ID = int(os.getenv("STATUS_MESSAGE_ID", "0"))  # Set this in .env after first run

# GitHub JSON URL
STATUS_JSON_URL = "https://raw.githubusercontent.com/Sysware-dev/sysware-user.github.io/refs/heads/main/Discord.Status.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Status storage
current_status = {
    'admin': {'status': 'Offline', 'last_update': None, 'color': '🔴'},
    'usermode': {'status': 'Offline', 'last_update': None, 'color': '🔴'},
    'server': {'status': 'Offline', 'last_update': None, 'color': '🔴'}
}

# Status message ID (will be updated instead of creating new messages)
status_message_id = STATUS_MESSAGE_ID

# Status options and colors
STATUS_OPTIONS = {
    'admin': {
        'Online': '🟢',
        'Busy': '🟡',
        'Sleeping': '🟠',
        'Offline': '🔴'
    },
    'usermode': {
        'Online': '🟢',
        'Updating': '🟡',
        'Offline': '🔴'
    },
    'server': {
        'Online': '🟢',
        'Medium': '🟡',
        'Offline': '🔴'
    }
}

def get_status_color(category, status):
    return STATUS_OPTIONS.get(category, {}).get(status, '⚪')

def create_status_embed():
    """Create a beautiful status embed"""
    embed = discord.Embed(
        title="🖥️ Sysware System Status",
        description="Real-time system component status monitoring",
        color=0x5865F2,
        timestamp=datetime.datetime.now()
    )
    
    # Admin Status
    admin = current_status['admin']
    embed.add_field(
        name=f"{admin['color']} Admin Status",
        value=f"**Status:** {admin['status']}\n**Last Update:** {admin['last_update'] or 'Never'}",
        inline=False
    )
    
    # Usermode Status
    usermode = current_status['usermode']
    embed.add_field(
        name=f"{usermode['color']} User Mode",
        value=f"**Status:** {usermode['status']}\n**Last Update:** {usermode['last_update'] or 'Never'}",
        inline=False
    )
    
    # Server Status
    server = current_status['server']
    embed.add_field(
        name=f"{server['color']} Server",
        value=f"**Status:** {server['status']}\n**Last Update:** {server['last_update'] or 'Never'}",
        inline=False
    )
    
    # Overall system health
    all_online = all(s['status'] in ['Online'] for s in current_status.values())
    any_offline = any(s['status'] == 'Offline' for s in current_status.values())
    
    if all_online:
        health = "✅ All Systems Operational"
        health_color = 0x57F287
    elif any_offline:
        health = "🔴 Critical Issues Detected"
        health_color = 0xED4245
    else:
        health = "⚠️ Some Systems Degraded"
        health_color = 0xFEE75C
    
    embed.color = health_color
    embed.set_footer(text=f"{health} • Auto-updates every 30s")
    
    return embed

async def fetch_status_from_github():
    """Fetch status from GitHub JSON file"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(STATUS_JSON_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"Fetched status: {data}")
                    
                    # Update status for each component
                    for component in ['admin', 'usermode', 'server']:
                        if component in data:
                            new_status = data[component]
                            if new_status in STATUS_OPTIONS.get(component, {}):
                                # Only update if status changed
                                if current_status[component]['status'] != new_status:
                                    current_status[component]['status'] = new_status
                                    current_status[component]['color'] = get_status_color(component, new_status)
                                    current_status[component]['last_update'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    print(f"Updated {component} to {new_status}")
                    return True
                else:
                    print(f"Failed to fetch status: HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"Error fetching status from GitHub: {e}")
        return False

async def update_status_message():
    """Update the status message in Discord (only edits, never creates new)"""
    global status_message_id
    
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("Channel not found!")
        return
    
    embed = create_status_embed()
    
    try:
        if status_message_id and status_message_id != 0:
            # Only edit existing message
            try:
                message = await channel.fetch_message(status_message_id)
                await message.edit(embed=embed)
                print(f"Updated status message {status_message_id}")
            except discord.NotFound:
                print(f"Status message {status_message_id} not found! Please update STATUS_MESSAGE_ID in .env")
            except Exception as e:
                print(f"Error editing message: {e}")
        else:
            print("No STATUS_MESSAGE_ID set! Please create a message manually and set its ID in .env")
    except Exception as e:
        print(f"Error updating status message: {e}")

@bot.event
async def on_ready():
    print(f'Sysware Status Bot logged in as {bot.user}')
    print(f'Channel ID: {CHANNEL_ID}')
    print(f'Status Message ID: {status_message_id}')
    
    if status_message_id == 0:
        print("\n⚠️  WARNING: STATUS_MESSAGE_ID not set!")
        print("Please create a status message manually and add its ID to .env")
        print("Example: STATUS_MESSAGE_ID=1234567890123456789\n")
    
    # Start the auto-update task
    auto_update_status.start()

@tasks.loop(seconds=30)
async def auto_update_status():
    """Fetch status from GitHub and update Discord message every 30 seconds"""
    await fetch_status_from_github()
    await update_status_message()

@auto_update_status.before_loop
async def before_auto_update():
    await bot.wait_until_ready()

@bot.command(name='setstatus')
@commands.has_permissions(administrator=True)
async def create_initial_status(ctx):
    """Command to create the initial status message (admin only)"""
    global status_message_id
    
    embed = create_status_embed()
    message = await ctx.send(embed=embed)
    status_message_id = message.id
    
    await ctx.send(f"✅ Status message created! Add this to your .env file:\n```STATUS_MESSAGE_ID={message.id}```")

if __name__ == "__main__":
    bot.run(TOKEN)