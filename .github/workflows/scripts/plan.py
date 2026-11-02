#!/usr/bin/env python3
"""计算构建矩阵，输出到 stdout（key=value 形式，由 workflow 追加到 $GITHUB_OUTPUT）。

从环境变量读取输入，不读仓库文件。
"""

import json
import os
import sys

default = [p.strip() for p in os.environ["DEFAULT_PLATFORMS"].split(",") if p.strip()]
raw = (os.environ.get("PLATFORM_INPUT") or "").strip()
plats = [p.strip() for p in raw.split(",") if p.strip()] if raw else default

# 可选平台 = 两条线合起来实测通过的 9 个。加新平台前必须先确认两件事：
#   1) 该架构能编出 curl / ngtcp2 / nghttp3（ja3 线还要能编出 BoringSSL）；
#   2) tests/smoke.py 的 ELF_MACHINE 里有它的 e_machine 编码。
allowed = {
    "linux/amd64", "linux/386", "linux/arm64", "linux/arm/v7",
    "linux/arm/v6", "linux/ppc64le", "linux/riscv64", "linux/s390x",
    "linux/loong64",
}
bad = [p for p in plats if p not in allowed]
if bad:
    sys.exit(
        "::error::不支持或未验证的平台: %s（可选: %s）"
        % (",".join(bad), ",".join(sorted(allowed)))
    )
dup = sorted({p for p in plats if plats.count(p) > 1})
if dup:
    sys.exit("::error::平台重复: %s" % ",".join(dup))

native = os.environ.get("NATIVE_ARM") != "false"
arm_runner = "ubuntu-24.04-arm" if native else "ubuntu-latest"
# RISE（Linux Foundation Europe）给开源项目提供免费的原生 riscv64 runner。
# 默认关闭：没装那个 GitHub App 时，runs-on: ubuntu-24.04-riscv 会一直排队，
# 把发布卡死。
riscv_runner = (
    "ubuntu-24.04-riscv" if os.environ.get("NATIVE_RISCV") == "true" else "ubuntu-latest"
)


def base_of(platform: str) -> str:
    """只有 loong64 需要换基座：alpine 官方没有该架构，ghcr.io/loong64/alpine 有同
    Alpine 版本与同版本构建工具链。空字符串 = 用 Dockerfile 里的默认
    ${BASE_IMAGE}=alpine:${ALPINE_VERSION}。"""
    if platform == "linux/loong64":
        return "%s:%s" % (os.environ["LOONG64_BASE"], os.environ["ALPINE"])
    return ""


# 每个平台独立一个 job。
#
# 为什么按平台拆而不是按组：--output type=local 不支持多平台，而两段式构建需要把
# wheel 从构建 job 导出给 runtime job。顺带的好处是并行度更高——原来 arm 组一次
# 串行构建三个架构要一小时，拆开后每个平台几分钟、彼此并行。
#
# runner 分配：
#   wheel   —— 挑编译最快的：arm 三兄弟都在原生 arm64（armv6 在那边编 2 分钟，
#              QEMU 下要 32 分钟）、riscv64 用 RISE、其余 x86_64。
#   runtime —— 统一 x86_64。arm64 runner 走内核 compat 时 Python 自报
#              linux-aarch64，uv 在那装 armv7l 的 wheel 会挂死（实测两版 uv 都超时，
#              pip 能过）。x86_64 + QEMU 下 Python 报 linux-armv7l，与 wheel 匹配。
def wheel_runner(platform: str) -> str:
    if platform in ("linux/arm64", "linux/arm/v7", "linux/arm/v6"):
        return arm_runner
    if platform == "linux/riscv64":
        return riscv_runner
    return "ubuntu-latest"


RUNTIME_RUNNER = "ubuntu-latest"


def arch_of(platform: str) -> str:
    return platform.replace("linux/", "").replace("/", "-")


wheel_matrix = [
    {
        "platform": p,
        "arch": arch_of(p),
        "runner": wheel_runner(p),
        "base_image": base_of(p),
        "file": os.environ["DOCKERFILE"],
    }
    for p in plats
]

runtime_matrix = [
    {
        "platform": p,
        "arch": arch_of(p),
        "runner": RUNTIME_RUNNER,
        "base_image": base_of(p),
        "file": os.environ["DOCKERFILE"],
    }
    for p in plats
]

smoke = [
    {
        "platform": p,
        "arch": arch_of(p),
        "runner": (arm_runner if p == "linux/arm64"
                   else riscv_runner if p == "linux/riscv64"
                   else "ubuntu-latest"),
        "base_image": base_of(p),
        "file": os.environ["DOCKERFILE"],
    }
    for p in plats
]

print("wheel_matrix=" + json.dumps({"include": wheel_matrix}))
print("runtime_matrix=" + json.dumps({"include": runtime_matrix}))
print("smoke_matrix=" + json.dumps({"include": smoke}))
print("expected=" + ",".join(sorted(plats)))
# 每个平台各产出一个 digest 文件，publish 合并前按平台数核对完整性
print("platforms=" + ",".join(sorted(plats)))
print("full=%s" % str(sorted(plats) == sorted(default)).lower())
