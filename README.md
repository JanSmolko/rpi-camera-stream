# RPI Camera stream
Stream from Raspberry Pi camera. Default on port 8000.


## Build
```
dpkg-deb --build ./src .
```

## Install
```
dpkg -i [BUILDED_PACKAGE_NAME].deb
```

## Enable service
```
systemctl enable rpi-camera-stream.service
```

---

## Config
in `/etc/rpi-camera-stream/config.ini`

---

## Remove
```
apt remove rpi-camera-stream
```
