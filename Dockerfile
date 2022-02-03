# 基础镜像
FROM a76yyyy/onnxruntime:latest

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qiandao-today/pycurl-docker

# Envirenment for pycurl
ENV PYCURL_SSL_LIBRARY=openssl
ENV CURL_VERSION=master
ENV DDDDOCR_VERSION=1.4.2

# Install packages & Install openssl ngtcp2 nghttp3 curl & Pip install pycurl
RUN apk update && \
    apk add --update --no-cache openrc redis bash git tzdata nano openssh-client ca-certificates\
    file libidn2-dev libgsasl-dev krb5-dev zstd-dev nghttp2-dev zlib-dev brotli-dev \
    python3 py3-numpy-dev py3-pip py3-setuptools py3-wheel py3-opencv py3-pillow python3-dev && \
    apk add --update --no-cache --virtual .build_deps cmake make perl autoconf g++ automake \
    linux-headers libtool util-linux && \
    file /bin/busybox && \
    [[ $(getconf LONG_BIT) = "32" && -z $(file /bin/busybox | grep -i "arm") ]] && configtmp="setarch i386 ./config -m32" || configtmp="./config " && \
    git clone --depth 1 -b $CURL_VERSION https://github.com/curl/curl && \
    git clone --depth 1 -b OpenSSL_1_1_1m+quic https://github.com/quictls/openssl && \
    git clone --depth 1 https://github.com/ngtcp2/nghttp3 && \
    git clone --depth 1 https://github.com/ngtcp2/ngtcp2 && \
    cd openssl && \
    echo $configtmp enable-tls1_3 --prefix=/usr && \
    $configtmp enable-tls1_3 --prefix=/usr && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install_sw && \
    cd .. && \
    rm -rf openssl && \
    cd nghttp3 && \
    autoreconf -i && \
    ./configure --prefix=/usr --enable-lib-only && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) check && \
    make install && \
    cd .. && \
    rm -rf nghttp3 && \
    cd ngtcp2 && \
    autoreconf -i && \
    ./configure PKG_CONFIG_PATH=/usr/lib/pkgconfig LDFLAGS="-Wl,-rpath,/usr/lib" --prefix=/usr --enable-lib-only && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) check && \
    make install && \
    cd .. && \
    rm -rf ngtcp2 && \
    cd curl && \
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
        --with-gssapi && \
    make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && \
    make install && \
    cd .. && \
    rm -rf curl && \
    pip install --no-cache-dir --compile pycurl && \
    wget https://files.pythonhosted.org/packages/5f/5d/4e6d39b8b0f8ddba32b30174bc4725ad811fa7d810a9e8d0a7512197bbf9/ddddocr-$DDDDOCR_VERSION.tar.gz && \
    tar -zxvf ddddocr-$DDDDOCR_VERSION.tar.gz  && \
    rm ddddocr-$DDDDOCR_VERSION.tar.gz && \
    cd ddddocr-$DDDDOCR_VERSION && \
    find . -type f -exec touch {} + && \
    sed -i '/install_package_data/d' setup.py && \
    sed -i '/install_requires/d' setup.py && \
    python setup.py install && \
    cd .. && \
    rm -rf /ddddocr-$DDDDOCR_VERSION && \
    apk del .build_deps && \
    rm -rf /var/cache/apk/* && \
    rm -rf /usr/share/man/* 
