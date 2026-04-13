import asyncio
import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn
import threading
import time

app = FastAPI()

@app.get("/sse")
async def sse():
    async def event_stream():
        try:
            for i in range(10):
                await asyncio.sleep(0.5)
                yield f"data: {i}\n\n"
        finally:
            print("finally called")
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(2)
    
    # Simulate client disconnect
    with httpx.Client() as client:
        with client.stream("GET", "http://127.0.0.1:8001/sse") as response:
            print(next(response.iter_lines()))
            # close immediately
    time.sleep(2)
