"""
Jellyfish OS v6 - Plugin Framework
Core plugin system for Jellyfish OS v6 agents
"""

from typing import Dict, List, Optional, Any, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime
import importlib
import pkgutil

@dataclass
class PluginMetadata:
    """Metadata for a plugin"""
    name: str
    version: str
    description: str
    author: str
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    loaded_at: Optional[datetime] = None

class PluginInterface:
    """Base interface for all plugins"""
    
    PLUGIN_METADATA: PluginMetadata
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration"""
        pass
    
    def execute(self, method: str, *args, **kwargs) -> Any:
        """Execute a plugin method"""
        if hasattr(self, method):
            return getattr(self, method)(*args, **kwargs)
        raise AttributeError(f"Plugin has no method '{method}'")
    
    def shutdown(self) -> None:
        """Clean up plugin resources"""
        pass

class PluginRegistry:
    """Central registry for all plugins"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.plugins: Dict[str, PluginInterface] = {}
            self.metadata: Dict[str, PluginMetadata] = {}
            self.hooks: Dict[str, List[Callable]] = {}
            self._initialized = True
    
    def register(self, plugin: PluginInterface) -> bool:
        """Register a plugin"""
        metadata = getattr(plugin, 'PLUGIN_METADATA', None)
        if not metadata:
            return False
        
        self.plugins[metadata.name] = plugin
        self.metadata[metadata.name] = metadata
        metadata.loaded_at = datetime.now()
        
        return True
    
    def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin"""
        if plugin_name not in self.plugins:
            return False
        
        plugin = self.plugins[plugin_name]
        plugin.shutdown()
        del self.plugins[plugin_name]
        del self.metadata[plugin_name]
        
        return True
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a plugin by name"""
        return self.plugins.get(plugin_name)
    
    def get_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """Get plugin metadata"""
        return self.metadata.get(plugin_name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugin names"""
        return list(self.plugins.keys())
    
    def has_capability(self, capability: str) -> List[str]:
        """Find plugins with a specific capability"""
        return [
            name for name, meta in self.metadata.items()
            if capability in meta.capabilities
        ]
    
    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a hook callback"""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)
    
    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Trigger all callbacks for a hook"""
        results = []
        for callback in self.hooks.get(hook_name, []):
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        return results
    
    def load_plugins_from_package(self, package_name: str) -> int:
        """Auto-discover and load plugins from a package"""
        try:
            package = importlib.import_module(package_name)
            discovered = 0
            
            for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
                if is_pkg:
                    continue
                
                module_name = f"{package_name}.{name}"
                try:
                    module = importlib.import_module(module_name)
                    
                    # Look for plugin classes
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type) and
                            issubclass(attr, PluginInterface) and
                            attr != PluginInterface
                        ):
                            plugin = attr()
                            if self.register(plugin):
                                discovered += 1
                
                except Exception as e:
                    print(f"Error loading module {module_name}: {e}")
            
            return discovered
        
        except Exception as e:
            print(f"Error loading package {package_name}: {e}")
            return 0

class PluginManager:
    """High-level plugin management facade"""
    
    def __init__(self):
        self.registry = PluginRegistry()
    
    def install_plugin(self, plugin: PluginInterface, config: Dict = None) -> bool:
        """Install and initialize a plugin"""
        if not self.registry.register(plugin):
            return False
        
        try:
            plugin.initialize(config or {})
            return True
        except Exception as e:
            self.registry.unregister(
                getattr(plugin, 'PLUGIN_METADATA', None).name
            )
            raise e
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """Uninstall a plugin"""
        return self.registry.unregister(plugin_name)
    
    def execute_plugin(
        self,
        plugin_name: str,
        method: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute a method on a plugin"""
        plugin = self.registry.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")
        
        return plugin.execute(method, *args, **kwargs)
    
    def get_status_report(self) -> Dict:
        """Get overall plugin system status"""
        plugins_info = []
        
        for name, meta in self.registry.metadata.items():
            plugins_info.append({
                "name": name,
                "version": meta.version,
                "capabilities": meta.capabilities,
                "loaded_at": meta.loaded_at.isoformat() if meta.loaded_at else None
            })
        
        return {
            "total_plugins": len(plugins_info),
            "plugins": plugins_info,
            "hooks_registered": len(self.registry.hooks)
        }

# Plugin system metadata
PLUGIN_SYSTEM_METADATA = {
    "version": "1.0.0",
    "name": "jellyfish-plugin-system",
    "description": "Core plugin framework for Jellyfish OS v6"
}

# Export main classes
__all__ = [
    "PluginInterface",
    "PluginMetadata",
    "PluginRegistry",
    "PluginManager",
    "PLUGIN_SYSTEM_METADATA"
]