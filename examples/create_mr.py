#!/usr/bin/env python3
"""
GitLab Merge Request Creator
一次性创建并拿到完整 MR 信息的稳健实现
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

import gitlab
from dotenv import load_dotenv
from gitlab import GitlabGetError
from gitlab.v4.objects import Project, ProjectMergeRequest

from src.config.settings import ENV_PATH

# --------------  配置  --------------
DEFAULT_TARGET = "main"  # 默认目标分支
TIMEOUT = 10  # 请求超时（秒）


# --------------  工具  --------------
def load_env() -> bool:
    """加载 .env 文件"""
    if os.path.isfile(ENV_PATH):
        load_dotenv(ENV_PATH, override=True)
        print(f"[OK] 加载环境变量：{ENV_PATH}")
        return True
    print("[WARN] 未找到 .env 文件，使用系统环境变量")
    return False


def get_gl() -> Optional[gitlab.Gitlab]:
    """拿到能用的 GitLab 客户端"""
    url = os.getenv("GITLAB_URL") or os.getenv("CI_SERVER_URL")
    token = os.getenv("GITLAB_API_TOKEN") or os.getenv("PRIVATE_TOKEN")
    if not (url and token):
        print("[ERR] 缺少 GITLAB_URL 或 GITLAB_API_TOKEN")
        return None

    try:
        gl = gitlab.Gitlab(url, private_token=token, timeout=TIMEOUT,
                           ssl_verify=os.getenv("GITLAB_SSL_VERIFY", "true").lower() != "false")
        gl.auth()  # 顺手测一把
        print(f"[OK] 连接到 GitLab：{url}")
        return gl
    except Exception as exc:
        print(f"[ERR] 连接 GitLab 失败：{exc}")
        return None


def list_projects(gl: gitlab.Gitlab) -> List[Project]:
    """拿「可见」项目列表（全量，不怕分页）"""
    try:
        return gl.projects.list(get_all=True, order_by="name", sort="asc")
    except Exception as exc:
        print(f"[ERR] 拉取项目列表失败：{exc}")
        return []


def pick_project(projects: List[Project]) -> Optional[Project]:
    """交互选项目"""
    if not projects:
        print("没有可见项目")
        return None

    for idx, p in enumerate(projects, 1):
        print(f"{idx}. {p.name}  ({p.path_with_namespace})  id={p.id}")

    while True:
        try:
            raw = input(f"请选择项目 (1-{len(projects)})，q 退出：").strip()
            if raw.lower() == "q":
                return None
            return projects[int(raw) - 1]
        except (ValueError, IndexError):
            print("输入无效，请重试")


def list_branches(project: Project) -> List[str]:
    """拿分支名列表"""
    try:
        return [b.name for b in project.branches.list(get_all=True)]
    except Exception as exc:
        print(f"[ERR] 拉取分支列表失败：{exc}")
        return []


def branch_exists(project: Project, name: str) -> bool:
    """判断分支是否存在"""
    try:
        project.branches.get(name)
        return True
    except GitlabGetError:
        return False


def create_mr(project: Project, *, source: str, target: str, title: str, description: str = "", ) -> Optional[
    ProjectMergeRequest]:
    """创建 MR 并立即重新查询，保证字段完整"""
    if not branch_exists(project, source):
        print(f"[ERR] 源分支不存在：{source}")
        return None
    if not branch_exists(project, target):
        print(f"[ERR] 目标分支不存在：{target}")
        return None

    try:
        # 1. 创建
        mr: ProjectMergeRequest = project.mergerequests.create(
            {"source_branch": source,
             "target_branch": target,
             "title": title,
             "description": description or "",
             "remove_source_branch": False, })
        # 2. 重新拉一次，保证字段齐全
        mr = project.mergerequests.get(mr.iid)
        print("[OK] MR 创建成功！")
        return mr
    except Exception as exc:
        print(f"[ERR] 创建 MR 失败：{exc}")
        return None


# --------------  交互主流程  --------------
def interactive_flow() -> None:
    if not load_env():
        return

    gl = get_gl()
    if not gl:
        sys.exit(1)

    project = pick_project(list_projects(gl))
    if not project:
        return

    branches = list_branches(project)
    if not branches:
        print("该项目下没有任何分支")
        return

    print(f"现有分支：{', '.join(branches)}")

    def _input_branch(prompt: str, default: str = "") -> str:
        while True:
            name = input(prompt).strip() or default
            if name in branches:
                return name
            print(f"分支 {name} 不存在，请重试")

    source = _input_branch("请输入源分支：")
    target = _input_branch(f"请输入目标分支 (默认 {DEFAULT_TARGET})：", DEFAULT_TARGET)
    title = input("请输入 MR 标题：").strip()
    if not title:
        print("标题不能为空")
        return
    desc = input("请输入 MR 描述（可选）：").strip()

    mr = create_mr(project, source=source, target=target, title=title, description=desc)
    if mr:
        print("\n" + "=" * 60)
        print(f"MR 已创建：{mr.web_url}")
        print(f"  IID: {mr.iid}")
        print(f"  状态: {mr.state}")
        print(f"  标题: {mr.title}")
        print("=" * 60)


# --------------  入口  --------------
if __name__ == "__main__":
    try:
        interactive_flow()
    except KeyboardInterrupt:
        print("\n用户中断，Bye~")
