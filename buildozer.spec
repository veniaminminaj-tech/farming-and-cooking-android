[app]
title = A Game About Farming and Cooking
package.name = farmingcooking
package.domain = org.veniaminminaj
source.dir = .
source.include_exts = py,json,png,jpg,jpeg,ttf,otf
source.exclude_dirs = .git,.github,bin,.buildozer,__pycache__
version = 1.0.0
requirements = python3,pygame
orientation = landscape
fullscreen = 1
android.api = 33
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

# Pygame's legacy python-for-android bootstrap is experimental and pinned below.
p4a.bootstrap = pygame
p4a.branch = v2022.09.04

[buildozer]
log_level = 2
warn_on_root = 1
