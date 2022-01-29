# 基础镜像
FROM python:3.9-alpine

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qiandao-today/pycurl-docker

# Envirenment for pycurl
ENV PYCURL_SSL_LIBRARY=openssl
ENV CURL_VERSION 7.81.0
ENV NUMPY_VERSION 1.22.1
ENV ONNXRUNTIME_TAG v1.10.0

# 换源 & For nghttp2-dev, we need testing respository.
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories && \
    echo https://dl-cdn.alpinelinux.org/alpine/edge/testing >>/etc/apk/repositories

# Install packages
RUN apk update && \
    apk add --update --no-cache --virtual build_deps cmake make perl autoconf g++ automake && \
    apk add --update --no-cache openrc redis bash git tzdata nano openssh-client \
    nghttp2-dev ca-certificates zlib-dev brotli-dev zstd-dev linux-headers libtool util-linux file \
    libidn2-dev libgsasl-dev krb5-dev lapack-dev libexecinfo-dev openblas-dev libbsd-dev

# Pip install numpy for alpine
RUN set -ex && \
    pip install --no-cache-dir 'setuptools<60.0.0' & \
    pip install --upgrade --no-cache-dir wheel nose cython && \
    wget https://github.com/numpy/numpy/releases/download/v$NUMPY_VERSION/numpy-$NUMPY_VERSION.tar.gz && \
    tar -zxvf numpy-$NUMPY_VERSION.tar.gz && \
    cd ./numpy-$NUMPY_VERSION && \
    [[ $(getconf LONG_BIT) = "32" && -z $(file /bin/busybox | grep -i "arm") ]] && ( \
    setarch i386 python3 setup.py build config_fc --fcompiler=gnu95 && \
    find . -type f -exec touch {} + && \
    setarch i386 python3 setup.py install config_fc --fcompiler=gnu95 ) || \
    ([[ -z $(file /bin/busybox | grep -i "arm") ]] && \
    pip install . || ( \
    python3 setup.py build config_fc --fcompiler=gnu95 && \
    find . -type f -exec touch {} + && \
    python3 setup.py install config_fc --fcompiler=gnu95 )) && \
    cd .. && \
    rm -rf ./numpy-$NUMPY_VERSION && \
    rm numpy-$NUMPY_VERSION.tar.gz

# git clone onnxruntime
RUN set -ex && \
    git clone --depth 1 --branch $ONNXRUNTIME_TAG --recursive https://github.com/Microsoft/onnxruntime && \
    rm ./onnxruntime/onnxruntime/test/providers/cpu/nn/string_normalizer_test.cc && \
    sed "s/    return filters/    filters += \[\'^test_strnorm.*\'\]\n    return filters/" -i ./onnxruntime/onnxruntime/test/python/onnx_backend_test_series.py 

# Pip install onnxruntime
RUN [[ $(getconf LONG_BIT) = "32" && -z $(file /bin/busybox | grep -i "arm") ]] && ( \
    setarch i386 ./onnxruntime/build.sh \
        --config Release \
        --parallel \
        --build_wheel \
        --enable_pybind \
        --cmake_extra_defines \
            CMAKE_CXX_FLAGS="-Wno-deprecated-copy -msse -msse2"\
            onnxruntime_BUILD_UNIT_TESTS=OFF \
            onnxruntime_OCCLUM=ON \
        --skip_tests ) || ( \
    ./onnxruntime/build.sh \
        --config Release \
        --parallel \
        --build_wheel \
        --enable_pybind \
        --cmake_extra_defines \
            CMAKE_CXX_FLAGS="-Wno-deprecated-copy"\
            onnxruntime_BUILD_UNIT_TESTS=OFF \
            onnxruntime_OCCLUM=ON \
        --skip_tests ) && \
    pip install --no-cache-dir ./onnxruntime/build/Linux/Release/dist/onnxruntime*.whl && \
    rm -rf ./onnxruntime

# Install openssl ngtcp2 nghttp3
RUN file /bin/busybox && \
    [[ $(getconf LONG_BIT) = "32" && -z $(file /bin/busybox | grep -i "arm") ]] && configtmp="setarch i386 ./config -m32" || configtmp="./config " && \
    wget https://curl.se/download/curl-$CURL_VERSION.tar.bz2 && \
    git clone --depth 1 -b OpenSSL_1_1_1m+quic https://github.com/quictls/openssl && \
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
        --with-libidn2 \
        --disable-static \
        --disable-ldap \
        --with-pic \
        --with-gssapi && \
    make && \
    make install && \
    cd .. && \
    rm -rf curl-$CURL_VERSION
    
# Pip install pycurl
RUN pip install --upgrade --no-cache-dir setuptools && \
    pip install --no-cache-dir --compile pycurl && \
    apk del build_deps && \
    rm -rf /var/cache/apk/* && \
    rm -rf /usr/share/man/* 
