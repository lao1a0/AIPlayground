# 统计和监控功能使用指南

## 📊 功能概述

新增了完整的代码审查统计和监控功能，帮助您了解：
- 代码审查活动趋势
- LLM 模型使用情况
- 文件类型分布
- 审查质量和成功率
- Token 消耗统计

## 🚀 快速开始

### 1. 启动服务

```bash
# 启动 Webhook 服务（包含监控 API）
python main.py
```

### 2. 访问监控仪表板

在浏览器中打开：
```
http://localhost:8000/monitoring/dashboard
```

您将看到可视化的监控仪表板，包含：
- 📈 关键指标卡片
- 📊 审查趋势图表
- 🤖 模型使用分布
- 📁 文件类型统计
- 🔔 最近活动列表

### 3. 查看统计数据

#### 方式一：命令行查看
```bash
python examples/view_statistics.py
```

#### 方式二：API 调用

**获取仪表板数据：**
```bash
curl "http://localhost:8000/api/monitoring/dashboard?days=30"
```

**获取 Markdown 报告：**
```bash
curl "http://localhost:8000/api/monitoring/report?project_id=1&format=markdown&days=30"
```

**获取 JSON 格式报告：**
```bash
curl "http://localhost:8000/api/monitoring/report?project_id=1&format=json&days=30"
```

**获取关键指标：**
```bash
curl "http://localhost:8000/api/monitoring/metrics?days=7"
```

## 📋 API 接口说明

### GET `/api/monitoring/dashboard`
获取仪表板完整数据

**参数：**
- `project_id` (可选): 项目 ID
- `days` (可选，默认 30): 统计天数

**返回示例：**
```json
{
  "success": true,
  "data": {
    "trend": [...],
    "models": [...],
    "file_types": [...],
    "project_summary": {...},
    "recent_activity": [...]
  }
}
```

### GET `/api/monitoring/report`
生成审查报告

**参数：**
- `project_id` (必填): 项目 ID
- `format` (可选): `markdown` 或 `json`
- `days` (可选，默认 30): 统计天数

### GET `/api/monitoring/metrics`
获取关键性能指标

**参数：**
- `days` (可选，默认 7): 统计天数

**返回：**
```json
{
  "success": true,
  "data": {
    "success_rate": 95.5,
    "avg_response_time": 2.5,
    "period_days": 7
  }
}
```

### GET `/monitoring/dashboard`
可视化监控仪表板页面（HTML）

## 💾 数据存储

统计数据自动保存在 SQLite 数据库中：
- **数据库文件**: `review_statistics.db`（自动创建）
- **表名**: `review_statistics`
- **记录字段**:
  - `id`: 主键
  - `project_id`: 项目 ID
  - `mr_iid`: Merge Request ID
  - `file_path`: 文件路径
  - `file_extension`: 文件扩展名
  - `review_status`: 审查状态（success/failed/skipped）
  - `model_used`: 使用的模型
  - `tokens_used`: Token 消耗量
  - `issues_count`: 发现的问题数量
  - `created_at`: 创建时间

## 🔍 统计维度

### 1. 时间趋势分析
- 每日审查次数
- 成功率趋势
- Token 消耗趋势
- 平均问题数趋势

### 2. 模型使用统计
- 各模型使用频率
- Token 消耗对比
- 发现问题能力对比
- 成本效益分析

### 3. 文件类型分析
- 不同语言/文件类型的审查分布
- 各类文件的问题密度
- 审查成功率对比

### 4. 项目级汇总
- MR 总数
- 涉及文件数
- 总体质量指标
- 资源消耗统计

## 📊 仪表板功能

### 核心特性

1. **实时数据刷新**
   - 点击刷新按钮立即更新
   - 可选择统计周期（7/30/90 天）

2. **可视化图表**
   - 折线图：展示审查趋势
   - 柱状图：模型使用对比
   - 饼图：文件类型分布

3. **导出报告**
   - 一键导出 Markdown 格式报告
   - 支持自定义统计周期

4. **响应式设计**
   - 适配桌面和移动设备
   - 美观的渐变 UI 设计

## 🔧 集成到现有流程

### 自动记录机制

每次代码审查都会自动记录统计数据：
- ✅ 成功审查 → `review_status='success'`
- ❌ 审查失败 → `review_status='failed'`
- ⏭️ 跳过文件 → `review_status='skipped'`

### 估算指标

系统会自动估算：
- **Token 使用量**: 基于字符数计算（字符数/4）
- **问题数量**: 通过识别评论中的问题标识符

## 📝 使用示例

### Python 代码调用

```python
from src.core.monitoring import MonitoringService

# 初始化服务
monitoring = MonitoringService()

# 获取最近 30 天数据
data = monitoring.get_dashboard_data(days=30)

# 生成报告
report = monitoring.generate_report(
    project_id=1,
    format='markdown',
    days=30
)

print(report)
```

### 自定义查询

```python
from src.core.statistics import StatisticsStorage

storage = StatisticsStorage()

# 查询特定日期范围
stats = storage.get_statistics_by_date_range(
    start_date=datetime(2024, 1, 1),
    end_date=datetime.now()
)

# 查询模型使用情况
model_stats = storage.get_model_usage_stats(days=7)

# 查询文件类型分布
file_stats = storage.get_file_type_stats(days=30)
```

## 🎯 最佳实践

### 1. 定期查看仪表板
- 每天检查最近的审查活动
- 每周分析趋势变化
- 每月生成完整报告

### 2. 优化模型选择
根据统计数据选择最适合的模型：
- **高频使用** → 考虑成本效益
- **高问题发现率** → 保证审查质量
- **低 Token 消耗** → 控制成本

### 3. 识别瓶颈
通过文件类型统计：
- 找出问题最多的文件类型
- 针对性改进代码质量
- 调整审查策略

### 4. 团队协作
- 分享监控仪表板链接
- 定期导出报告给团队
- 在技术会议中讨论趋势

## 🐛 故障排查

### 数据库不存在
系统会自动创建数据库文件，确保运行目录有写权限。

### 数据为空
- 确认已经执行过代码审查
- 检查项目 ID 是否正确
- 确认统计周期内有数据

### API 返回错误
- 检查服务是否正常运行
- 验证参数格式是否正确
- 查看服务器日志获取详细错误信息

## 🔮 未来扩展

当前版本已实现基础统计功能，未来可扩展：
- [ ] 实时告警通知
- [ ] 多维度数据对比
- [ ] 自定义报表生成
- [ ] 数据导出（CSV、Excel）
- [ ] 用户权限管理
- [ ] 更多图表类型
- [ ] 数据保留策略

## 📞 技术支持

如有问题，请查看：
- 项目文档
- API 日志
- 数据库文件状态

---

**最后更新**: 2026-03-12  
**版本**: v1.0.0
