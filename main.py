import os
from fastapi import FastAPI, HTTPException
from typing import Optional
import httpx
import asyncio

app = FastAPI(title="Hermes Revenue Gateway")

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_MAPPING = {'google-maps': '3UqWSAQ1r03aQgL7T', 'linkedin-profile': 'LB1zjIZesVonP8waB', 'trustpilot': 'byY4mgLT5eGAoYU8c'}

async def run_apify_actor(actor_id: str, input_data: dict):
    url = f"https://api.apify.com/v2/acts/{actor_id}/runs"
    params = {"token": APIFY_TOKEN}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params, json=input_data)
        if response.status_code != 201:
            raise HTTPException(status_code=response.status_code, detail="Apify Actor start failed")
        
        run_data = response.json()
        run_id = run_data["data"]["id"]
        
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        
        while True:
            status_resp = await client.get(status_url)
            status_data = status_resp.json()["data"]
            status = status_data["status"]
            
            if status == "SUCCEEDED":
                break
            elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                raise HTTPException(status_code=500, detail=f"Apify Actor failed with status: {status}")
            
            await asyncio.sleep(2)
            
        dataset_id = status_data["defaultDatasetId"]
        dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
        results_resp = await client.get(dataset_url)
        return results_resp.json()

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/scrape/google-maps")
async def scrape_google_maps(payload: dict):
    return await run_apify_actor(ACTOR_MAPPING["google-maps"], payload)

@app.post("/scrape/linkedin-profile")
async def scrape_linkedin(payload: dict):
    return await run_apify_actor(ACTOR_MAPPING["linkedin-profile"], payload)

@app.post("/scrape/trustpilot")
async def scrape_trustpilot(payload: dict):
    return await run_apify_actor(ACTOR_MAPPING["trustpilot"], payload)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
