# FastAPI for Agentic Search pipeline
import json
import asyncio
import logging
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.config import settings

logging.basicConfig(level=settings.LOG_LEVEL)

app = FastAPI(title="Agentic Search", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/search")
async def search(q: str = Query(..., description="Topic query")):
    """Run full pipeline, return results."""
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run(q)
    return result.model_dump()


@app.get("/api/search/stream")
async def search_stream(q: str = Query(..., description="Topic query")):
    # Run pipeline with SSE streaming 
    async def event_generator():
        stage_queue = asyncio.Queue()
        def on_stage(name):
            stage_queue.put_nowait(name)

        orchestrator = PipelineOrchestrator()
        task = asyncio.create_task(orchestrator.run(q, on_stage=on_stage))

        while not task.done():
            try:
                stage = await asyncio.wait_for(stage_queue.get(), timeout=0.5)
                yield f"data: {json.dumps({'type': 'stage', 'stage': stage})}\n\n"
            except asyncio.TimeoutError:
                continue

        # Drain remaining stages
        while not stage_queue.empty():
            stage = stage_queue.get_nowait()
            yield f"data: {json.dumps({'type': 'stage', 'stage': stage})}\n\n"
        result = await task
        yield f"data: {json.dumps({'type': 'result', 'data': result.model_dump()})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.LLM_MODEL}

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")