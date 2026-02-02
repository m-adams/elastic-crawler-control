"""
Health check endpoint.

Provides service health status for monitoring and load balancers.
"""

from typing import Dict

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> Dict[str, str]:
    """
    Service health check.
    
    Returns:
        Health status with service name and version
    """
    return {
        "status": "healthy", 
        "service": "crawly", 
        "version": "1.1.0"  # Bumped for config generator features
    }
