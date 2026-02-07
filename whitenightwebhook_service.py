import os
from fastapi import FastAPI, Request
import httpx

# FONTOS: a változóban NE legyen enter a végén, de itt strip-eljük is
BOT_QUEUE_URL = os.environ["BOT_QUEUE_URL"].strip()

app = FastAPI()

@app.get("/debug")
async def debug():
    return {"BOT_QUEUE_URL_raw": os.environ.get("BOT_QUEUE_URL", ""), "BOT_QUEUE_URL_stripped": BOT_QUEUE_URL}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    if "discordId" not in data or "result" not in data:
        return {"status": "error", "message": "Missing discordId or result"}

    # 10 sec timeout, redirect követés
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            r = await client.post(BOT_QUEUE_URL, json=data)
            return {
                "status": "ok",
                "forward_to": BOT_QUEUE_URL,
                "forward_status": r.status_code,
                "forward_body": r.text[:300]
            }
        except Exception as e:
            return {"status": "error", "forward_to": BOT_QUEUE_URL, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    PORT = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=PORT)
