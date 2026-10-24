#!/bin/sh
# ja3 变体冒烟测试。运行方式（CI 与本地通用，无需挂载）：
#   docker run --rm -i <image> sh -s < tests/smoke-ja3.sh
# 验证点：pycurl.IMPERSONATE 补丁生效（常量 10999）+ pycurl 层完整复刻 chrome152 指纹
#
# 指纹判定说明：chrome152 profile 启用 tls_permute_extensions，TLS 扩展顺序逐连接
# 随机置换，ja3_hash 每次不同是设计行为；稳定指标是 ja3n_hash（扩展排序归一化），
# 与 CLI/pycurl 双路实测的稳定值 bd4930bd9b000ee684830e44bab76fdf 比对。
# 数据源 tls.browserleaks.com/json 直接返回 ja3n_hash 字段。
set -eu

BROWSERLEAKS="https://tls.browserleaks.com/json"
EXPECTED_JA3N="bd4930bd9b000ee684830e44bab76fdf"
CHROME_UA_PREFIX="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152."

echo "== 1. pycurl.IMPERSONATE 常量存在且为 10999（补丁生效）=="
python3 -c "import pycurl; assert pycurl.IMPERSONATE == 10999, pycurl.IMPERSONATE; print('pycurl.IMPERSONATE =', pycurl.IMPERSONATE)"

echo "== 2. pycurl + IMPERSONATE('chrome152') 指纹实测 =="
BROWSERLEAKS="$BROWSERLEAKS" EXPECTED_JA3N="$EXPECTED_JA3N" CHROME_UA_PREFIX="$CHROME_UA_PREFIX" python3 - <<'EOF'
import json
import os
import pycurl
from io import BytesIO

buf = BytesIO()
c = pycurl.Curl()
c.setopt(pycurl.URL, os.environ["BROWSERLEAKS"])
c.setopt(pycurl.IMPERSONATE, "chrome152")
c.setopt(pycurl.ACCEPT_ENCODING, "")  # libcurl 内置 zstd/brotli/gzip 解压
c.setopt(pycurl.WRITEDATA, buf)
c.setopt(pycurl.TIMEOUT, 30)
c.perform()
code = c.getinfo(pycurl.RESPONSE_CODE)
c.close()
assert code == 200, f"browserleaks 请求失败: HTTP {code}"

body = json.loads(buf.getvalue().decode())
ja3_hash = body.get("ja3_hash")
ja3n = body.get("ja3n_hash")
ua = body.get("user_agent", "")
print(f"ja3_hash : {ja3_hash}  (逐连接随机置换，仅参考)")
print(f"ja3n_hash: {ja3n}")
print(f"user_agent: {ua}")

assert ja3n == os.environ["EXPECTED_JA3N"], \
    f"ja3n 指纹不匹配: {ja3n} != {os.environ['EXPECTED_JA3N']}（profile 未生效或指纹变更）"
assert ua.startswith(os.environ["CHROME_UA_PREFIX"]), f"UA 异常: {ua}"
print("chrome152 指纹 OK（ja3n 稳定值一致 + UA 正确）")
EOF

echo
echo "smoke-ja3: ALL PASS"
