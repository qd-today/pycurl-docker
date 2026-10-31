#!/usr/bin/env python3
"""pycurl 两条构建线的统一冒烟入口。

容器内以 stdin 执行，脚本不进镜像、不加层、不依赖 bind mount：

    docker run --rm -i --platform <platform> <image> python3 - <role> <platform> < tests/smoke.py

    role: main（不含 IMPERSONATE） | ja3（含 IMPERSONATE）

脚本跑在**最终 runtime 镜像**里（不是在干净 alpine 里重装 wheel），所以通过就同时证明两件
事：wheelhouse 里的 wheel 在只装了 system-packages.txt 的环境里能装，以及镜像本身可运行。

检查项各自防一类回归：

1. 无 /wheels、/w 残留 —— wheelhouse 只该在构建期 bind mount，装完即随 layer 消失；
2. pycurl 可 import、libcurl 特性位含 HTTP/3 —— 编译期缺失（ngtcp2/nghttp3 没接上）在这里暴露；
3. 依赖自包含 —— pycurl.libs/ 收进了 libcurl，且系统里没有 libcurl，说明 wheel 不依赖系统库；
4. 无 OCR 栈 —— 镜像不再集成 ddddocr/onnxruntime，它按预期不存在；
5. ELF e_machine —— 产物是不是目标架构的机器码（QEMU 下架构探测被 uname 骗过时会错）；
6. 真实 HTTPS 请求 —— TLS 栈能对外握手，这是唯一的外部依赖；
7. ja3 线额外：IMPERSONATE 选项在位 + 本地抓 ClientHello 自算 ja3n（不依赖第三方站点）。

ja3 指纹为什么本地算：请求 tls.browserleaks.com 读回 ja3n 等于把发布闸门交给第三方可用性。
改为本地起一个 TCP 监听，直接从 socket 读 ClientHello 原始字节，用纯标准库解析出
cipher/extension/curve 列表后自算 ja3/ja3n。期望值 bd4930bd9b000ee684830e44bab76fdf 已双向
验证：既等于 browserleaks 对 chrome152 的返回值，也等于本实现的离线计算结果。
"""

import glob
import hashlib
import os
import platform
import socket
import struct
import sys
import threading
import time

# RFC 8701 GREASE 保留值，JA3 计算前必须剔除，否则同一浏览器每次握手指纹都不同
GREASE = frozenset({
    0x0A0A, 0x1A1A, 0x2A2A, 0x3A3A, 0x4A4A, 0x5A5A, 0x6A6A, 0x7A7A,
    0x8A8A, 0x9A9A, 0xAAAA, 0xBABA, 0xCACA, 0xDADA, 0xEAEA, 0xFAFA,
})

ROLES = ("main", "ja3")

# ELF e_machine 编码（/usr/include/elf.h）
ELF_MACHINE = {
    "linux/amd64": 62, "linux/386": 3, "linux/arm64": 183,
    "linux/arm/v7": 40, "linux/arm/v6": 40, "linux/ppc64le": 21,
    "linux/riscv64": 243, "linux/s390x": 22, "linux/loong64": 258,
}


def elf_machine(path):
    """读 ELF 头的 e_machine（不依赖 readelf/file，镜像里未必有）。"""
    with open(path, "rb") as handle:
        header = handle.read(20)
    assert header[:4] == b"\x7fELF", "%s 不是 ELF 文件" % path
    # EI_DATA: 1=小端 2=大端（s390x 大端，e_machine 也按大端存）
    endian = "<" if header[5] == 1 else ">"
    return struct.unpack(endian + "H", header[18:20])[0]


def check_arch(platform_name, patterns):
    """断言镜像里的原生产物确实是目标平台的机器码。

    这是「所有未显式声明的架构探测」的通用兜底：在原生 arm64 runner 上跑 armv7 容器时，
    内核 compat 模式让 uname 仍报 aarch64，configure/cmake 的探测会被骗。逐个去修每个
    configure 不可持续，改成在产物层面验一次。
    """
    expected = ELF_MACHINE.get(platform_name)
    if expected is None:
        print("跳过 ELF 架构校验（未知平台 %r）" % platform_name)
        return

    checked = 0
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            got = elf_machine(path)
            assert got == expected, (
                "%s 的 ELF machine=%d，期望 %d（%s）—— 构建时架构探测错了"
                % (path, got, expected, platform_name)
            )
            checked += 1
    assert checked, "没有找到可校验的原生产物（检查 glob 模式是否写错）"
    print("ELF 架构校验通过：%d 个产物 = %s（e_machine=%d）"
          % (checked, platform_name, expected))


# --------------------------------------------------------------------------- #
# 通用
# --------------------------------------------------------------------------- #
def check_no_wheelhouse():
    """runtime 镜像里不该出现 wheelhouse：它只在构建期 bind mount。"""
    leftovers = [p for p in ("/wheels", "/w") if os.path.exists(p)]
    assert not leftovers, "runtime 镜像里残留 wheel 目录: %s" % ", ".join(leftovers)
    print("未发现 /wheels 或 /w")


def check_no_build_tools():
    """git 只该在构建期存在，它对运行时没有任何用途，还会带进一整套证书与网络工具链。"""
    import shutil

    assert shutil.which("git") is None, "镜像里出现 git，它只该在构建期存在"
    print("git: 不存在（符合预期）")


def check_no_ocr():
    """镜像不再集成 OCR 栈：这些模块必须按预期 import 失败。

    做成断言而不是「探测到就跳过」：依赖被无意加回镜像时要立刻失败。
    """
    for mod in ("ddddocr", "onnxruntime", "cv2"):
        try:
            __import__(mod)
        except ImportError:
            print("%-12s 不存在（符合预期，OCR 由上层从各自 wheelhouse 装）" % mod)
        else:
            raise AssertionError("%s 竟然可以 import —— 本镜像不含 OCR 栈" % mod)


