[app]
title = CimaCam
package.name = cimacam
package.domain = ar.com.cimahys
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.3
icon.filename = logo.png

# ESTA ES LA CLAVE:
# 1. Sin 'pillow' (innecesario y conflictivo).
# 2. opencv-python-headless (sin interfaz gráfica).
# 3. numpy==1.26.4 (OBLIGATORIO poner versión exacta sin 'v' para evitar el error unique.cpp).
requirements = python3, kivy==2.3.0, opencv, android, numpy

orientation = portrait
fullscreen = 0
android.permissions = CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
p4a.branch = master
