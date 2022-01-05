# 基础镜像
FROM python:3.9-alpine

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qiandao-today/pycurl-docker

# Envirenment for pycurl
ENV PYCURL_SSL_LIBRARY=openssl
ENV CURL_VERSION 7.80.0

# 换源 & For nghttp2-dev, we need testing respository.
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories && \
    echo https://dl-cdn.alpinelinux.org/alpine/edge/testing >>/etc/apk/repositories 

# Install packages
RUN apk update && \
    apk add --update --no-cache openrc redis bash git autoconf g++ tzdata nano openssh-client automake \
    nghttp2-dev ca-certificates zlib zlib-dev brotli brotli-dev zstd zstd-dev linux-headers libtool util-linux file

RUN file /bin/busybox && \
    [[ $(getconf LONG_BIT) = "32" && -z $(file /bin/busybox | grep "arm") ]] && configtmp="setarch i386 ./config -m32" || configtmp="./config " && \
    apk add --update --no-cache --virtual curldeps make perl && \
    wget https://curl.se/download/curl-$CURL_VERSION.tar.bz2 && \
    git clone --depth 1 -b OpenSSL_1_1_1l+quic https://github.com/quictls/openssl && \
    git clone https://github.com/ngtcp2/nghttp3 && \
    git clone https://github.com/ngtcp2/ngtcp2 && \
    cd openssl && \
    echo $configtmp enable-tls1_3 --prefix=/usr && \
    $configtmp enable-tls1_3 --prefix=/usr && \
    make && \
    make install_sw && \
    cd .. && \
    rm -rf openssl && \
    cd nghttp3 && \
    autoreconf -i && \
    ./configure --prefix=/usr --enable-lib-only && \
    make && \
    make install && \
    cd .. && \
    rm -rf nghttp3 && \
    cd ngtcp2 && \
    autoreconf -i && \
    ./configure PKG_CONFIG_PATH=/usr/lib/pkgconfig:/usr/lib/pkgconfig LDFLAGS="-Wl,-rpath,/usr/lib" --prefix=/usr --enable-lib-only && \
    make && \
    make install && \
    cd .. && \
    rm -rf ngtcp2 && \
    tar xjvf curl-$CURL_VERSION.tar.bz2 && \
    rm curl-$CURL_VERSION.tar.bz2 && \
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
        --without-libidn \
        --disable-static \
        --disable-ldap \
        --with-pic && \
    make && \
    make install && \
    cd .. && \
    rm -rf curl-$CURL_VERSION && \
    apk del curldeps
    
# Pip install modules
RUN pip install --upgrade setuptools && \
    pip install --upgrade wheel && \
    pip install pycurl && \
    rm -rf /var/cache/apk/* && \
    rm -rf /usr/share/man/* 

