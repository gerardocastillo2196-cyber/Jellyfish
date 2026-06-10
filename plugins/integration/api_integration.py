"""
Jellyfish OS v6 - API Integration Plugin
Integrates with external APIs and services
"""

import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from urllib.parse import urljoin

from plugins.plugin_core import PluginInterface, PluginMetadata

class APIEndpoint:
    """Represents a single API endpoint"""
    
    def __init__(
        self,
        name: str,
        method: str,
        path: str,
        handler: Callable,
        auth_required: bool = True,
        rate_limit: Optional[int] = None
    ):
        self.name = name
        self.method = method.upper()
        self.path = path
        self.handler = handler
        self.auth_required = auth_required
        self.rate_limit = rate_limit
        self.call_count = 0
        self.last_called: Optional[datetime] = None

class APIRouter:
    """Simple API router for agent services"""
    
    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.middleware: List[Callable] = []
    
    def register(
        self,
        path: str,
        method: str = "GET",
        auth_required: bool = True,
        rate_limit: Optional[int] = None
    ):
        """Decorator to register an endpoint"""
        def decorator(func: Callable) -> Callable:
            endpoint = APIEndpoint(
                name=func.__name__,
                method=method,
                path=urljoin(self.base_url, path),
                handler=func,
                auth_required=auth_required,
                rate_limit=rate_limit
            )
            self.endpoints[f"{method}:{path}"] = endpoint
            return func
        return decorator
    
    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware function"""
        self.middleware.append(middleware)
    
    def route(self, path: str, method: str = "GET") -> Optional[APIEndpoint]:
        """Find endpoint for path and method"""
        key = f"{method.upper()}:{path}"
        return self.endpoints.get(key)

class APIIntegrationPlugin(PluginInterface):
    """Plugin for API integrations and service orchestration"""
    
    PLUGIN_METADATA = PluginMetadata(
        name="api-integration",
        version="1.0.0",
        description="Integrate with external APIs and services",
        author="Jellyfish OS Team",
        capabilities=[
            "api_routing",
            "service_configuration",
            "auth_management",
            "rate_limiting",
            "usage_tracking"
        ]
    )
    
    def __init__(self):
        super().__init__()
        self.routers: Dict[str, APIRouter] = {}
        self.api_keys: Dict[str, str] = {}
        self.service_configs: Dict[str, Dict] = {}
        self.call_logs: List[Dict] = []
    
    def create_router(self, name: str, base_url: str = "") -> APIRouter:
        """Create a new API router"""
        router = APIRouter(base_url)
        self.routers[name] = router
        return router
    
    def configure_service(
        self,
        service_name: str,
        base_url: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> None:
        """Configure an external service"""
        self.service_configs[service_name] = {
            "base_url": base_url,
            "api_key": api_key,
            "headers": headers or {},
            "configured_at": datetime.now().isoformat()
        }
        
        if api_key:
            self.api_keys[service_name] = api_key
    
    def get_headers(self, service_name: str) -> Dict[str, str]:
        """Get headers for a service including auth"""
        config = self.service_configs.get(service_name, {})
        headers = config.get("headers", {}).copy()
        
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        
        return headers
    
    def log_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """Log an API call"""
        self.call_logs.append({
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_usage_stats(self, service: Optional[str] = None) -> Dict:
        """Get API usage statistics"""
        logs = self.call_logs
        if service:
            logs = [l for l in logs if l["service"] == service]
        
        if not logs:
            return {"total_calls": 0}
        
        total_calls = len(logs)
        avg_duration = sum(l["duration_ms"] for l in logs) / total_calls
        status_codes = {}
        
        for log in logs:
            code = log["status_code"]
            status_codes[code] = status_codes.get(code, 0) + 1
        
        return {
            "total_calls": total_calls,
            "average_duration_ms": round(avg_duration, 2),
            "status_codes": status_codes,
            "last_call": logs[-1]["timestamp"] if logs else None
        }

# Module-level metadata for package import compatibility
PLUGIN_METADATA = {
    "name": "api-integration",
    "version": "1.0.0",
    "description": "Integrate with external APIs and services",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "api_routing",
        "service_configuration",
        "auth_management",
        "rate_limiting",
        "usage_tracking"
    ]
}