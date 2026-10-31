# syntax=docker/dockerfile:1.7
#
# pycurl（不含 IMPERSONATE）：自编 curl + ngtcp2 / nghttp3，TLS 用 Alpine 的 OpenSSL 3.5
#
# 三个出口：
#   build   编译 ngtcp2 / nghttp3 / curl 与 pycurl，auditwheel 把 DT_NEEDED 闭包收进
#           pycurl.libs/，产出 /wheels（wheel + SHA256SUMS + system-packages.txt + 索引）
#   wheel   FROM scratch，只有 /wheels —— wheelhouse 镜像，供上层 bind mount 消费
#   runtime 只从 wheelhouse 装 pycurl，没有编译工具，也没有 /wheels
#
# 镜像里不带 ddddocr / onnxruntime：OCR 由上层从各自的 wheelhouse 装。因此这条线同时供给
# latest 与 lite-latest 两个 tag（同一个 manifest）。
ARG ALPINE_VERSION=3.24
# loong64 没有官方 alpine 镜像，构建时传 --build-arg BASE_IMAGE=ghcr.io/loong64/alpine:3.24
ARG BASE_IMAGE=alpine:${ALPINE_VERSION}

########################################################################
# 构建：编译传输栈 + pycurl
########################################################################
FROM ${BASE_IMAGE} AS build

ARG APK_MIRROR=""
ARG PIP_MIRROR=""
ARG GIT_DOMAIN="https://github.com"
ARG PYCURL_VERSION=7.48.0
# OpenSSL 3.5 为 LTS（支持至 2030-04），3.5.0+ 原生提供 QUIC API，ngtcp2 1.12+ 可直接对接，
# 无需已废弃的 quictls fork。Alpine 3.24 的 openssl 已是 3.5.9（与本文件旧版自编版本同号），
# 直接用发行版包：省一次全量编译，CA 路径也天然是 /etc/ssl
ARG CURL_VERSION=8.23.0
ARG NGTCP2_VERSION=1.25.0
ARG NGHTTP3_VERSION=1.18.0
ARG AUDITWHEEL_VERSION=6.8.2

LABEL maintainer="a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qd-today/pycurl-docker

RUN if [ -n "${APK_MIRROR}" ]; then \
        sed -i "s|https://dl-cdn.alpinelinux.org|${APK_MIRROR%/}|g" /etc/apk/repositories; \
    fi \
 && cat /etc/apk/repositories

# 构建阶段整层都会被丢弃，不需要 .build_deps 那套「装完再删、把被覆盖的库备份再还原」的
# 把戏。patchelf 是 auditwheel 改写 RPATH 时调用的外部程序
RUN apk add --no-cache \
        autoconf automake libtool m4 pkgconf \
        build-base linux-headers perl bzip2 git wget \
        openssl-dev \
        nghttp2-dev zlib-dev brotli-dev libidn2-dev libgsasl-dev krb5-dev \
        zstd-dev c-ares-dev libpsl-dev \
        python3 python3-dev py3-pip py3-setuptools py3-wheel \
        patchelf

RUN set -eux; \
    if [ -n "${PIP_MIRROR}" ]; then pip_args="-i ${PIP_MIRROR}"; else pip_args=""; fi; \
    python3 -m pip install --no-cache-dir --break-system-packages \
        ${pip_args} "auditwheel==${AUDITWHEEL_VERSION}"; \
    python3 -m auditwheel --version

# --prefix=/usr --libdir=lib：装进系统路径，auditwheel 才能在默认搜索路径里定位到它们
RUN set -eux; \
    git clone --depth 1 -b v${NGHTTP3_VERSION} ${GIT_DOMAIN}/ngtcp2/nghttp3 /tmp/nghttp3; \
    cd /tmp/nghttp3; \
    git submodule update --init; \
    autoreconf -fi; \
    ./configure --prefix=/usr --libdir=/usr/lib --enable-lib-only; \
    make -j"$(nproc)"; \
    make install; \
    cd /; rm -rf /tmp/nghttp3

RUN set -eux; \
    git clone --depth 1 -b v${NGTCP2_VERSION} ${GIT_DOMAIN}/ngtcp2/ngtcp2 /tmp/ngtcp2; \
    cd /tmp/ngtcp2; \
    git submodule update --init; \
    autoreconf -fi; \
    ./configure --prefix=/usr --libdir=/usr/lib --enable-lib-only --with-openssl; \
    make -j"$(nproc)"; \
    make install; \
    cd /; rm -rf /tmp/ngtcp2

# 发布 tarball 自带 configure，不需要 autoreconf。--disable-static：wheel 里要的是动态库
RUN set -eux; \
    cd /tmp; \
    wget -q https://curl.se/download/curl-${CURL_VERSION}.tar.bz2; \
    tar xjf curl-${CURL_VERSION}.tar.bz2; \
    rm curl-${CURL_VERSION}.tar.bz2; \
    cd /tmp/curl-${CURL_VERSION}; \
    ./configure \
        --with-openssl=/usr \
        --with-nghttp2=/usr \
        --with-nghttp3=/usr \
        --with-ngtcp2=/usr \
        --prefix=/usr \
        --libdir=/usr/lib \
        --enable-ipv6 \
        --enable-unix-sockets \
        --with-libidn2 \
        --disable-static \
        --disable-ldap \
        --with-pic \
        --with-gssapi \
        --enable-ares; \
    make -j"$(nproc)"; \
    make install; \
    curl --version | grep -q HTTP3; \
    cd /; rm -rf /tmp/curl-${CURL_VERSION}

