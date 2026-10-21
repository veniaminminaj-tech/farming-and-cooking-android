# A Game About Farming and Cooking — Android packaging attempt

This project is based on the uploaded single-file Pygame game. The game logic and pixel-art rendering are retained, and mobile touch controls were added in `main.py`:

- Virtual joystick on the lower-left (hold and drag to move)
- **USE** button to use the selected item/tool
- **TALK** button for interaction (harvest, cook, shop, sleep, etc.)
- **RUN** button (hold)
- **BAG** button to open inventory
- Tap support for the title/help/dialog screens

## Build APK with GitHub Actions

1. Create a GitHub repository and upload the contents of this folder to its root.
2. Push to `main` or `master`, or open **Actions → Build Android APK → Run workflow**.
3. When the workflow succeeds, open the workflow run and download the `farming-cooking-android-apk` artifact.
4. Extract the APK and install it on an Android device. Android may ask you to allow installation from the app used to open the APK.

The workflow also uploads build logs if compilation fails.

## Important compatibility note

The original game uses `pygame`. Current `python-for-android` documentation says the modern SDL2 bootstrap does not provide a `pygame_sdl2` recipe; this project therefore pins the older **legacy Pygame bootstrap** as an experimental build path. That toolchain is old and may fail with current Android SDK/NDK or dependency downloads. The workflow is prepared to try the build, but **no APK is claimed to exist until a GitHub Actions run completes successfully**. If it fails, use the uploaded log to identify the exact blocker; a reliable long-term solution may require porting the renderer/input layer to a currently supported Android framework.

## Desktop run

Install Pygame and run:

```bash
python -m pip install pygame
python main.py
```

Save data is written to `farm_cooking_save.json` beside the game file.
