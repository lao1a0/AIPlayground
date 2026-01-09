import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .code_reviewer import GitLabCodeReviewer
from ..core.base import BaseLLM
from ..models.deepseek_llm import DeepSeekLLM
from ..models.kimi_llm import KimiLLM
from ..models.openai_llm import OpenAILLM
from ..config.settings import OPENAI_API_KEY, DEEPSEEK_API_KEY, KIMI_API_KEY

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
MODEL_TYPE = os.getenv("MODEL_TYPE", "kimi")  # 默认使用 kimi

# 全局 LLM 实例
llm: BaseLLM = None


def init_llm(model_type: str = MODEL_TYPE) -> BaseLLM:
    """初始化 LLM 模型"""
    global llm
    if llm is not None:
        return llm

    if model_type == "deepseek":
        api_key = DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        llm = DeepSeekLLM(api_key=api_key)
    elif model_type == "openai":
        api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        llm = OpenAILLM(api_key=api_key)
    elif model_type == "kimi":
        api_key = KIMI_API_KEY or os.getenv("KIMI_API_KEY")
        if not api_key:
            raise ValueError("KIMI_API_KEY not found in environment variables")
        llm = KimiLLM(api_key=api_key)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")
    return llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时验证配置
    required_vars = ["GITLAB_URL", "GITLAB_TOKEN", "WEBHOOK_SECRET"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    # 初始化 LLM
    try:
        init_llm()
        logger.info(f"Initialized LLM with model type: {MODEL_TYPE}")
    except ValueError as e:
        logger.error(f"Failed to initialize LLM: {e}")
        raise

    yield

    # 清理资源（如果需要）
    logger.info("Shutting down application")


app = FastAPI(lifespan=lifespan)

# CORS 设置 - 限制为 GitLab 相关域名（如果已知）
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["POST"],
    allow_headers=["*"], )


@app.post("/webhook/gitlab")
async def handle_webhook(request: Request):
    logger.info("Received webhook request")

    # 验证 Webhook 签名
    signature = request.headers.get("X-Gitlab-Token")
    if not signature or signature != WEBHOOK_SECRET:
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 只处理合并请求事件
    object_kind = payload.get("object_kind")
    if object_kind != "merge_request":
        logger.info(f"Ignored event type: {object_kind}")
        return {"status": "ignored", "reason": "not a merge request event"}

    # 获取合并请求属性
    object_attributes = payload.get("object_attributes", {})
    action = object_attributes.get("action")

    # 只在开启或更新合并请求时进行审查
    if action not in ["open", "update"]:
        logger.info(f"Ignored merge request action: {action}")
        return {"status": "ignored", "reason": f"action '{action}' not supported"}

    # 提取必要信息
    try:
        project_id = payload["project"]["id"]
        mr_iid = object_attributes["iid"]
    except KeyError as e:
        logger.error(f"Missing required payload field: {e}")
        raise HTTPException(status_code=400, detail=f"Missing required field: {e}")

    try:
        # 初始化代码审查器
        reviewer = GitLabCodeReviewer(
            gitlab_url=GITLAB_URL,
            private_token=GITLAB_TOKEN,
            project_id=project_id,
            llm=llm
        )

        logger.info(f"Starting code review for project {project_id}, MR {mr_iid}")

        # 执行代码审查
        await reviewer.review_merge_request(mr_iid)

        logger.info(f"Code review completed for project {project_id}, MR {mr_iid}")
        return {"status": "success", "project_id": project_id, "mr_iid": mr_iid}

    except Exception as e:
        logger.error(f"Error during code review: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Code review failed: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "model_type": MODEL_TYPE}
