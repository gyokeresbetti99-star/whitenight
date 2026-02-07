import os
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/debug")
async def debug():
    v = os.environ.get("BOT_QUEUE_URL", "")
    return {
        "BOT_QUEUE_URL_raw": v,
        "BOT_QUEUE_URL_stripped": v.strip(),
        "raw_len": len(v),
        "stripped_len": len(v.strip()),
    }

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    bot_queue_url_raw = os.environ.get("BOT_QUEUE_URL", "")
    bot_queue_url = bot_queue_url_raw.strip()

    if not bot_queue_url:
        return {"status": "error", "message": "BOT_QUEUE_URL missing or empty"}

    if "discordId" not in data or "result" not in data:
        return {"status": "error", "message": "Missing discordId or result", "received": data}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(bot_queue_url, json=data)
        return {
            "status": "ok",
            "forward_to": bot_queue_url,
            "forward_status": r.status_code,
            "forward_body": (r.text[:300] if r.text else "")
        }
    except Exception as e:
        return {
            "status": "error",
            "forward_to": bot_queue_url,
            "error_type": type(e).__name__,
            "error": str(e)
        }
