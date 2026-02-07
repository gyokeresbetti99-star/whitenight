import os
import json
from fastapi import FastAPI, Request
import httpx

# Környezeti változó: DISCORD_BOT_QUEUE_URL → Service 1 URL-je
DISCORD_BOT_QUEUE_URL = os.environ.get("DISCORD_BOT_QUEUE_URL")

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    discord_id = data.get("discordId")
    result = data.get("result")

    if not discord_id or not result:
        return {"status": "error", "message": "Missing discordId or result"}

    # Küldés a Discord bot service-nek (HTTP POST)
    async with httpx.AsyncClient() as client:
        try:
            await client.post(DISCORD_BOT_QUEUE_URL, json={"discordId": discord_id, "result": result})
        except Exception as e:
            print(f"Error sending to bot service: {e}")
            return {"status": "error", "message": "Bot service error"}

    # Azonnali válasz a webhooknak
    return {"status": "ok"}
