# A Game About Farming and Cooking — Android build

This repository contains the Python/Pygame farming and cooking game and an experimental GitHub Actions workflow for building an Android debug APK.

## Build APK

1. Open the **Actions** tab.
2. Select **Build Android APK**.
3. Tap **Run workflow** on the `main` branch.
4. When the run completes successfully, open it and download the `farming-cooking-android-apk` artifact.

If the build fails, download the `android-build-logs` artifact and check the first native build error.

## Compatibility note

The workflow uses Buildozer, python-for-android, SDL2, and a local `pygame-ce` recipe. Android packaging of Pygame is sensitive to the SDK/NDK and native library versions, so the workflow is experimental. No APK is available until a GitHub Actions run succeeds. The existing game controls are inherited from the Python source; touchscreen controls still need to be tested and may require further adaptation.

## Run on desktop

```bash
python -m pip install pygame-ce
python main.py
```
