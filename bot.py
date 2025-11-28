import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Configuration
TRACKING_DOMAINS = [
    'ubereats.com',
    'doordash.com',
    'grubhub.com',
    'postmates.com',
    'deliveroo.com'
]

PUNCHES_PER_REWARD = 5
DATA_FILE = 'punchcards.json'

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Data management
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                content = f.read().strip()
                if not content:  # Handle empty file
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            # Corrupt file, start new
            print("⚠️ Warning: punchcards.json is corrupted. Starting fresh.")
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_user_data(user_id):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            'punches': 0,
            'free_orders': 0,
            'referrals': 0
        }
        save_data(data)
    return data[user_id_str]

def update_user_data(user_id, updates):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            'punches': 0,
            'free_orders': 0,
            'referrals': 0
        }
    
    for key, value in updates.items():
        data[user_id_str][key] = value
    
    save_data(data)
    return data[user_id_str]

# Events
@bot.event
async def on_ready():
    try:
        # Sync commands globally
        synced = await bot.tree.sync()
        print(f'🟢 {bot.user} is online!')
        print(f'✅ Synced {len(synced)} commands globally')
        
        # Also sync to each guild for instant updates
        for guild in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=guild)
                guild_synced = await bot.tree.sync(guild=guild)
                print(f'✅ Synced {len(guild_synced)} commands to {guild.name}')
            except Exception as guild_error:
                print(f'❌ Failed to sync to {guild.name}: {guild_error}')
        
        print(f'📊 Tracking {len(TRACKING_DOMAINS)} delivery domains')
        print(f'🎁 Reward every {PUNCHES_PER_REWARD} punches')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Check for tracking links
    for domain in TRACKING_DOMAINS:
        if domain.lower() in message.content.lower():
            user_data = get_user_data(message.author.id)
            
            # Add punch
            new_punches = user_data['punches'] + 1
            new_free_orders = user_data['free_orders']
            
            # Check if earned reward
            if new_punches >= PUNCHES_PER_REWARD:
                new_free_orders += 1
                new_punches = 0
                
                # Update data
                update_user_data(message.author.id, {
                    'punches': new_punches,
                    'free_orders': new_free_orders,
                    'referrals': user_data['referrals']
                })
                
                # Send reward message
                embed = discord.Embed(
                    title="🎉 FREE ORDER EARNED!",
                    description=f"{message.author.mention} just earned a **free order**!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Your Rewards",
                    value=f"🎁 Free Orders: **{new_free_orders}**\n🍓 Referrals: **{user_data['referrals']}**"
                )
                await message.channel.send(embed=embed)
            else:
                # Just add punch
                update_user_data(message.author.id, {
                    'punches': new_punches,
                    'free_orders': new_free_orders,
                    'referrals': user_data['referrals']
                })
                
                # Confirmation message
                punches_left = PUNCHES_PER_REWARD - new_punches
                await message.add_reaction('✅')
                
                embed = discord.Embed(
                    description=f"✅ **+1 punch** added to {message.author.mention}",
                    color=0x3498db
                )
                embed.add_field(
                    name="Progress",
                    value=f"🔲 {new_punches}/{PUNCHES_PER_REWARD} punches\n📦 {punches_left} more until free order!"
                )
                await message.channel.send(embed=embed, delete_after=10)
            
            break
    
    await bot.process_commands(message)

