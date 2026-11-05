from typing import Optional, List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.admission_link_snapshots import AdmissionLinkSnapshots


class AdmissionLinkSnapshotsService:
    """
    处理 AdmissionLinkSnapshots 相关的业务逻辑
    表: admission_link_snapshots - 申请链接落地页内容指纹基线
    """

    async def fetch(self, db: AsyncSession, id: int) -> Optional[AdmissionLinkSnapshots]:
        """
        根据 ID 查询记录
        :param db: 异步数据库会话
        :param id: 记录ID
        :return: AdmissionLinkSnapshots 对象或 None
        """
        statement = select(AdmissionLinkSnapshots).where(AdmissionLinkSnapshots.id == id)
        result = await db.exec(statement)
        return result.first()

    async def list(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[AdmissionLinkSnapshots]:
        """
        分页查询记录列表
        :param db: 异步数据库会话
        :param skip: 跳过记录数
        :param limit: 返回记录数
        :return: AdmissionLinkSnapshots 列表
        """
        statement = select(AdmissionLinkSnapshots).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()

    async def query_list(
        self, 
        db: AsyncSession, 
        condition: Dict[str, Any], 
        order_by: Optional[str] = None, 
        sort_by: Optional[str] = "asc"
    ) -> List[AdmissionLinkSnapshots]:
        """
        根据条件查询记录列表
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :param order_by: 排序字段
        :param sort_by: 排序方式 ('asc' or 'desc')
        :return: AdmissionLinkSnapshots 列表
        """
        statement = select(AdmissionLinkSnapshots)
        for key, value in condition.items():
            if hasattr(AdmissionLinkSnapshots, key):
                statement = statement.where(getattr(AdmissionLinkSnapshots, key) == value)
        
        if order_by and hasattr(AdmissionLinkSnapshots, order_by):
            order_col = getattr(AdmissionLinkSnapshots, order_by)
            if sort_by and sort_by.lower() == 'desc':
                statement = statement.order_by(order_col.desc())
            else:
                statement = statement.order_by(order_col.asc())
        
        result = await db.exec(statement)
        return result.all()

    async def query_one(self, db: AsyncSession, condition: Dict[str, Any]) -> Optional[AdmissionLinkSnapshots]:
        """
        根据条件查询单条记录
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :return: AdmissionLinkSnapshots 对象或 None
        """
        statement = select(AdmissionLinkSnapshots)
        for key, value in condition.items():
            if hasattr(AdmissionLinkSnapshots, key):
                statement = statement.where(getattr(AdmissionLinkSnapshots, key) == value)
        
        result = await db.exec(statement)
        return result.first()

    async def create(self, db: AsyncSession, admission_link_snapshots: AdmissionLinkSnapshots) -> AdmissionLinkSnapshots:
        """
        创建新记录
        :param db: 异步数据库会话
        :param admission_link_snapshots: 要创建的记录对象
        :return: 创建后的记录对象
        """
        db.add(admission_link_snapshots)
        await db.flush()
        return admission_link_snapshots

    async def update(self, db: AsyncSession, admission_link_snapshots: AdmissionLinkSnapshots) -> AdmissionLinkSnapshots:
        """
        更新记录
        :param db: 异步数据库会话
        :param admission_link_snapshots: 要更新的记录对象
        :return: 更新后的记录对象
        """
        db.add(admission_link_snapshots)
        await db.flush()
        return admission_link_snapshots

    async def delete(self, db: AsyncSession, id: int) -> bool:
        """
        删除记录
        :param db: 异步数据库会话
        :param id: 记录ID
        :return: 是否删除成功
        """
        admission_link_snapshots = await self.fetch(db, id)
        if admission_link_snapshots:
            await db.delete(admission_link_snapshots)
            await db.flush()
            return True
        return False

# 创建单例实例 (Singleton)
admission_link_snapshots_service = AdmissionLinkSnapshotsService()