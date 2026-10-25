# pycurl Docker 镜像（Alpine）

基于 Alpine 的 pycurl 镜像。同一仓库三条发布线，按需选择：

| 标签 | 内容 |
|---|---|
| `latest` | pycurl + ddddocr / onnxruntime，自编 OpenSSL 与 ngtcp2 / nghttp3 |
| `ja3-latest` | 在 `latest` 基础上换成 curl-impersonate + BoringSSL，提供 TLS 指纹伪装 |
| `lite-latest` | 仅 pycurl，Alpine 原生 OpenSSL，不含 OCR |
| `ja3-lite-latest` | `lite` 的基座 + curl-impersonate，有指纹伪装、无 OCR |

- Docker Hub：<https://hub.docker.com/r/a76yyyy/pycurl>
- 源码：[qd-today/pycurl-docker](https://github.com/qd-today/pycurl-docker)

三条线都支持 TLS 1.3、HTTP/3（QUIC）、zstd 与 brotli；`latest` 与 `ja3-latest` 另带
ddddocr 与 onnxruntime。

## 快速开始

```bash
docker pull a76yyyy/pycurl:latest      # 或 ja3-latest / lite-latest
```

在 Python 中使用（三个标签一致）：

```python
import pycurl

body = bytearray()
c = pycurl.Curl()
c.setopt(pycurl.URL, "https://example.com")
c.setopt(pycurl.WRITEFUNCTION, body.extend)
c.perform()
print(c.getinfo(pycurl.RESPONSE_CODE), len(body))
```

以本镜像为基础（`latest` 与 `ja3-latest` 已包含 ddddocr，可直接 `import ddddocr`）：

```dockerfile
FROM a76yyyy/pycurl:latest
```

## 镜像内容

| 组件 | latest | ja3-latest | lite-latest | ja3-lite-latest |
|---|---|---|---|---|
| 基础镜像 | `a76yyyy/ddddocr:latest` | `a76yyyy/ddddocr:latest` | `alpine:3.24` | `alpine:3.24` |
| Python | 3.14 | 3.14 | 3.14 | 3.14 |
| curl | 8.23.0（自编） | curl-impersonate（固定 commit `df38987`，基于 curl 8.23.0） | 8.23.0（自编） | 同 ja3-latest |
| TLS 库 | OpenSSL 3.5.9 LTS（自编） | BoringSSL（随 curl-impersonate 的固定 commit） | OpenSSL 3.5.9 LTS（Alpine 包） | BoringSSL |
| HTTP/3 后端 | ngtcp2 1.25.0 + nghttp3 1.18.0 | ngtcp2 + BoringSSL | 同 latest | ngtcp2 + BoringSSL |
| pycurl | 7.48.0（`PYCURL_VERSION` 可覆盖） | 7.48.0 + `patches/pycurl-impersonate.patch` | 7.48.0（`PYCURL_VERSION` 可覆盖） | 同 ja3-latest |
| OCR | ddddocr 1.6.1 + onnxruntime 1.24.4 | 同 latest | 无 | 无 |

OpenSSL 3.5 是 LTS（支持至 2030-04），原生提供 QUIC API，ngtcp2 v1.12.0 起可直接对接，
因此不需要已停止维护的 quictls fork。

## TLS 指纹伪装（ja3-latest）

基于 [lexiforest/curl-impersonate](https://github.com/lexiforest/curl-impersonate) 的 superbuild
（固定 commit `df38987`，构建脚本里的 `CURL_IMPERSONATE_REF` 可覆盖），浏览器指纹覆盖 Chrome 151/152、Safari 27、Firefox 153–155（含 ECH、ZSTD、
PQC 与 HTTP/3 指纹）。

命令行：镜像内的 `curl` 默认以 chrome152 发起请求，也可显式指定目标或使用其它包装脚本。

```bash
curl https://tls.browserleaks.com/json
curl-impersonate --impersonate chrome152 --http3 https://www.example.com
curl_safari270 https://www.example.com
```

pycurl：`pycurl.IMPERSONATE` 由补丁提供，一行开启完整浏览器指纹。

```python
import pycurl

c = pycurl.Curl()
c.setopt(pycurl.URL, "https://tls.browserleaks.com/json")
c.setopt(pycurl.IMPERSONATE, "chrome152")   # 等价于 CLI 的 --impersonate chrome152
c.perform()
```

指纹目标会自动配置 TLS 套件、曲线、扩展、ALPN、HTTP/2 settings 与浏览器请求头，无需手动
复刻；补丁同时清掉 pycurl 构造时强设的默认 User-Agent，使指纹自带的 UA 生效。要自定义 UA，
在其后 `setopt(pycurl.USERAGENT, ...)` 覆盖即可。

两点限制：

- chrome152 等指纹启用 `tls_permute_extensions`，TLS 扩展顺序逐连接随机置换，因此
  **ja3_hash 每次请求都不同**（命令行同样如此）。比对指纹请用 ja3n_hash，即扩展排序归一化
  后的稳定值。
- BoringSSL 未提供 `SSL_CTX_set_ciphersuites()`，本线的 `pycurl.TLS13_CIPHERS` 恒返回
  `CURLE_NOT_BUILT_IN`——TLS 1.3 套件由 impersonate 目标内部配置，无需也无法手动设置。
  若不能使用打过补丁的 pycurl，可用 ctypes 直调 `curl_easy_setopt(handle, 10999, b"chrome152")`，
  10999 即 `CURLOPT_IMPERSONATE`。

## 支持的平台

| 平台 | latest | ja3-latest | lite-latest | ja3-lite-latest |
|---|---|---|---|---|
| linux/amd64 | ✓ | ✓ | ✓ | ✓ |
| linux/386 | ✓ | ✓ | ✓ | ✓ |
| linux/arm64 | ✓ | ✓ | ✓ | ✓ |
| linux/arm/v7 | ✓ | ✓ | ✓ | ✓ |
| linux/arm/v6 | ✓ | ✓ | ✓ | ✓ |
| linux/ppc64le | ✓ | — | ✓ | — |
| linux/riscv64 | ✓ | ✓ | ✓ | ✓ |
| linux/s390x | ✓ | — | ✓ | — |
| linux/loong64 | ✓ | — | ✓ | — |

ja3 线的平台范围由 BoringSSL 决定，而非 Dockerfile 的选择。BoringSSL 在
`include/openssl/target.h` 的官方架构清单只有 x86 / x86_64 / aarch64 / arm / mips64 /
riscv64 / pnacl / wasm / asmjs / myriad2，因此：

- **ppc64le**：不在清单内。虽是 little-endian，给 `target.h` 打补丁并关掉
  `-Werror=unused-function` 可以编过，但要长期维护对加密库的源码补丁、每次升级
  curl-impersonate 都需重新核对，不纳入发布。需要时可用 `workflow_dispatch` 指定
  `platforms=linux/ppc64le` 手工构建，不承诺可用。
- **s390x**：大端。`target.h` 原文为 “Functions will not produce the correct answer on
  other systems”，能编过也会算错，不支持。
- **loong64**：BoringSSL 没有 loongarch 条目。

`latest` 与 `lite-latest` 使用 OpenSSL，不受上述限制；qd 在 ppc64le / s390x / riscv64 上可正常
运行，只是用不到 TLS 指纹伪装。

## 标签

| 标签 | 含义 |
|---|---|
| `latest`、`ja3-latest`、`lite-latest`、`ja3-lite-latest` | 四条线各自的最新构建 |
| `<版本>`、`ja3-<版本>`、`lite-<版本>`、`ja3-lite-<版本>` | 版本号标签，与仓库发布版本对齐 |

发布由 tag 推送触发，四条线各自构建全平台并合并 manifest；日常验证走 workflow_dispatch，
默认不推送任何镜像。

## 构建

四个 Dockerfile 对应四条线：`Dockerfile`（latest）、`Dockerfile.ja3`（ja3-latest）、
`Dockerfile.lite`（lite-latest）、`Dockerfile.ja3.lite`（ja3-lite-latest）。

派生文件只换基座、其余与基准逐字相同，CI 会校验这一点：
`Dockerfile.ja3.lite` 取自 `Dockerfile.ja3`，`Dockerfile.lite.loong64` 取自 `Dockerfile.lite`。

`latest` 与 `lite` 自编 curl，配置项一致：

```bash
LDFLAGS="-Wl,-rpath,/usr/lib" ./configure \
    --with-openssl=/usr \
    --with-nghttp2=/usr \
    --with-nghttp3=/usr \
    --with-ngtcp2=/usr \
    --prefix=/usr \
    --enable-ipv6 \
    --enable-unix-sockets \
    --with-libidn2 \
    --disable-static \
    --disable-ldap \
    --with-pic \
    --with-gssapi \
    --enable-ares
```

`ja3` 线的 curl 由 curl-impersonate 的 superbuild 产出，配置由上游决定。

pycurl 版本由 `PYCURL_VERSION` 构建参数固定（默认 7.48.0），三条线一致；需要其它版本时
`--build-arg PYCURL_VERSION=x.y.z`，与 `APK_MIRROR` / `PIP_MIRROR` 一起传入即可。

三个构建参数默认即 CI 行为，国内构建可按下表覆盖：

| 参数 | 作用 | 国内构建时的示例 |
|---|---|---|
| `APK_MIRROR` | apk 包源 | `https://mirrors.tuna.tsinghua.edu.cn` |
| `PIP_MIRROR` | pip 索引（pycurl sdist 也走它） | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| `GIT_DOMAIN` | 源码 clone 的 GitHub 前缀，覆盖 openssl / nghttp3 / ngtcp2 / curl-impersonate | `https://gh-proxy.com/https://github.com` |

```bash
docker buildx build --platform linux/ppc64le \
  --build-arg APK_MIRROR=https://mirrors.tuna.tsinghua.edu.cn \
  --build-arg PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg GIT_DOMAIN=https://gh-proxy.com/https://github.com \
  -f Dockerfile -t pycurl:test . --load
```

国内构建建议三个参数一起给：apk 与 pip 走镜像，源码 clone 走 `GIT_DOMAIN`。只给前两个时，
构建仍会卡在从 GitHub 拉 openssl / nghttp3 / ngtcp2 / curl-impersonate。

---

<details>
<summary>CI 架构（维护者）</summary>

四条线共用 `.github/workflows/_image.yml`（workflow_call），各自只有一个约 30 行的调用方，
差异全部由 `with` 传入。

### 流水线

```
plan    按 dispatch 的 platforms 输入计算架构分组
  ├─ build x86      (ubuntu-latest)     amd64(原生) + 386
  ├─ build arm      (ubuntu-24.04-arm)  arm64(原生) + armv7 + armv6
  ├─ build ppc64le  (ubuntu-latest)     ppc64le + s390x
  ├─ build riscv64  (ubuntu-latest)     riscv64
  └─ build loong64  (ubuntu-latest)     loong64（仅 latest 线）
        ↓ 全部构建成功
  smoke（每个平台一个 job）  复用构建层缓存重建镜像后逐平台实跑
        ↓ 全部冒烟通过
  publish  各架构组按 digest 合并成正式 tag → 校验 manifest 平台完整性
```

### 设计原则

1. **发布即全绿**：`publish` 需要所有构建与所有冒烟成功，测试失败不产生 tag。
2. **零重复编译**：构建阶段把层缓存写入 GHA cache（scope 按「标签-架构组」隔离），冒烟与
   发布阶段 `cache-from` 命中同一份缓存，同一次提交不重复编译。
3. **不产临时 tag**：发布模式下各架构组以 `push-by-digest` 推到 Docker Hub（不带 tag），
   `publish` 用 `imagetools create` 合并成正式多架构 tag。

### 触发与跳过

tag 推送始终全量构建。workflow_dispatch 会先比对「该分支最近一次成功运行的 commit」，
按变体判定是否需要重建：共享输入（`patches/`、`tests/`、`_image.yml`）改动重建全部；
某个 Dockerfile 改动只重建对应那条线，派生文件跟着基准走（改 `Dockerfile.ja3` 会同时
重建 ja3 与 ja3-lite）；只改文档、或同一 commit 已有成功运行则整体跳过。`force` 可强制重跑。

### workflow_dispatch 输入

| 输入 | 默认 | 说明 |
|---|---|---|
| `push` | false | 不勾选即只构建与冒烟，不发布任何镜像 |
| `platforms` | 空（该标签的全部平台） | 平台子集用于加速迭代；子集构建默认禁止发布 |
| `native_arm` | true | 用 `ubuntu-24.04-arm` 原生构建 arm64；该 runner 不可用时取消勾选回退 QEMU |

### 冒烟

`tests/smoke.py` 按标签与 OCR 期望显式传参：

```bash
docker run --rm -i --platform <platform> <image> \
  python3 - <main|ja3|lite> <ocr|nocr> <platform> < tests/smoke.py
```

- pycurl 可导入、libcurl 特性位含 HTTP/3、真实 HTTPS 请求成功
- ja3 线额外在本地起 TCP 监听，直接读 ClientHello 计算 ja3n，与 chrome152 的期望值比对，
  不依赖外部站点
- 按目标平台校验原生产物（pycurl 扩展、libcurl、libssl）ELF 头中的 `e_machine`

</details>
