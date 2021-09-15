# Pycurl-Docker

Python:3.8-Alpine latest with pycurl

## VERSION

- PYTHON_VERSION == 3.8
- CURL_VERSION == 7.79.0
- OPENSSL_VERSION == 1_1_1l+quic

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
