# pycurl Docker 镜像（Alpine）
[![FOSSA Status](https://app.fossa.com/api/projects/custom%2B38165%2Fpycurl-docker.svg?type=shield)](https://app.fossa.com/projects/custom%2B38165%2Fpycurl-docker?ref=badge_shield)


pycurl 的 musllinux wheel 分发，另附装好的可运行镜像。两条线：`latest` 用自编 curl + OpenSSL，
`ja3-latest` 用 curl-impersonate + BoringSSL，提供浏览器 TLS 指纹。

- Docker Hub：<https://hub.docker.com/r/a76yyyy/pycurl>
- 源码：[qd-today/pycurl-docker](https://github.com/qd-today/pycurl-docker)

## 快速开始

```bash
docker pull a76yyyy/pycurl:latest        # 或 ja3-latest
```

```python
import pycurl

body = bytearray()
c = pycurl.Curl()
c.setopt(pycurl.URL, "https://example.com")
c.setopt(pycurl.WRITEFUNCTION, body.extend)
c.perform()
print(c.getinfo(pycurl.RESPONSE_CODE), len(body))
```

以 wheelhouse 作为依赖来源：

```dockerfile
# syntax=docker/dockerfile:1.7
FROM alpine:3.24
RUN --mount=type=bind,from=a76yyyy/pycurl:wheelhouse,source=/wheels,target=/w1 \
    apk add --no-cache $(cat /w1/system-packages.txt) uv && \
    uv pip install --system --break-system-packages --no-cache \
        --index-url https://pypi.org/simple \
        --extra-index-url file:///w1/simple \
        "pycurl==7.49.0"
```

| 写法 | 原因 |
|---|---|
| `apk add $(cat /w1/system-packages.txt)` | 清单是 wheelhouse 的运行时前置条件（解释器与 `libz`），写错会在这里构建失败 |
| `--index-url https://pypi.org/simple` | 默认索引是**最低**优先级，只用于兜底纯 Python 依赖 |
| `--extra-index-url file:///w1/simple` | first-index 策略下第一个含该包的索引胜出，因此本地那份一定被选中 |
| 发行名与 PyPI 同名 | wheel 用 PyPI 同名发行名，换回 PyPI 版不用改任何配置 |

`/w1/simple` 是 PEP 503 索引，链接为相对路径，可与 wheel 目录一起挂到任意位置。

`RUN --mount` 需要 BuildKit（首行 `# syntax=docker/dockerfile:1`）；Kaniko 等不支持时用
`COPY --from=<wheelhouse> /wheels /wheels`，代价是 `/wheels` 会进镜像层，且 `rm` 删不掉。

## 镜像内容

| 组件 | `latest` | `ja3-latest` |
|---|---|---|
| 基础镜像 | `alpine:3.24`；loong64 为 `ghcr.io/loong64/alpine:3.24` | `alpine:3.24` |
| Python | 3.14 | 3.14 |
| curl | 8.23.0（自编） | curl-impersonate（固定 commit，基于 curl 8.23.0） |
| TLS 库 | OpenSSL 3.5.9（Alpine 包，随 wheel 打进镜像） | BoringSSL（随 curl-impersonate 静态链接） |
| HTTP/3 后端 | ngtcp2 1.25.0 + nghttp3 1.18.0（自编） | ngtcp2 + BoringSSL |
| pycurl | 7.49.0 | 7.49.0 + `patches/pycurl-impersonate.patch`（`pycurl.IMPERSONATE`） |
| 系统包 | `python3`、`ca-certificates`、`tzdata` | 同左 |
| C 依赖位置 | `site-packages/pycurl.libs/` | 同左 |

两条线的 `import pycurl` 都只依赖解释器与 wheel 自带的库；`pycurl.libs/` 里是
`libcurl`、`libssl`/`libcrypto`（或 `libcurl-impersonate`、`libstdc++`）、`ngtcp2`、`nghttp3`、
`nghttp2`、`libidn2`、`libpsl`、`libbrotli`、`libzstd`、`c-ares` 与 GSSAPI 链。

## 支持的平台

| 平台 | `latest` | `ja3-latest` |
|---|---|---|
| `linux/amd64` | ✓ | ✓ |
| `linux/386` | ✓ | ✓ |
| `linux/arm64` | ✓ | ✓ |
| `linux/arm/v7` | ✓ | ✓ |
| `linux/arm/v6` | ✓ | ✓ |
| `linux/riscv64` | ✓ | ✓ |
| `linux/ppc64le` | ✓ | — |
| `linux/s390x` | ✓ | — |
| `linux/loong64` | ✓ | — |

ja3 线的平台范围由 BoringSSL 决定：`include/openssl/target.h` 的官方架构清单只有 x86 / x86_64 /
aarch64 / arm / mips64 / riscv64 等，因此 ppc64le 没有对应移植、s390x 是大端、loong64 无
loongarch 条目。

loong64 构建需 `--build-arg BASE_IMAGE=ghcr.io/loong64/alpine:3.24`（官方 alpine 无此架构，CI 会自动注入）。

## 标签

| 标签 | 内容 |
|---|---|
| `latest`、`lite-latest` | **同一个 manifest**：pycurl + 自编 curl + OpenSSL + ngtcp2/nghttp3 |
| `<ver>`、`lite-<ver>` | 同上，按发布版本固定 |
| `ja3-latest`、`ja3-lite-latest` | **同一个 manifest**：pycurl（含 `IMPERSONATE`）+ curl-impersonate + BoringSSL |
| `ja3-<ver>`、`ja3-lite-<ver>` | 同上，按发布版本固定 |
| `wheelhouse`、`<ver>-wheelhouse` | `scratch` + `/wheels`：不含指纹伪装那条线的 wheel 载体 |
| `dev`、`lite-dev`、`ja3-dev`、`ja3-lite-dev` | 上面各条线的开发版，跟随 main 分支的最新构建 |
| `ja3-wheelhouse`、`ja3-<ver>-wheelhouse` | 同上，含指纹伪装 |

`lite` 只是 `latest` 的别名：两个标签由一次 `imagetools create` 挂到同一个 manifest，digest 相同。
`<ver>` 与 `latest` 只在 tag 推送时产出，latest 始终追最近一次 tag；main 推送与 workflow_dispatch 只推进 dev，不动正式标签与滚动标签。

## 构建

wheel 的构建与镜像的组装分两步：第一步产出 wheel 与 curl 命令行，第二步用这份产物组装镜像。
两步之间可以用不同的架构环境（CI 里 arm 系列在原生 arm64 上编，组装统一在 x86_64）。

```bash
# ① 编译产物：/wheels 与 /opt/curl-cli
docker buildx build --platform linux/arm64 --target artifacts \
    --output type=local,dest=./dist .

# ② 可运行镜像
docker buildx build --platform linux/arm64 --target runtime \
    --build-context wheelsrc=./dist -t pycurl:latest .

# ③ wheelhouse 镜像（供上层 COPY --from / bind mount）
docker buildx build --platform linux/arm64 --target wheel-from-artifacts \
    --build-context wheelsrc=./dist -t pycurl:wheelhouse .

# 指纹伪装那条线把 -f Dockerfile.ja3 加上，三步相同
```

`--target runtime` 不传 `--build-context wheelsrc` 会失败：镜像里必须有 pycurl，宁可报错也不要
静默产出一个没有它的基座。

| 参数 | 默认 | 说明 |
|---|---|---|
| `ALPINE_VERSION` | `3.24` | 决定 Python 版本与 wheel 的 `cpXX` tag |
| `BASE_IMAGE` | `alpine:${ALPINE_VERSION}` | loong64 传 `ghcr.io/loong64/alpine:3.24` |
| `PYCURL_VERSION` | `7.49.0` | 与 wheel 名、`SHA256SUMS` 一致 |
| `CURL_VERSION` | `8.23.0` | 仅 `Dockerfile` |
| `NGTCP2_VERSION` / `NGHTTP3_VERSION` | `1.25.0` / `1.18.0` | 仅 `Dockerfile` |
| `CURL_IMPERSONATE_REF` | 固定 commit | 仅 `Dockerfile.ja3` |
| `AUDITWHEEL_VERSION` | `6.8.2` | 依赖收集与打标 |
| `APK_MIRROR` | 空 | 本地加速用，如 `https://mirrors.tuna.tsinghua.edu.cn` |
| `PIP_MIRROR` | 空 | 安装 auditwheel / 取 pycurl sdist 用；空 = 官方 PyPI |
| `GIT_DOMAIN` | `https://github.com` | 源码 clone 前缀（ngtcp2 / nghttp3 / curl-impersonate） |

国内构建三个镜像参数一起给：apk 与 pip 走镜像，源码 clone 走 `GIT_DOMAIN`。只给前两个时构建仍会
卡在从 GitHub 拉源码。

## 产物

```
/wheels/
  pycurl-<ver>-cpXXX-cpXXX-musllinux_1_2_<arch>.whl
  SHA256SUMS
  system-packages.txt
  simple/
    index.html
    pycurl/index.html        # href="../../<wheel>#sha256=<hex>"
```

`system-packages.txt` 是需要 `apk add` 的运行时包，一行一个：

| 包 | 为什么在清单里 |
|---|---|
| `python3` | 解释器本身；它的依赖 `zlib` 提供 `libz.so.1`，这是 wheel 里唯一没有被 `auditwheel` 收走的动态库 |
| `ca-certificates` | TLS 信任链（`/etc/ssl/certs/ca-certificates.crt`）。基础镜像自带 `ca-certificates-bundle`，显式列出以免换到更瘦的基座后静默失去证书校验 |
| `tzdata` | Python 的 `zoneinfo` 需要系统时区库；pycurl 本身不用，但本镜像作为上层基座，缺了会让 `ZoneInfo("Asia/Shanghai")` 直接失败 |

判定依据是 wheel 里 ELF 的 `DT_NEEDED` 闭包：除 musl 的 `libc` 与 `libz.so.1` 外全部被
`auditwheel` 收进 `pycurl.libs/`（可以用 `unzip -l pycurl-*.whl | grep libs/` 核对）。

| wheel 标签 | 含义 |
|---|---|
| `musllinux_1_2_<arch>` | 在 musl ≥ 1.2 上构建，除 musl 外不依赖系统库 |
| `linux_<arch>` | 只说明 CPU 架构，不是最终产物 |

## TLS 指纹（ja3 线）

`pycurl.IMPERSONATE` 由 `patches/pycurl-impersonate.patch` 提供（选项号 10999），一行开启完整
浏览器指纹；补丁同时清掉 pycurl 构造时强设的默认 User-Agent，使指纹自带的 UA 生效。

```python
import pycurl

c = pycurl.Curl()
c.setopt(pycurl.URL, "https://example.com")
c.setopt(pycurl.IMPERSONATE, "chrome152")
c.perform()
```

指纹目标覆盖 Chrome 151/152、Safari 27、Firefox 153–155（含 ECH、ZSTD、PQC 与 HTTP/3 指纹），
由 curl-impersonate 的 target 配置决定 TLS 套件、曲线、扩展、ALPN 与 HTTP/2 settings。要自定义 UA，
在其后 `setopt(pycurl.USERAGENT, ...)` 覆盖。

## 已知限制

- 镜像带 `curl` 命令行（build 阶段编好的那份，与 pycurl 扩展同源），二进制与它的私有库放在
  `/opt/curl-cli`，由 `/usr/local/bin/curl` 包装脚本限定 `LD_LIBRARY_PATH` 的作用域。ja3 线的
  CLI 是 `curl-impersonate`（`curl 8.23.0-IMPERSONATE`，BoringSSL），与 pycurl 扩展同一套补丁；
  main 线的 CLI 是普通 curl（OpenSSL）。
- wheel 的 `cp314` 与 `alpine:3.24` 的 Python 3.14 绑定；换 Python 小版本需要重新构建。
- BoringSSL 未提供 `SSL_CTX_set_ciphersuites()`，ja3 线的 `pycurl.TLS13_CIPHERS` 恒返回
  `CURLE_NOT_BUILT_IN`——TLS 1.3 套件由 impersonate target 内部配置。若不能用打过补丁的 pycurl，
  可 `curl_easy_setopt(handle, 10999, b"chrome152")`（10999 即 `CURLOPT_IMPERSONATE`）。
- chrome152 等 target 启用 `tls_permute_extensions`，TLS 扩展顺序逐连接随机置换，**ja3_hash 每次
  请求都不同**；比对指纹请用扩展排序归一化后的 ja3n。
- wheel 里只有 `ca-certificates` 提供的信任链，没有额外 CA；需要自定义 CA 时自行挂载并设
  `pycurl.CAINFO`。
- wheel 的 zip 条目带 mtime，构建不可逐字节复现；内容一致，`sha256` 每次不同。

## 维护者

<details>
<summary>版本参数</summary>

上游发新版时，改这里或 dispatch 时传同名输入即可构建新版本；产物版本与传入版本不一致时
构建失败（`--expect-version` 断言），不会出现「tag 写着新版、内容是旧版」。

| 参数 | 作用 | 默认值 |
|---|---|---|
| `pycurl_version` | pycurl 版本（从 PyPI sdist 自编） | 7.49.0 |
| `curl_version` | curl 源码版本（自编 libcurl） | 8.23.0 |
| `ngtcp2_version` | ngtcp2 源码版本（HTTP/2 over QUIC） | 1.25.0 |
| `nghttp3_version` | nghttp3 源码版本（HTTP/3） | 1.18.0 |
| `alpine_version` | alpine 版本，决定 Python 小版本与 wheel 的 cpXX tag | 3.24 |

`curl-impersonate` 固定到 commit，不随版本参数变化。

</details>

<details>
<summary>CI 结构</summary>

两条线各一个调用方（`Build Image.yml` / `Build Ja3 Image.yml`），共用 `.github/workflows/_image.yml`，
四段：plan → build-wheel → build → smoke → publish。矩阵与 manifest 校验脚本在
`.github/workflows/scripts/`。

- 仅 `workflow_dispatch` 与 tag push 触发
- 每平台两个 job：`build-wheel` 编 wheel 与 curl 命令行并导出成 artifact，`build` 用这份产物组装
  两个出口并推 digest。拆开是为了让 arm 系列在原生 arm64 runner 上编（`--output type=local`
  不支持多平台，只能按平台拆）
- `build` 统一跑 x86_64：arm64 runner 走内核 compat 模式时 Python 自报 `linux-aarch64`，
  uv 在那装 armv7l 的 wheel 会挂死
- 发布时两个出口各自 `push-by-digest`，artifact 按出口分名（`digest-wheelhouse-*` / `digest-runtime-*`）
- 同一条线的多个别名（`latest` 与 `lite-latest`）由**一次** `imagetools create` 挂到同一个 manifest
- 冒烟直接跑 runtime 镜像：`tests/smoke.py` 校验环境架构、`/wheels` 无残留、pycurl 版本与 HTTP/3
  特性位、`pycurl.libs/` 自包含、原生产物的 ELF `e_machine`、一次真实 HTTPS 请求；ja3 线另加
  `IMPERSONATE` 与本地抓包自算的 ja3n
- 闸门 fail-closed：有发布意图 && build 与 smoke 均 `success` && 平台集合完整，才合并 manifest

</details>


## License
[![FOSSA Status](https://app.fossa.com/api/projects/custom%2B38165%2Fpycurl-docker.svg?type=large)](https://app.fossa.com/projects/custom%2B38165%2Fpycurl-docker?ref=badge_large)