import os
import asyncio
import httpx
import subprocess
from fastapi import FastAPI, HTTPException
from typing import Optional

app = FastAPI(title="Hermes Revenue Gateway with Cognee Memory")

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_MAPPING = {'google-maps': '3UqWSAQ1r03aQgL7T', 'linkedin-profile': 'LB1zjIZesVonP8waB', 'trustpilot': 'byY4mgLT5eGAoYU8c'}
COGNEE_DIR = "/home/peso/cognee"

async def remember_in_cognee(data: str):
    """
    Sends the scraped data to Cognee for indexing using the CLI.
    """
    try:
        # We use 'uv run cognee-cli add' to inject the data into the knowledge graph
        # We wrap the data in quotes to ensure it's passed as a single string
        process = await asyncio.create_subprocess_exec(
            "uv", "run", "cognee-cli", "add", data,
            cwd=COGNEE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return True
    except Exception as e:
        print(f"Cognee Memory Error: {e}")
        return False

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
        results = results_resp.json()
        
        # --- COGNEE INTEGRATION ---
        # Convert results to a string and "remember" them
        # This happens in the background so we don't delay the user response
        asyncio.create_task(remember_in_cognee(str(results)))
        
        return results

@app.get("/health")
async def health():
    return {"status": "healthy", "memory": "cognee_active"}

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
