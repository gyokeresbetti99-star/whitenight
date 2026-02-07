import os
import asyncio
import logging

from fastapi import FastAPI, Request
import discord
from discord.ext import commands
import uvicorn

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
    print(f"✅ Discord logged in as: {bot.user} | guilds={[g.id for g in bot.guilds]}", flush=True)
    # 🔥 ITT INDÍTJUK a feldolgozót, csak akkor amikor a bot már ready
    bot.loop.create_task(process_queue_forever())

async def process_queue_forever():
    while True:
        data = await queue.get()
        try:
            user_id = int(data.get("discordId"))
            result = data.get("result")

            print(f"📩 QUEUE received: user_id={user_id} result={result}", flush=True)

            # DM
            try:
                user = await bot.fetch_user(user_id)
                await user.send(f"Teszt eredményed: {result}")
                print("✅ DM sent", flush=True)
            except Exception as e:
                print(f"❌ DM error: {e}", flush=True)

            # Channel message
            try:
                channel = bot.get_channel(CHANNEL_ID)
                if channel:
                    await channel.send(f"<@{user_id}> Teszt eredmény: {result}")
                    print("✅ Channel message sent", flush=True)
                else:
                    print("❌ Channel not found (CHANNEL_ID?)", flush=True)
            except Exception as e:
                print(f"❌ Channel error: {e}", flush=True)

            # Role only if success
            if str(result).lower() in ["sikeres", "success", "ok", "pass", "true", "1"]:
                await give_role(user_id)

        except Exception as e:
            print(f"❌ Queue processing error: {e}", flush=True)

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

        me = guild.get_member(bot.user.id) or await guild.fetch_member(bot.user.id)
        if me.top_role <= role:
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

async def main():
    # uvicorn ASYNC ugyanazon a loopon
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)

    api_task = asyncio.create_task(server.serve())
    bot_task = asyncio.create_task(bot.start(TOKEN))

    done, pending = await asyncio.wait(
        {api_task, bot_task},
        return_when=asyncio.FIRST_EXCEPTION
    )

    for task in done:
        exc = task.exception()
        if exc:
            raise exc

if __name__ == "__main__":
    asyncio.run(main())
