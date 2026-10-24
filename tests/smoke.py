#!/usr/bin/env python3
"""pycurl 三个变体的统一冒烟入口。

容器内以 stdin 执行，脚本不进镜像、不加层、不依赖 bind mount、不访问外网：

    docker run --rm -i --platform <platform> <image> python3 - <role> [ocr|nocr] < tests/smoke.py

    role: main | ja3 | lite      —— 变体自身的固有能力要求
    argv2: ocr | nocr            —— 该平台上是否应该有 OCR 栈（默认 ocr）

两个维度分开传，因为它们是独立的：ja3 变体也有 386/armv6 这种「pycurl 完整、
但基座 ddddocr 是空壳」的平台组合。

为什么只有一个文件：三个变体的检查项高度重叠（pycurl 能否 import、libcurl 是否带
HTTP3、是否被意外塞进 OCR 依赖），拆成三份会让公共部分各写一遍并逐渐漂移。
差异用参数表达，而不是用文件数量表达。

为什么 ja3 检查不联网：原来的实现请求 tls.browserleaks.com 读回 ja3n，等于把
发布闸门交给第三方可用性。现在改为本地起一个 TCP 监听，直接从 socket 读
ClientHello 原始字节，用纯标准库解析出 cipher/extension/curve 列表后自算 ja3/ja3n。
期望值 bd4930bd9b000ee684830e44bab76fdf 已双向验证：既等于 browserleaks 对
chrome152 的返回值，也等于本实现的离线计算结果（且裸 libcurl 为 4fd7cab6...
说明指纹确实被 impersonate 改写）。
"""

import hashlib
import platform
import socket
import sys
import time
import threading

# RFC 8701 GREASE 保留值，JA3 计算前必须剔除，否则同一浏览器每次握手指纹都不同
GREASE = frozenset({
    0x0A0A, 0x1A1A, 0x2A2A, 0x3A3A, 0x4A4A, 0x5A5A, 0x6A6A, 0x7A7A,
    0x8A8A, 0x9A9A, 0xAAAA, 0xBABA, 0xCACA, 0xDADA, 0xEAEA, 0xFAFA,
})

ROLES = ("main", "ja3", "lite")
# chrome152 profile 的 ja3n（扩展排序归一化后的 md5），来源见模块 docstring
CHROME152_JA3N = "bd4930bd9b000ee684830e44bab76fdf"
CHROME152_UA_PREFIX = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152."
)


# --------------------------------------------------------------------------- #
# 通用
# --------------------------------------------------------------------------- #
def check_pycurl():
    import pycurl

    info = pycurl.version_info()
    print("pycurl %s | libcurl %s" % (pycurl.version.split()[0], info[1]))
    assert hasattr(pycurl, "CURL_VERSION_HTTP3"), "pycurl 缺 CURL_VERSION_HTTP3 常量"
    # 注意不能用 "HTTP3" in pycurl.version 判断：pycurl 的版本串里只有 nghttp3/1.15.0
    # 这种依赖名，不含 curl 的 Features 行（Features 只在 curl --version 里）
    assert info[4] & pycurl.CURL_VERSION_HTTP3, (
        "libcurl 未编译 HTTP3（features=0x%x）: 变体应带 ngtcp2/nghttp3 后端" % info[4]
    )
    print("HTTP3: 已启用（features=0x%x）" % info[4])
    return pycurl


