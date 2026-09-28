"""最小验证脚本（方案 §9）：argon2 / JWT 双向往返 + 篡改拒绝 + 合并规则纯逻辑。用完可删。"""
from datetime import datetime

from app.core.auth import create_token, decode_token, hash_password, verify_password
from app.models.users import Users

# --- argon2 round-trip ---
h = hash_password("Passw0rd123")
assert h.startswith("$argon2"), h[:20]
assert verify_password("Passw0rd123", h)
assert not verify_password("wrong", h)
print("OK: argon2 hash/verify roundtrip")

# --- JWT round-trip + 篡改/垃圾 token 拒绝 ---
u = Users(
    id=42, username="tester", password_hash=h, email="t@t.com",
    register_ip="1.2.3.4", created_at=datetime.now(), updated_at=datetime.now(),
)
tok = create_token(u)
p = decode_token(tok)
assert p and p["sub"] == "42" and p["username"] == "tester", p
assert decode_token(tok + "x") is None, "tampered token accepted"
assert decode_token("not.a.token") is None, "garbage token accepted"
print("OK: jwt roundtrip, tamper/garbage rejected")

# --- 订阅合并规则（纯逻辑推演，与 subscriptions_service.subscribe 一致）---
def merge(existing_grades: set, grades: list) -> set:
    want_all = not grades or "all" in grades
    if want_all:
        return {"all"} if existing_grades != {"all"} else existing_grades
    if "all" in existing_grades:
        return existing_grades  # 静默吞掉
    return existing_grades | set(dict.fromkeys(grades))

assert merge(set(), []) == {"all"}                      # 不选年级 → all
assert merge({"all"}, ["P3"]) == {"all"}                # all 覆盖具体年级
assert merge({"P3"}, ["all"]) == {"all"}                # 具体年级 → all 先删后插
assert merge({"P3"}, ["P3"]) == {"P3"}                  # 重复幂等
assert merge({"P3"}, ["P4", "P5"]) == {"P3", "P4", "P5"}  # 增量补插
print("OK: subscription merge rules")

print("ALL CHECKS PASSED")
