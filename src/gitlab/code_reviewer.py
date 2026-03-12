import re
from datetime import datetime
from typing import Dict, Any

import gitlab

from ..core.base import BaseLLM
from ..core.monitoring import MonitoringService


class GitLabCodeReviewer:
    def __init__(self, gitlab_url: str, private_token: str, project_id: int, llm: BaseLLM):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        self.project = self.gl.projects.get(project_id)
        self.llm = llm
        self.monitoring = MonitoringService()
        self.project_id = project_id

    async def review_merge_request(self, mr_iid: int) -> None:
        """审查指定的合并请求"""
        mr = self.project.mergerequests.get(mr_iid)
        changes = mr.changes()

        for change in changes.get('changes', []):
            await self._review_file_changes(mr, change)

    async def _review_file_changes(self, mr: Any, change: Dict[str, Any]) -> None:
        """审查单个文件的变更"""
        file_path = change.get('new_path')
        if not self._should_review_file(file_path):
            # 记录被跳过的文件
            self.monitoring.record_review(
                project_id=self.project_id,
                mr_iid=mr.iid,
                file_path=file_path or 'unknown',
                file_extension='skipped',
                review_status='skipped',
                model_used='N/A',
                tokens_used=0,
                issues_count=0
            )
            return

        diff = change.get('diff', '')
        if not diff:
            return

        # 准备代码上下文
        context = self._extract_diff_context(diff)

        # 生成审查提示
        prompt = self._create_review_prompt(file_path, context)

        # 获取 AI 反馈
        try:
            review_comment = await self.llm.generate(prompt)
            
            # 估算 token 使用量（简单按字符数计算）
            tokens_used = len(prompt) // 4 + len(review_comment) // 4
            
            # 统计问题数量（通过检测关键词）
            issues_count = self._count_issues(review_comment)
            
            if review_comment.strip():
                self._post_review_comment(mr, file_path, review_comment)
                
                # 记录成功的审查
                self.monitoring.record_review(
                    project_id=self.project_id,
                    mr_iid=mr.iid,
                    file_path=file_path,
                    file_extension=self._get_file_extension(file_path),
                    review_status='success',
                    model_used=self.llm.__class__.__name__,
                    tokens_used=tokens_used,
                    issues_count=issues_count
                )
        except Exception as e:
            print(f"Error reviewing {file_path}: {str(e)}")
            
            # 记录失败的审查
            self.monitoring.record_review(
                project_id=self.project_id,
                mr_iid=mr.iid,
                file_path=file_path or 'unknown',
                file_extension=self._get_file_extension(file_path) if file_path else 'unknown',
                review_status='failed',
                model_used=self.llm.__class__.__name__,
                tokens_used=0,
                issues_count=0
            )

    def _should_review_file(self, file_path: str) -> bool:
        """判断文件是否需要审查"""
        if not file_path:
            return False

        # 忽略的文件类型
        ignore_patterns = [r'\.lock$', r'\.json$', r'\.md$', r'\.txt$', r'\.yaml$', r'\.yml$', r'package-lock\.json$',
            r'yarn\.lock$', r'\.gitignore$', r'\.env.*', ]

        return not any(re.search(pattern, file_path) for pattern in ignore_patterns)

    def _extract_diff_context(self, diff: str) -> Dict[str, Any]:
        """提取差异上下文"""
        lines = diff.split('\n')
        added_lines = []
        removed_lines = []

        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                removed_lines.append(line[1:])

        return {'added': added_lines, 'removed': removed_lines, 'full_diff': diff}

    def _create_review_prompt(self, file_path: str, context: Dict[str, Any]) -> str:
        """创建代码审查提示"""
        return f"""请作为高级开发工程师审查以下代码变更:

文件: {file_path}

变更内容:
{context['full_diff']}
"""

    def _post_review_comment(self, mr: Any, file_path: str, review_comment: str) -> None:
        """发布审查评论"""
        comment = (f"## AI 代码审查意见 - `{file_path}`\n\n"
                   f"{review_comment}\n\n"
                   f"---\n"
                   f"_自动审查时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        mr.notes.create({"body": comment})
    
    def _get_file_extension(self, file_path: str) -> str:
        """获取文件扩展名"""
        if not file_path or '.' not in file_path:
            return 'unknown'
        return '.' + file_path.split('.')[-1]
    
    def _count_issues(self, review_comment: str) -> int:
        """统计评论中提到的问题数量"""
        # 通过检测常见的问题标识来计数
        issue_indicators = [
            '问题：', '建议：', '注意：', '警告：', '错误：',
            'Issue:', 'Warning:', 'Error:', 'Suggestion:',
            '❌', '⚠️', '💡',
            '- [ ]', '* ', '• ',
            '\n-', '\n*', '\n•',
        ]
        
        count = 0
        for indicator in issue_indicators:
            count += review_comment.count(indicator)
        
        # 去重估算（因为一个可能被多个模式匹配）
        return max(1, count // 3)
