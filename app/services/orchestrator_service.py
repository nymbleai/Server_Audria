import httpx
import logging
from typing import Dict, Any
from app.core.config import settings
from app.schemas.orchestrator import ProcessJsonRequest

logger = logging.getLogger(__name__)

class OrchestratorService:
    """Simple proxy service for Orchestrator API"""
    
    def __init__(self):
        self.base_url = settings.orchestrator_base_url
        self.timeout = settings.orchestrator_timeout
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # Optional API key support via env in the future
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers
    
    async def proxy_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Generic proxy method for all orchestrator requests"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                **kwargs
            )
            response.raise_for_status()
            return response.json()

# Create singleton instance
orchestrator_service = OrchestratorService()