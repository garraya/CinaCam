[app]
title = CimaCam
package.name = cimacam
package.domain = ar.com.cimahys
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.3
icon.filename = logo.png

python.version = 3.10

requirements = python3, kivy==2.3.0, camera4kivy, gestures4kivy, numpy==1.24.4

orientation = portrait
fullscreen = 0
android.permissions = CAMERA, RECORD_AUDIO
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.accept_sdk_license = True
android.archs = arm64-v8a
android.gradle_dependencies = androidx.camera:camera-core:1.3.2,androidx.camera:camera-camera2:1.3.2,androidx.camera:camera-lifecycle:1.3.2,androidx.camera:camera-video:1.3.2,androidx.camera:camera-view:1.3.2,androidx.camera:camera-extensions:1.3.2
p4a.branch = develop
sdl2.version = 2.28.5
