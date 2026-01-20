#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 多模型统一测试脚本（重写版）
用法:
    python test_llm.py                      # 跑全部模型 + 全部用例
    python test_llm.py --model kimi         # 只跑 Kimi
    python test_llm.py --no-stream          # 关闭流式测试
    python test_llm.py --prompt "讲个笑话"  # 自定义提示语
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# 把项目根目录塞进 PATH，保证 src 下的模块一定能 import
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.exceptions import APIKeyNotFoundError
from src.models.deepseek_llm import DeepSeekLLM
from src.models.kimi_llm import KimiLLM

if TYPE_CHECKING:
    from src.core.base_llm import BaseLLM  # 假设所有 LLM 都继承自 BaseLLM

# -------------------- 配置区 -------------------- #
MODEL_MAP: dict[str, type[BaseLLM]] = {
    "kimi": KimiLLM,
    "deepseek": DeepSeekLLM,
}

DEFAULT_PROMPTS = {
    "basic": "请用简短的话介绍下你自己。",
    "creative": "写一个关于未来科技的短故事，不超过100字。",
    "stream": "请从1数到5，每个数字单独一行。",
}
# ------------------------------------------------ #

# 美化终端
custom_theme = Theme({"info": "cyan", "warning": "yellow", "error": "bold red"})
console = Console(theme=custom_theme)

# 日志
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
log = logging.getLogger("test_llm")


# -------------------- 业务逻辑 -------------------- #
async def generate_once(llm: BaseLLM, prompt: str) -> None:
    """单次非流式调用"""
    console.rule(f"[bold green]{llm.__class__.__name__} · 非流式[/]", style="info")
    try:
        response = await llm.generate(prompt)
        console.print(response)
    except APIKeyNotFoundError as e:
        log.warning("API 密钥缺失 → %s", e)
    except Exception as e:
        log.exception("生成失败 → %s", e)


async def generate_stream(llm: BaseLLM, prompt: str) -> None:
    """流式调用"""
    console.rule(f"[bold magenta]{llm.__class__.__name__} · 流式[/]", style="info")
    try:
        async for chunk in llm.stream(prompt):
            console.print(chunk, end="", style="bright_blue")
        console.print()
    except APIKeyNotFoundError as e:
        log.warning("API 密钥缺失 → %s", e)
    except Exception as e:
        log.exception("流式生成失败 → %s", e)


async def run_tests(
    models: Iterable[type[BaseLLM]],
    prompts: dict[str, str],
    *,
    skip_stream: bool = False,
) -> None:
    """执行完整测试套件"""
    for cls in models:
        llm = cls()
        await generate_once(llm, prompts["basic"])
        await generate_once(llm, prompts["creative"])
        if not skip_stream:
            await generate_stream(llm, prompts["stream"])


# -------------------- CLI 入口 -------------------- #
def main(
    model: list[str] = typer.Option(
        [], "--model", "-m", help="指定要测试的模型（可多次），默认全部"
    ),
    prompt: str = typer.Option(None, "--prompt", "-p", help="自定义流式测试提示语"),
    skip_stream: bool = typer.Option(False, "--no-stream", help="跳过流式测试"),
) -> None:
    """AI 多模型统一测试入口"""
    # 决定跑哪些模型
    if model:
        to_run = [MODEL_MAP[m] for m in model if m in MODEL_MAP]
        if not to_run:
            console.print("[error]未找到任何合法模型[/]")
            raise typer.Exit(1)
    else:
        to_run = list(MODEL_MAP.values())

    # 决定提示语
    prompts = DEFAULT_PROMPTS.copy()
    if prompt:
        prompts["stream"] = prompt

    # asyncio.run 在 3.11+ 推荐用 Runner，可自动清理未关闭资源
    if sys.version_info >= (3, 11):
        with asyncio.Runner() as runner:
            runner.run(run_tests(to_run, prompts, skip_stream=skip_stream))
    else:
        asyncio.run(run_tests(to_run, prompts, skip_stream=skip_stream))


if __name__ == "__main__":
    typer.run(main)
