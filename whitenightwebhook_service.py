
import os
from fastapi import FastAPI, Request
import httpx

BOT_QUEUE_URL = os.environ["BOT_QUEUE_URL"]  # pl. https://whitenight-bot.up.railway.app/queue

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # basic validation
    if "discordId" not in data or "result" not in data:
        return {"status": "error", "message": "Missing discordId or result"}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(BOT_QUEUE_URL, json=data)
        return {"status": "ok", "forward_status": r.status_code}
