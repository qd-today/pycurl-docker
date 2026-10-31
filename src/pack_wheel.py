#!/usr/bin/env python3
"""把源码编译出的 pycurl 变成「自包含 wheel」，并为 wheelhouse 生成 PEP 503 索引。

两个入口：

* ``--wheel-dir``（Dockerfile 的 build 阶段用）：吃 ``pip wheel`` 产出的
  ``pycurl-<ver>-cpXXX-cpXXX-linux_<arch>.whl``，交给 ``auditwheel repair``。它按
  ``DT_NEEDED`` 递归闭包把非 musl 的依赖（libcurl / libssl / libcrypto / ngtcp2 /
  nghttp3 …）改名收进 ``pycurl.libs/``，把每个 ELF 的 RPATH 设成
  ``$ORIGIN/../pycurl.libs``，并把标签从 ``linux_<arch>`` 改成
  ``musllinux_1_2_<arch>``。policy 不靠 ``--plat`` 硬编码：auditwheel 从 ELF 的
  interpreter 认出 musl。
* ``--emit-index``（收尾用）：为 ``--out-dir`` 里已有的 wheel 生成 PEP 503 索引
  ``simple/``，供 uv/pip 用 ``--extra-index-url file:///wheels/simple`` 消费。链接是
  相对路径（``../../<wheel>``），所以挂到任何目录都成立。

``--require-lib`` 是可重复的模式列表，断言修复后 ``pycurl.libs/`` 里确实收进了这些库。
wheel 只「能 import」不代表自包含：库可能仍从系统路径解析，换到干净镜像里才炸。这条
断言把「哪些库必须进 wheel」写成构建期契约（两条线各自的差异也在这里体现）。
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def die(message: str) -> int:
    print(f"错误: {message}", file=sys.stderr)
    return 1


def repair(raw_wheel: Path, out_dir: Path) -> Path:
    """让 auditwheel 收集依赖、改名入 <pkg>.libs/、改 RPATH、重打标签。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    before = {p.resolve() for p in out_dir.glob("*.whl")}
    subprocess.run(
        [
            sys.executable, "-m", "auditwheel", "repair",
            "--wheel-dir", str(out_dir),
            str(raw_wheel),
        ],
        check=True,
    )
    produced = sorted({p.resolve() for p in out_dir.glob("*.whl")} - before)
    if len(produced) != 1:
        raise SystemExit(f"错误: 期望 {out_dir} 里新增恰好 1 个 wheel, 实际 {produced}")
    return produced[0]


def bundled_libs(wheel: Path) -> list[tuple[str, int]]:
    with zipfile.ZipFile(wheel) as zf:
        return [
            (Path(info.filename).name, info.file_size)
            for info in zf.infolist()
            if ".libs/" in info.filename and ".so" in info.filename
        ]


def assert_self_contained(wheel: Path, patterns: list[str]) -> None:
    names = [name for name, _ in bundled_libs(wheel)]
    missing = [p for p in patterns if not any(fnmatch.fnmatch(n, p) for n in names)]
    if missing:
        raise SystemExit(
            f"错误: {wheel.name} 的 .libs/ 里缺少 {missing}（现有: {names}）—— "
            "依赖没被收进 wheel，换到干净镜像里会因找不到库而无法 import"
        )


def report(wheel: Path) -> None:
    print(f"\n产物: {wheel.name}")
    print(f"大小: {wheel.stat().st_size / 1024 / 1024:.1f} MiB")
    libs = sorted(bundled_libs(wheel), key=lambda e: -e[1])
    print(f"pycurl.libs/ 库数量: {len(libs)}")
    for name, size in libs:
        print(f"  {name:48s} {size / 1024 / 1024:8.2f} MiB")


