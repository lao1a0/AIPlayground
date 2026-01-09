import asyncio
import os
import re
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any

import gitlab
from dotenv import load_dotenv

from src.config.settings import ENV_PATH
from src.core.base import BaseLLM
from src.models.deepseek_llm import DeepSeekLLM
from src.models.kimi_llm import KimiLLM
from src.models.openai_llm import OpenAILLM

load_dotenv(dotenv_path=ENV_PATH)


class GitLabAIReviewer:
    def __init__(self, gitlab_url: str, private_token: str, project_id: int, model_type: str = "deepseek",
            # 默认使用 deepseek
            max_files: int = 10, max_lines: int = 500, ):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        self.project = self.gl.projects.get(project_id)
        self.max_files = max_files
        self.max_lines = max_lines
        self.llm = self._init_llm(model_type)

    def _init_llm(self, model_type: str) -> BaseLLM:
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

    async def get_merge_requests(self, state: str = "opened") -> List[Any]:
        """获取待审查的合并请求"""
        return self.project.mergerequests.list(state=state)

    def get_changes(self, mr: Any) -> List[Dict[str, Any]]:
        """获取合并请求的具体改动"""
        changes = mr.changes()
        return changes["changes"][: self.max_files]  # 限制文件数量

    def _should_review_file(self, file_path: str) -> bool:
        """判断文件是否需要审查"""
        ignore_patterns = [r"\.lock$", r"package-lock\.json$", r"yarn\.lock$", r"\.gitignore$", r"\.env.*", r"\.md$",
            r"\.txt$", r"\.csv$", r"\.json$", r"\.yaml$", r"\.yml$", ]
        return not any(re.search(pattern, file_path) for pattern in ignore_patterns)

    def _prepare_review_prompt(self, change: Dict[str, Any]) -> str:
        """准备代码审查提示"""
        file_path = change.get("new_path", "")
        diff = change.get("diff", "")
        file_extension = os.path.splitext(file_path)[1] if file_path else ""
        is_react_native = "react-native" in file_path.lower() or "/rn/" in file_path.lower()

        if len(diff.split("\n")) > self.max_lines:
            diff = ("\n".join(diff.split("\n")[: self.max_lines]) + "\n... (diff too long, truncated)")

        # 根据文件类型调整审查重点
        language_specific_checks = {".py": """Python 特定检查点:
- 代码是否遵循 PEP 8 规范
- 是否正确处理异常
- 是否有适当的类型注解
- 是否有必要的文档字符串
- 是否正确使用异步特性""", ".ts": """TypeScript 特定检查点:
- 类型定义是否准确和完整
- 是否正确使用 TypeScript 特性（泛型、接口、类型守卫等）
- 是否避免了 any 类型的滥用
- 是否正确处理 null/undefined
- 是否使用了合适的类型推导
- 是否遵循项目的 TSConfig 配置
- 是否有不必要的类型断言
- 错误处理是否完善
- 是否考虑了类型的向后兼容性""" + ("""

React Native 类型检查点:
- 原生模块类型定义是否完整
- 平台特定类型是否正确处理
- 事件类型是否准确定义
- 样式类型是否符合 React Native 规范
- 导航参数类型是否完整
- 第三方库类型集成是否正确""" if is_react_native else ""), ".tsx": """React TypeScript 特定检查点:
- 组件 Props 和 State 的类型定义是否完整
- 是否正确使用 React.FC 或函数组件声明
- 事件处理器的类型是否正确
- 是否正确使用 React Hooks 的类型
- 是否避免了不必要的重渲染
- 组件生命周期的类型安全
- 是否正确处理异步状态和加载状态
- 是否遵循 React 最佳实践
- 样式和主题的类型定义
- 是否考虑了可访问性(ARIA)属性""" + ("""

React Native 特定检查点:
- 平台特定代码是否正确处理 (iOS/Android)
- 性能优化（如 useCallback、useMemo 的使用）
- 样式是否符合 React Native 最佳实践
- 是否正确处理设备旋转和屏幕尺寸
- 手势处理是否合理
- 动画性能是否优化
- 原生模块集成是否正确
- 内存管理是否合理
- 是否考虑了离线状态处理
- 是否正确使用 React Native 的导航系统
- 是否考虑了应用生命周期
- 是否正确处理键盘事件
- 是否考虑了深色模式支持
- 无障碍功能支持是否完善""" if is_react_native else ""), ".js": """JavaScript 特定检查点:
- 是否使用现代 ES6+ 特性
- 是否正确处理异步操作
- 是否有潜在的内存泄漏
- 是否考虑浏览器兼容性
- 是否遵循项目的 ESLint 规则""", ".go": """Go 特定检查点:
- 是否遵循 Go 的代码规范
- 错误处理是否合适
- 是否有潜在的并发问题
- 是否正确使用 defer
- 性能优化建议""", }.get(file_extension, "")

        security_checks = """安全检查:
1. 是否存在潜在的安全漏洞
2. 敏感信息是否得到保护
3. 输入验证是否充分
4. 是否有权限控制问题
5. 是否有潜在的注入风险"""

        performance_checks = """性能检查:
1. 算法复杂度是否合理
2. 是否有性能瓶颈
3. 资源使用是否高效
4. 是否有不必要的计算
5. 缓存策略是否合适"""

        maintainability_checks = """可维护性检查:
1. 代码结构是否清晰
2. 命名是否符合规范
3. 是否有重复代码
4. 是否有适当的注释
5. 是否遵循 SOLID 原则"""

        # 如果是 React Native 相关文件，添加额外的性能检查
        if is_react_native:
            performance_checks += """

React Native 性能检查:
1. 是否避免了不必要的重渲染
2. 列表渲染是否使用了性能优化（如 FlatList）
3. 图片加载和缓存策略是否合理
4. JavaScript 线程是否有潜在的阻塞操作
5. 动画是否使用了原生驱动
6. 是否正确处理了内存泄漏
7. Bridge 通信是否优化
8. 是否合理使用了 Hermes 引擎特性"""

        return f"""作为高级开发工程师，请对以下代码变更进行全面审查。

文件信息:
- 路径: {file_path}
- 类型: {file_extension}

代码变更:
{diff}

请根据以下准则进行审查：
1. 确保代码改动符合项目规范和最佳实践。
2. 检查是否存在潜在的错误或改进空间。
3. 提供详细的审查意见和建议。

{language_specific_checks}

{security_checks}

{performance_checks}

{maintainability_checks}
"""

    async def review_code(self, change: Dict[str, Any]) -> Optional[str]:
        """使用 LLM 审查代码"""
        try:
            if not self._should_review_file(change.get("new_path", "")):
                print(f"Skipping file: {change.get('new_path', '')}")
                return None

            prompt = self._prepare_review_prompt(change)
            print(f"Reviewing file: {change.get('new_path', '')}")
            print(f"Prompt length: {len(prompt)} characters")

            review_comment = await self.llm.generate(prompt)
            if not review_comment:
                print("Warning: Empty review comment received")
            return review_comment
        except Exception as e:
            print(f"Error reviewing code: {str(e)}")
            print(f"Error type: {type(e)}")

            print(f"Traceback: {traceback.format_exc()}")
            return None

    def post_review_comment(self, mr: Any, file_path: str, review_comment: str) -> None:
        """发布审查评论"""
        comment = (f"## AI 代码审查意见 - `{file_path}`\n\n"
                   f"{review_comment}\n\n"
                   f"---\n"
                   f"_自动审查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        mr.notes.create({"body": comment})

    async def run(self, mr_iid: Optional[int] = None) -> None:
        """运行审查流程"""
        try:
            if mr_iid:
                mr = self.project.mergerequests.get(mr_iid)
                mrs = [mr]
            else:
                mrs = self.get_merge_requests()

            for mr in mrs:
                print(f"Reviewing MR: {mr.iid}")
                if not mr.has_conflicts:
                    changes = self.get_changes(mr)
                    print(f"Found {len(changes)} files to review")
                    for change in changes:
                        review_comment = await self.review_code(change)
                        if review_comment:
                            self.post_review_comment(mr, change["new_path"], review_comment)
                            print(f"Posted review for {change['new_path']}")
                        else:
                            print(f"No review comment generated for {change['new_path']}")
                else:
                    print(f"MR {mr.iid} has conflicts, skipping")
        except Exception as e:
            print(f"Error in review process: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            raise


def select_from_list(items, prompt, item_formatter=None):
    """交互式选择列表中的项目"""
    if not items:
        print("No items available.")
        return None

    print(f"\n{prompt}")
    print("-" * 50)

    for i, item in enumerate(items, 1):
        if item_formatter:
            print(f"{i}. {item_formatter(item)}")
        else:
            print(f"{i}. {item}")

    print("-" * 50)

    while True:
        try:
            choice = input(f"Select (1-{len(items)}), or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                return None
            choice_num = int(choice)
            if 1 <= choice_num <= len(items):
                return items[choice_num - 1]
            else:
                print(f"Please enter a number between 1 and {len(items)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")


def get_projects_interactive(gitlab_url, gitlab_token):
    """交互式获取项目列表"""
    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=gitlab_token)
        projects = gl.projects.list(get_all=True, order_by="name", sort="asc")

        if not projects:
            print("No projects found.")
            return None

        def project_formatter(project):
            return f"{project.name} (ID: {project.id}, Path: {project.path_with_namespace})"

        selected_project = select_from_list(projects, "Available projects:", project_formatter)

        return selected_project
    except Exception as e:
        print(f"Error fetching projects: {str(e)}")
        return None


def get_merge_requests_interactive(project):
    """交互式获取合并请求列表"""
    try:
        mrs = project.mergerequests.list(state="opened", get_all=True, order_by="updated_at", sort="desc")

        if not mrs:
            print("No open merge requests found.")
            return None

        def mr_formatter(mr):
            status = "✓" if not mr.has_conflicts else "✗"
            return f"!{mr.iid} - {mr.title} (Updated: {mr.updated_at[:10]}) {status}"

        selected_mr = select_from_list(mrs, "Available merge requests:", mr_formatter)

        return selected_mr
    except Exception as e:
        print(f"Error fetching merge requests: {str(e)}")
        return None


async def interactive_mode():
    """交互式模式"""
    print("=" * 60)
    print("GitLab AI Code Reviewer - Interactive Mode")
    print("=" * 60)

    # 获取必要的环境变量
    gitlab_url = os.getenv("GITLAB_URL")
    gitlab_token = os.getenv("GITLAB_API_TOKEN")

    if not gitlab_url or not gitlab_token:
        print("Error: GITLAB_URL and GITLAB_API_TOKEN must be set in environment variables.")
        print("Please check your .env file.")
        return

    print(f"Connecting to GitLab: {gitlab_url}")

    # 1. 选择项目
    selected_project = get_projects_interactive(gitlab_url, gitlab_token)
    if not selected_project:
        return

    print(f"\nSelected project: {selected_project.name} (ID: {selected_project.id})")

    # 2. 选择合并请求
    selected_mr = get_merge_requests_interactive(selected_project)
    if not selected_mr:
        return

    print(f"\nSelected merge request: !{selected_mr.iid} - {selected_mr.title}")

    # 3. 获取模型类型
    model_type = os.getenv("REVIEW_MODEL", "deepseek")
    print(f"\nUsing model: {model_type}")

    # 4. 运行代码审查
    print("\n" + "=" * 60)
    print("Starting code review...")
    print("=" * 60)

    try:
        reviewer = GitLabAIReviewer(gitlab_url=gitlab_url, private_token=gitlab_token, project_id=selected_project.id,
            model_type=model_type, max_files=int(os.getenv("REVIEW_MAX_FILES", "10")),
            max_lines=int(os.getenv("REVIEW_MAX_LINES", "500")), )

        await reviewer.run(mr_iid=selected_mr.iid)
        print("\nCode review completed successfully!")

    except Exception as e:
        print(f"\nError during code review: {str(e)}")
        raise


async def main():
    """主入口函数 - 支持交互式和自动模式"""
    try:
        # 检查是否在 CI 环境中
        if os.getenv("CI_SERVER_URL"):
            print("Running in CI mode...")
            # CI 模式 - 使用环境变量
            gitlab_url = os.getenv("CI_SERVER_URL")
            gitlab_token = os.getenv("GITLAB_API_TOKEN")
            project_id = os.getenv("CI_PROJECT_ID")
            mr_iid = os.getenv("CI_MERGE_REQUEST_IID")
        else:
            # 本地开发模式
            print("Running in local development mode...")
            gitlab_url = os.getenv("GITLAB_URL")
            gitlab_token = os.getenv("GITLAB_API_TOKEN")
            project_id = os.getenv("GITLAB_PROJECT_ID")
            mr_iid = os.getenv("REVIEW_MR_IID")

        model_type = os.getenv("REVIEW_MODEL", "deepseek")

        # 检查是否所有必要的环境变量都已设置
        has_all_vars = all([gitlab_url, gitlab_token, project_id, mr_iid])

        if has_all_vars:
            # 自动模式 - 使用环境变量
            print(f"GitLab URL: {gitlab_url}")
            print(f"Project ID: {project_id}")
            print(f"MR IID: {mr_iid}")
            print(f"Model Type: {model_type}")

            print(f"\nStarting code review for MR !{mr_iid}")

            reviewer = GitLabAIReviewer(gitlab_url=gitlab_url, private_token=gitlab_token, project_id=int(project_id),
                model_type=model_type, max_files=int(os.getenv("REVIEW_MAX_FILES", "10")),
                max_lines=int(os.getenv("REVIEW_MAX_LINES", "500")), )

            await reviewer.run(mr_iid=int(mr_iid))
            print("Code review completed successfully")

        else:
            # 缺少环境变量，进入交互式模式
            print("\nSome environment variables are missing.")
            print("Switching to interactive mode...\n")
            await interactive_mode()

    except Exception as e:
        print(f"Error during code review: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
