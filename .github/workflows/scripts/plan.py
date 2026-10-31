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


# 按「是否本机原生 + 编译量级」分组；组间完全并行，互不抢 CPU，组内串行复用层缓存。
# ppc64le / s390x 各自成组：两者都要在 QEMU 下全量编译 curl 与 BoringSSL，合在一组会
# 串行累加，接近单 job 时限。
GROUPS = [
    ("x86", "ubuntu-latest", ["linux/amd64", "linux/386"]),
    ("arm", arm_runner, ["linux/arm64", "linux/arm/v7", "linux/arm/v6"]),
    ("ppc64le", "ubuntu-latest", ["linux/ppc64le"]),
    ("s390x", "ubuntu-latest", ["linux/s390x"]),
    ("riscv64", riscv_runner, ["linux/riscv64"]),
    ("loong64", "ubuntu-latest", ["linux/loong64"]),
]

GROUP_OF = {p: name for name, _, members in GROUPS for p in members}

include = []
for name, runner, members in GROUPS:
    selected = [p for p in members if p in plats]
    if selected:
        include.append({
            "group": name,
            "runner": runner,
            "platforms": ",".join(selected),
            "base_image": base_of(selected[0]),
            "file": os.environ["DOCKERFILE"],
            "arch": name,
        })
if not include:
    sys.exit("::error::没有可构建的平台")

smoke = [
    {
        "platform": p,
        "group": GROUP_OF[p],
        "runner": (arm_runner if p == "linux/arm64"
                   else riscv_runner if p == "linux/riscv64"
                   else "ubuntu-latest"),
        "base_image": base_of(p),
        "file": os.environ["DOCKERFILE"],
        "arch": p.replace("linux/", "").replace("/", "-"),
    }
    for p in plats
]

print("matrix=" + json.dumps({"include": include}))
print("smoke_matrix=" + json.dumps({"include": smoke}))
print("expected=" + ",".join(sorted(plats)))
# 每个架构组产出一个 digest 文件，publish 合并前按组数核对完整性
print("groups=" + ",".join(entry["group"] for entry in include))
print("full=%s" % str(sorted(plats) == sorted(default)).lower())