def from_wheel_dir(src_dir: Path, out_dir: Path, expect_version: str, patterns: list[str]) -> int:
    wheels = sorted(src_dir.glob("*.whl"))
    if len(wheels) != 1:
        return die(f"期望 {src_dir} 里恰好 1 个 wheel, 实际 {len(wheels)}: {wheels}")

    raw = wheels[0]
    # 中间产物必须落在 out_dir 之外：CI 用 --output type=local 把整个目录取走，
    # 原始 wheel（linux_<arch> 标签）混进去会让下游的 *.whl 装错文件
    staging = Path(tempfile.mkdtemp(prefix="pycurlraw-"))
    try:
        shutil.copy2(raw, staging / raw.name)
        wheel = repair(staging / raw.name, out_dir)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    if "musllinux" not in wheel.name:
        return die(f"{wheel.name} 的标签不是 musllinux —— auditwheel 没认出 musl 环境？")
    if expect_version and f"-{expect_version}-" not in wheel.name:
        return die(f"{wheel.name} 的版本不是 {expect_version}")

    assert_self_contained(wheel, patterns)
    report(wheel)
    return 0


def emit_index(root: Path) -> int:
    """为 root 下的 wheel 生成 PEP 503 索引，写入 root/simple/。

    链接用相对路径 ``../../<wheel>#sha256=...``，所以索引与 wheel 的相对位置固定
    （simple/<name> -> 上两级），但整个目录可以被挂载到任意路径。
    重复执行会重建 simple/，不会残留上一次的项目目录。
    """
    wheels = sorted(root.glob("*.whl"))
    if not wheels:
        return die(f"{root} 下没有 .whl，无法生成索引")

    simple = root / "simple"
    if simple.exists():
        shutil.rmtree(simple)

    projects: dict[str, list[Path]] = {}
    for wheel in wheels:
        # wheel 文件名首段是 distribution（PEP 427 要求其中的 - 已经换成 _）
        projects.setdefault(wheel.name.split("-")[0].lower(), []).append(wheel)

    for name, files in sorted(projects.items()):
        page = simple / name
        page.mkdir(parents=True)
        links = "\n".join(
            f'    <a href="../../{w.name}#sha256={hashlib.sha256(w.read_bytes()).hexdigest()}">{w.name}</a><br/>'
            for w in files
        )
        (page / "index.html").write_text(
            f'<!DOCTYPE html>\n<html>\n  <head><meta charset="utf-8"/><title>{name}</title></head>\n'
            f"  <body>\n{links}\n  </body>\n</html>\n",
            encoding="utf-8",
        )

    links = "\n".join(f'    <a href="{n}/">{n}</a><br/>' for n in sorted(projects))
    (simple / "index.html").write_text(
        "<!DOCTYPE html>\n<html>\n  <head><meta charset=\"utf-8\"/><title>Simple index</title></head>\n"
        f"  <body>\n{links}\n  </body>\n</html>\n",
        encoding="utf-8",
    )

    print(f"索引: {simple}（{len(projects)} 个项目 / {len(wheels)} 个 wheel）", flush=True)
    for name, files in sorted(projects.items()):
        print(f"  {name}: {len(files)}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel-dir", help="含 pip wheel 产物（linux_<arch>）的目录")
    ap.add_argument(
        "--emit-index",
        action="store_true",
        help="只为 --out-dir 里已有的 wheel 生成 PEP 503 索引（simple/），不打包",
    )
    ap.add_argument("--out-dir", required=True, help="wheel 输出目录；--emit-index 时为索引所在目录")
    ap.add_argument(
        "--require-lib",
        action="append",
        default=[],
        metavar="GLOB",
        help="断言 pycurl.libs/ 里存在匹配该模式的库（可重复）",
    )
    ap.add_argument(
        "--expect-version",
        default="",
        help="断言产出的版本，防止 PYCURL_VERSION 与 wheel 名不一致",
    )
    args = ap.parse_args()

    if bool(args.wheel_dir) == bool(args.emit_index):
        return die("--wheel-dir / --emit-index 必须且只能给一个")

    out_dir = Path(args.out_dir).resolve()
    if args.emit_index:
        return emit_index(out_dir)
    return from_wheel_dir(Path(args.wheel_dir).resolve(), out_dir, args.expect_version, args.require_lib)


if __name__ == "__main__":
    sys.exit(main())