# Slash Commands
class Punchcards(app_commands.Group):
    @app_commands.command(name="add", description="Add punches to a user")
    @app_commands.describe(user="The user to add punches to", amount="Number of punches to add")
    async def add_punches(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission.", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
            return
        
        user_data = get_user_data(user.id)
        new_punches = user_data['punches'] + amount
        new_free_orders = user_data['free_orders']
        
        # Calculate rewards earned
        rewards_earned = new_punches // PUNCHES_PER_REWARD
        if rewards_earned > 0:
            new_free_orders += rewards_earned
            new_punches = new_punches % PUNCHES_PER_REWARD
        
        update_user_data(user.id, {
            'punches': new_punches,
            'free_orders': new_free_orders,
            'referrals': user_data['referrals']
        })
        
        embed = discord.Embed(
            title="✅ Punches Added",
            description=f"Added **{amount}** punches to {user.mention}",
            color=0x00ff00
        )
        embed.add_field(name="New Punch Count", value=f"🔲 {new_punches}/{PUNCHES_PER_REWARD}", inline=True)
        embed.add_field(name="Free Orders", value=f"🎁 {new_free_orders}", inline=True)
        
        if rewards_earned > 0:
            embed.add_field(name="Rewards Earned", value=f"🎉 +{rewards_earned} free orders!", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="remove", description="Remove punches from a user")
    @app_commands.describe(user="The user to remove punches from", amount="Number of punches to remove")
    async def remove_punches(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission.", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
            return
        
        user_data = get_user_data(user.id)
        new_punches = max(0, user_data['punches'] - amount)
        
        update_user_data(user.id, {
            'punches': new_punches,
            'free_orders': user_data['free_orders'],
            'referrals': user_data['referrals']
        })
        
        embed = discord.Embed(
            title="✅ Punches Removed",
            description=f"Removed **{amount}** punches from {user.mention}",
            color=0xe74c3c
        )
        embed.add_field(name="New Punch Count", value=f"🔲 {new_punches}/{PUNCHES_PER_REWARD}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="removefree", description="Remove free orders from a user")
    @app_commands.describe(user="The user to remove free orders from", count="Number of free orders to remove")
    async def remove_free(self, interaction: discord.Interaction, user: discord.Member, count: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission.", ephemeral=True)
            return
        
        if count <= 0:
            await interaction.response.send_message("❌ Count must be positive.", ephemeral=True)
            return
        
        user_data = get_user_data(user.id)
        old_free_orders = user_data['free_orders']
        new_free_orders = max(0, user_data['free_orders'] - count)
        actual_removed = old_free_orders - new_free_orders
        
        update_user_data(user.id, {
            'punches': user_data['punches'],
            'free_orders': new_free_orders,
            'referrals': user_data['referrals']
        })
        
        embed = discord.Embed(
            title="🎁 Free Orders Removed",
            description=f"Removed **{actual_removed}** free order(s) from {user.mention}",
            color=0xe67e22
        )
        embed.add_field(name="Remaining Free Orders", value=f"🎁 {new_free_orders}", inline=True)
        embed.add_field(name="Current Punches", value=f"🔲 {user_data['punches']}/{PUNCHES_PER_REWARD}", inline=True)
        
        if actual_removed < count:
            embed.add_field(
                name="⚠️ Note",
                value=f"User only had {old_free_orders} free order(s) available.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="stats", description="View punchcard statistics")
    @app_commands.describe(user="The user to view stats for (leave empty for yourself)")
    async def stats(self, interaction: discord.Interaction, user: discord.Member = None):
        target_user = user or interaction.user
        user_data = get_user_data(target_user.id)
        
        punches_left = PUNCHES_PER_REWARD - user_data['punches']
        
        embed = discord.Embed(
            title=f"📊 Punchcard for {target_user.display_name}",
            color=0x9b59b6
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="🔲 Punches", value=f"{user_data['punches']}/{PUNCHES_PER_REWARD}", inline=True)
        embed.add_field(name="🎁 Free Orders", value=str(user_data['free_orders']), inline=True)
        embed.add_field(name="👥 Referrals", value=str(user_data['referrals']), inline=True)
        embed.add_field(
            name="📦 Next Reward",
            value=f"{punches_left} punches away",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="referral", description="Add referral credit to a user")
@app_commands.describe(user="The user who made the referral", amount="Number of referrals to add")
async def referral(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need 'Manage Messages' permission.", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
    
    user_data = get_user_data(user.id)
    new_referrals = user_data['referrals'] + amount
    
    update_user_data(user.id, {
        'punches': user_data['punches'],
        'free_orders': user_data['free_orders'],
        'referrals': new_referrals
    })
    
    embed = discord.Embed(
        title="👥 Referral Added",
        description=f"Added **{amount}** referral(s) to {user.mention}",
        color=0xf39c12
    )
    embed.add_field(name="Total Referrals", value=f"👥 {new_referrals}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="referralremove", description="Remove referral credit from a user")
@app_commands.describe(user="The user to remove referrals from", amount="Number of referrals to remove")
async def referral_remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need 'Manage Messages' permission.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return

    user_data = get_user_data(user.id)
    old_referrals = user_data['referrals']
    new_referrals = max(0, old_referrals - amount)
    actual_removed = old_referrals - new_referrals

    update_user_data(user.id, {
        'punches': user_data['punches'],
        'free_orders': user_data['free_orders'],
        'referrals': new_referrals
    })

    embed = discord.Embed(
        title="👥 Referrals Removed",
        description=f"Removed **{actual_removed}** referral(s) from {user.mention}",
        color=0xe67e22
    )
    embed.add_field(name="Remaining Referrals", value=f"👥 {new_referrals}", inline=True)

    if actual_removed < amount:
        embed.add_field(
            name="⚠️ Note",
            value=f"User only had {old_referrals} referral(s) available.",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Register command group
bot.tree.add_command(Punchcards(name="punchcards", description="Manage punchcards"))

# Run bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN not found in .env file")
    else:
        bot.run(TOKEN)