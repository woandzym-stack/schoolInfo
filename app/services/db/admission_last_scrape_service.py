from typing import Optional, List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.admission_last_scrape import AdmissionLastScrape


class AdmissionLastScrapeService:
    """
    处理 AdmissionLastScrape 相关的业务逻辑
    表: admission_last_scrape - 上次抓取原始集合（变更 diff 基准）
    """

    async def fetch(self, db: AsyncSession, school_id: int) -> Optional[AdmissionLastScrape]:
        """
        根据 ID 查询记录
        :param db: 异步数据库会话
        :param school_id: 记录ID
        :return: AdmissionLastScrape 对象或 None
        """
        statement = select(AdmissionLastScrape).where(AdmissionLastScrape.school_id == school_id)
        result = await db.exec(statement)
        return result.first()

    async def list(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[AdmissionLastScrape]:
        """
        分页查询记录列表
        :param db: 异步数据库会话
        :param skip: 跳过记录数
        :param limit: 返回记录数
        :return: AdmissionLastScrape 列表
        """
        statement = select(AdmissionLastScrape).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()

    async def query_list(
        self, 
        db: AsyncSession, 
        condition: Dict[str, Any], 
        order_by: Optional[str] = None, 
        sort_by: Optional[str] = "asc"
    ) -> List[AdmissionLastScrape]:
        """
        根据条件查询记录列表
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :param order_by: 排序字段
        :param sort_by: 排序方式 ('asc' or 'desc')
        :return: AdmissionLastScrape 列表
        """
        statement = select(AdmissionLastScrape)
        for key, value in condition.items():
            if hasattr(AdmissionLastScrape, key):
                statement = statement.where(getattr(AdmissionLastScrape, key) == value)
        
        if order_by and hasattr(AdmissionLastScrape, order_by):
            order_col = getattr(AdmissionLastScrape, order_by)
            if sort_by and sort_by.lower() == 'desc':
                statement = statement.order_by(order_col.desc())
            else:
                statement = statement.order_by(order_col.asc())
        
        result = await db.exec(statement)
        return result.all()

    async def query_one(self, db: AsyncSession, condition: Dict[str, Any]) -> Optional[AdmissionLastScrape]:
        """
        根据条件查询单条记录
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :return: AdmissionLastScrape 对象或 None
        """
        statement = select(AdmissionLastScrape)
        for key, value in condition.items():
            if hasattr(AdmissionLastScrape, key):
                statement = statement.where(getattr(AdmissionLastScrape, key) == value)
        
        result = await db.exec(statement)
        return result.first()

    async def create(self, db: AsyncSession, admission_last_scrape: AdmissionLastScrape) -> AdmissionLastScrape:
        """
        创建新记录
        :param db: 异步数据库会话
        :param admission_last_scrape: 要创建的记录对象
        :return: 创建后的记录对象
        """
        db.add(admission_last_scrape)
        await db.flush()
        return admission_last_scrape

    async def update(self, db: AsyncSession, admission_last_scrape: AdmissionLastScrape) -> AdmissionLastScrape:
        """
        更新记录
        :param db: 异步数据库会话
        :param admission_last_scrape: 要更新的记录对象
        :return: 更新后的记录对象
        """
        db.add(admission_last_scrape)
        await db.flush()
        return admission_last_scrape

    async def delete(self, db: AsyncSession, school_id: int) -> bool:
        """
        删除记录
        :param db: 异步数据库会话
        :param school_id: 记录ID
        :return: 是否删除成功
        """
        admission_last_scrape = await self.fetch(db, school_id)
        if admission_last_scrape:
            await db.delete(admission_last_scrape)
            await db.flush()
            return True
        return False

# 创建单例实例 (Singleton)
admission_last_scrape_service = AdmissionLastScrapeService()