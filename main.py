import os
import asyncio
import logging
from fastapi import FastAPI, Request
import discord
from discord.ext import commands
import uvicorn

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)

# ===== ENV =====
TOKEN = os.environ["TOKEN"]
SERVER_ID = int(os.environ["SERVER_ID"])
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
ROLE_ID = int(os.environ["ROLE_ID"])
PORT = int(os.environ.get("PORT", 8080))

# ===== DISCORD =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== API =====
app = FastAPI()
queue: asyncio.Queue = asyncio.Queue()

@app.get("/")
async def root():
    return {"ok": True, "service": "whitenight-bot"}

@app.post("/queue")
async def queue_endpoint(request: Request):
    data = await request.json()
    await queue.put(data)
    return {"status": "queued"}

@bot.event
async def on_ready():
    print(f"✅ Bot ready: {bot.user} | guilds={[g.id for g in bot.guilds]}", flush=True)
    bot.loop.create_task(process_queue())

async def process_queue():
    while True:
        data = await queue.get()
        try:
            user_id = int(data.get("discordId"))
            result = data.get("result")

            print(f"📩 QUEUE: user_id={user_id} result={result}", flush=True)

            # DM
            try:
                user = await bot.fetch_user(user_id)
                await user.send(f"Teszt eredményed: {result}")
                print("✅ DM sent", flush=True)
            except Exception as e:
                print(f"❌ DM error: {e}", flush=True)

            # Channel
            try:
                channel = bot.get_channel(CHANNEL_ID)
                if channel:
                    await channel.send(f"<@{user_id}> Teszt eredmény: {result}")
                    print("✅ Channel message sent", flush=True)
                else:
                    print("❌ Channel not found (CHANNEL_ID?)", flush=True)
            except Exception as e:
                print(f"❌ Channel error: {e}", flush=True)

            # Role only on success
            if str(result).lower() in ["sikeres", "success", "ok", "pass", "true", "1"]:
                await give_role(user_id)

        except Exception as e:
            print(f"❌ Queue process error: {e}", flush=True)

async def give_role(user_id: int):
    try:
        guild = bot.get_guild(SERVER_ID)
        if not guild:
            print(f"❌ Guild not found SERVER_ID={SERVER_ID}", flush=True)
            return

        member = await guild.fetch_member(user_id)
        role = guild.get_role(ROLE_ID)
        if not role:
            print(f"❌ Role not found ROLE_ID={ROLE_ID}", flush=True)
            return

        bot_member = guild.get_member(bot.user.id) or await guild.fetch_member(bot.user.id)
        if bot_member.top_role <= role:
            print("❌ Role hierarchy issue: bot role too low", flush=True)
            return

        if role in member.roles:
            print("ℹ️ Member already has role", flush=True)
            return

        await member.add_roles(role, reason="Whitenight success")
        print(f"✅ Role added to {member}", flush=True)

    except discord.Forbidden:
        print("❌ Forbidden: Manage Roles / hierarchy", flush=True)
    except Exception as e:
        print(f"❌ ROLE error: {e}", flush=True)

async def start_discord():
    await bot.start(TOKEN)

def main():
    loop = asyncio.get_event_loop()
    loop.create_task(start_discord())
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
