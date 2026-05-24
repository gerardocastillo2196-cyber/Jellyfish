"""
Jellyfish OS v6 - Output Formatter Plugin
Formats agent outputs to various structured formats
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime

class OutputFormatter:
    """Plugin to format agent outputs in various structured formats"""
    
    @staticmethod
    def to_markdown_table(data: List[Dict], headers: Optional[List[str]] = None) -> str:
        """Convert list of dicts to markdown table"""
        if not data:
            return "No data to display"
        
        # Auto-generate headers if not provided
        if headers is None:
            headers = list(data[0].keys())
        
        # Header row
        table = "| " + " | ".join(headers) + " |\n"
        table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        
        # Data rows
        for row in data:
            values = [str(row.get(h, "")) for h in headers]
            table += "| " + " | ".join(values) + " |\n"
        
        return table
    
    @staticmethod
    def to_json(data: Any, indent: int = 2) -> str:
        """Format data as JSON"""
        return json.dumps(data, indent=indent, ensure_ascii=False)
    
    @staticmethod
    def to_structured_text(data: Dict, prefix: str = "") -> str:
        """Format data as structured text with indentation"""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(OutputFormatter.to_structured_text(value, prefix + "  "))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)
    
    @staticmethod
    def to_csv(data: List[Dict]) -> str:
        """Convert data to CSV format"""
        if not data:
            return ""
        
        headers = list(data[0].keys())
        lines = [",".join(headers)]
        
        for row in data:
            values = []
            for h in headers:
                val = str(row.get(h, "")).replace('"', '""')
                values.append(f'"{val}"')
            lines.append(",".join(values))
        
        return "\n".join(lines)
    
    @staticmethod
    def format_response(
        content: str,
        format_type: str = "markdown",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Format a complete response with metadata"""
        return {
            "content": content,
            "format": format_type,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }

# Plugin metadata
PLUGIN_METADATA = {
    "name": "output-formatter",
    "version": "1.0.0",
    "description": "Format agent outputs to various structured formats",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "markdown_table",
        "json_format",
        "csv_format",
        "structured_text"
    ]
}