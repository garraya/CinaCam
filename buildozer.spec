[app]
title = CimaCam
package.name = cimacam
package.domain = ar.com.cimahys
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.4
icon.filename = logo.png

# REQUISITOS CLAVE:
# 1. opencv-python-headless: Vital para que no busque ventana gráfica y falle.
# 2. android: Para permisos.
requirements = python3, kivy==2.3.0, opencv-python-headless==4.9.0.80, android, numpy

orientation = portrait
fullscreen = 0
android.permissions = CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

# Pantalla de carga personalizada (opcional, dejamos default por ahora)
# android.presplash_color = #FFFFFF

p4a.branch = master
