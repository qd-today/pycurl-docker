# 基础镜像
FROM a76yyyy/ddddocr:latest

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qd-today/pycurl-docker

# Envirenment for pycurl
ENV PYCURL_SSL_LIBRARY=openssl
# OpenSSL 3.5 为 LTS（支持至 2030-04），且 3.5.0+ 原生提供 QUIC API，
# ngtcp2 v1.12.0+ 可直接对接，无需再使用已废弃的 quictls fork（2025-04 abandoned）
ENV SSL_VERSION=3.5.9
ENV CURL_VERSION=8.23.0
ENV NGTCP2_VERSION=1.25.0
ENV NGHTTP3_VERSION=1.18.0

# 本地构建加速（CI 在海外无需配置）：APK_MIRROR 例 https://mirrors.tuna.tsinghua.edu.cn，
# PIP_MIRROR 例 https://pypi.tuna.tsinghua.edu.cn/simple（与 ddddocr-docker 保持一致）
ARG APK_MIRROR=""
ARG PIP_MIRROR=""
# buildx 自动注入；OpenSSL 的配置目标由它显式决定（见下）
ARG TARGETARCH

# Install packages & Install openssl nghttp3 ngtcp2 curl & Pip install pycurl
RUN { [ -z "$APK_MIRROR" ] || sed -i "s|https://dl-cdn.alpinelinux.org|$APK_MIRROR|g" /etc/apk/repositories; } && \
    { [ -z "$PIP_MIRROR" ] || export PIP_INDEX_URL="$PIP_MIRROR"; } && \
    apk update && \
    apk add --update --no-cache bash git tzdata ca-certificates python3 py3-six && \
    apk add --update --no-cache --virtual .build_deps nano openssh-client \
    cmake make perl autoconf g++ automake linux-headers libtool util-linux file \
    libidn2-dev libgsasl-dev krb5-dev zstd-dev nghttp2-dev zlib-dev brotli-dev \
    python3-dev py3-pip py3-setuptools py3-wheel c-ares-dev libpsl-dev && \
    # Alpine 3.24 起 pyconfig.h 归 python3 包所有；基础镜像瘦身时误删了 /usr/include，
    # python3-dev 只补回其余头文件。编译 C 扩展前检测并恢复（幂等，存在则跳过）
    ls /usr/include/python3.*/pyconfig.h >/dev/null 2>&1 || apk fix python3 && \
    file /bin/busybox && \
    # OpenSSL 目标必须显式指定，不能靠 ./config 的 uname 自动探测：
    # 在 GitHub 原生 arm64 runner 上，32 位 ARM（armv6/armv7）容器由内核 compat 模式
    # 直接跑、不经 QEMU，uname -m 返回 aarch64 -> ./config 选中 linux-aarch64 ->
    # 拿 arm32 汇编器去编 md5-aarch64.S，报 bad instruction `ldp ...`（实测踩过）。
    # 显式映射后与宿主架构彻底解耦；linux-x86 目标自带 -m32，无需再 setarch/-m32。
    case "${TARGETARCH}" in \
        amd64)   openssl_target=linux-x86_64 ;; \
        arm64)   openssl_target=linux-aarch64 ;; \
        arm)     openssl_target=linux-armv4 ;; \
        386)     openssl_target=linux-x86 ;; \
        ppc64le) openssl_target=linux-ppc64le ;; \
        riscv64) openssl_target=linux64-riscv64 ;; \
        s390x)   openssl_target=linux64-s390x ;; \
        loong64) openssl_target=linux64-loongarch64 ;; \
        *) echo "不支持的 TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    wget https://curl.se/download/curl-$CURL_VERSION.tar.bz2 && \
    tar xjf curl-$CURL_VERSION.tar.bz2 && \
    rm curl-$CURL_VERSION.tar.bz2 && \
    git clone --depth 1 -b openssl-$SSL_VERSION https://github.com/openssl/openssl && \
    cd openssl && \
    # openssldir 必须与 Alpine 一致（/etc/ssl）：本构建会替换 /usr/lib/libssl.so.3、
    # libcrypto.so.3，apk-tools 等系统组件依赖 libcrypto 的默认 CA 路径做证书校验，
    # 用默认值（/usr/ssl）会导致系统级 TLS 校验失败
    ./Configure "$openssl_target" --prefix=/usr --libdir=lib --openssldir=/etc/ssl && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install_sw && \
    cd .. && \
    rm -rf openssl && \
    git clone --depth 1 -b v$NGHTTP3_VERSION https://github.com/ngtcp2/nghttp3 && \
    cd nghttp3 && \
    git submodule update --init && \
    autoreconf -fi && \
    ./configure PKG_CONFIG_PATH=/usr/lib/pkgconfig LDFLAGS="-Wl,-rpath,/usr/lib" --prefix=/usr --libdir=/usr/lib --enable-lib-only && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install && \
    cd .. && \
    rm -rf nghttp3 && \
    git clone --depth 1 -b v$NGTCP2_VERSION https://github.com/ngtcp2/ngtcp2 && \
    cd ngtcp2 && \
    git submodule update --init && \
    autoreconf -fi && \
    ./configure PKG_CONFIG_PATH=/usr/lib/pkgconfig LDFLAGS="-Wl,-rpath,/usr/lib" --prefix=/usr --libdir=/usr/lib --enable-lib-only --with-openssl && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install && \
    cd .. && \
    rm -rf ngtcp2 && \
    cd curl-$CURL_VERSION && \
    autoreconf -fi && \
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
        --enable-ares && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install && \
    cd .. && \
    rm -rf ./curl-$CURL_VERSION && \
    pip install --no-cache-dir --compile --break-system-packages pycurl && \
    # 构建期自检：HTTP3 特性在位 + pycurl 可 import（编译/链接问题在此暴露，不留到运行时）
    curl --version | grep -q HTTP3 && \
    python3 -c "import pycurl" && \
    apk del .build_deps && \
    # 运行时补齐被 .build_deps 清除的动态依赖（不用 --update：索引已在 RUN 开头刷新过，
    # 避免多余的索引拉取引入网络不确定性）
    apk add --no-cache libidn2 libgsasl zstd-libs zlib c-ares nghttp2 libpsl brotli-libs && \
    rm -rf /var/cache/apk/* && \
    rm -rf /usr/share/man/*
