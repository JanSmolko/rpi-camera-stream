## Build
```
dpkg-deb --build ./src .
```

## Install
```
dpkg -i [BUILDED_PACKAGE_NAME].deb
```

## Remove
```
apt remove rpi-camera-stream
```

## Enable service
```
systemctl enable rpi-camera-stream.service
```
