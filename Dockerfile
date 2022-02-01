# 基础镜像
FROM alpine:edge

# 维护者信息
LABEL maintainer "a76yyyy <q981331502@163.com>"
LABEL org.opencontainers.image.source=https://github.com/qiandao-today/pycurl-docker

# Envirenment for pycurl
ENV ONNXRUNTIME_TAG=master

# 换源 & Install packages
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories && \
    apk update && \
    apk add --update --no-cache openrc redis bash git tzdata nano openssh-client ca-certificates\
    file libidn2-dev libgsasl-dev krb5-dev zstd-dev nghttp2-dev zlib-dev brotli-dev \
    python3 py3-numpy-dev py3-pip py3-setuptools py3-wheel py3-opencv py3-pillow && \
    ln -s /usr/bin/python3 /usr/bin/python

# git clone onnxruntime & Pip install onnxruntime
RUN apk add --update --no-cache --virtual .build_deps cmake make perl autoconf g++ automake \
    linux-headers libtool util-linux libexecinfo-dev openblas-dev python3-dev \
    protobuf-dev flatbuffers-dev date-dev gtest-dev eigen-dev  && \
    git clone --depth 1 --branch $ONNXRUNTIME_TAG https://github.com./Microsoft/onnxruntime && \
    cd /onnxruntime && \
    git submodule update --init --recursive && \
    cd .. && \
    rm /onnxruntime/onnxruntime/test/providers/cpu/nn/string_normalizer_test.cc && \
    sed "s/    return filters/    filters += \[\'^test_strnorm.*\'\]\n    return filters/" \
    -i /onnxruntime/onnxruntime/test/python/onnx_backend_test_series.py && \
    [[ $(getconf LONG_BIT) = "32" && -z $(file /bin/busybox | grep -i "arm") ]] &&  \
    { bashtmp='setarch i386 /onnxruntime/build.sh' && cxxtmp='-msse -msse2'; } || {\
    [[ -z $(file /bin/busybox | grep -i "arm") ]] && \
    { bashtmp='/onnxruntime/build.sh' && cxxtmp=''; } || \
    { [[ $(getconf LONG_BIT) = "32" ]] && \
    { bashtmp='setarch arm /onnxruntime/build.sh' && cxxtmp=''; } || \
    { bashtmp='setarch arm64 /onnxruntime/build.sh' && cxxtmp=''; }; }; } && \
    echo 'add_subdirectory(${PROJECT_SOURCE_DIR}/external/nsync EXCLUDE_FROM_ALL)' >> /onnxruntime/cmake/CMakeLists.txt && \
    echo $bashtmp && echo $cxxtmp && \
    $bashtmp --config MinSizeRel  \
        --parallel \
        --build_wheel \
        --enable_pybind \
        --cmake_extra_defines \
            CMAKE_CXX_FLAGS="-Wno-deprecated-copy -Wno-unused-variable $cxxtmp"\
            onnxruntime_BUILD_UNIT_TESTS=OFF \
            onnxruntime_BUILD_SHARED_LIB=OFF \
            onnxruntime_USE_PREINSTALLED_EIGEN=ON \
            onnxruntime_PREFER_SYSTEM_LIB=ON \
            eigen_SOURCE_PATH=/usr/include/eigen3 \
        --skip_tests && \
    apk del .build_deps && \
    apk add libprotobuf-lite && \
    pip install --no-cache-dir ./onnxruntime/build/Linux/MinSizeRel/dist/onnxruntime*.whl && \
    ln -s $(python -c 'import warnings;warnings.filterwarnings("ignore");\
    from distutils.sysconfig import get_python_lib;print(get_python_lib())')/onnxruntime/capi/libonnxruntime_providers_shared.so /usr/lib && \
    rm -rf ./onnxruntime

    # git clone --depth 1 --branch $ONNXRUNTIME_TAG https://github.com.cnpmjs.org/Microsoft/onnxruntime && \
    # cd /onnxruntime && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" .gitmodules && \
    # git submodule sync && \
    # git submodule update --init && \
    # cd /onnxruntime/cmake/external/onnx && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" .gitmodules && \
    # git submodule sync && \
    # git submodule update --init && \
    # cd /onnxruntime/cmake/external/onnx-tensorrt && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" .gitmodules && \
    # git submodule sync && \
    # git submodule update --init && \
    # cd /onnxruntime/cmake/external/onnx-tensorrt/third_party/onnx && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" .gitmodules && \
    # git submodule sync && \
    # git submodule update --init && \
    # cd /onnxruntime/cmake/external/protobuf && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" .gitmodules && \
    # git submodule sync && \
    # git submodule update --init && \
    # # cd /onnxruntime/cmake/external/tvm && \
    # # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" .gitmodules && \
    # # git submodule sync && \
    # # git submodule update --init && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" /onnxruntime/cmake/external/pybind11.cmake && \
    # sed -i "s/https\:\/\/github.com\//https\:\/\/github.com.cnpmjs.org\//g" /onnxruntime/cmake/external/abseil-cpp.cmake && \

    # echo "https://mirrors.ustc.edu.cn/alpine/v3.11/main" > /etc/apk/repositories && \
    # apk add --update --no-cache protobuf-dev=3.11.2-r1 flatbuffers-dev date-dev gtest-dev && \
    # configtmp='-DCMAKE_BUILD_TYPE=Release -Dprotobuf_WITH_ZLIB=OFF -DCMAKE_TOOLCHAIN_FILE=/onnxruntime/build/tool.cmake \
    # -Donnxruntime_ENABLE_PYTHON=ON -DPYTHON_EXECUTABLE=/usr/bin/python3 -Donnxruntime_BUILD_SHARED_LIB=OFF \
    # -Donnxruntime_DEV_MODE=OFF -DONNX_CUSTOM_PROTOC_EXECUTABLE=/usr/bin/protoc \
    # -Donnxruntime_BUILD_UNIT_TESTS=OFF  -Donnxruntime_PREFER_SYSTEM_LIB=ON' && \
    # mkdir /onnxruntime/build && \
    # echo "SET(CMAKE_SYSTEM_NAME Linux)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_SYSTEM_VERSION 1)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_C_COMPILER gcc)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_CXX_COMPILER g++)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)" >> /onnxruntime/build/tool.cmake && \
    # echo "SET(CMAKE_FIND_ROOT_PATH /)" >> /onnxruntime/build/tool.cmake && \
    # echo 'STRING(APPEND CMAKE_CXX_FLAGS " -Wno-deprecated-copy")' >> /onnxruntime/build/tool.cmake && \
    # cd /onnxruntime/build && cmake ../cmake $configtmp && \
    # make -j$(($(grep -c ^processor /proc/cpuinfo) - 0)) && python3 setup.py bdist_wheel && cd / )) \