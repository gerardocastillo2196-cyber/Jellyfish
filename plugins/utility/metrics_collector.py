"""
Jellyfish OS v6 - Metrics Collector Plugin
Collects and aggregates metrics from agent activities
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

class MetricBucket:
    """Container for time-bucketed metrics"""
    
    def __init__(self, interval: str = "hour"):
        self.interval = interval
        self.data: List[Dict] = []
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
    
    def increment(self, metric: str, value: float = 1.0) -> None:
        """Increment a counter metric"""
        self.counters[metric] += value
    
    def set_gauge(self, metric: str, value: float) -> None:
        """Set a gauge metric"""
        self.gauges[metric] = value
    
    def record_histogram(self, metric: str, value: float) -> None:
        """Record a histogram value"""
        self.histograms[metric].append(value)
    
    def get_summary(self, metric: str) -> Optional[Dict]:
        """Get summary statistics for a histogram"""
        if metric not in self.histograms:
            return None
        
        values = self.histograms[metric]
        if not values:
            return None
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(sorted_values),
            "p95": sorted_values[int(n * 0.95)] if n > 1 else sorted_values[0],
            "p99": sorted_values[int(n * 0.99)] if n > 1 else sorted_values[0]
        }

class MetricsCollectorPlugin:
    """Plugin to collect and analyze agent metrics"""
    
    def __init__(self):
        self.buckets: Dict[str, MetricBucket] = {}
        self.current_bucket: Optional[MetricBucket] = None
        self.agent_sessions: Dict[str, Dict] = {}
        self.skill_usage: Dict[str, int] = defaultdict(int)
        self.task_metrics: Dict[str, Dict] = {}
    
    def _get_bucket_key(self, timestamp: datetime) -> str:
        """Generate bucket key based on interval"""
        return timestamp.strftime("%Y%m%d%H")
    
    def _get_or_create_bucket(self, timestamp: datetime) -> MetricBucket:
        """Get or create a metric bucket"""
        key = self._get_bucket_key(timestamp)
        
        if key not in self.buckets:
            self.buckets[key] = MetricBucket()
        
        return self.buckets[key]
    
    def record_metric(
        self,
        metric_type: str,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Record a metric value"""
        ts = timestamp or datetime.now()
        bucket = self._get_or_create_bucket(ts)
        
        if metric_type == "counter":
            bucket.increment(metric_name, value)
        elif metric_type == "gauge":
            bucket.set_gauge(metric_name, value)
        elif metric_type == "histogram":
            bucket.record_histogram(metric_name, value)
    
    def start_agent_session(self, agent_id: str, context: Dict = None) -> None:
        """Start tracking an agent session"""
        self.agent_sessions[agent_id] = {
            "started_at": datetime.now(),
            "context": context or {},
            "interactions": 0,
            "tokens_used": 0,
            "skills_used": []
        }
    
    def end_agent_session(self, agent_id: str) -> Optional[Dict]:
        """End an agent session and return metrics"""
        session = self.agent_sessions.get(agent_id)
        if not session:
            return None
        
        session["ended_at"] = datetime.now()
        session["duration_seconds"] = (
            session["ended_at"] - session["started_at"]
        ).total_seconds()
        
        self.record_metric("histogram", "session_duration", session["duration_seconds"])
        self.record_metric("counter", "total_sessions", 1)
        
        return session
    
    def record_interaction(self, agent_id: str) -> None:
        """Record an agent interaction"""
        if agent_id in self.agent_sessions:
            self.agent_sessions[agent_id]["interactions"] += 1
    
    def record_skill_usage(self, skill_name: str) -> None:
        """Record skill usage"""
        self.skill_usage[skill_name] += 1
        self.record_metric("counter", f"skill_{skill_name}", 1)
    
    def get_metrics_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """Get aggregated metrics summary"""
        start = start_time or datetime.now() - timedelta(days=1)
        end = end_time or datetime.now()
        
        # Filter buckets in time range
        relevant_buckets = [
            b for key, b in self.buckets.items()
            if start <= datetime.strptime(key, "%Y%m%d%H") <= end
        ]
        
        if not relevant_buckets:
            return {"message": "No metrics in time range"}
        
        # Aggregate counters
        aggregated_counters = defaultdict(float)
        for bucket in relevant_buckets:
            for metric, value in bucket.counters.items():
                aggregated_counters[metric] += value
        
        # Aggregate histograms
        aggregated_histograms = defaultdict(list)
        for bucket in relevant_buckets:
            for metric, values in bucket.histograms.items():
                aggregated_histograms[metric].extend(values)
        
        # Calculate histogram summaries
        histogram_summaries = {}
        for metric, values in aggregated_histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                histogram_summaries[metric] = {
                    "count": n,
                    "min": min(values),
                    "max": max(values),
                    "mean": statistics.mean(values),
                    "p95": sorted_values[int(n * 0.95)]
                }
        
        return {
            "time_range": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "counters": dict(aggregated_counters),
            "histograms": histogram_summaries,
            "top_skills": sorted(
                self.skill_usage.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def get_agent_performance(self, agent_id: str) -> Optional[Dict]:
        """Get performance metrics for a specific agent"""
        session = self.agent_sessions.get(agent_id)
        if not session:
            return None
        
        return {
            "agent_id": agent_id,
            "interactions": session["interactions"],
            "skills_used": session["skills_used"],
            "tokens_used": session.get("tokens_used", 0),
            "session_duration": session.get("duration_seconds", 0),
            "efficiency": session["interactions"] / max(session.get("duration_seconds", 1), 1) * 60
        }

# Plugin metadata
PLUGIN_METADATA = {
    "name": "metrics-collector",
    "version": "1.0.0",
    "description": "Collect and analyze agent activity metrics",
    "author": "Jellyfish OS Team",
    "capabilities": [
        "metric_recording",
        "session_tracking",
        "skill_usage_tracking",
        "performance_analytics"
    ]
}