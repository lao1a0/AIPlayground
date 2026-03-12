import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ReviewStatistics:
    """审查统计数据模型"""
    id: Optional[int]
    project_id: int
    mr_iid: int
    file_path: str
    file_extension: str
    review_status: str  # success, failed, skipped
    model_used: str
    tokens_used: int
    issues_count: int
    created_at: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReviewStatistics':
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StatisticsStorage:
    """统计数据存储层"""
    
    def __init__(self, db_path: str = "review_statistics.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                mr_iid INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_extension TEXT NOT NULL,
                review_status TEXT NOT NULL,
                model_used TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                issues_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                INDEX idx_project (project_id),
                INDEX idx_mr (project_id, mr_iid),
                INDEX idx_created (created_at)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_review_record(self, record: ReviewStatistics) -> int:
        """保存审查记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO review_statistics 
            (project_id, mr_iid, file_path, file_extension, review_status, 
             model_used, tokens_used, issues_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.project_id,
            record.mr_iid,
            record.file_path,
            record.file_extension,
            record.review_status,
            record.model_used,
            record.tokens_used,
            record.issues_count,
            record.created_at
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return record_id
    
    def get_statistics_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """获取指定日期范围内的统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_reviews,
                SUM(CASE WHEN review_status = 'success' THEN 1 ELSE 0 END) as successful_reviews,
                SUM(CASE WHEN review_status = 'failed' THEN 1 ELSE 0 END) as failed_reviews,
                AVG(tokens_used) as avg_tokens,
                AVG(issues_count) as avg_issues
            FROM review_statistics
            WHERE created_at >= ? AND created_at <= ?
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        ''', (start_date.strftime('%Y-%m-%d %H:%M:%S'), end_date.strftime('%Y-%m-%d %H:%M:%S')))
        
        columns = ['date', 'total_reviews', 'successful_reviews', 'failed_reviews', 'avg_tokens', 'avg_issues']
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return results
    
    def get_model_usage_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取模型使用统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            SELECT 
                model_used,
                COUNT(*) as usage_count,
                SUM(tokens_used) as total_tokens,
                AVG(tokens_used) as avg_tokens,
                AVG(issues_count) as avg_issues
            FROM review_statistics
            WHERE created_at >= ?
            GROUP BY model_used
            ORDER BY usage_count DESC
        ''', (start_date,))
        
        columns = ['model_used', 'usage_count', 'total_tokens', 'avg_tokens', 'avg_issues']
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return results
    
    def get_file_type_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取文件类型统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            SELECT 
                file_extension,
                COUNT(*) as review_count,
                AVG(issues_count) as avg_issues,
                SUM(CASE WHEN review_status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
            FROM review_statistics
            WHERE created_at >= ?
            GROUP BY file_extension
            ORDER BY review_count DESC
        ''', (start_date,))
        
        columns = ['file_extension', 'review_count', 'avg_issues', 'success_rate']
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return results
    
    def get_project_summary(self, project_id: int, days: int = 30) -> Dict[str, Any]:
        """获取项目总体统计摘要"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT mr_iid) as total_mrs,
                COUNT(*) as total_files,
                SUM(CASE WHEN review_status = 'success' THEN 1 ELSE 0 END) as successful_reviews,
                SUM(tokens_used) as total_tokens,
                AVG(issues_count) as avg_issues_per_file,
                COUNT(DISTINCT file_path) as unique_files
            FROM review_statistics
            WHERE project_id = ? AND created_at >= ?
        ''', (project_id, start_date))
        
        row = cursor.fetchone()
        columns = ['total_mrs', 'total_files', 'successful_reviews', 'total_tokens', 'avg_issues_per_file', 'unique_files']
        result = dict(zip(columns, row)) if row else {}
        
        conn.close()
        return result
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的审查活动"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                project_id,
                mr_iid,
                file_path,
                review_status,
                model_used,
                issues_count,
                created_at
            FROM review_statistics
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        columns = ['project_id', 'mr_iid', 'file_path', 'review_status', 'model_used', 'issues_count', 'created_at']
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return results
