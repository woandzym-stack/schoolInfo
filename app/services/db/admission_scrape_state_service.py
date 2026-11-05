from typing import Optional, List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.admission_scrape_state import AdmissionScrapeState


class AdmissionScrapeStateService:
    """
    处理 AdmissionScrapeState 相关的业务逻辑
    表: admission_scrape_state - 学校申请链接抓取基线状态
    """

    async def fetch(self, db: AsyncSession, school_id: int) -> Optional[AdmissionScrapeState]:
        """
        根据 ID 查询记录
        :param db: 异步数据库会话
        :param school_id: 记录ID
        :return: AdmissionScrapeState 对象或 None
        """
        statement = select(AdmissionScrapeState).where(AdmissionScrapeState.school_id == school_id)
        result = await db.exec(statement)
        return result.first()

    async def list(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[AdmissionScrapeState]:
        """
        分页查询记录列表
        :param db: 异步数据库会话
        :param skip: 跳过记录数
        :param limit: 返回记录数
        :return: AdmissionScrapeState 列表
        """
        statement = select(AdmissionScrapeState).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()

    async def query_list(
        self, 
        db: AsyncSession, 
        condition: Dict[str, Any], 
        order_by: Optional[str] = None, 
        sort_by: Optional[str] = "asc"
    ) -> List[AdmissionScrapeState]:
        """
        根据条件查询记录列表
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :param order_by: 排序字段
        :param sort_by: 排序方式 ('asc' or 'desc')
        :return: AdmissionScrapeState 列表
        """
        statement = select(AdmissionScrapeState)
        for key, value in condition.items():
            if hasattr(AdmissionScrapeState, key):
                statement = statement.where(getattr(AdmissionScrapeState, key) == value)
        
        if order_by and hasattr(AdmissionScrapeState, order_by):
            order_col = getattr(AdmissionScrapeState, order_by)
            if sort_by and sort_by.lower() == 'desc':
                statement = statement.order_by(order_col.desc())
            else:
                statement = statement.order_by(order_col.asc())
        
        result = await db.exec(statement)
        return result.all()

    async def query_one(self, db: AsyncSession, condition: Dict[str, Any]) -> Optional[AdmissionScrapeState]:
        """
        根据条件查询单条记录
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :return: AdmissionScrapeState 对象或 None
        """
        statement = select(AdmissionScrapeState)
        for key, value in condition.items():
            if hasattr(AdmissionScrapeState, key):
                statement = statement.where(getattr(AdmissionScrapeState, key) == value)
        
        result = await db.exec(statement)
        return result.first()

    async def create(self, db: AsyncSession, admission_scrape_state: AdmissionScrapeState) -> AdmissionScrapeState:
        """
        创建新记录
        :param db: 异步数据库会话
        :param admission_scrape_state: 要创建的记录对象
        :return: 创建后的记录对象
        """
        db.add(admission_scrape_state)
        await db.flush()
        return admission_scrape_state

    async def update(self, db: AsyncSession, admission_scrape_state: AdmissionScrapeState) -> AdmissionScrapeState:
        """
        更新记录
        :param db: 异步数据库会话
        :param admission_scrape_state: 要更新的记录对象
        :return: 更新后的记录对象
        """
        db.add(admission_scrape_state)
        await db.flush()
        return admission_scrape_state

    async def delete(self, db: AsyncSession, school_id: int) -> bool:
        """
        删除记录
        :param db: 异步数据库会话
        :param school_id: 记录ID
        :return: 是否删除成功
        """
        admission_scrape_state = await self.fetch(db, school_id)
        if admission_scrape_state:
            await db.delete(admission_scrape_state)
            await db.flush()
            return True
        return False

# 创建单例实例 (Singleton)
admission_scrape_state_service = AdmissionScrapeStateService()