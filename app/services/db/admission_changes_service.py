from typing import Optional, List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.admission_changes import AdmissionChanges


class AdmissionChangesService:
    """
    处理 AdmissionChanges 相关的业务逻辑
    表: admission_changes - 申请链接变更记录
    """

    async def fetch(self, db: AsyncSession, id: int) -> Optional[AdmissionChanges]:
        """
        根据 ID 查询记录
        :param db: 异步数据库会话
        :param id: 记录ID
        :return: AdmissionChanges 对象或 None
        """
        statement = select(AdmissionChanges).where(AdmissionChanges.id == id)
        result = await db.exec(statement)
        return result.first()

    async def list(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[AdmissionChanges]:
        """
        分页查询记录列表
        :param db: 异步数据库会话
        :param skip: 跳过记录数
        :param limit: 返回记录数
        :return: AdmissionChanges 列表
        """
        statement = select(AdmissionChanges).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()

    async def query_list(
        self, 
        db: AsyncSession, 
        condition: Dict[str, Any], 
        order_by: Optional[str] = None, 
        sort_by: Optional[str] = "asc"
    ) -> List[AdmissionChanges]:
        """
        根据条件查询记录列表
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :param order_by: 排序字段
        :param sort_by: 排序方式 ('asc' or 'desc')
        :return: AdmissionChanges 列表
        """
        statement = select(AdmissionChanges)
        for key, value in condition.items():
            if hasattr(AdmissionChanges, key):
                statement = statement.where(getattr(AdmissionChanges, key) == value)
        
        if order_by and hasattr(AdmissionChanges, order_by):
            order_col = getattr(AdmissionChanges, order_by)
            if sort_by and sort_by.lower() == 'desc':
                statement = statement.order_by(order_col.desc())
            else:
                statement = statement.order_by(order_col.asc())
        
        result = await db.exec(statement)
        return result.all()

    async def query_one(self, db: AsyncSession, condition: Dict[str, Any]) -> Optional[AdmissionChanges]:
        """
        根据条件查询单条记录
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :return: AdmissionChanges 对象或 None
        """
        statement = select(AdmissionChanges)
        for key, value in condition.items():
            if hasattr(AdmissionChanges, key):
                statement = statement.where(getattr(AdmissionChanges, key) == value)
        
        result = await db.exec(statement)
        return result.first()

    async def create(self, db: AsyncSession, admission_changes: AdmissionChanges) -> AdmissionChanges:
        """
        创建新记录
        :param db: 异步数据库会话
        :param admission_changes: 要创建的记录对象
        :return: 创建后的记录对象
        """
        db.add(admission_changes)
        await db.flush()
        return admission_changes

    async def update(self, db: AsyncSession, admission_changes: AdmissionChanges) -> AdmissionChanges:
        """
        更新记录
        :param db: 异步数据库会话
        :param admission_changes: 要更新的记录对象
        :return: 更新后的记录对象
        """
        db.add(admission_changes)
        await db.flush()
        return admission_changes

    async def delete(self, db: AsyncSession, id: int) -> bool:
        """
        删除记录
        :param db: 异步数据库会话
        :param id: 记录ID
        :return: 是否删除成功
        """
        admission_changes = await self.fetch(db, id)
        if admission_changes:
            await db.delete(admission_changes)
            await db.flush()
            return True
        return False

# 创建单例实例 (Singleton)
admission_changes_service = AdmissionChangesService()