import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
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
intents.members = True          # role-hoz kellhet
intents.message_content = True  # nem kötelező ehhez, de maradhat

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


async def _enqueue_data(data: dict):
    global _last_payload
    _last_payload = data
    await queue.put(data)


@app.post("/queue")
async def enqueue(request: Request):
    data = await request.json()
    await _enqueue_data(data)
    return {"status": "queued", "queue_size": queue.qsize()}


# ✅ ÚJ: webhook endpoint (ugyanaz, mint a queue)
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    await _enqueue_data(data)
    return {"status": "ok", "queued": True, "queue_size": queue.qsize()}


@bot.event
async def on_ready():
    print(f"✅ Discord logged in as: {bot.user} | guilds={[g.id for g in bot.guilds]}")


async def send_dm(user_id: int, result: str):
    user = await bot.fetch_user(user_id)
    await user.send(f"Teszt eredményed: {result}")


async def send_channel_message(user_id: int, result: str):
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        channel = await bot.fetch_channel(CHANNEL_ID)
    await channel.send(f"<@{user_id}> Teszt eredmény: {result}")


async def give_role(user_id: int):
    if ROLE_ID == 0:
        print("ℹ️ ROLE_ID=0 -> skipping role")
        return

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
            # ⚠️ discordId lehet string -> tisztítsuk
            raw_id = data.get("discordId")
            discord_id = int(str(raw_id).strip())
            result = str(data.get("result", "")).strip()

            print(f"📩 QUEUE item: discordId={discord_id}, result={result}, raw={data}")

            # DM
            try:
                await send_dm(discord_id, result)
                print("✅ DM sent")
            except Exception as e:
                print(f"❌ DM failed: {e}")

            # Channel
            try:
                await send_channel_message(discord_id, result)
                print("✅ Channel message sent")
            except Exception as e:
                print(f"❌ Channel message failed: {e}")

            # Role
            if result.lower() in ["sikeres", "success", "ok", "pass", "true", "1"]:
                try:
                    await give_role(discord_id)
                except Exception as e:
                    print(f"❌ Role failed: {e}")
            else:
                print("ℹ️ Not successful -> no role")

        except Exception as e:
            print(f"❌ Worker error: {e}")
        finally:
            queue.task_done()


async def start_discord_and_worker():
    await bot.login(TOKEN)
    asyncio.create_task(bot.connect())
    await bot.wait_until_ready()
    asyncio.create_task(worker_loop())


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_discord_and_worker())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
