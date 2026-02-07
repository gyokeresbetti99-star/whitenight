import os
import asyncio
from fastapi import FastAPI, Request
import discord
from discord.ext import commands

# ===== ENV =====
TOKEN = os.environ["TOKEN"]
SERVER_ID = int(os.environ["SERVER_ID"])
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
ROLE_ID = int(os.environ.get("ROLE_ID", "0"))  # optional
PORT = int(os.environ.get("PORT", "8080"))

# ===== DISCORD =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== API =====
app = FastAPI()
queue: asyncio.Queue = asyncio.Queue()
_last_payload = None


@app.get("/health")
async def health():
    return {
        "ok": True,
        "bot_ready": bot.is_ready(),
        "queue_size": queue.qsize(),
        "last_payload": _last_payload,
        "guilds": [g.id for g in bot.guilds],
    }


@app.post("/queue")
async def enqueue(request: Request):
    global _last_payload
    data = await request.json()
    _last_payload = data
    await queue.put(data)
    return {"status": "queued", "queue_size": queue.qsize()}


@bot.event
async def on_ready():
    print(f"✅ Discord logged in as: {bot.user} | guilds={[g.id for g in bot.guilds]}")


async def send_dm(user_id: int, result: str):
    user = await bot.fetch_user(user_id)
    await user.send(f"Teszt eredményed: {result}")


async def send_channel_message(user_id: int, result: str):
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        # ha nincs cache-ben
        channel = await bot.fetch_channel(CHANNEL_ID)

    await channel.send(f"<@{user_id}> Teszt eredmény: {result}")


async def give_role(user_id: int):
    if ROLE_ID == 0:
        return  # nincs role beállítva

    guild = bot.get_guild(SERVER_ID)
    if not guild:
        print(f"❌ Guild not found. SERVER_ID={SERVER_ID} bot_guilds={[g.id for g in bot.guilds]}")
        return

    role = guild.get_role(ROLE_ID)
    if not role:
        print(f"❌ Role not found. ROLE_ID={ROLE_ID}")
        return

    member = guild.get_member(user_id)
    if member is None:
        member = await guild.fetch_member(user_id)

    me = guild.me or await guild.fetch_member(bot.user.id)
    if me.top_role <= role:
        print(f"❌ Role hierarchy: bot top_role ({me.top_role.id}) <= target role ({role.id})")
        return

    if role in member.roles:
        print("ℹ️ Member already has role")
        return

    await member.add_roles(role, reason="Webhook role assign")
    print(f"✅ Role added: {member} -> {role.name}")


async def worker_loop():
    print("✅ Queue worker started")
    while True:
        data = await queue.get()
        try:
            discord_id = int(data.get("discordId"))
            result = str(data.get("result", ""))

            print(f"📩 QUEUE item: discordId={discord_id}, result={result}")

            await send_dm(discord_id, result)
            await send_channel_message(discord_id, result)

            if result.lower() in ["sikeres", "success", "ok", "pass", "true", "1"]:
                await give_role(discord_id)
            else:
                print("ℹ️ Not successful -> no role")

        except Exception as e:
            print(f"❌ Worker error: {e}")
        finally:
            queue.task_done()


async def start_discord_and_worker():
    # ✅ biztos init: login -> connect külön
    await bot.login(TOKEN)
    asyncio.create_task(bot.connect())  # nem blokkol
    await bot.wait_until_ready()        # innentől már biztonságos
    asyncio.create_task(worker_loop())


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_discord_and_worker())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
