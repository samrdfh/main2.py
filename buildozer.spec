[app]
title = MobileRemote
package.name = mobileremote
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3, kivy, plyer, requests, android, jnius
orientation = portrait
fullscreen = 0

[android]
arch = armeabi-v7a
permissions = CAMERA, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, RECORD_AUDIO, VIBRATE, INTERNET
