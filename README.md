# **Pycurl-Docker-default**

Python:3.9-Alpine latest with pycurl - default ( **not support TLS1.3 and Http3** )

## **Repository**

**Github :** [https://github.com/qiandao-today/pycurl-docker/tree/default](https://github.com/qiandao-today/pycurl-docker/tree/default)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

```bash
docker pull a76yyyy/pycurl:default-latest
```

## **VERSION**

- PYTHON_VERSION == 3.9
- CURL_VERSION == 7.81.0
- OPENSSL_VERSION == 1.1.1m-r1
- PYCURL_VERSION == 7.44.1
- ONNXRUNTIME_TAG == v1.10.0

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
