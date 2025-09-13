"""
Analytics Dashboard Interface - Phase 3.2 Implementation

Provides a simple web-based dashboard for monitoring fire-and-forget
action metrics, system performance, and error analysis.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AnalyticsDashboard:
    """
    Simple analytics dashboard for monitoring system metrics.
    
    Provides both programmatic access to metrics and a basic web interface
    for real-time monitoring of fire-and-forget action performance.
    """
    
    def __init__(self, metrics_collector=None):
        self.logger = logging.getLogger(f"{__name__}.AnalyticsDashboard")
        self.metrics_collector = metrics_collector
        self._dashboard_data_cache: Optional[Dict[str, Any]] = None
        self._cache_expiry: float = 0
        self._cache_duration = 30.0  # seconds
    
    def set_metrics_collector(self, metrics_collector) -> None:
        """Set the metrics collector for data source"""
        self.metrics_collector = metrics_collector
    
    def get_dashboard_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data with caching.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            Dashboard data dictionary
        """
        import time
        
        # Check cache validity
        if not force_refresh and self._dashboard_data_cache and time.time() < self._cache_expiry:
            return self._dashboard_data_cache
        
        if not self.metrics_collector:
            return self._get_empty_dashboard_data()
        
        try:
            # Get fresh data from metrics collector
            dashboard_data = self.metrics_collector.get_dashboard_data()
            
            # Add dashboard metadata
            dashboard_data.update({
                "dashboard_info": {
                    "generated_at": datetime.now().isoformat(),
                    "cache_duration": self._cache_duration,
                    "data_source": "MetricsCollector"
                }
            })
            
            # Cache the data
            self._dashboard_data_cache = dashboard_data
            self._cache_expiry = time.time() + self._cache_duration
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate dashboard data: {e}")
            return self._get_empty_dashboard_data()
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get a concise system health summary"""
        if not self.metrics_collector:
            return {"status": "unknown", "reason": "No metrics collector available"}
        
        try:
            system_metrics = self.metrics_collector.get_system_metrics()
            active_actions = self.metrics_collector.get_active_actions_summary()
            error_analysis = self.metrics_collector.get_error_analysis()
            
            # Determine overall health status
            success_rate = system_metrics.get("average_success_rate", 0.0)
            active_count = active_actions.get("count", 0)
            recent_failures = error_analysis.get("total_recent_failures", 0)
            
            if success_rate >= 0.95 and recent_failures == 0:
                status = "excellent"
            elif success_rate >= 0.90 and recent_failures <= 2:
                status = "good"
            elif success_rate >= 0.80 and recent_failures <= 5:
                status = "fair"
            elif success_rate >= 0.70:
                status = "poor"
            else:
                status = "critical"
            
            return {
                "status": status,
                "success_rate": success_rate,
                "active_actions": active_count,
                "recent_failures": recent_failures,
                "uptime_hours": system_metrics.get("uptime_seconds", 0) / 3600,
                "total_actions": system_metrics.get("total_actions_completed", 0)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate health summary: {e}")
            return {"status": "error", "reason": str(e)}
    
    def get_performance_report(self, time_window: Optional[float] = None) -> Dict[str, Any]:
        """
        Generate a detailed performance report.
        
        Args:
            time_window: Time window in seconds (None for all history)
            
        Returns:
            Performance report dictionary
        """
        if not self.metrics_collector:
            return {"error": "No metrics collector available"}
        
        try:
            performance_summary = self.metrics_collector.get_performance_summary(time_window)
            domain_metrics = self.metrics_collector.get_all_domain_metrics()
            error_analysis = self.metrics_collector.get_error_analysis()
            
            # Generate insights
            insights = []
            
            # Performance insights
            if performance_summary["success_rate"] < 0.90:
                insights.append({
                    "type": "warning",
                    "message": f"Success rate is below 90% ({performance_summary['success_rate']:.1%})",
                    "recommendation": "Review recent failures and consider implementing additional error handling"
                })
            
            if performance_summary["average_duration"] > 30.0:
                insights.append({
                    "type": "info",
                    "message": f"Average action duration is {performance_summary['average_duration']:.1f}s",
                    "recommendation": "Consider optimizing long-running actions or adjusting timeout settings"
                })
            
            # Domain-specific insights
            for domain, metrics in domain_metrics.items():
                if metrics.error_rate > 0.20:
                    insights.append({
                        "type": "warning",
                        "message": f"Domain '{domain}' has high error rate ({metrics.error_rate:.1%})",
                        "recommendation": f"Investigate failures in {domain} domain"
                    })
            
            return {
                "time_window": time_window,
                "performance_summary": performance_summary,
                "domain_breakdown": {
                    domain: {
                        "total_actions": metrics.total_actions,
                        "success_rate": (metrics.successful_actions / metrics.total_actions) if metrics.total_actions > 0 else 0.0,
                        "average_duration": metrics.average_duration,
                        "error_rate": metrics.error_rate
                    }
                    for domain, metrics in domain_metrics.items()
                },
                "error_analysis": error_analysis,
                "insights": insights,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate performance report: {e}")
            return {"error": str(e)}
    
    def export_metrics_json(self, file_path: Optional[Path] = None) -> Path:
        """
        Export current metrics to JSON file.
        
        Args:
            file_path: Output file path (auto-generated if None)
            
        Returns:
            Path to exported file
        """
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = Path(f"metrics_export_{timestamp}.json")
        
        try:
            dashboard_data = self.get_dashboard_data(force_refresh=True)
            
            with open(file_path, 'w') as f:
                json.dump(dashboard_data, f, indent=2, default=str)
            
            self.logger.info(f"Metrics exported to: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
            raise
    
    def generate_html_dashboard(self) -> str:
        """Generate a simple HTML dashboard for web viewing"""
        dashboard_data = self.get_dashboard_data()
        health_summary = self.get_system_health_summary()
        
        # Simple HTML template
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Irene Analytics Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .header { text-align: center; color: #333; }
                .status-excellent { color: #28a745; }
                .status-good { color: #17a2b8; }
                .status-fair { color: #ffc107; }
                .status-poor { color: #fd7e14; }
                .status-critical { color: #dc3545; }
                .metric { display: inline-block; margin: 10px 20px; text-align: center; }
                .metric-value { font-size: 2em; font-weight: bold; }
                .metric-label { font-size: 0.9em; color: #666; }
                .table { width: 100%; border-collapse: collapse; }
                .table th, .table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }
                .table th { background-color: #f8f9fa; }
                .refresh-info { text-align: center; color: #666; font-size: 0.9em; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h1 class="header">🤖 Irene Analytics Dashboard</h1>
                    <p class="refresh-info">Generated: {generated_at} | Auto-refresh every 30 seconds</p>
                </div>
                
                <div class="card">
                    <h2>System Health</h2>
                    <div class="metric">
                        <div class="metric-value status-{health_status}">{health_status_display}</div>
                        <div class="metric-label">Overall Status</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{success_rate:.1%}</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{active_actions}</div>
                        <div class="metric-label">Active Actions</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{uptime_hours:.1f}h</div>
                        <div class="metric-label">Uptime</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Performance Summary</h2>
                    <table class="table">
                        <tr><th>Metric</th><th>Value</th></tr>
                        <tr><td>Total Actions</td><td>{total_actions}</td></tr>
                        <tr><td>Successful Actions</td><td>{successful_actions}</td></tr>
                        <tr><td>Failed Actions</td><td>{failed_actions}</td></tr>
                        <tr><td>Average Duration</td><td>{avg_duration:.2f}s</td></tr>
                        <tr><td>Peak Concurrent</td><td>{peak_concurrent}</td></tr>
                    </table>
                </div>
                
                <div class="card">
                    <h2>Domain Metrics</h2>
                    <table class="table">
                        <tr><th>Domain</th><th>Actions</th><th>Success Rate</th><th>Avg Duration</th></tr>
                        {domain_rows}
                    </table>
                </div>
                
                <div class="card">
                    <h2>Recent Errors</h2>
                    {error_info}
                </div>
            </div>
            
            <script>
                // Auto-refresh every 30 seconds
                setTimeout(function() {{ location.reload(); }}, 30000);
            </script>
        </body>
        </html>
        """
        
        # Prepare template variables
        system_metrics = dashboard_data.get("system_metrics", {})
        performance = dashboard_data.get("performance_summary", {})
        domain_metrics = dashboard_data.get("domain_metrics", {})
        error_analysis = dashboard_data.get("error_analysis", {})
        
        # Generate domain rows
        domain_rows = ""
        for domain, metrics in domain_metrics.items():
            domain_rows += f"""
                <tr>
                    <td>{domain}</td>
                    <td>{metrics['total_actions']}</td>
                    <td>{metrics['success_rate']:.1%}</td>
                    <td>{metrics['average_duration']:.2f}s</td>
                </tr>
            """
        
        # Generate error info
        error_info = f"<p>Recent failures: {error_analysis.get('total_recent_failures', 0)}</p>"
        if error_analysis.get('most_common_errors'):
            error_info += "<ul>"
            for error_type, info in error_analysis['most_common_errors'][:3]:
                error_info += f"<li>{error_type}: {info['count']} occurrences</li>"
            error_info += "</ul>"
        
        # Fill template
        return html_template.format(
            generated_at=dashboard_data.get("dashboard_info", {}).get("generated_at", "Unknown"),
            health_status=health_summary.get("status", "unknown"),
            health_status_display=health_summary.get("status", "unknown").title(),
            success_rate=health_summary.get("success_rate", 0.0),
            active_actions=health_summary.get("active_actions", 0),
            uptime_hours=health_summary.get("uptime_hours", 0.0),
            total_actions=performance.get("total_actions", 0),
            successful_actions=performance.get("successful_actions", 0),
            failed_actions=performance.get("failed_actions", 0),
            avg_duration=performance.get("average_duration", 0.0),
            peak_concurrent=system_metrics.get("peak_concurrent_actions", 0),
            domain_rows=domain_rows,
            error_info=error_info
        )
    
    def _get_empty_dashboard_data(self) -> Dict[str, Any]:
        """Get empty dashboard data structure"""
        return {
            "system_metrics": {
                "total_actions_started": 0,
                "total_actions_completed": 0,
                "total_actions_failed": 0,
                "average_success_rate": 0.0,
                "current_concurrent_actions": 0,
                "uptime_seconds": 0
            },
            "domain_metrics": {},
            "performance_summary": {
                "total_actions": 0,
                "success_rate": 0.0,
                "average_duration": 0.0
            },
            "active_actions": {"count": 0, "actions": []},
            "error_analysis": {"total_recent_failures": 0},
            "dashboard_info": {
                "generated_at": datetime.now().isoformat(),
                "data_source": "Empty (no metrics collector)"
            }
        }


# Global dashboard instance
_analytics_dashboard: Optional[AnalyticsDashboard] = None


def get_analytics_dashboard() -> AnalyticsDashboard:
    """Get the global analytics dashboard instance"""
    global _analytics_dashboard
    if _analytics_dashboard is None:
        _analytics_dashboard = AnalyticsDashboard()
    return _analytics_dashboard


def initialize_analytics_dashboard(metrics_collector) -> AnalyticsDashboard:
    """Initialize the global analytics dashboard"""
    dashboard = get_analytics_dashboard()
    dashboard.set_metrics_collector(metrics_collector)
    return dashboard
