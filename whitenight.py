
import os
import asyncio
from fastapi import FastAPI, Request
import discord
from discord.ext import commands
import uvicorn

# ===== ENV =====
TOKEN = os.environ["TOKEN"]
SERVER_ID = int(os.environ["SERVER_ID"])
CHANNEL_ID = int(os.environ["CHANNEL_ID"]
)
ROLE_ID = int(os.environ["ROLE_ID"])
PORT = int(os.environ.get("PORT", 8080))

# ===== DISCORD =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== API (BOT SERVICE) =====
app = FastAPI()
queue = asyncio.Queue()

@app.post("/queue")
async def queue_endpoint(request: Request):
    data = await request.json()
    await queue.put(data)
    return {"status": "queued"}

@bot.event
async def on_ready():
    print(f"✅ [whitenight] Bot ready: {bot.user}", flush=True)
    bot.loop.create_task(process_queue())

async def process_queue():
    while True:
        data = await queue.get()
        try:
            discord_id = int(data.get("discordId"))
            result = data.get("result")

            await send_dm(discord_id, result)
            await send_server_message(discord_id, result)

            if str(result).lower() in ["sikeres", "success", "ok", "pass", "true", "1"]:
                await give_role(discord_id)

        except Exception as e:
            print(f"❌ process_queue error: {e}", flush=True)

async def send_dm(user_id, result):
    try:
        user = await bot.fetch_user(user_id)
        await user.send(f"Teszt eredményed: {result}")
    except Exception as e:
        print(f"DM error: {e}", flush=True)

async def send_server_message(user_id, result):
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"<@{user_id}> Teszt eredmény: {result}")
    except Exception as e:
        print(f"Channel message error: {e}", flush=True)

async def give_role(user_id: int):
    try:
        guild = bot.get_guild(SERVER_ID)
        if not guild:
            print("❌ Guild not found", flush=True)
            return

        member = await guild.fetch_member(user_id)
        role = guild.get_role(ROLE_ID)

        if not role:
            print("❌ Role not found", flush=True)
            return

        bot_member = guild.get_member(bot.user.id) or await guild.fetch_member(bot.user.id)
        if role.managed:
            print("❌ Managed role, not assignable", flush=True)
            return
        if bot_member.top_role <= role:
            print("❌ Role hierarchy issue", flush=True)
            return

        if role in member.roles:
            return

        await member.add_roles(role, reason="Whitenight webhook success")
        print(f"✅ Role added to {member}", flush=True)

    except discord.Forbidden:
        print("❌ Forbidden (permissions/hierarchy)", flush=True)
    except Exception as e:
        print(f"ROLE error: {e}", flush=True)

async def start_bot():
    await bot.start(TOKEN)

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    # API + bot ugyanabban a processben, de külön taskban
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    start_api()
