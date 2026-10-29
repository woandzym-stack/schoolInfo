"""pv_stats 过滤与来源解析的回归验证（调整 UA 黑名单/来源归桶后跑一遍）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.requests import Request

from app.services.pv_stats import resolve_source, should_count

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HOST = "school.ddup.app"


def make_request(method: str = "GET", headers: dict[str, str] | None = None, query_string: str = "") -> Request:
    hdrs = {"host": HOST, **(headers or {})}
    raw = [(k.lower().encode(), v.encode()) for k, v in hdrs.items()]
    return Request({"type": "http", "method": method, "headers": raw, "query_string": query_string.encode()})


count_cases = [
    # (描述, request, 期望)
    (
        "真实浏览器导航（带 Sec-Fetch）",
        make_request(headers={"user-agent": CHROME_UA, "sec-fetch-dest": "document", "sec-fetch-mode": "navigate"}),
        True,
    ),
    ("真实浏览器（老浏览器不带 Sec-Fetch）", make_request(headers={"user-agent": CHROME_UA}), True),
    (
        "直接扫描服务器 IP（Host 非正式域名）",
        make_request(headers={"host": "47.242.217.80", "user-agent": CHROME_UA, "referer": "https://47.242.217.80/"}),
        False,
    ),
    ("其他域名 Host", make_request(headers={"host": "example.com", "user-agent": CHROME_UA}), False),
    ("正式域名带端口", make_request(headers={"host": f"{HOST}:443", "user-agent": CHROME_UA}), True),
    ("curl 默认 UA", make_request(headers={"user-agent": "curl/8.5.0"}), False),
    ("python 脚本", make_request(headers={"user-agent": "python-requests/2.31.0"}), False),
    (
        "Googlebot",
        make_request(
            headers={"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
        ),
        False,
    ),
    ("sqlmap 扫描", make_request(headers={"user-agent": "sqlmap/1.7.2"}), False),
    ("空 UA", make_request(), False),
    ("HEAD 探测（正常浏览器 UA）", make_request(method="HEAD", headers={"user-agent": CHROME_UA}), False),
    (
        "Sec-Fetch-Dest 非 document（如脚本发起的 fetch）",
        make_request(headers={"user-agent": CHROME_UA, "sec-fetch-dest": "empty"}),
        False,
    ),
    (
        "无头 Chrome",
        make_request(
            headers={
                "user-agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "HeadlessChrome/120.0.0.0 Safari/537.36"
                )
            }
        ),
        False,
    ),
]

source_cases = [
    # (描述, request, 期望来源)
    ("无 utm 无 Referer", make_request(), "direct"),
    ("utm_source 优先（大小写归一）", make_request(query_string="utm_source=Google&utm_medium=cpc"), "google"),
    ("utm_source 非法字符清洗", make_request(query_string="utm_source=wechat!!%3Cscript%3E"), "wechatscript"),
    ("Google 搜索 Referer", make_request(headers={"referer": "https://www.google.com.hk/search?q=xxx"}), "google"),
    ("Bing 搜索 Referer", make_request(headers={"referer": "https://cn.bing.com/search?q=xxx"}), "bing"),
    ("百度 Referer", make_request(headers={"referer": "https://www.baidu.com/s?wd=xxx"}), "baidu"),
    ("站内跳转（Referer 即本站）", make_request(headers={"referer": f"https://{HOST}/ui/subscriptions"}), "direct"),
    (
        "一般外链按域名记录",
        make_request(headers={"referer": "https://www.discuss.com.hk/viewthread.php?tid=1"}),
        "discuss.com.hk",
    ),
    (
        "utm 为空字符串回退 Referer",
        make_request(headers={"referer": "https://www.google.com/"}, query_string="utm_source="),
        "google",
    ),
]

failed = 0
for desc, req, expected in count_cases:
    got = should_count(req)
    ok = got == expected
    failed += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} | 计数过滤 | {desc} | 期望={expected} 实际={got}")

for desc, req, expected in source_cases:
    got = resolve_source(req)
    ok = got == expected
    failed += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} | 来源解析 | {desc} | 期望={expected} 实际={got}")

total = len(count_cases) + len(source_cases)
print(f"\n{total - failed}/{total} 通过")
raise SystemExit(1 if failed else 0)