# pycurl 官方只有 sdist（PyPI 无 musllinux 轮子），这里编出 linux_<arch> wheel，交给
# auditwheel 改标签。--no-build-isolation：用 apk 的 setuptools/wheel，不去 PyPI 再取一遍
COPY src/pack_wheel.py /usr/local/bin/pack_wheel.py

RUN set -eux; \
    if [ -n "${PIP_MIRROR}" ]; then pip_args="-i ${PIP_MIRROR}"; else pip_args=""; fi; \
    PYCURL_SSL_LIBRARY=openssl \
    python3 -m pip wheel --no-cache-dir --no-build-isolation --no-deps \
        ${pip_args} --wheel-dir /raw "pycurl==${PYCURL_VERSION}"; \
    python3 /usr/local/bin/pack_wheel.py \
        --wheel-dir /raw \
        --out-dir /wheels \
        --expect-version "${PYCURL_VERSION}" \
        --require-lib 'libcurl*.so.4*' \
        --require-lib 'libssl*.so.3*' \
        --require-lib 'libcrypto*.so.3*' \
        --require-lib 'libngtcp2*.so.*' \
        --require-lib 'libnghttp3*.so.*'

# apk 清单随 wheelhouse 发布，上层照单安装即可，不必各自维护
COPY system-packages.txt /wheels/system-packages.txt

# 把 curl 命令行收进 /opt/curl-cli：二进制 + 它实际链接的库。
# 用 ldd 结果收集而不是手写库名：库的集合随编译配置变（HTTP/3 后端、TLS 实现），
# 手写清单迟早会漏一个，报错还表现在运行期。
RUN set -eux; \
    mkdir -p /opt/curl-cli; \
    cp /usr/bin/curl /opt/curl-cli/curl; \
    ldd /usr/bin/curl 2>/dev/null \
        | sed -n 's/.*=> \(\/[^ ]*\).*/\1/p; s/^\s*\(\/[^ ]*\) (0x[0-9a-f]*).*/\1/p' \
        | sort -u \
        | while read -r lib; do cp -L "$lib" /opt/curl-cli/ 2>/dev/null || true; done; \
    ls -1 /opt/curl-cli


RUN set -eux; \
    python3 /usr/local/bin/pack_wheel.py --emit-index --out-dir /wheels; \
    cd /wheels; \
    sha256sum ./*.whl > SHA256SUMS; \
    ls -l; \
    cat SHA256SUMS; \
    python3 -m pip install --no-cache-dir --break-system-packages \
        --no-index --find-links /wheels "pycurl==${PYCURL_VERSION}"; \
    python3 -c "import pycurl; assert pycurl.version_info()[4] & pycurl.CURL_VERSION_HTTP3"

########################################################################
# wheelhouse 出口（CI 用 --output type=local 或按 digest 推送）
########################################################################
FROM scratch AS wheel

COPY --from=build /wheels/ /wheels/

########################################################################
# 运行时出口：只有解释器 + wheelhouse 里的 pycurl，没有编译工具、没有 OCR
#
# 不用 COPY --from=build /wheels + RUN rm -rf：COPY 与 RUN 是两层，删掉的字节仍留在下层。
# bind mount 只在这条 RUN 里存在，装完随 layer 一起消失，镜像里没有 /wheels。
########################################################################
FROM ${BASE_IMAGE} AS runtime

ARG PYCURL_VERSION=7.48.0
ARG APK_MIRROR=""
ARG PIP_MIRROR=""

LABEL maintainer="a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qd-today/pycurl-docker

RUN if [ -n "${APK_MIRROR}" ]; then \
        sed -i "s|https://dl-cdn.alpinelinux.org|${APK_MIRROR%/}|g" /etc/apk/repositories; \
    fi \
 && cat /etc/apk/repositories

# 清单写错会在这里构建失败，不会等到上层才发现。uv 是工具不是运行时依赖，单独列出
RUN --mount=type=bind,from=build,source=/wheels,target=/w \
    apk add --no-cache $(cat /w/system-packages.txt) uv

# --no-index + --find-links：保证 pycurl 一定来自这个 wheelhouse，而不是 PyPI 上的旧版本。
# --no-cache：否则解压副本会写进 /root/.cache/uv，原样留在镜像层里
RUN --mount=type=bind,from=build,source=/wheels,target=/w \
    set -eux; \
    uv pip install --system --break-system-packages --no-cache \
        --index-url "${PIP_MIRROR:-https://pypi.org/simple}" \
        --extra-index-url file:///w/simple \
        "pycurl==${PYCURL_VERSION}"; \
    uv pip check --system; \
    python3 -c "import pycurl; print(pycurl.version)"


# curl 命令行：二进制与它的私有库放在一起，用包装脚本限定 LD_LIBRARY_PATH 的作用域，
# 免得污染镜像里其他进程的库解析。
COPY --from=build /opt/curl-cli /opt/curl-cli
RUN set -eux; \
    printf '#!/bin/sh\nexec env LD_LIBRARY_PATH=/opt/curl-cli /opt/curl-cli/curl "$@"\n' \
        > /usr/local/bin/curl; \
    chmod +x /usr/local/bin/curl; \
    curl --version | head -1

CMD ["python3", "-c", "import pycurl; print(pycurl.version)"]
