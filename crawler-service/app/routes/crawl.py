"""
Crawl management endpoints.

Handles crawl job lifecycle: trigger, status, cancel, list, logs.
"""

import datetime
import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

import db
from crawler import run_crawler_process
from models import CrawlConfig, CrawlStatus

router = APIRouter(prefix="/api", tags=["crawl"])

# Store active processes (shared across requests)
active_processes: Dict[str, Any] = {}


@router.post("/crawl")
async def trigger_crawl(
    config: CrawlConfig,
    background_tasks: BackgroundTasks,
    async_mode: bool = True,
) -> Dict[str, Any]:
    """
    Start a new crawl job.
    
    Args:
        config: Crawl configuration (domains, output_index, rules, etc.)
        async_mode: If True (default), run crawl in background
        
    Returns:
        Initial CrawlStatus with execution_id
    """
    crawl_config = config.model_dump(exclude_none=True)
    execution_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat()

    es_host = crawl_config.pop("elasticsearch_url", None) or os.environ.get("ES_URL")
    es_api_key = crawl_config.pop("elasticsearch_api_key", None) or os.environ.get("ES_API_KEY")

    print(f"Starting crawl with execution ID: {execution_id}. Output ES: {es_host}")
    
    initial_status = CrawlStatus(
        status="started",
        execution_id=execution_id,
        started_at=started_at,
        message="Crawl queued for execution",
    )
    
    db.create_crawl(execution_id, CrawlConfig(**crawl_config), initial_status)

    if async_mode:
        background_tasks.add_task(
            run_crawler_process, 
            execution_id, 
            crawl_config, 
            es_host, 
            es_api_key, 
            active_processes
        )
        return initial_status.model_dump()
    else:
        result = run_crawler_process(
            execution_id, 
            crawl_config, 
            es_host, 
            es_api_key, 
            active_processes
        )
        return result


@router.get("/status/{execution_id}")
async def check_status(execution_id: str) -> Dict[str, Any]:
    """
    Get crawl status by execution ID.
    
    Args:
        execution_id: UUID of the crawl execution
        
    Returns:
        Complete CrawlStatus with config, stats, and result
    """
    status = db.get_crawl_status(execution_id)
    
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Execution {execution_id} not found"
        )
    
    return status.model_dump()


@router.post("/cancel/{execution_id}")
async def cancel_crawl(execution_id: str) -> Dict[str, Any]:
    """
    Cancel a running crawl.
    
    Args:
        execution_id: UUID of the crawl execution to cancel
        
    Returns:
        Updated CrawlStatus with cancelled state
    """
    if not db.crawl_exists(execution_id):
        raise HTTPException(
            status_code=404,
            detail=f"Execution {execution_id} not found"
        )

    process = active_processes.get(execution_id)
    message = ""
    
    if process and process.poll() is None:
        process.kill()
        process.wait()
        message = "Crawl has been cancelled"
        del active_processes[execution_id]
    else:
        message = "Crawl already completed or not running"
    
    status = db.get_crawl_status(execution_id)
    if status:
        status.status = "cancelled"
        status.message = message
        db.update_status(execution_id, status)
        return status.model_dump()
    
    return {"status": "cancelled", "message": message}


@router.get("/crawls")
async def list_crawls() -> Dict[str, Any]:
    """
    List all crawls.
    
    Returns:
        Dictionary with total count and all crawl statuses
    """
    crawls = db.list_all_crawls()
    crawls_data = {exec_id: status.model_dump() for exec_id, status in crawls.items()}
    return {
        "total": len(crawls_data),
        "crawls": crawls_data
    }


@router.get("/logs/{execution_id}")
async def get_logs_endpoint(execution_id: str) -> Response:
    """
    Get crawler logs for an execution.
    
    Args:
        execution_id: UUID of the crawl execution
        
    Returns:
        Plain text log content
    """
    content = db.get_logs(execution_id)
    
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=f"Log file for execution {execution_id} not found"
        )
    
    return Response(content=content, media_type="text/plain")


@router.get("/info/{execution_id}")
async def get_info(execution_id: str) -> Dict[str, Any]:
    """
    Get complete crawl information (raw JSON from info.json).
    
    Args:
        execution_id: UUID of the crawl execution
        
    Returns:
        Raw crawl info dictionary
    """
    info = db.get_crawl_info(execution_id)
    
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Info file for execution {execution_id} not found"
        )
    
    return info
