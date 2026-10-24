# **Pycurl-Docker**

**Python3.14:Alpine with pycurl ddddocr**

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker](https://github.com/qiandao-today/pycurl-docker)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:latest
```

## **VERSION**

- ALPINE_VERSION == 3.24
- PYTHON_VERSION == 3.14
- CURL_VERSION == 8.23.0
- OPENSSL_VERSION == 3.5.9 (LTS，支持至 2030-04)
- NGTCP2_VERSION == 1.25.0
- NGHTTP3_VERSION == 1.18.0
- PYCURL_VERSION == 7.48.0
- ONNXRUNTIME_TAG == v1.24.4
- DDDDOCR_VERSION == 1.6.1

支持 TLS1.3 & Http3(QUIC) & zstd & brotli & OnnxRuntime & ddddocr。

> 注：OpenSSL 3.5 LTS 已原生提供 QUIC API（ngtcp2 v1.12.0+ 直接对接），
> 不再需要已废弃的 quictls fork（2025-04 abandoned）。

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

# **Pycurl-Ja3-Docker**

**基于 [lexiforest/curl-impersonate](https://github.com/lexiforest/curl-impersonate) v2.4.0 的 JA3/TLS 指纹伪装版**

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker](https://github.com/qiandao-today/pycurl-docker)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:ja3-latest
```

## **VERSION**

- CURL_IMPERSONATE_VERSION == 2.4.0（基于 curl 8.23.0）
- 浏览器指纹：Chrome 151/152、Safari 27、Firefox 153-155（含 ECH/ZSTD/PQC/HTTP-3 指纹）
- BORINGSSL_COMMIT == 156c7b75ae9b（Chrome 150）
- QUIC 后端：ngtcp2 + BoringSSL（替代已停滞的 lwthiker 0.6.1 + cloudflare/quiche 方案）
- PYCURL_VERSION == 7.48.0（官方源码 + `patches/pycurl-impersonate.patch`：
  libcurl-impersonate 独有的 `CURLOPT_IMPERSONATE`（选项 10999）不在 pycurl 的 setopt
  类型表与常量表中，补丁为其补上，使 pycurl 可直接使用 impersonate 总开关）

用法示例：

```bash
# CLI：默认 curl 即以 chrome152 指纹发起请求
curl https://tls.browserleaks.com/json

# 指定其他指纹 / 使用 HTTP-3 指纹
curl-impersonate --impersonate chrome152 --http3 https://www.example.com
curl_safari270 https://www.example.com
```

pycurl 中使用（补丁新增 `pycurl.IMPERSONATE`，一行开启完整浏览器指纹）：

```python
import pycurl

c = pycurl.Curl()
c.setopt(pycurl.URL, "https://tls.browserleaks.com/json")
c.setopt(pycurl.IMPERSONATE, "chrome152")   # 由补丁提供；等价于 CLI --impersonate chrome152
# 指纹目标会自动配置 TLS 套件/曲线/扩展/ALPN/HTTP2 settings/浏览器请求头，无需手动复刻；
# 补丁还会清掉 pycurl 构造时强设的默认 User-Agent，让指纹自带的浏览器 UA 生效
# （如需自定义 UA，在本行之后再 setopt(pycurl.USERAGENT, ...) 即可覆盖）
c.perform()
```

实测（tls.browserleaks.com）：pycurl 路径与 CLI 路径的 **ja3n_hash 完全一致**
（`bd4930bd9b000ee684830e44bab76fdf`），User-Agent 为 Chrome/152.0.0.0。

> 注意 1：chrome152 等指纹启用 `tls_permute_extensions`，TLS 扩展顺序逐连接随机置换，
> 因此 **ja3_hash 每次请求都不同是设计行为**（CLI 层同样如此），比对指纹请用
> ja3n_hash（扩展排序归一化后的稳定值）。

> 注意 2：BoringSSL 未提供 `SSL_CTX_set_ciphersuites()` API，因此本构建的
> `pycurl.TLS13_CIPHERS` 恒返回 `CURLE_NOT_BUILT_IN`——TLS1.3 套件已由 impersonate
> 目标内部配置，无需也无法手动设置。若不能用打过补丁的 pycurl，也可用 ctypes
> 直调 `curl_easy_setopt(handle, 10999, b"chrome152")`（选项号即 `CURLOPT_IMPERSONATE`）。

# **Pycurl-Lite-Docker**

**Python3.14:Alpine-edge only with pycurl（不含 ddddocr/onnxruntime）**

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker](https://github.com/qiandao-today/pycurl-docker)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:lite-latest
```

## **VERSION**

- ALPINE_VERSION == edge
- PYTHON_VERSION == 3.14
- CURL_VERSION == 8.23.0
- OPENSSL_VERSION == 3.5.9 (LTS)
- NGTCP2_VERSION == 1.25.0
- NGHTTP3_VERSION == 1.18.0
- PYCURL_VERSION == 7.48.0

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

# **Pycurl-Docker-default**

Python:Alpine latest with pycurl - default ( **not support TLS1.3 & Http3 & OnnxRuntime & ddddocr** )

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker/tree/default](https://github.com/qiandao-today/pycurl-docker/tree/default)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:default-latest
```
