[app]
title = Proxy Collector
package.name = proxycollector
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = src/*,ui/mobile/*

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 31
android.minapi = 21
android.ndk = 25b
android.arch = arm64-v8a

requirements = python3,kivy==2.2.0,requests,urllib3,plyer,certifi

# Build configuration
android.accept_sdk_license = True
p4a.source_dir = 
p4a.bootstrap = sdl2

# Version
version = 1.0.0
# version.regex = version\s*=\s*["'](?P<version>[0-9.]+)["']
# version.filename = src/core/proxy_collect/__init__.py
