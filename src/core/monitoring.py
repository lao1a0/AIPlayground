from datetime import datetime, timedelta
from typing import Dict, Any, List

from .statistics import StatisticsStorage, ReviewStatistics


class MonitoringService:
    """监控服务 - 提供统计分析功能"""
    
    def __init__(self, storage: StatisticsStorage = None):
        self.storage = storage or StatisticsStorage()
    
    def record_review(self, project_id: int, mr_iid: int, file_path: str, 
                     file_extension: str, review_status: str, model_used: str,
                     tokens_used: int = 0, issues_count: int = 0) -> int:
        """记录一次代码审查"""
        record = ReviewStatistics(
            id=None,
            project_id=project_id,
            mr_iid=mr_iid,
            file_path=file_path,
            file_extension=file_extension,
            review_status=review_status,
            model_used=model_used,
            tokens_used=tokens_used,
            issues_count=issues_count,
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        return self.storage.save_review_record(record)
    
    def get_dashboard_data(self, project_id: int = None, days: int = 30) -> Dict[str, Any]:
        """获取仪表板数据"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 时间趋势数据
        trend_data = self.storage.get_statistics_by_date_range(start_date, end_date)
        
        # 模型使用统计
        model_stats = self.storage.get_model_usage_stats(days)
        
        # 文件类型统计
        file_type_stats = self.storage.get_file_type_stats(days)
        
        # 项目摘要
        if project_id:
            project_summary = self.storage.get_project_summary(project_id, days)
        else:
            project_summary = {}
        
        # 最近活动
        recent_activity = self.storage.get_recent_activity(limit=10)
        
        return {
            'trend': trend_data,
            'models': model_stats,
            'file_types': file_type_stats,
            'project_summary': project_summary,
            'recent_activity': recent_activity,
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'days': days
            }
        }
    
    def calculate_success_rate(self, days: int = 7) -> float:
        """计算审查成功率"""
        stats = self.storage.get_model_usage_stats(days)
        
        total_count = sum(item['usage_count'] for item in stats)
        if total_count == 0:
            return 0.0
        
        # 假设所有记录都是成功的（失败的需要标记为 failed）
        successful_count = sum(
            item['usage_count'] for item in stats 
            if item.get('avg_issues', 0) >= 0  # 简单判断
        )
        
        return (successful_count / total_count) * 100
    
    def get_average_response_time(self, days: int = 7) -> float:
        """获取平均响应时间（需要实际实现时间追踪）"""
        # 这个需要扩展数据模型来记录开始和结束时间
        # 暂时返回一个估算值
        return 2.5  # 秒
    
    def generate_report(self, project_id: int, format: str = 'markdown', days: int = 30) -> str:
        """生成审查报告"""
        data = self.get_dashboard_data(project_id, days)
        
        if format == 'markdown':
            return self._generate_markdown_report(data, project_id, days)
        elif format == 'json':
            import json
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_markdown_report(self, data: Dict[str, Any], project_id: int, days: int) -> str:
        """生成 Markdown 格式报告"""
        report = f"""# 代码审查统计报告

**项目 ID**: {project_id}  
**统计周期**: {data['period']['start']} 至 {data['period']['end']} ({days}天)  
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 总体概览

"""
        
        summary = data.get('project_summary', {})
        if summary:
            report += f"""
- **审查的 MR 数量**: {summary.get('total_mrs', 0)}
- **审查的文件总数**: {summary.get('total_files', 0)}
- **成功审查数**: {summary.get('successful_reviews', 0)}
- **总 Token 消耗**: {summary.get('total_tokens', 0)}
- **平均每文件问题数**: {summary.get('avg_issues_per_file', 0):.2f}
- **涉及的不同文件数**: {summary.get('unique_files', 0)}
"""
        else:
            report += "*暂无数据*\n"
        
        # 模型使用情况
        report += "\n## 🤖 模型使用情况\n\n"
        if data['models']:
            report += "| 模型 | 使用次数 | 总 Token | 平均 Token | 平均问题数 |\n"
            report += "|------|---------|---------|-----------|-----------|\n"
            for model in data['models']:
                report += f"| {model['model_used']} | {model['usage_count']} | {model['total_tokens']} | {model['avg_tokens']:.1f} | {model['avg_issues']:.2f} |\n"
        else:
            report += "*暂无数据*\n"
        
        # 文件类型分布
        report += "\n## 📁 文件类型分布\n\n"
        if data['file_types']:
            report += "| 文件类型 | 审查次数 | 平均问题数 | 成功率 |\n"
            report += "|---------|---------|-----------|-------|\n"
            for file_type in data['file_types']:
                report += f"| {file_type['file_extension']} | {file_type['review_count']} | {file_type['avg_issues']:.2f} | {file_type['success_rate']:.1f}% |\n"
        else:
            report += "*暂无数据*\n"
        
        # 最近活动
        report += "\n## 🔔 最近活动\n\n"
        if data['recent_activity']:
            for i, activity in enumerate(data['recent_activity'][:5], 1):
                status_emoji = "✅" if activity['review_status'] == 'success' else "❌"
                report += f"{i}. **MR #{activity['mr_iid']}** - `{activity['file_path']}` {status_emoji}\n"
                report += f"   - 模型：{activity['model_used']} | 问题数：{activity['issues_count']}\n"
                report += f"   - 时间：{activity['created_at']}\n\n"
        else:
            report += "*暂无活动记录*\n"
        
        return report
