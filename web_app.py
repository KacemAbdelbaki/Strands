import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from agent import create_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Strands Assistant Web UI")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# Mount the static directory for CSS/JS/HTML
app.mount("/static", StaticFiles(directory="static"), name="static")

# Lazy load agent
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        logger.info("Initializing Strands Agent...")
        _agent = create_agent()
    return _agent

class ChatRequest(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: static/index.html not found.</h1>"

@app.post("/chat")
async def chat(request: ChatRequest):
    """Handle chat messages."""
    agent = get_agent()
    try:
        logger.info(f"Received message: {request.message[:50]}...")
        # agent(message) returns the response string (or object that can be cast to string)
        response_obj = agent(request.message)
        response_text = str(response_obj)
        return JSONResponse(content={"response": response_text})
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Ultra-Simple Web UI on http://localhost:8000")
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
