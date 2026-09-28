from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlmodel import Field, SQLModel


class Users(SQLModel, table=True):
    """用户表"""
    __tablename__ = "users"

    id: int = Field(sa_column=Column("id", Integer, primary_key=True, autoincrement=True))
    # 登录用户名（唯一）
    username: str = Field(sa_column=Column("username", String(50), nullable=False, unique=True))
    # argon2 密码哈希
    password_hash: str = Field(sa_column=Column("password_hash", String(255), nullable=False))
    # 邮箱（本期仅存档，不验证不唯一）
    email: str = Field(sa_column=Column("email", String(255), nullable=False))
    # 注册时客户端 IP（XFF 首跳），滥用追溯用
    register_ip: str = Field(sa_column=Column("register_ip", String(45), nullable=False))
    created_at: datetime = Field(sa_column=Column("created_at", DateTime, nullable=False))
    updated_at: datetime = Field(sa_column=Column("updated_at", DateTime, nullable=False))