def check_ocr(expect):
    """expect=True 断言 OCR 栈真的能推理；False 断言这里确实没有 OCR 栈。

    386/armv6/s390x 的基座 ddddocr 是空壳镜像（无 onnxruntime/OpenCV），
    pycurl 变体在这些平台上仍完整可用，只是没有 OCR 能力——所以这一项按平台
    显式传入，而不是让脚本自己探测（探测会在依赖意外消失时静默降级为通过）。
    """
    if not expect:
        for mod in ("ddddocr", "cv2", "onnxruntime"):
            try:
                __import__(mod)
            except ImportError:
                print("%-12s 不存在（符合该平台的空壳基座契约）" % mod)
            else:
                raise AssertionError(
                    "%s 竟然可以 import —— 若该平台已提供 OCR，请同步更新 README 与平台矩阵" % mod
                )
        return

    try:
        import cv2
        import ddddocr
        import numpy as np
        import onnxruntime
    except ImportError as exc:
        raise AssertionError(
            "该平台应当有完整 OCR 栈，但缺少依赖（%s）—— 若该平台实际只支持空壳基座，"
            "请把 smoke 期望改为 nocr，并同步更新 README 平台矩阵" % exc
        )

    print("cv2 %s | numpy %s | onnxruntime %s"
          % (cv2.__version__, np.__version__, onnxruntime.__version__))

    img = np.full((40, 120, 3), 255, dtype=np.uint8)
    cv2.putText(img, "AB12", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    data = cv2.imencode(".png", img)[1].tobytes()

    # ddddocr 1.6.x 按功能分类型：默认 ocr=True 是分类；det=True 才是目标检测
    text = ddddocr.DdddOcr(show_ad=False).classification(data)
    boxes = ddddocr.DdddOcr(det=True, show_ad=False).detection(data)
    assert isinstance(text, str) and 1 <= len(text) <= 6, "classification 异常: %r" % (text,)
    assert isinstance(boxes, list), "detection 异常: %r" % (type(boxes),)
    print("OCR 推理: %r / %d 框" % (text, len(boxes)))


def check_https():
    """真实 HTTPS 请求，验证「TLS 栈真的能对外握手」——这是唯一的外部依赖。

    用 generate_204（返回 204、无正文）而不是首页，避免被跳转/内容差异干扰。
    ja3 变体的额外价值：它带着 impersonate profile 走完整握手，能抓到
    「指纹配置让握手直接失败」这类问题（本地抓包只看 ClientHello，抓不到）。
    """
    import pycurl
    from io import BytesIO

    url = "https://www.google.com/generate_204"
    buf = BytesIO()
    handle = pycurl.Curl()
    handle.setopt(pycurl.URL, url)
    handle.setopt(pycurl.WRITEDATA, buf)
    handle.setopt(pycurl.TIMEOUT, 30)
    handle.perform()
    code = handle.getinfo(pycurl.RESPONSE_CODE)
    handle.close()
    assert code == 204, "HTTPS 请求失败: HTTP %s（%s）" % (code, url)
    print("HTTPS 204 OK")


# --------------------------------------------------------------------------- #
# ja3：本地抓 ClientHello，自算指纹，全程离线
# --------------------------------------------------------------------------- #
def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("对端在读完 ClientHello 前关闭了连接")
        buf += chunk
    return buf


def _serve_capture_hello(port_holder, record_holder):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_holder.append(srv.getsockname()[1])
    conn, _ = srv.accept()
    conn.settimeout(20)
    try:
        # TLS record: type(1) version(2) length(2)
        header = _recv_exact(conn, 5)
        record_holder.append(header + _recv_exact(conn, int.from_bytes(header[3:5], "big")))
    finally:
        conn.close()
        srv.close()


def _serve_one_http(port_holder, request_holder):
    """最小 HTTP 服务端：只读一份请求头并回 200，用来观察 impersonate 带来的请求头。"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_holder.append(srv.getsockname()[1])
    conn, _ = srv.accept()
    conn.settimeout(20)
    try:
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
        request_holder.append(buf.decode("latin-1"))
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
    finally:
        conn.close()
        srv.close()


def _start(target, holders, timeout=20.0):
    """启动一个一次性的本地服务端线程，等它就绪后返回它监听的端口。

    等待必须有上限：若服务端线程启动失败（端口占用、参数错误等），无界空转会
    让整个冒烟 job 卡死到 CI 超时，而不是给出可读的失败原因。
    """
    thread = threading.Thread(target=target, args=tuple(holders), daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while not holders[0]:
        if not thread.is_alive():
            raise RuntimeError("本地服务端线程启动失败（%s）" % target.__name__)
        if time.monotonic() > deadline:
            raise RuntimeError("本地服务端 %.0fs 内未就绪（%s）" % (timeout, target.__name__))
        time.sleep(0.01)
    return holders[0][0], thread


def _wait_filled(bucket, thread, timeout=20.0, what="数据"):
    deadline = time.monotonic() + timeout
    while not bucket:
        if not thread.is_alive():
            raise RuntimeError("本地服务端线程在收到%s前退出" % what)
        if time.monotonic() > deadline:
            raise RuntimeError("%.0fs 内未收到%s" % (timeout, what))
        time.sleep(0.01)


def _parse_client_hello(record):
    assert record[0] == 22, "首条 TLS 记录不是 handshake (content_type=%d)" % record[0]
    handshake = record[5:]
    assert handshake[0] == 1, "首个 handshake 消息不是 ClientHello (type=%d)" % handshake[0]
    body = handshake[4:]
    pos = 0
    version = int.from_bytes(body[0:2], "big")
    pos = 2 + 32                                    # version + random
    pos += 1 + body[pos]                            # session_id
    n = int.from_bytes(body[pos:pos + 2], "big")
    pos += 2
    ciphers = [int.from_bytes(body[pos + i:pos + i + 2], "big") for i in range(0, n, 2)]
    pos += n
    pos += 1 + body[pos]                            # compression_methods
    extensions = []
    if pos + 2 <= len(body):
        total = int.from_bytes(body[pos:pos + 2], "big")
        pos += 2
        end = pos + total
        while pos + 4 <= end:
            etype = int.from_bytes(body[pos:pos + 2], "big")
            elen = int.from_bytes(body[pos + 2:pos + 4], "big")
            extensions.append((etype, body[pos + 4:pos + 4 + elen]))
            pos += 4 + elen
    groups, formats = [], []
    for etype, edata in extensions:
        if etype == 10:      # supported_groups
            groups = [int.from_bytes(edata[i:i + 2], "big") for i in range(2, len(edata), 2)]
        elif etype == 11:    # ec_point_formats
            formats = list(edata[1:])
    return version, ciphers, [t for t, _ in extensions], groups, formats


def _ja3_string(parsed, sort_extensions=False):
    version, ciphers, extensions, groups, formats = parsed
    c = [x for x in ciphers if x not in GREASE]
    e = [x for x in extensions if x not in GREASE]
    if sort_extensions:
        # chrome 启用 tls_permute_extensions 后扩展顺序逐连接随机，
        # ja3n 就是把扩展排序归一化后的版本（浏览器指纹库的通用做法）
        e = sorted(e)
    g = [x for x in groups if x not in GREASE]
    return "%d,%s,%s,%s,%s" % (
        version,
        "-".join(map(str, c)),
        "-".join(map(str, e)),
        "-".join(map(str, g)),
        "-".join(map(str, formats)),
    )


def _ja3n_of(impersonate):
    import pycurl

    ports, records = [], []
    port, thread = _start(_serve_capture_hello, (ports, records))
    # 必须用主机名而非 IP：用 IP 时客户端不发 SNI 扩展，扩展列表与真实浏览器不同，
    # 算出的 ja3n 自然对不上（实测少一个扩展，哈希完全不同）
    handle = pycurl.Curl()
    handle.setopt(pycurl.URL, "https://localhost:%d/" % port)
    handle.setopt(pycurl.SSL_VERIFYPEER, 0)
    handle.setopt(pycurl.SSL_VERIFYHOST, 0)
    handle.setopt(pycurl.TIMEOUT, 20)
    if impersonate:
        handle.setopt(pycurl.IMPERSONATE, impersonate)
    try:
        handle.perform()
    except pycurl.error:
        pass          # 我们对端只读 ClientHello 就关闭，握手必然失败
    handle.close()
    _wait_filled(records, thread, what="ClientHello")
    parsed = _parse_client_hello(records[0])
    return (
        hashlib.md5(_ja3_string(parsed).encode()).hexdigest(),
        hashlib.md5(_ja3_string(parsed, sort_extensions=True).encode()).hexdigest(),
        len(parsed[1]),
        len(parsed[2]),
    )


def check_ja3():
    import pycurl

    assert hasattr(pycurl, "IMPERSONATE"), "pycurl 缺 IMPERSONATE —— patches/ 补丁未生效"
    assert pycurl.IMPERSONATE == 10999, "IMPERSONATE 选项号异常: %r" % (pycurl.IMPERSONATE,)
    print("pycurl.IMPERSONATE = %d（补丁生效）" % pycurl.IMPERSONATE)

    # 1) 裸 libcurl 的指纹（对照组）
    bare_ja3, bare_ja3n, bare_c, bare_e = _ja3n_of(None)
    print("裸 libcurl : ja3n=%s (%d cipher / %d ext)" % (bare_ja3n, bare_c, bare_e))

    # 2) impersonate 后的指纹
    ja3, ja3n, ciphers, exts = _ja3n_of("chrome152")
    print("chrome152 : ja3n=%s (%d cipher / %d ext)" % (ja3n, ciphers, exts))
    print("            ja3=%s" % ja3)

    assert ja3n == CHROME152_JA3N, (
        "ja3n 与 chrome152 期望值不符: %s != %s（profile 未生效或指纹变更）"
        % (ja3n, CHROME152_JA3N)
    )
    assert ja3n != bare_ja3n, "impersonate 后指纹与裸 libcurl 相同，说明 IMPERSONATE 未真正生效"

    # 3) 请求头也要跟着变（pycurl 补丁会在 setopt(IMPERSONATE) 时清掉默认 UA）
    ports, requests = [], []
    port, thread = _start(_serve_one_http, (ports, requests))
    handle = pycurl.Curl()
    handle.setopt(pycurl.URL, "http://127.0.0.1:%d/" % port)
    handle.setopt(pycurl.TIMEOUT, 20)
    handle.setopt(pycurl.WRITEFUNCTION, lambda data: len(data))
    handle.setopt(pycurl.IMPERSONATE, "chrome152")
    handle.perform()
    handle.close()
    _wait_filled(requests, thread, what="HTTP 请求")

    lines = [ln for ln in requests[0].split("\r\n")[1:] if ":" in ln]
    user_agents = [ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("user-agent")]
    print("User-Agent: %s | 请求头 %d 个" % (user_agents or ["<无>"], len(lines)))
    assert user_agents, "impersonate 后未发送 User-Agent"
    assert user_agents[0].startswith(CHROME152_UA_PREFIX), (
        "UA 不是 chrome152 的浏览器 UA（可能是 pycurl 默认 UA 没被清掉）: %s" % user_agents[0]
    )
    assert len(lines) >= 10, (
        "请求头只有 %d 个，浏览器指纹未生效（应为 15+ 个）" % len(lines)
    )


# --------------------------------------------------------------------------- #
def main(argv):
    role = argv[1] if len(argv) > 1 else ""
    ocr = (argv[2] if len(argv) > 2 else "ocr")
    if role not in ROLES:
        raise SystemExit("用法: python3 - <%s> [ocr|nocr] < tests/smoke.py" % "|".join(ROLES))
    if ocr not in ("ocr", "nocr"):
        raise SystemExit("第二个参数只能是 ocr 或 nocr，收到: %r" % ocr)

    print("== 环境 ==")
    print("python %s | %s" % (platform.python_version(), platform.machine()))

    print("== pycurl 基础能力 ==")
    check_pycurl()

    print("== 真实 HTTPS 请求 ==")
    check_https()

    if role == "ja3":
        print("== TLS 指纹（本地抓包，无外部依赖）==")
        check_ja3()

    print("== OCR 栈（期望：%s）==" % ocr)
    check_ocr(ocr == "ocr")

    print("smoke(%s/%s): PASS" % (role, ocr))


if __name__ == "__main__":
    main(sys.argv)
