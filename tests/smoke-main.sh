#!/bin/sh
# 主变体冒烟测试。运行方式（CI 与本地通用，无需挂载）：
#   docker run --rm -i <image> sh -s < tests/smoke-main.sh
# 验证点：pycurl 可用、curl 带 HTTP3、HTTPS 请求通（204）、ddddocr/onnxruntime/cv2 OCR 栈完整
set -eu

URL_204="https://www.google.com/generate_204"

echo "== 1. 版本信息 =="
python3 -c "import pycurl; print('pycurl:', pycurl.version)"
curl --version | head -1

echo "== 2. curl Features 必须含 HTTP3 =="
curl --version | grep -q "HTTP3" || { echo "FAIL: curl 缺少 HTTP3 特性"; exit 1; }
echo "HTTP3 OK"

echo "== 3. pycurl HTTPS 请求（generate_204，期望 204）=="
URL_204="$URL_204" python3 - <<'EOF'
import os
import pycurl
from io import BytesIO

buf = BytesIO()
c = pycurl.Curl()
c.setopt(pycurl.URL, os.environ["URL_204"])
c.setopt(pycurl.WRITEDATA, buf)
c.setopt(pycurl.TIMEOUT, 30)
c.perform()
code = c.getinfo(pycurl.RESPONSE_CODE)
c.close()
assert code == 204, f"HTTPS 请求失败: HTTP {code}"
print("HTTPS 204 OK")
EOF

echo "== 4. OCR 栈完整性（ddddocr / onnxruntime / cv2 import）=="
python3 -c "import ddddocr, onnxruntime, cv2; print('OCR stack import OK')"

echo
echo "smoke-main: ALL PASS"
