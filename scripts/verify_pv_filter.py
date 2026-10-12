"""pv_stats.should_count 过滤逻辑的回归验证（调整 UA 黑名单后跑一遍）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.requests import Request

from app.services.pv_stats import should_count

CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def make_request(method: str = "GET", headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": method, "headers": raw})


cases = [
    # (描述, request, 期望)
    ("真实浏览器导航（带 Sec-Fetch）", make_request(headers={"user-agent": CHROME_UA, "sec-fetch-dest": "document", "sec-fetch-mode": "navigate"}), True),
    ("真实浏览器（老浏览器不带 Sec-Fetch）", make_request(headers={"user-agent": CHROME_UA}), True),
    ("curl 默认 UA", make_request(headers={"user-agent": "curl/8.5.0"}), False),
    ("python 脚本", make_request(headers={"user-agent": "python-requests/2.31.0"}), False),
    ("Googlebot", make_request(headers={"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}), False),
    ("sqlmap 扫描", make_request(headers={"user-agent": "sqlmap/1.7.2"}), False),
    ("空 UA", make_request(), False),
    ("HEAD 探测（正常浏览器 UA）", make_request(method="HEAD", headers={"user-agent": CHROME_UA}), False),
    ("Sec-Fetch-Dest 非 document（如脚本发起的 fetch）", make_request(headers={"user-agent": CHROME_UA, "sec-fetch-dest": "empty"}), False),
    ("无头 Chrome", make_request(headers={"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36"}), False),
]

failed = 0
for desc, req, expected in cases:
    got = should_count(req)
    ok = got == expected
    failed += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} | {desc} | 期望={expected} 实际={got}")

print(f"\n{len(cases) - failed}/{len(cases)} 通过")
raise SystemExit(1 if failed else 0)
