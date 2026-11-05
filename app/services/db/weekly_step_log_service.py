from typing import Optional, List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.weekly_step_log import WeeklyStepLog


class WeeklyStepLogService:
    """
    处理 WeeklyStepLog 相关的业务逻辑
    表: weekly_step_log - 每周刷新步骤级日志（断点续跑依据）
    """

    async def fetch(self, db: AsyncSession, id: int) -> Optional[WeeklyStepLog]:
        """
        根据 ID 查询记录
        :param db: 异步数据库会话
        :param id: 记录ID
        :return: WeeklyStepLog 对象或 None
        """
        statement = select(WeeklyStepLog).where(WeeklyStepLog.id == id)
        result = await db.exec(statement)
        return result.first()

    async def list(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[WeeklyStepLog]:
        """
        分页查询记录列表
        :param db: 异步数据库会话
        :param skip: 跳过记录数
        :param limit: 返回记录数
        :return: WeeklyStepLog 列表
        """
        statement = select(WeeklyStepLog).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()

    async def query_list(
        self, 
        db: AsyncSession, 
        condition: Dict[str, Any], 
        order_by: Optional[str] = None, 
        sort_by: Optional[str] = "asc"
    ) -> List[WeeklyStepLog]:
        """
        根据条件查询记录列表
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :param order_by: 排序字段
        :param sort_by: 排序方式 ('asc' or 'desc')
        :return: WeeklyStepLog 列表
        """
        statement = select(WeeklyStepLog)
        for key, value in condition.items():
            if hasattr(WeeklyStepLog, key):
                statement = statement.where(getattr(WeeklyStepLog, key) == value)
        
        if order_by and hasattr(WeeklyStepLog, order_by):
            order_col = getattr(WeeklyStepLog, order_by)
            if sort_by and sort_by.lower() == 'desc':
                statement = statement.order_by(order_col.desc())
            else:
                statement = statement.order_by(order_col.asc())
        
        result = await db.exec(statement)
        return result.all()

    async def query_one(self, db: AsyncSession, condition: Dict[str, Any]) -> Optional[WeeklyStepLog]:
        """
        根据条件查询单条记录
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :return: WeeklyStepLog 对象或 None
        """
        statement = select(WeeklyStepLog)
        for key, value in condition.items():
            if hasattr(WeeklyStepLog, key):
                statement = statement.where(getattr(WeeklyStepLog, key) == value)
        
        result = await db.exec(statement)
        return result.first()

    async def create(self, db: AsyncSession, weekly_step_log: WeeklyStepLog) -> WeeklyStepLog:
        """
        创建新记录
        :param db: 异步数据库会话
        :param weekly_step_log: 要创建的记录对象
        :return: 创建后的记录对象
        """
        db.add(weekly_step_log)
        await db.flush()
        return weekly_step_log

    async def update(self, db: AsyncSession, weekly_step_log: WeeklyStepLog) -> WeeklyStepLog:
        """
        更新记录
        :param db: 异步数据库会话
        :param weekly_step_log: 要更新的记录对象
        :return: 更新后的记录对象
        """
        db.add(weekly_step_log)
        await db.flush()
        return weekly_step_log

    async def delete(self, db: AsyncSession, id: int) -> bool:
        """
        删除记录
        :param db: 异步数据库会话
        :param id: 记录ID
        :return: 是否删除成功
        """
        weekly_step_log = await self.fetch(db, id)
        if weekly_step_log:
            await db.delete(weekly_step_log)
            await db.flush()
            return True
        return False

# 创建单例实例 (Singleton)
weekly_step_log_service = WeeklyStepLogService()