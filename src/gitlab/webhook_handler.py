import os
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .code_reviewer import GitLabCodeReviewer
from ..core.base import BaseLLM
from ..models.deepseek_llm import DeepSeekLLM
from ..models.kimi_llm import KimiLLM
from ..models.openai_llm import OpenAILLM
from ..core.monitoring import MonitoringService
from ..core.statistics import StatisticsStorage

app = FastAPI()

# CORS 设置
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
    allow_headers=["*"], )

# 配置
GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_TOKEN = os.getenv("GITLAB_API_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
MODEL_TYPE = os.getenv("REVIEW_MODEL")  # 默认使用 kimi


def init_llm(model_type: str = MODEL_TYPE) -> BaseLLM:
    """初始化 LLM 模型"""
    if model_type == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        return DeepSeekLLM(api_key=api_key)
    elif model_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        return OpenAILLM(api_key=api_key)
    elif model_type == "kimi":
        api_key = os.getenv("KIMI_API_KEY")
        if not api_key:
            raise ValueError("KIMI_API_KEY not found in environment variables")
        return KimiLLM(api_key=api_key)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")


# 初始化 LLM
llm = init_llm()

# 初始化监控服务
monitoring_service = MonitoringService()


@app.post("/webhook/gitlab")
async def handle_webhook(request: Request):
    # 验证 Webhook 签名
    signature = request.headers.get("X-Gitlab-Token")
    if not signature or signature != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()

    # 只处理合并请求事件
    if payload.get("object_kind") != "merge_request":
        return {"status": "ignored"}

    # 只在开启合并请求时进行审查
    if payload.get("object_attributes", {}).get("action") != "open":
        return {"status": "ignored"}

    try:
        project_id = payload["project"]["id"]
        mr_iid = payload["object_attributes"]["iid"]

        # 初始化代码审查器
        reviewer = GitLabCodeReviewer(gitlab_url=GITLAB_URL, private_token=GITLAB_TOKEN, project_id=project_id, llm=llm)

        # 执行代码审查
        await reviewer.review_merge_request(mr_iid)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 监控和统计 API ====================

@app.get("/api/monitoring/dashboard")
async def get_dashboard_data(
    project_id: int = Query(None, description="项目 ID"),
    days: int = Query(30, description="统计天数")
):
    """获取仪表板数据"""
    try:
        data = monitoring_service.get_dashboard_data(project_id, days)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitoring/report")
async def get_monitoring_report(
    project_id: int = Query(..., description="项目 ID"),
    format: str = Query("markdown", description="报告格式：markdown 或 json"),
    days: int = Query(30, description="统计天数")
):
    """获取审查报告"""
    try:
        report = monitoring_service.generate_report(project_id, format, days)
        
        if format == "json":
            from fastapi.responses import JSONResponse
            import json
            return JSONResponse(content=json.loads(report))
        else:
            return HTMLResponse(content=report, media_type="text/markdown")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitoring/metrics")
async def get_metrics(days: int = Query(7, description="统计天数")):
    """获取关键指标"""
    try:
        success_rate = monitoring_service.calculate_success_rate(days)
        avg_response_time = monitoring_service.get_average_response_time(days)
        
        return {
            "success": True,
            "data": {
                "success_rate": success_rate,
                "avg_response_time": avg_response_time,
                "period_days": days
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitoring/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """监控仪表板页面"""
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>代码审查监控仪表板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .metric-card h3 {
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        .metric-card .value {
            font-size: 2.5em;
            font-weight: bold;
        }
        .chart-container {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .chart-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .activity-list {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
        }
        .activity-item {
            padding: 15px;
            background: white;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        .activity-item.success { border-left-color: #28a745; }
        .activity-item.failed { border-left-color: #dc3545; }
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 1.2em;
            color: #666;
        }
        .controls {
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
        }
        select, button {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            background: #667eea;
            color: white;
            cursor: pointer;
            font-size: 1em;
        }
        button:hover {
            background: #5568d3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 代码审查监控仪表板</h1>
        <p class="subtitle">实时监控代码审查活动与质量指标</p>
        
        <div class="controls">
            <label>统计周期：</label>
            <select id="daysSelect" onchange="loadDashboard()">
                <option value="7">最近 7 天</option>
                <option value="30" selected>最近 30 天</option>
                <option value="90">最近 90 天</option>
            </select>
            <button onclick="loadDashboard()">🔄 刷新</button>
            <button onclick="exportReport()">📄 导出报告</button>
        </div>
        
        <div id="dashboard">
            <div class="loading">正在加载数据...</div>
        </div>
    </div>

    <script>
        let dashboardData = null;
        
        async function loadDashboard() {
            const days = document.getElementById('daysSelect').value;
            try {
                const response = await fetch(`/api/monitoring/dashboard?days=${days}`);
                const result = await response.json();
                
                if (result.success) {
                    dashboardData = result.data;
                    renderDashboard();
                }
            } catch (error) {
                console.error('加载失败:', error);
                document.getElementById('dashboard').innerHTML = 
                    '<div class="loading">加载失败，请重试</div>';
            }
        }
        
        function renderDashboard() {
            if (!dashboardData) return;
            
            const html = `
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>总审查次数</h3>
                        <div class="value">${dashboardData.project_summary.total_files || 0}</div>
                    </div>
                    <div class="metric-card">
                        <h3>MR 数量</h3>
                        <div class="value">${dashboardData.project_summary.total_mrs || 0}</div>
                    </div>
                    <div class="metric-card">
                        <h3>平均问题数/文件</h3>
                        <div class="value">${(dashboardData.project_summary.avg_issues_per_file || 0).toFixed(2)}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Token 消耗</h3>
                        <div class="value">${(dashboardData.project_summary.total_tokens || 0).toLocaleString()}</div>
                    </div>
                </div>
                
                <div class="chart-row">
                    <div class="chart-container">
                        <canvas id="trendChart"></canvas>
                    </div>
                    <div class="chart-container">
                        <canvas id="modelChart"></canvas>
                    </div>
                </div>
                
                <div class="chart-row">
                    <div class="chart-container">
                        <canvas id="fileTypeChart"></canvas>
                    </div>
                    <div class="activity-list">
                        <h3 style="margin-bottom: 15px;">🔔 最近活动</h3>
                        ${renderActivityList()}
                    </div>
                </div>
            `;
            
            document.getElementById('dashboard').innerHTML = html;
            
            // 渲染图表
            renderCharts();
        }
        
        function renderActivityList() {
            if (!dashboardData.recent_activity || dashboardData.recent_activity.length === 0) {
                return '<p style="color: #999;">暂无活动记录</p>';
            }
            
            return dashboardData.recent_activity.map(activity => `
                <div class="activity-item ${activity.review_status === 'success' ? 'success' : 'failed'}">
                    <strong>MR #${activity.mr_iid}</strong> - ${activity.file_path}<br>
                    <small>模型：${activity.model_used} | 问题：${activity.issues_count} | ${activity.created_at}</small>
                </div>
            `).join('');
        }
        
        function renderCharts() {
            // 趋势图
            const trendCtx = document.getElementById('trendChart').getContext('2d');
            new Chart(trendCtx, {
                type: 'line',
                data: {
                    labels: dashboardData.trend.map(d => d.date),
                    datasets: [{
                        label: '审查次数',
                        data: dashboardData.trend.map(d => d.total_reviews),
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: '审查趋势'
                        }
                    }
                }
            });
            
            // 模型使用图
            const modelCtx = document.getElementById('modelChart').getContext('2d');
            new Chart(modelCtx, {
                type: 'bar',
                data: {
                    labels: dashboardData.models.map(m => m.model_used),
                    datasets: [{
                        label: '使用次数',
                        data: dashboardData.models.map(m => m.usage_count),
                        backgroundColor: ['#667eea', '#764ba2', '#f093fb']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: '模型使用情况'
                        }
                    }
                }
            });
            
            // 文件类型图
            const fileTypeCtx = document.getElementById('fileTypeChart').getContext('2d');
            new Chart(fileTypeCtx, {
                type: 'doughnut',
                data: {
                    labels: dashboardData.file_types.map(f => f.file_extension),
                    datasets: [{
                        data: dashboardData.file_types.map(f => f.review_count),
                        backgroundColor: ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: '文件类型分布'
                        }
                    }
                }
            });
        }
        
        function exportReport() {
            const days = document.getElementById('daysSelect').value;
            window.open(`/api/monitoring/report?project_id=1&format=markdown&days=${days}`, '_blank');
        }
        
        // 初始加载
        loadDashboard();
    </script>
</body>
</html>
    """
    return html_content
