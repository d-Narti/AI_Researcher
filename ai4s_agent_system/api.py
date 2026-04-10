from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from src.celery.tasks import solve_task_async
from celery.result import AsyncResult
from src.logging_setup import setup_logging

logger = setup_logging(__name__)

# Configure custom model credentials
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY = "ollama"

app = FastAPI(title="Agent System API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request and response
class TaskRequest(BaseModel):
    task: str
    model_name: str = "gemma4:e4b"
    temperature: float = 0.2
    max_steps: int = 8
    use_custom_model: bool = True
    base_url: str = DEFAULT_BASE_URL
    api_key: str = DEFAULT_API_KEY
    max_new_tokens: int = 2048

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str = "Task submitted successfully"

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    message: str = ""
    result: dict = None
    error: str = None
    partial: dict = None

class FinalTaskResponse(BaseModel):
    final_solution: str = ""
    code: str = ""
    success_rate: float = 0.0
    agents_used: list = []
    test_results: dict = {}
    decomposition: str = ""

@app.post("/solve", response_model=TaskResponse)
async def solve_task(request: TaskRequest):
    try:
        task_data = {
            'task': request.task,
            'model_name': request.model_name,
            'temperature': request.temperature,
            'max_steps': request.max_steps,
            'use_custom_model': request.use_custom_model,
            'base_url': request.base_url,
            'api_key': request.api_key,
            'max_new_tokens': request.max_new_tokens
        }

        logger.info("Submitting task to Celery with model=%s, max_steps=%s", request.model_name, request.max_steps)
        task_result = solve_task_async.delay(task_data)

        return TaskResponse(
            task_id=task_result.id,
            status="pending",
            message="Task submitted successfully"
        )
    except Exception as e:
        logger.exception("Failed to submit task")
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")

@app.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    try:
        logger.debug("Fetching task status for %s", task_id)
        task_result = AsyncResult(task_id)

        response = TaskStatusResponse(
            task_id=task_id,
            status=task_result.status
        )

        if task_result.state == "PENDING":
            response.message = "Task is waiting to be processed"
        elif task_result.state == "PROGRESS":
            response.progress = task_result.info.get('progress', 0)
            response.message = task_result.info.get('message', '')
            response.partial = task_result.info.get('partial')
        elif task_result.state == "SUCCESS":
            response.result = task_result.result
            response.message = "Task completed successfully"
        elif task_result.state == "FAILURE":
            response.error = str(task_result.info)
            response.message = "Task failed"

        logger.debug("Task %s status=%s", task_id, response.status)
        return response
    except Exception as e:
        logger.exception("Failed to get task status for %s", task_id)
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@app.get("/task/{task_id}/result", response_model=FinalTaskResponse)
async def get_task_result(task_id: str):
    try:
        logger.debug("Fetching final task result for %s", task_id)
        task_result = AsyncResult(task_id)

        if task_result.state == "SUCCESS":
            result_data = task_result.result
            logger.info("Task %s completed successfully", task_id)
            return FinalTaskResponse(**result_data)
        elif task_result.state == "FAILURE":
            logger.error("Task %s failed: %s", task_id, str(task_result.info))
            raise HTTPException(status_code=400, detail=f"Task failed: {str(task_result.info)}")
        elif task_result.state == "PENDING":
            logger.info("Task %s is still processing", task_id)
            raise HTTPException(status_code=202, detail="Task is still processing")
        else:
            logger.info("Task %s status: %s", task_id, task_result.state)
            raise HTTPException(status_code=202, detail=f"Task status: {task_result.state}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get task result for %s", task_id)
        raise HTTPException(status_code=500, detail=f"Failed to get task result: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 