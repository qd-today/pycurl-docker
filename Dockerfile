# 基础镜像
FROM python:alpine

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qiandao-today/pycurl-docker-default

# Envirenment for pycurl
ENV PYCURL_SSL_LIBRARY=openssl
ENV CURL_VERSION 7.82.0

# 换源 && Install packages
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories && \
    apk update && \
    apk add --update --no-cache openssl-dev bash git tzdata nano openssh-client \
    nghttp2-dev ca-certificates zlib-dev brotli-dev zstd-dev libidn2-dev libgsasl-dev krb5-dev && \
    apk add --update --no-cache --virtual curldeps autoconf g++ perl cmake make automake linux-headers libtool && \
    wget https://curl.haxx.se/download/curl-$CURL_VERSION.tar.bz2 && \
    tar xjvf curl-$CURL_VERSION.tar.bz2 && \
    rm curl-$CURL_VERSION.tar.bz2 && \
    cd curl-$CURL_VERSION && \
    autoreconf -fi && \
    LDFLAGS="-Wl,-rpath,/usr/lib" ./configure \
        --with-nghttp2=/usr \
        --prefix=/usr \
        --with-ssl \
        --enable-ipv6 \
        --enable-unix-sockets \
        --with-libidn2 \
        --disable-static \
        --disable-ldap \
        --with-pic \
        --with-gssapi && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install && \
    cd .. && \
    rm -r ./curl-$CURL_VERSION && \
    pip install --upgrade --no-cache-dir pip setuptools wheel \
    && pip install --no-cache-dir pycurl && \
    apk del curldeps && \
    rm -rf /var/cache/apk/* && \
    rm -rf /usr/share/man/* 
