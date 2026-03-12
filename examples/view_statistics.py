"""
示例：查看代码审查统计数据
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.monitoring import MonitoringService
from src.core.statistics import StatisticsStorage


def main():
    # 初始化监控服务
    monitoring = MonitoringService()
    
    print("=" * 60)
    print("📊 代码审查统计仪表板")
    print("=" * 60)
    
    # 获取最近 30 天的数据
    dashboard_data = monitoring.get_dashboard_data(days=30)
    
    print(f"\n统计周期：{dashboard_data['period']['start']} 至 {dashboard_data['period']['end']}")
    
    # 显示项目摘要
    summary = dashboard_data.get('project_summary', {})
    if summary:
        print("\n📈 总体指标:")
        print(f"  - 审查的 MR 数量：{summary.get('total_mrs', 0)}")
        print(f"  - 审查的文件总数：{summary.get('total_files', 0)}")
        print(f"  - 成功审查数：{summary.get('successful_reviews', 0)}")
        print(f"  - 总 Token 消耗：{summary.get('total_tokens', 0):,}")
        print(f"  - 平均每文件问题数：{summary.get('avg_issues_per_file', 0):.2f}")
    
    # 显示模型使用情况
    models = dashboard_data.get('models', [])
    if models:
        print("\n🤖 模型使用情况:")
        for model in models:
            print(f"  - {model['model_used']}:")
            print(f"    使用次数：{model['usage_count']}")
            print(f"    平均 Token: {model['avg_tokens']:.1f}")
            print(f"    平均问题数：{model['avg_issues']:.2f}")
    
    # 显示文件类型分布
    file_types = dashboard_data.get('file_types', [])
    if file_types:
        print("\n📁 文件类型分布:")
        for file_type in file_types[:5]:  # 显示前 5 个
            print(f"  - {file_type['file_extension']}:")
            print(f"    审查次数：{file_type['review_count']}")
            print(f"    平均问题数：{file_type['avg_issues']:.2f}")
            print(f"    成功率：{file_type['success_rate']:.1f}%")
    
    # 显示最近活动
    activities = dashboard_data.get('recent_activity', [])
    if activities:
        print("\n🔔 最近活动:")
        for i, activity in enumerate(activities[:5], 1):
            status = "✅" if activity['review_status'] == 'success' else "❌"
            print(f"  {i}. MR #{activity['mr_iid']} - {activity['file_path']} {status}")
            print(f"     模型：{activity['model_used']} | 问题：{activity['issues_count']}")
    
    # 生成 Markdown 报告
    print("\n" + "=" * 60)
    print("📄 生成完整报告...")
    print("=" * 60)
    
    report = monitoring.generate_report(project_id=1, format='markdown', days=30)
    
    # 保存报告到文件
    report_path = "review_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 报告已保存到：{report_path}")
    print(f"\n💡 提示：访问 http://localhost:8000/monitoring/dashboard 查看可视化仪表板")
    
    return report


if __name__ == "__main__":
    main()
