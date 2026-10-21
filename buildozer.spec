[app]
title = A Game About Farming and Cooking
package.name = farmingcooking
package.domain = org.veniaminminaj
source.dir = .
source.include_exts = py,json,png,jpg,jpeg,ttf,otf
source.exclude_dirs = .git,.github,bin,.buildozer,__pycache__,p4a-recipes
version = 1.0.0
requirements = python3,pygame-ce
orientation = landscape
fullscreen = 1
android.api = 34
android.minapi = 23
android.ndk_api = 23
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
p4a.bootstrap = sdl2
p4a.local_recipes = ./p4a-recipes

[buildozer]
log_level = 2
warn_on_root = 0
