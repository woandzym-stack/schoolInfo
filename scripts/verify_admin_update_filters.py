"""最小验证：管理快讯列表的类型/学校筛选。

用依赖覆盖替换鉴权与数据库，捕获 service 实际执行的 SQL，
断言 change_kind / school_id 条件进入 COUNT 与 SELECT 的 WHERE 子句，
并校验参数非法时返回 422。不需要真实 MySQL / Redis。

运行：poetry run python scripts/verify_admin_update_filters.py
"""
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import admin_updates
from app.core.auth import get_admin_user
from app.core.db import get_async_db


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def one(self) -> Any:
        return self._rows[0]

    def all(self) -> list[Any]:
        return self._rows


class FakeDB:
    """第一次 exec 是 COUNT，第二次是分页 SELECT；记录 WHERE 子句。"""

    def __init__(self) -> None:
        self.wheres: list[str] = []

    async def exec(self, stmt: Any) -> FakeResult:
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        self.wheres.append(sql.split("WHERE", 1)[1] if "WHERE" in sql else "")
        return FakeResult([0]) if len(self.wheres) == 1 else FakeResult([])


def build_app(db: FakeDB) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_updates.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_admin_user] = lambda: object()

    async def fake_db() -> Any:
        yield db

    app.dependency_overrides[get_async_db] = fake_db
    return app


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def main() -> None:
    db = FakeDB()
    client = TestClient(build_app(db))

    resp = client.get(
        "/api/v1/admin/updates",
        params={
            "status": "draft", "keyword": "拔萃", "change_kind": "opened", "school_id": 3,
            "district": "九龍城區", "stage": "secondary",
        },
    )
    check("带筛选请求返回 200", resp.status_code == 200)
    check("返回空列表结构", resp.json()["data"] == {"items": [], "page": 1, "page_size": 20, "total": 0, "pages": 0})
    check("COUNT 与 SELECT 均被执行", len(db.wheres) == 2)
    for label, where in zip(("COUNT", "SELECT"), db.wheres):
        check(f"{label} 含 change_kind 等值条件", "admission_updates.change_kind = 'opened'" in where)
        check(f"{label} 含 school_id 等值条件", "admission_updates.school_id = 3" in where)
        check(f"{label} 含 district 等值条件", "schools.district = '九龍城區'" in where)
        check(f"{label} 含 stage 等值条件", "schools.stage = 'secondary'" in where)
        check(f"{label} 保留 status 条件", "admission_updates.status = 'draft'" in where)
        check(f"{label} 保留学校名 LIKE 条件", "schools.name LIKE" in where)

    db2 = FakeDB()
    client2 = TestClient(build_app(db2))
    resp = client2.get("/api/v1/admin/updates")
    check("无筛选请求返回 200", resp.status_code == 200)
    check("无筛选时 WHERE 不含 change_kind 条件", all("change_kind =" not in w for w in db2.wheres))
    check("无筛选时 WHERE 不含 school_id 条件", all("school_id =" not in w for w in db2.wheres))

    resp = client.get("/api/v1/admin/updates", params={"school_id": "abc"})
    check("school_id 非整数返回 422", resp.status_code == 422)
    resp = client.get("/api/v1/admin/updates", params={"change_kind": "x" * 31})
    check("change_kind 超长返回 422", resp.status_code == 422)
    resp = client.get("/api/v1/admin/updates", params={"stage": "kindergarten"})
    check("stage 非法值返回 422", resp.status_code == 422)

    db3 = FakeDB()
    client3 = TestClient(build_app(db3))
    resp = client3.get(
        "/api/v1/admin/admission-changes",
        params={"status": "all", "change_type": "added", "school_id": 3, "district": "九龍城區", "stage": "secondary"},
    )
    check("候选带筛选请求返回 200", resp.status_code == 200)
    check("候选 COUNT 与 SELECT 均被执行", len(db3.wheres) == 2)
    for label, where in zip(("COUNT", "SELECT"), db3.wheres):
        check(f"候选 {label} 含 change_type 条件", "admission_changes.change_type = 'added'" in where)
        check(f"候选 {label} 含 school_id 条件", "admission_changes.school_id = 3" in where)
        check(f"候选 {label} 含 district 条件", "schools.district = '九龍城區'" in where)
        check(f"候选 {label} 含 stage 条件", "schools.stage = 'secondary'" in where)
    resp = client3.get("/api/v1/admin/admission-changes", params={"stage": "x"})
    check("候选 stage 非法值返回 422", resp.status_code == 422)

    resp = client3.get("/api/v1/admin/school-districts")
    check("地区选项接口返回 200", resp.status_code == 200 and resp.json()["data"] == [])
    print("全部通过")


if __name__ == "__main__":
    main()
