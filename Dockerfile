# 基础镜像
FROM python:3.9-alpine

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qiandao-today/pycurl-docker-default

# Envirenment for pycurl
ENV PYCURL_SSL_LIBRARY=openssl
ENV CURL_VERSION 7.81.0

# 换源 & For nghttp2-dev, we need testing respository.
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories && \
    echo https://dl-cdn.alpinelinux.org/alpine/edge/testing >>/etc/apk/repositories 

# Install packages
RUN apk update && \
    apk add --update --no-cache openssl openssl-dev openrc redis bash git autoconf g++ tzdata nano openssh-client automake \
    nghttp2-dev ca-certificates zlib zlib-dev brotli brotli-dev zstd zstd-dev linux-headers libtool \
    libidn2 libidn2-dev libgsasl libgsasl-dev krb5 krb5-dev

RUN apk add --update --no-cache --virtual curldeps make perl && \
    wget https://curl.se/download/curl-$CURL_VERSION.tar.bz2 && \
    tar xjvf curl-$CURL_VERSION.tar.bz2 && \
    rm curl-$CURL_VERSION.tar.bz2 && \
    cd curl-$CURL_VERSION && \
    ./configure \
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
    make && \
    make install && \
    cd .. && \
    rm -r curl-$CURL_VERSION && \
    apk del curldeps
    
# Pip install modules
RUN pip install --upgrade setuptools \
    && pip install --upgrade wheel \
    && pip install pycurl \
    && rm -rf /var/cache/apk/* \
    && rm -rf /usr/share/man/* 

