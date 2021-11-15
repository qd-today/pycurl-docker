# **Pycurl-Docker**

**Python:3.8-Alpine latest with pycurl**

## **Repository**

**Github :** [https://github.com/a76yyyy/pycurl-docker](https://github.com/a76yyyy/pycurl-docker)

**DockerHub :** [https://hub.docker.com/r/a76yyyy/pycurl](https://hub.docker.com/r/a76yyyy/pycurl)

## **VERSION**

- PYTHON_VERSION == 3.8
- CURL_VERSION == 7.80.0
- OPENSSL_VERSION == 1_1_1l+quic
- PYCURL_VERSION == 7.44.1

```bash
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
    --with-pic
```
