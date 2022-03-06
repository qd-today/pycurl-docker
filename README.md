# **Pycurl-Docker**

**Python3.10:Alpine-edge with pycurl**

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker](https://github.com/qiandao-today/pycurl-docker)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:latest
```

## **VERSION**

- PYTHON_VERSION == 3.10
- CURL_VERSION == 7.82.0
- OPENSSL_VERSION == 1_1_1m+quic
- PYCURL_VERSION == 7.44.1
- ONNXRUNTIME_TAG == master(20220306)
- DDDDOCR_VERSION == 1.4.3

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
    --with-gssapi
```

# **Pycurl-Docker-default**

Python:3.10-Alpine latest with pycurl - default ( **not support TLS1.3 & Http3 & OnnxRuntime & ddddocr** )

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker/tree/default](https://github.com/qiandao-today/pycurl-docker/tree/default)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:default-latest
```

## **VERSION**

- PYTHON_VERSION == 3.10
- CURL_VERSION == 7.82.0
- OPENSSL_VERSION == 1.1.1
- PYCURL_VERSION == 7.44.1

```bash
./configure \
    --with-ssl \
    --with-nghttp2=/usr \
    --prefix=/usr \
    --enable-ipv6 \
    --enable-unix-sockets \
    --with-libidn2 \
    --disable-static \
    --disable-ldap \
    --with-pic \
    --with-gssapi
```