def check_pycurl():
    import pycurl

    info = pycurl.version_info()
    print("pycurl %s | libcurl %s | 加载自 %s"
          % (pycurl.version.split()[0], info[1], os.path.dirname(pycurl.__file__)))
    assert hasattr(pycurl, "CURL_VERSION_HTTP3"), "pycurl 缺 CURL_VERSION_HTTP3 常量"
    # 不能用 "HTTP3" in pycurl.version 判断：pycurl 的版本串里只有 nghttp3/1.18.0 这类
    # 依赖名，Features 行只在 curl --version 里
    assert info[4] & pycurl.CURL_VERSION_HTTP3, (
        "libcurl 未编译 HTTP3（features=0x%x）: 应带 ngtcp2/nghttp3 后端" % info[4]
    )
    print("HTTP3: 已启用（features=0x%x）" % info[4])
    return pycurl


def check_self_contained():
    """依赖应当在 wheel 里，而不是系统里。

    镜像只 apk 装了 system-packages.txt 里那几个包，没有 libcurl —— 若 pycurl.libs/ 少了
    libcurl，`import pycurl` 早就该失败；这条断言把「确实来自 wheel」写死，防止有人用
    `apk add libcurl` 把问题盖住。
    """
    import pycurl

    # auditwheel 把依赖放在 site-packages/pycurl.libs/，与 pycurl/ 目录平级
    libs_dir = os.path.join(os.path.dirname(os.path.dirname(pycurl.__file__)), "pycurl.libs")
    assert os.path.isdir(libs_dir), "%s 不存在 —— wheel 没有把依赖收进来" % libs_dir

    libs = sorted(os.path.basename(p) for p in glob.glob(os.path.join(libs_dir, "*.so*")))
    assert any("libcurl" in name for name in libs), (
        "pycurl.libs/ 里没有 libcurl（现有 %s）" % libs
    )
    system = sorted(glob.glob("/usr/lib/libcurl.so*") + glob.glob("/lib/libcurl.so*"))
    assert not system, "系统里出现 libcurl（%s）—— 依赖应完全来自 wheel" % system

    for path in sorted(glob.glob(os.path.join(libs_dir, "*.so*"))):
        size = os.path.getsize(path) / 1024 / 1024
        if size >= 0.5:
            print("  %-44s %6.2f MiB" % (os.path.basename(path), size))
    print("pycurl.libs/: %d 个库，系统无 libcurl" % len(libs))


def check_https():
    """真实 HTTPS 请求，验证「TLS 栈真的能对外握手」——这是唯一的外部依赖。

    用 generate_204（返回 204、无正文）而不是首页，避免被跳转/内容差异干扰。ja3 线的额外
    价值：它带着 impersonate profile 走完整握手，能抓到「指纹配置让握手直接失败」这类问题
    （本地抓包只看 ClientHello，抓不到）。
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
CHROME152_JA3N = "bd4930bd9b000ee684830e44bab76fdf"
CHROME152_UA_PREFIX = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152."
)


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

    等待必须有上限：若服务端线程启动失败，无界空转会让整个冒烟 job 卡死到 CI 超时，
    而不是给出可读的失败原因。
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
    # 算出的 ja3n 自然对不上
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
        "请求头只有 %d 个，浏览器指纹未生效" % len(lines)
    )


def check_no_impersonate():
    """main 线用未打补丁的 pycurl：IMPERSONATE 不该存在。

    两条线共用同一套 Dockerfile 结构，只有 ja3 线打 patches/。这条断言防的是「补丁被
    误应用到 main 线」，那样 lite 镜像会悄悄带上指纹能力，与基线不符。
    """
    import pycurl

    assert not hasattr(pycurl, "IMPERSONATE"), (
        "main 线的 pycurl 竟带 IMPERSONATE —— patches/ 被误用到了这条线"
    )
    print("pycurl.IMPERSONATE: 不存在（main 线未打补丁）")


# --------------------------------------------------------------------------- #
def main(argv):
    role = argv[1] if len(argv) > 1 else ""
    platform_name = argv[2] if len(argv) > 2 else ""
    if role not in ROLES:
        raise SystemExit("用法: python3 - <%s> <platform> < tests/smoke.py" % "|".join(ROLES))

    print("== 环境 ==")
    print("python %s | %s" % (platform.python_version(), platform.machine()))

    print("== 无 wheelhouse 残留 ==")
    check_no_wheelhouse()

    print("== 运行时不带构建工具 ==")
    check_no_build_tools()

    print("== pycurl 基础能力 ==")
    check_pycurl()

    print("== 依赖自包含 ==")
    check_self_contained()

    print("== OCR 栈（期望：不存在）==")
    check_no_ocr()

    print("== 产物架构 ==")
    # pycurl 扩展与它 bundle 的全部依赖都要是目标架构的机器码
    site = "/usr/lib/python3.*/site-packages"
    check_arch(platform_name, [
        site + "/pycurl*.so",
        site + "/pycurl.libs/*.so*",
    ])

    print("== 真实 HTTPS 请求 ==")
    check_https()

    if role == "ja3":
        print("== TLS 指纹（本地抓包，无外部依赖）==")
        check_ja3()
    else:
        print("== IMPERSONATE 缺席（main 线契约）==")
        check_no_impersonate()

    print("smoke(%s/%s): PASS" % (role, platform_name))


if __name__ == "__main__":
    main(sys.argv)
