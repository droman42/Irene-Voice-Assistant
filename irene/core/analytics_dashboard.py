"""
Analytics Dashboard Interface - Phase 3.2 Implementation

Provides a simple web-based dashboard for monitoring fire-and-forget
action metrics, system performance, and error analysis.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
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
        Get comprehensive dashboard data with caching - Phase 3: Enhanced with all unified metrics.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            Dashboard data dictionary with VAD, intent, component, and system metrics
        """
        import time
        
        # Check cache validity
        if not force_refresh and self._dashboard_data_cache and time.time() < self._cache_expiry:
            return self._dashboard_data_cache
        
        if not self.metrics_collector:
            return self._get_empty_dashboard_data()
        
        try:
            # Get base dashboard data from metrics collector
            dashboard_data = self.metrics_collector.get_dashboard_data()
            
            # Phase 3: Add comprehensive unified metrics
            # 1. Intent Analytics (Phase 2 integration)
            intent_analytics = self.metrics_collector.get_intent_analytics()
            session_analytics = self.metrics_collector.get_session_analytics()
            
            # 2. VAD Performance Metrics (Phase 1 integration)  
            vad_metrics = self.metrics_collector.get_vad_metrics()
            vad_advanced_metrics = self.metrics_collector.get_vad_advanced_metrics()
            
            # 3. Component Health Metrics (Phase 1 integration)
            component_metrics = self.metrics_collector.get_all_component_metrics()
            
            # 4. Cross-System Correlation Analysis
            correlation_analysis = self._generate_correlation_analysis(
                intent_analytics, vad_metrics, component_metrics
            )
            
            # Enhance dashboard data with unified metrics
            dashboard_data.update({
                # Phase 2: Intent analytics integration
                "intent_analytics": intent_analytics,
                "session_analytics": session_analytics,
                
                # Phase 1: VAD metrics integration
                "vad_metrics": vad_metrics,
                "vad_advanced_metrics": vad_advanced_metrics,
                
                # Phase 1: Component metrics integration  
                "component_metrics": component_metrics,
                
                # Phase 3: Cross-system insights
                "correlation_analysis": correlation_analysis,
                
                # Enhanced dashboard metadata
                "dashboard_info": {
                    "generated_at": datetime.now().isoformat(),
                    "cache_duration": self._cache_duration,
                    "data_source": "Unified MetricsCollector",
                    "metrics_included": ["system", "domain", "intent", "session", "vad", "component"],
                    "phase3_enhanced": True
                }
            })
            
            # Cache the enhanced data
            self._dashboard_data_cache = dashboard_data
            self._cache_expiry = time.time() + self._cache_duration
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate enhanced dashboard data: {e}")
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
    
    def validate_system_performance(self) -> Dict[str, Any]:
        """
        Phase 3: Validate unified metrics system performance impact.
        
        Returns:
            Performance validation report
        """
        try:
            validation_start = time.time()
            
            # Collect performance metrics
            system_metrics = self.metrics_collector.get_system_metrics() if self.metrics_collector else {}
            vad_metrics = self.metrics_collector.get_vad_metrics() if self.metrics_collector else {}
            component_metrics = self.metrics_collector.get_all_component_metrics() if self.metrics_collector else {}
            
            validation_duration = time.time() - validation_start
            
            # Performance analysis
            performance_analysis = {
                "metrics_collection_overhead": validation_duration * 1000,  # ms
                "vad_performance": self._analyze_vad_performance(vad_metrics),
                "intent_performance": self._analyze_intent_performance(),
                "component_performance": self._analyze_component_performance(component_metrics),
                "system_health": self._analyze_system_health(system_metrics),
                "validation_timestamp": datetime.now().isoformat()
            }
            
            # Calculate overall performance score
            performance_score = self._calculate_performance_score(performance_analysis)
            
            # Generate performance recommendations
            recommendations = self._generate_performance_recommendations(performance_analysis)
            
            return {
                "performance_score": performance_score,
                "performance_analysis": performance_analysis,
                "recommendations": recommendations,
                "validation_criteria": {
                    "metrics_overhead_threshold_ms": 5.0,  # Should be < 5ms
                    "vad_processing_threshold_ms": 50.0,   # Should be < 50ms
                    "success_rate_threshold": 0.95,        # Should be > 95%
                    "cache_hit_threshold": 0.5             # Should be > 50%
                },
                "meets_criteria": performance_score >= 0.8,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Performance validation failed: {e}")
            return {
                "performance_score": 0.0,
                "error": str(e),
                "meets_criteria": False,
                "generated_at": datetime.now().isoformat()
            }
    
    def _analyze_vad_performance(self, vad_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze VAD performance metrics"""
        processing_time = vad_metrics.get("average_processing_time_ms", 0.0)
        cache_hit_rate = vad_metrics.get("cache_hit_rate", 0.0)
        chunks_processed = vad_metrics.get("total_chunks_processed", 0)
        
        # Performance scoring
        time_score = max(0.0, 1.0 - (processing_time - 25.0) / 50.0)  # Good < 25ms, Poor > 75ms
        cache_score = cache_hit_rate
        throughput_score = min(1.0, chunks_processed / 1000.0)  # Good > 1000 chunks
        
        overall_score = (time_score * 0.5 + cache_score * 0.3 + throughput_score * 0.2)
        
        return {
            "processing_time_ms": processing_time,
            "cache_hit_rate": cache_hit_rate,
            "chunks_processed": chunks_processed,
            "time_score": time_score,
            "cache_score": cache_score,
            "throughput_score": throughput_score,
            "overall_score": overall_score,
            "status": "excellent" if overall_score > 0.8 else "good" if overall_score > 0.6 else "needs_attention"
        }
    
    def _analyze_intent_performance(self) -> Dict[str, Any]:
        """Analyze intent processing performance"""
        if not self.metrics_collector:
            return {"error": "No metrics collector available"}
        
        try:
            intent_analytics = self.metrics_collector.get_intent_analytics()
            overview = intent_analytics.get("overview", {})
            
            success_rate = overview.get("overall_success_rate", 0.0)
            confidence = overview.get("average_confidence", 0.0)
            total_intents = overview.get("total_intents_processed", 0)
            
            # Performance scoring
            success_score = success_rate
            confidence_score = confidence
            volume_score = min(1.0, total_intents / 100.0)  # Good > 100 intents
            
            overall_score = (success_score * 0.5 + confidence_score * 0.3 + volume_score * 0.2)
            
            return {
                "success_rate": success_rate,
                "average_confidence": confidence,
                "total_intents": total_intents,
                "success_score": success_score,
                "confidence_score": confidence_score,
                "volume_score": volume_score,
                "overall_score": overall_score,
                "status": "excellent" if overall_score > 0.8 else "good" if overall_score > 0.6 else "needs_attention"
            }
            
        except Exception as e:
            return {"error": str(e), "overall_score": 0.0}
    
    def _analyze_component_performance(self, component_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze component health and performance"""
        active_components = len([c for c in component_metrics.values() if c])
        total_components = len(component_metrics) if component_metrics else 1
        
        availability_score = active_components / total_components
        
        return {
            "active_components": active_components,
            "total_components": total_components,
            "availability_score": availability_score,
            "component_details": {name: "active" if data else "inactive" 
                                for name, data in component_metrics.items()},
            "overall_score": availability_score,
            "status": "excellent" if availability_score > 0.8 else "good" if availability_score > 0.5 else "critical"
        }
    
    def _analyze_system_health(self, system_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall system health"""
        success_rate = system_metrics.get("average_success_rate", 0.0)
        uptime = system_metrics.get("uptime_seconds", 0)
        concurrent_actions = system_metrics.get("current_concurrent_actions", 0)
        total_completed = system_metrics.get("total_actions_completed", 0)
        
        # Health scoring
        success_score = success_rate
        uptime_score = min(1.0, uptime / 86400.0)  # Max score after 24h
        load_score = 1.0 - min(1.0, concurrent_actions / 50.0)  # Penalize > 50 concurrent
        volume_score = min(1.0, total_completed / 1000.0)  # Good > 1000 actions
        
        overall_score = (success_score * 0.4 + uptime_score * 0.2 + load_score * 0.2 + volume_score * 0.2)
        
        return {
            "success_rate": success_rate,
            "uptime_hours": uptime / 3600.0,
            "concurrent_actions": concurrent_actions,
            "total_completed": total_completed,
            "success_score": success_score,
            "uptime_score": uptime_score,
            "load_score": load_score,
            "volume_score": volume_score,
            "overall_score": overall_score,
            "status": "excellent" if overall_score > 0.8 else "good" if overall_score > 0.6 else "degraded"
        }
    
    def _calculate_performance_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall performance score (0.0-1.0)"""
        scores = []
        
        # Metrics collection overhead (20% weight)
        overhead_ms = analysis.get("metrics_collection_overhead", 0)
        overhead_score = max(0.0, 1.0 - (overhead_ms - 1.0) / 10.0)  # Good < 1ms, Poor > 11ms
        scores.append(("overhead", overhead_score, 0.2))
        
        # VAD performance (30% weight)
        vad_score = analysis.get("vad_performance", {}).get("overall_score", 0.0)
        scores.append(("vad", vad_score, 0.3))
        
        # Intent performance (25% weight)
        intent_score = analysis.get("intent_performance", {}).get("overall_score", 0.0)
        scores.append(("intent", intent_score, 0.25))
        
        # Component performance (15% weight)
        component_score = analysis.get("component_performance", {}).get("overall_score", 0.0)
        scores.append(("component", component_score, 0.15))
        
        # System health (10% weight)
        system_score = analysis.get("system_health", {}).get("overall_score", 0.0)
        scores.append(("system", system_score, 0.1))
        
        # Calculate weighted score
        weighted_score = sum(score * weight for _, score, weight in scores)
        return min(1.0, max(0.0, weighted_score))
    
    def _generate_performance_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate performance improvement recommendations"""
        recommendations = []
        
        # Metrics overhead check
        overhead = analysis.get("metrics_collection_overhead", 0)
        if overhead > 5.0:
            recommendations.append({
                "category": "metrics_overhead",
                "priority": "high",
                "message": f"Metrics collection overhead is {overhead:.1f}ms (target: <5ms)",
                "recommendation": "Consider reducing metrics collection frequency or optimizing data structures"
            })
        
        # VAD performance check
        vad_perf = analysis.get("vad_performance", {})
        if vad_perf.get("processing_time_ms", 0) > 50.0:
            recommendations.append({
                "category": "vad_performance",
                "priority": "medium",
                "message": f"VAD processing time is {vad_perf.get('processing_time_ms', 0):.1f}ms (target: <50ms)",
                "recommendation": "Optimize VAD algorithms or increase cache size"
            })
        
        # Cache efficiency check
        if vad_perf.get("cache_hit_rate", 0) < 0.5:
            recommendations.append({
                "category": "cache_efficiency",
                "priority": "medium",
                "message": f"VAD cache hit rate is {vad_perf.get('cache_hit_rate', 0):.1%} (target: >50%)",
                "recommendation": "Increase cache size or improve cache algorithms"
            })
        
        # Intent success rate check
        intent_perf = analysis.get("intent_performance", {})
        if intent_perf.get("success_rate", 0) < 0.95:
            recommendations.append({
                "category": "intent_accuracy",
                "priority": "high",
                "message": f"Intent success rate is {intent_perf.get('success_rate', 0):.1%} (target: >95%)",
                "recommendation": "Review NLU model training or intent handler implementations"
            })
        
        # Component availability check
        component_perf = analysis.get("component_performance", {})
        if component_perf.get("availability_score", 0) < 0.8:
            recommendations.append({
                "category": "component_health",
                "priority": "high",
                "message": f"Component availability is {component_perf.get('availability_score', 0):.1%} (target: >80%)",
                "recommendation": "Investigate inactive components and ensure proper initialization"
            })
        
        # Default recommendation if no issues
        if not recommendations:
            recommendations.append({
                "category": "system_health",
                "priority": "info",
                "message": "System performance is within acceptable parameters",
                "recommendation": "Continue monitoring and maintain current optimization levels"
            })
        
        return recommendations
    
    def generate_html_dashboard(self) -> str:
        """Generate enhanced HTML dashboard with unified metrics - Phase 3 implementation"""
        dashboard_data = self.get_dashboard_data()
        health_summary = self.get_system_health_summary()
        
        # Enhanced HTML template with unified metrics
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Irene Unified Analytics Dashboard - Phase 3</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
                .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
                .card { background: white; padding: 24px; margin: 16px 0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                .header { text-align: center; color: white; margin-bottom: 20px; }
                .header h1 { font-size: 2.5em; margin: 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
                .phase-badge { background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px; color: white; font-size: 0.9em; margin-top: 10px; }
                .status-excellent { color: #28a745; }
                .status-good { color: #17a2b8; }
                .status-fair { color: #ffc107; }
                .status-poor { color: #fd7e14; }
                .status-critical { color: #dc3545; }
                .metric { display: inline-block; margin: 10px 20px; text-align: center; }
                .metric-value { font-size: 2.2em; font-weight: bold; }
                .metric-label { font-size: 0.9em; color: #666; margin-top: 8px; }
                .table { width: 100%; border-collapse: collapse; margin-top: 16px; }
                .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
                .table th { background-color: #f8f9fa; font-weight: 600; }
                .table tr:hover { background-color: #f5f5f5; }
                .refresh-info { text-align: center; color: rgba(255,255,255,0.8); font-size: 0.9em; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
                .health-score { font-size: 3em; font-weight: bold; text-align: center; margin: 20px 0; }
                .insight { padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #007bff; background: #f8f9fa; }
                .insight.warning { border-color: #ffc107; background: #fff8e1; }
                .insight.error { border-color: #dc3545; background: #ffebee; }
                .insight.optimization { border-color: #28a745; background: #e8f5e9; }
                .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
                .correlation-section { background: linear-gradient(45deg, #f8f9fa, #e9ecef); padding: 20px; border-radius: 8px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 Irene Unified Analytics Dashboard</h1>
                    <div class="phase-badge">Phase 3: Complete Metrics Integration</div>
                    <p class="refresh-info">Generated: {generated_at} | Health Score: {health_score:.1%} | Auto-refresh: 30s</p>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h2>🎯 System Health Overview</h2>
                        <div class="health-score status-{health_status}">{health_score:.1%}</div>
                        <div class="metric-grid">
                            <div class="metric">
                                <div class="metric-value status-{health_status}">{health_status_display}</div>
                                <div class="metric-label">Status</div>
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
                    </div>
                    
                    <div class="card">
                        <h2>🧠 Intent Analytics</h2>
                        <div class="metric-grid">
                            <div class="metric">
                                <div class="metric-value">{total_intents}</div>
                                <div class="metric-label">Total Intents</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">{intent_success_rate:.1%}</div>
                                <div class="metric-label">Intent Success</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">{intent_confidence:.2f}</div>
                                <div class="metric-label">Avg Confidence</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">{unique_intents}</div>
                                <div class="metric-label">Intent Types</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h2>🔊 VAD Performance</h2>
                        <table class="table">
                            <tr><th>Metric</th><th>Value</th></tr>
                            <tr><td>Chunks Processed</td><td>{vad_chunks:,}</td></tr>
                            <tr><td>Voice Segments</td><td>{vad_voice_segments:,}</td></tr>
                            <tr><td>Avg Processing Time</td><td>{vad_processing_time:.1f}ms</td></tr>
                            <tr><td>Cache Hit Rate</td><td>{vad_cache_rate:.1%}</td></tr>
                            <tr><td>Buffer Overflows</td><td>{vad_overflows}</td></tr>
                        </table>
                    </div>
                    
                    <div class="card">
                        <h2>💬 Session Analytics</h2>
                        <table class="table">
                            <tr><th>Metric</th><th>Value</th></tr>
                            <tr><td>Active Sessions</td><td>{active_sessions}</td></tr>
                            <tr><td>Total Sessions</td><td>{total_sessions}</td></tr>
                            <tr><td>Avg Session Duration</td><td>{avg_session_duration:.1f}s</td></tr>
                            <tr><td>Avg Intents/Session</td><td>{avg_intents_per_session:.1f}</td></tr>
                            <tr><td>User Satisfaction</td><td>{user_satisfaction:.1%}</td></tr>
                        </table>
                    </div>
                </div>
                
                <div class="card">
                    <h2>⚙️ Component Health</h2>
                    <table class="table">
                        <tr><th>Component</th><th>Status</th><th>Key Metrics</th></tr>
                        {component_rows}
                    </table>
                </div>
                
                <div class="card">
                    <h2>📊 Cross-System Correlation Analysis</h2>
                    <div class="correlation-section">
                        <h3>Performance Indicators</h3>
                        <div class="metric-grid">
                            <div class="metric">
                                <div class="metric-value">{correlation_efficiency:.3f}</div>
                                <div class="metric-label">System Efficiency</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">{vad_processing_time:.1f}ms</div>
                                <div class="metric-label">VAD Impact</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">{vad_cache_rate:.1%}</div>
                                <div class="metric-label">Cache Efficiency</div>
                            </div>
                        </div>
                        
                        <h3>System Insights</h3>
                        {correlation_insights}
                    </div>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h2>📈 Performance Summary</h2>
                        <table class="table">
                            <tr><th>Metric</th><th>Value</th></tr>
                            <tr><td>Total Actions</td><td>{total_actions:,}</td></tr>
                            <tr><td>Successful Actions</td><td>{successful_actions:,}</td></tr>
                            <tr><td>Failed Actions</td><td>{failed_actions:,}</td></tr>
                            <tr><td>Average Duration</td><td>{avg_duration:.2f}s</td></tr>
                            <tr><td>Peak Concurrent</td><td>{peak_concurrent}</td></tr>
                        </table>
                    </div>
                    
                    <div class="card">
                        <h2>⚠️ Recent Issues</h2>
                        {error_info}
                    </div>
                </div>
                
                <div class="card">
                    <h2>🏷️ Domain Breakdown</h2>
                    <table class="table">
                        <tr><th>Domain</th><th>Actions</th><th>Success Rate</th><th>Avg Duration</th><th>Error Rate</th></tr>
                        {domain_rows}
                    </table>
                </div>
            </div>
            
            <script>
                // Enhanced auto-refresh with fade transition
                function refreshDashboard() {{
                    document.body.style.opacity = '0.8';
                    setTimeout(function() {{ location.reload(); }}, 1000);
                }}
                setTimeout(refreshDashboard, 30000);
                
                // Add loading animation
                window.addEventListener('beforeunload', function() {{
                    document.body.style.opacity = '0.5';
                }});
            </script>
        </body>
        </html>
        """
        
        # Prepare template variables - Phase 3 enhanced
        system_metrics = dashboard_data.get("system_metrics", {})
        performance = dashboard_data.get("performance_summary", {})
        domain_metrics = dashboard_data.get("domain_metrics", {})
        error_analysis = dashboard_data.get("error_analysis", {})
        
        # Phase 3: Extract unified metrics
        intent_analytics = dashboard_data.get("intent_analytics", {})
        session_analytics = dashboard_data.get("session_analytics", {})
        vad_metrics = dashboard_data.get("vad_metrics", {})
        component_metrics = dashboard_data.get("component_metrics", {})
        correlation_analysis = dashboard_data.get("correlation_analysis", {})
        
        # Enhanced domain rows with error rates
        domain_rows = ""
        for domain, metrics in domain_metrics.items():
            error_rate = getattr(metrics, 'error_rate', 0.0) if hasattr(metrics, 'error_rate') else 0.0
            domain_rows += f"""
                <tr>
                    <td>{domain}</td>
                    <td>{metrics.get('total_actions', 0):,}</td>
                    <td>{metrics.get('success_rate', 0.0):.1%}</td>
                    <td>{metrics.get('average_duration', 0.0):.2f}s</td>
                    <td>{error_rate:.1%}</td>
                </tr>
            """
        
        # Component health rows
        component_rows = ""
        for component_name, component_data in component_metrics.items():
            status = "🟢 Active" if component_data else "🔴 Inactive"
            key_metrics = "N/A"
            if isinstance(component_data, dict):
                if 'resampling_operations' in str(component_data):
                    key_metrics = "Resampling active"
                elif 'detection_operations' in str(component_data):
                    key_metrics = "Detection active"
                else:
                    key_metrics = f"{len(component_data)} metrics"
            
            component_rows += f"""
                <tr>
                    <td>{component_name}</td>
                    <td>{status}</td>
                    <td>{key_metrics}</td>
                </tr>
            """
        
        # Correlation insights
        insights = correlation_analysis.get("insights", [])
        correlation_insights = ""
        if insights:
            for insight in insights[:5]:  # Top 5 insights
                insight_type = insight.get("type", "info")
                correlation_insights += f"""
                    <div class="insight {insight_type}">
                        <strong>{insight.get('correlation', 'System').title()}:</strong> 
                        {insight.get('message', 'No details available')}
                        <br><em>Recommendation: {insight.get('recommendation', 'Monitor system')}</em>
                    </div>
                """
        else:
            correlation_insights = "<p>No correlation insights available yet. System is learning...</p>"
        
        # Enhanced error info
        error_info = f"<p>Recent failures: {error_analysis.get('total_recent_failures', 0)}</p>"
        if error_analysis.get('most_common_errors'):
            error_info += "<ul>"
            for error_type, info in error_analysis['most_common_errors'][:3]:
                error_info += f"<li><strong>{error_type}</strong>: {info['count']} occurrences</li>"
            error_info += "</ul>"
        else:
            error_info += "<p style='color: #28a745;'>✅ No recent errors detected</p>"
        
        # Health score calculation
        health_score = correlation_analysis.get("health_score", health_summary.get("success_rate", 0.0))
        
        # Fill enhanced template with all unified metrics
        return html_template.format(
            # Basic info
            generated_at=dashboard_data.get("dashboard_info", {}).get("generated_at", "Unknown"),
            health_score=health_score,
            health_status=health_summary.get("status", "unknown"),
            health_status_display=health_summary.get("status", "unknown").title(),
            success_rate=health_summary.get("success_rate", 0.0),
            active_actions=health_summary.get("active_actions", 0),
            uptime_hours=health_summary.get("uptime_hours", 0.0),
            
            # Performance metrics
            total_actions=performance.get("total_actions", 0),
            successful_actions=performance.get("successful_actions", 0),
            failed_actions=performance.get("failed_actions", 0),
            avg_duration=performance.get("average_duration", 0.0),
            peak_concurrent=system_metrics.get("peak_concurrent_actions", 0),
            
            # Intent analytics
            total_intents=intent_analytics.get("overview", {}).get("total_intents_processed", 0),
            intent_success_rate=intent_analytics.get("overview", {}).get("overall_success_rate", 0.0),
            intent_confidence=intent_analytics.get("overview", {}).get("average_confidence", 0.0),
            unique_intents=intent_analytics.get("overview", {}).get("unique_intent_types", 0),
            
            # VAD metrics
            vad_chunks=vad_metrics.get("total_chunks_processed", 0),
            vad_voice_segments=vad_metrics.get("voice_segments_detected", 0),
            vad_processing_time=vad_metrics.get("average_processing_time_ms", 0.0),
            vad_cache_rate=vad_metrics.get("cache_hit_rate", 0.0),
            vad_overflows=vad_metrics.get("buffer_overflow_count", 0),
            
            # Session analytics
            active_sessions=session_analytics.get("overview", {}).get("active_sessions", 0),
            total_sessions=session_analytics.get("overview", {}).get("total_sessions", 0),
            avg_session_duration=session_analytics.get("overview", {}).get("average_session_duration", 0.0),
            avg_intents_per_session=session_analytics.get("overview", {}).get("average_intents_per_session", 0.0),
            user_satisfaction=session_analytics.get("overview", {}).get("average_user_satisfaction", 0.8),
            
            # Correlation analysis
            correlation_efficiency=correlation_analysis.get("correlation_summary", {}).get("system_efficiency", 0.0),
            correlation_insights=correlation_insights,
            
            # Tables
            domain_rows=domain_rows,
            component_rows=component_rows,
            error_info=error_info
        )
    
    def _generate_correlation_analysis(self, intent_analytics: Dict[str, Any], 
                                      vad_metrics: Dict[str, Any], 
                                      component_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate cross-system correlation analysis - Phase 3 enhancement.
        
        Args:
            intent_analytics: Intent recognition and execution analytics
            vad_metrics: VAD performance metrics
            component_metrics: Component health metrics
            
        Returns:
            Cross-system correlation insights
        """
        try:
            insights = []
            performance_indicators = {}
            
            # 1. Intent Recognition vs VAD Performance Correlation
            intent_success_rate = intent_analytics.get("overview", {}).get("overall_success_rate", 0.0)
            vad_processing_time = vad_metrics.get("average_processing_time_ms", 0.0)
            vad_voice_detection = vad_metrics.get("voice_segments_detected", 0)
            
            if vad_processing_time > 50.0 and intent_success_rate < 0.8:
                insights.append({
                    "type": "warning",
                    "correlation": "vad_intent_performance",
                    "message": f"High VAD processing time ({vad_processing_time:.1f}ms) may be affecting intent recognition",
                    "recommendation": "Consider VAD optimization or threshold tuning"
                })
            
            # 2. Component Health vs System Performance
            asr_metrics = component_metrics.get("asr", {})
            voice_trigger_metrics = component_metrics.get("voice_trigger", {})
            
            if asr_metrics and "resampling_operations" in str(asr_metrics):
                performance_indicators["asr_health"] = "active"
            if voice_trigger_metrics:
                performance_indicators["voice_trigger_health"] = "active"
            
            # 3. Session Duration vs Intent Success Rate
            session_overview = intent_analytics.get("overview", {})
            avg_confidence = session_overview.get("average_confidence", 0.0)
            
            if avg_confidence < 0.7 and intent_success_rate < 0.8:
                insights.append({
                    "type": "info",
                    "correlation": "confidence_success",
                    "message": f"Low average confidence ({avg_confidence:.2f}) correlates with lower success rate",
                    "recommendation": "Review NLU model training or threshold settings"
                })
            
            # 4. VAD Cache Performance Impact
            cache_hit_rate = vad_metrics.get("cache_hit_rate", 0.0)
            if cache_hit_rate < 0.5 and vad_processing_time > 30.0:
                insights.append({
                    "type": "optimization",
                    "correlation": "cache_performance",
                    "message": f"Low VAD cache hit rate ({cache_hit_rate:.1%}) affecting processing time",
                    "recommendation": "Consider increasing cache size or improving cache algorithms"
                })
            
            # 5. Overall System Health Correlation
            total_intents = intent_analytics.get("overview", {}).get("total_intents_processed", 0)
            vad_chunks = vad_metrics.get("total_chunks_processed", 0)
            
            if total_intents > 0 and vad_chunks > 0:
                intent_to_chunk_ratio = total_intents / vad_chunks
                performance_indicators["intent_efficiency"] = intent_to_chunk_ratio
                
                if intent_to_chunk_ratio < 0.01:  # Less than 1% of chunks result in intents
                    insights.append({
                        "type": "efficiency",
                        "correlation": "processing_efficiency", 
                        "message": f"Low intent-to-chunk ratio ({intent_to_chunk_ratio:.3f}) suggests processing inefficiency",
                        "recommendation": "Review wake word sensitivity or voice activity detection thresholds"
                    })
            
            return {
                "insights": insights,
                "performance_indicators": performance_indicators,
                "correlation_summary": {
                    "vad_performance_impact": vad_processing_time,
                    "intent_success_correlation": intent_success_rate,
                    "cache_efficiency": cache_hit_rate,
                    "system_efficiency": performance_indicators.get("intent_efficiency", 0.0)
                },
                "health_score": self._calculate_health_score(intent_analytics, vad_metrics, component_metrics),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate correlation analysis: {e}")
            return {
                "insights": [],
                "performance_indicators": {},
                "correlation_summary": {},
                "health_score": 0.0,
                "error": str(e)
            }
    
    def _calculate_health_score(self, intent_analytics: Dict[str, Any], 
                               vad_metrics: Dict[str, Any],
                               component_metrics: Dict[str, Any]) -> float:
        """Calculate overall system health score (0.0-1.0) based on all metrics"""
        try:
            scores = []
            
            # Intent performance score (40% weight)
            intent_success_rate = intent_analytics.get("overview", {}).get("overall_success_rate", 0.0)
            intent_confidence = intent_analytics.get("overview", {}).get("average_confidence", 0.0)
            intent_score = (intent_success_rate * 0.7 + intent_confidence * 0.3)
            scores.append(("intent", intent_score, 0.4))
            
            # VAD performance score (30% weight)
            vad_processing_time = vad_metrics.get("average_processing_time_ms", 0.0)
            vad_cache_rate = vad_metrics.get("cache_hit_rate", 0.0)
            # Normalize processing time (good < 25ms, poor > 100ms)
            vad_time_score = max(0.0, 1.0 - (vad_processing_time - 25.0) / 75.0)
            vad_score = (vad_time_score * 0.6 + vad_cache_rate * 0.4)
            scores.append(("vad", vad_score, 0.3))
            
            # Component health score (20% weight)
            component_score = 1.0 if component_metrics else 0.5  # Basic availability check
            scores.append(("component", component_score, 0.2))
            
            # System stability score (10% weight)
            uptime_seconds = self.metrics_collector.get_system_metrics().get("uptime_seconds", 0)
            stability_score = min(1.0, uptime_seconds / 86400.0)  # Max score after 24h uptime
            scores.append(("stability", stability_score, 0.1))
            
            # Calculate weighted average
            weighted_score = sum(score * weight for _, score, weight in scores)
            return min(1.0, max(0.0, weighted_score))
            
        except Exception as e:
            self.logger.error(f"Failed to calculate health score: {e}")
            return 0.5  # Default neutral score
    
    def _get_empty_dashboard_data(self) -> Dict[str, Any]:
        """Get empty dashboard data structure - Phase 3 enhanced"""
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
            # Phase 3: Enhanced empty data structure
            "intent_analytics": {"overview": {"total_intents_processed": 0, "overall_success_rate": 0.0}},
            "session_analytics": {"overview": {"active_sessions": 0, "total_sessions": 0}},
            "vad_metrics": {"total_chunks_processed": 0, "average_processing_time_ms": 0.0},
            "component_metrics": {},
            "correlation_analysis": {"insights": [], "health_score": 0.0},
            "dashboard_info": {
                "generated_at": datetime.now().isoformat(),
                "data_source": "Empty (no metrics collector)",
                "phase3_enhanced": True
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
