# **Pycurl-Docker**

**Python:3.9-Alpine latest with pycurl**

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker](https://github.com/qiandao-today/pycurl-docker)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:latest
```

## **VERSION**

- PYTHON_VERSION == 3.9
- CURL_VERSION == 7.81.0
- OPENSSL_VERSION == 1_1_1m+quic
- PYCURL_VERSION == 7.44.1
- ONNXRUNTIME_TAG == v1.10.0

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
