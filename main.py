#!/usr/bin/env python3
"""
A GAME ABOUT FARMING AND COOKING
A cozy, Stardew-Valley-style farming sim made with pygame.
All art is drawn in code, so this is a single file with no assets.

Install:  pip install pygame
Run:      python a_game_about_farming_and_cooking.py

CONTROLS
  WASD / Arrows   move (hold SHIFT to run)
  SPACE / Click   use the selected tool / plant seeds / eat food
  E / Right-click interact (harvest, pick flowers, cook, shop, ship, sleep, talk)
  1-9, 0, - , =   choose hotbar slot   (Q / R or mouse wheel to cycle)
  I or TAB        inventory (eat food from here too)
  F1              help        ESC  pause / save

HOW TO PLAY
  1. Hoe grass to make soil, plant seeds, water them every day.
  2. Crops grow one day for each day they are watered (rain waters for you!).
  3. Harvest with E. Cook crops into meals at the Kitchen (the teal hut).
  4. Put goods in the Shipping Bin (the wooden box). You get paid overnight.
  5. Open your CAFE (big building east of the farm): cook what guests order and
     serve them at their tables. Order seeds, recipes and upgrades on the PC by
     the house, fish in the river or the sea, and play mini-games at the village arcade.
  6. Chop trees (axe) and mine rocks (pickaxe) to clear land.
  7. Sleep in your house before 2am or you will pass out!
"""
import hashlib
import json
import math
import os
import random
import sys

import json
import socket
import threading

import pygame


# ============================================================ config
TILE = 16
VIEW_W, VIEW_H = 480, 320
SCALE = 2
WIN_W, WIN_H = VIEW_W * SCALE, VIEW_H * SCALE
NO_HUD_DEFAULT = False   # build_exes.py flips this for the No-HUD PC build
NO_HUD = NO_HUD_DEFAULT or ("--no-hud" in sys.argv)
NET_PORT = 7788
GAME_BUILD_DEFAULT = "host"   # build_exes.py flips this to "player" for the join-only build
GAME_BUILD = "player" if "--player" in sys.argv else GAME_BUILD_DEFAULT
CAN_HOST = GAME_BUILD == "host"
MAP_W, MAP_H = 160, 96
FARM_W = 128             # width of the land; the sea fills the columns east of the beach
SEA_SHORE = 126          # the beach starts here; the shoreline wobbles a little from row to row
FPS = 60
ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
_SAVE_DIR = os.environ.get("ANDROID_PRIVATE") if ANDROID else os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(_SAVE_DIR or ".", "farm_cooking_save.json")
MIN_PER_SEC = 3.0            # game minutes per real second
WAKE_HOUR, PASSOUT_HOUR = 6.0, 26.0
SEASONS = ["Spring", "Summer", "Fall"]
DAYS_PER_SEASON = 10
GRASS, PATH, WATER, SAND = 0, 1, 2, 3
WOOD_FLOOR, WALL = 4, 5
BRIDGE = 6                    # the one wooden bridge over the river
BRIDGE_ROWS = (43, 46)       # first and last row of the bridge deck
RX0, RY0, RX1, RY1 = 20, 14, 43, 29          # cafe room, inclusive tile bounds
CAFE_DOOR_IN = (32 * TILE + 8, 28 * TILE + 8)  # inside, next to the exit door
CAFE_EXIT_OUT = (42 * TILE + 8, 19 * TILE + 10)  # outside, facing the cafe front
HOUSE_EXIT_OUT = (29 * TILE + 8, 10 * TILE + 10)  # outside, facing the front door of the house
VILLAGE_PORT_TX, VILLAGE_PORT_TY = 121, 43        # the ferry port at the far east end, past the secondary village
VILLAGE_PORT_OUT = ((VILLAGE_PORT_TX + 2) * TILE + 8, VILLAGE_PORT_TY * TILE + 8)
FARM_DOCK_OUT = VILLAGE_PORT_OUT                   # the ferry port is the only way to sail now
PORT_HOUSE_TX, PORT_HOUSE_TY = 120, 48             # the port house on the harbour's south shore
PORT_HOUSE_OUT = ((PORT_HOUSE_TX + 2) * TILE + 8, (PORT_HOUSE_TY + 5) * TILE + 10)   # outside, facing its door
STATION_SPAWN = (25 * TILE + 8, 37 * TILE + 8)     # at the Ruined Station dock, facing the boat
ISLAND_SPAWN = (34 * TILE + 8, 47 * TILE + 8)      # on the island, facing the return dock
NEAR_DISTANCE = 420                                 # players further away than this are not sent
ROOM_SIZE = 100                                     # players in one room, the host included
MAX_PLAYERS = ROOM_SIZE - 1                         # LAN clients (the host is the one more)
FISH_MASTER_LINES = [
    "Every fish out here has a story. Bring me yours.",
    "Catch every species and I'll give you the Master Rod.",
    "Rare fish bite hardest when you cast perfectly.",
    "I pay a fair price for a fair catch.",
]
FISHERMAN_LINES = [
    "The river's been good to me. Cross the bridge to reach the village.",
    "Fish bite best at dawn, right beside the bridge posts.",
    "Got a Villager House Kit? Build it anywhere on the farm.",
    "Mind the water. Only the bridge crosses the river here.",
]
MASTERY = [(3, "Fish Apprentice", 0.10), (6, "Fish Master", 0.20), (8, "Grand Angler", 0.30)]
# Next to the .exe when packaged (the code itself runs from a temp folder), else next to main.py
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
TEXTURE_DIRS = []   # folders that contain PNG texture overrides (from mods)
LOADED_MODS = []
_TEX_CACHE = {}
WORKBENCH = {
    "computer": dict(name="Computer", needs={"wood": 10, "stone": 6},
                     desc="Built for the house. Unlocks the PC in your bedroom."),
    "can2": dict(name="Big Watering Can", needs={"wood": 6, "stone": 3},
                 desc="Holds 40 water instead of 20."),
    "hook": dict(name="Fishing Hook", needs={"wood": 4, "stone": 2},
                 desc="+5% chance of rare fish."),
    "villager_house": dict(name="Build Villager House", needs={"wood": 30, "stone": 20},
                 desc="Crafts a house kit. Place it on the farm, then pick a spot."),
}


def tex(name, size=16):
    """A texture override PNG from a loaded mod, or None to use the built-in art."""
    key = (name, size)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]
    result = None
    for folder in TEXTURE_DIRS:
        path = os.path.join(folder, name + ".png")
        if os.path.isfile(path):
            try:
                img = pygame.image.load(path)
                if img.get_size() != (size, size):
                    img = pygame.transform.scale(img, (size, size))
                try:
                    img = img.convert_alpha()
                except pygame.error:
                    pass
                result = img
            except pygame.error:
                result = None
            break
    _TEX_CACHE[key] = result
    return result


def apply_mod(data, folder):
    """Adds crops, items, and recipes described in mod.json. Raises ValueError on bad data."""
    ov = data.get("overrides", {})
    for key, o in ov.get("crops", {}).items():
        if key not in CROPS:
            raise ValueError("override for unknown crop %r" % key)
        c = CROPS[key]
        if "name" in o:
            c["name"] = str(o["name"])[:30]
        for field in ("days", "seed", "sell"):
            if field in o:
                c[field] = max(1 if field == "days" else 0, int(o[field]))
        c["days"] = min(30, c["days"])
        if o.get("shape") in ("root", "round", "wheat", "big"):
            c["shape"] = o["shape"]
        ITEMS[key]["name"], ITEMS[key]["sell"] = c["name"], c["sell"]
        seed = ITEMS[key + "_seed"]
        seed["name"], seed["buy"], seed["sell"] = c["name"] + " Seeds", c["seed"], c["seed"] // 2
    for key, o in ov.get("items", {}).items():
        if key not in ITEMS:
            raise ValueError("override for unknown item %r" % key)
        it = ITEMS[key]
        if "name" in o:
            it["name"] = str(o["name"])[:30]
        if "sell" in o:
            it["sell"] = max(0, int(o["sell"]))
        if it["kind"] == "crop" and key in CROPS:
            CROPS[key]["sell"] = it["sell"]   # keep the crop and its item price in step
    for key, c in data.get("crops", {}).items():
        if key in CROPS:
            raise ValueError("crop %r already exists" % key)
        CROPS[key] = dict(name=c["name"], days=int(c["days"]), sell=int(c["sell"]), seed=int(c["seed"]),
                          fruit=tuple(c.get("fruit", [200, 200, 120])), shape=c.get("shape", "round"))
        ITEMS[key + "_seed"] = dict(name=c["name"] + " Seeds", kind="seed", sell=int(c["seed"]) // 2,
                                    crop=key, buy=int(c["seed"]))
        ITEMS[key] = dict(name=c["name"], kind="crop", sell=int(c["sell"]))
    for key, it in data.get("items", {}).items():
        ITEMS[key] = dict(name=it["name"], kind=it.get("kind", "mat"), sell=int(it.get("sell", 0)),
                          energy=int(it.get("energy", 0)))
    for key, r in data.get("recipes", {}).items():
        for ing in r["needs"]:
            if ing not in ITEMS:
                raise ValueError("recipe %r needs unknown item %r" % (key, ing))
        RECIPES[key] = dict(name=r["name"], needs=dict(r["needs"]), energy=int(r.get("energy", 0)),
                            sell=int(r.get("sell", 0)))
        ITEMS[key] = dict(name=r["name"], kind="food", sell=RECIPES[key]["sell"], energy=RECIPES[key]["energy"])
        if r.get("start"):
            UNLOCKED_START.append(key)
        else:
            RECIPE_PRICE[key] = int(r.get("price", 300))
    for key, f in data.get("fish", {}).items():
        if key in FISH:
            raise ValueError("fish %r already exists" % key)
        FISH[key] = dict(name=f["name"], sell=int(f.get("sell", 50)), weight=int(f.get("weight", 10)),
                         tier=max(0, min(4, int(f.get("tier", 0)))),
                         color=tuple(f.get("color", [120, 150, 190])))
        ITEMS[key] = dict(name=f["name"], kind="mat", sell=FISH[key]["sell"], energy=0)
    tex_dir = os.path.join(folder, "textures")
    if os.path.isdir(tex_dir):
        TEXTURE_DIRS.append(tex_dir)


def load_mods(folder=None):
    """Loads every folder in mods/ that has a mod.json. A broken mod is skipped, not fatal."""
    folder = folder or os.path.join(APP_DIR, "mods")
    if not os.path.isdir(folder):
        return LOADED_MODS
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        meta = os.path.join(path, "mod.json")
        if not os.path.isfile(meta):
            continue
        try:
            with open(meta, encoding="utf-8") as f:
                data = json.load(f)
            apply_mod(data, path)
            LOADED_MODS.append(data.get("name", name))
        except (ValueError, KeyError, TypeError, OSError) as e:
            print("Mod %s was skipped: %s" % (name, e))
    return LOADED_MODS
DIRS = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}

INK = (52, 36, 28)
PANEL = (222, 178, 118)
PANEL_D = (150, 100, 60)
PANEL_L = (246, 218, 160)
TEXT = (70, 40, 24)
GOLD = (250, 200, 60)
CREAM = (255, 244, 220)

PAL = {
    "Spring": dict(grass=(104, 168, 74), grass_d=(90, 152, 64), grass_l=(128, 188, 92),
                   leaf=(76, 150, 68), leaf_l=(112, 184, 84), leaf_d=(52, 116, 56),
                   flower=[(248, 176, 200), (255, 240, 160), (190, 170, 250)]),
    "Summer": dict(grass=(88, 158, 62), grass_d=(74, 140, 54), grass_l=(112, 178, 78),
                   leaf=(54, 134, 58), leaf_l=(88, 166, 70), leaf_d=(38, 100, 46),
                   flower=[(250, 120, 120), (255, 210, 90), (250, 250, 250)]),
    "Fall": dict(grass=(150, 152, 72), grass_d=(132, 134, 62), grass_l=(172, 168, 86),
                 leaf=(214, 118, 48), leaf_l=(238, 166, 64), leaf_d=(168, 78, 40),
                 flower=[(220, 120, 60), (250, 200, 80), (180, 90, 60)]),
}

# ============================================================ game data
CROPS = {
    "parsnip": dict(name="Parsnip", days=4, sell=45, seed=20, fruit=(240, 230, 196), shape="root"),
    "wheat": dict(name="Wheat", days=4, sell=30, seed=15, fruit=(232, 196, 84), shape="wheat"),
    "potato": dict(name="Potato", days=6, sell=80, seed=40, fruit=(190, 146, 92), shape="round"),
    "tomato": dict(name="Tomato", days=8, sell=120, seed=60, fruit=(222, 60, 50), shape="round"),
    "pumpkin": dict(name="Pumpkin", days=10, sell=300, seed=100, fruit=(236, 126, 40), shape="big"),
    "strawberry": dict(name="Strawberry", days=5, sell=90, seed=35, fruit=(220, 40, 70), shape="round"),
    "corn": dict(name="Corn", days=7, sell=160, seed=50, fruit=(250, 220, 70), shape="wheat"),
    "cabbage": dict(name="Cabbage", days=4, sell=55, seed=25, fruit=(150, 210, 120), shape="round"),
    "eggplant": dict(name="Eggplant", days=9, sell=260, seed=90, fruit=(110, 50, 120), shape="round"),
}
CROPS.update({
    "radish": dict(name="Radish", days=3, sell=35, seed=12, fruit=(120, 141, 168), shape="leaf"),
    "onion": dict(name="Onion", days=4, sell=43, seed=16, fruit=(221, 225, 66), shape="bush"),
    "garlic": dict(name="Garlic", days=5, sell=52, seed=20, fruit=(147, 213, 199), shape="stalk"),
    "leek": dict(name="Leek", days=6, sell=60, seed=24, fruit=(232, 167, 186), shape="bulb"),
    "beet": dict(name="Beet", days=7, sell=68, seed=28, fruit=(230, 185, 190), shape="pod"),
    "carrot": dict(name="Carrot", days=8, sell=77, seed=32, fruit=(202, 121, 40), shape="spike"),
    "spinach": dict(name="Spinach", days=9, sell=85, seed=36, fruit=(247, 80, 68), shape="round"),
    "lettuce": dict(name="Lettuce", days=10, sell=94, seed=40, fruit=(163, 85, 155), shape="root"),
    "kale": dict(name="Kale", days=11, sell=102, seed=44, fruit=(92, 185, 120), shape="wheat"),
    "broccoli": dict(name="Broccoli", days=12, sell=110, seed=48, fruit=(143, 161, 104), shape="big"),
    "cauliflower": dict(name="Cauliflower", days=13, sell=119, seed=52, fruit=(179, 151, 136), shape="leaf"),
    "celery": dict(name="Celery", days=14, sell=127, seed=56, fruit=(221, 223, 59), shape="bush"),
    "artichoke": dict(name="Artichoke", days=3, sell=136, seed=60, fruit=(177, 82, 182), shape="stalk"),
    "asparagus": dict(name="Asparagus", days=4, sell=144, seed=64, fruit=(227, 134, 113), shape="bulb"),
    "peas": dict(name="Peas", days=5, sell=152, seed=68, fruit=(207, 96, 187), shape="pod"),
    "green_beans": dict(name="Green Beans", days=6, sell=161, seed=72, fruit=(169, 66, 134), shape="spike"),
    "cucumber": dict(name="Cucumber", days=7, sell=169, seed=76, fruit=(183, 178, 148), shape="round"),
    "zucchini": dict(name="Zucchini", days=8, sell=178, seed=80, fruit=(113, 162, 189), shape="root"),
    "watermelon": dict(name="Watermelon", days=9, sell=186, seed=84, fruit=(231, 187, 69), shape="wheat"),
    "melon": dict(name="Melon", days=10, sell=194, seed=88, fruit=(198, 189, 193), shape="big"),
    "grapes": dict(name="Grapes", days=11, sell=203, seed=92, fruit=(215, 161, 174), shape="leaf"),
    "blueberry": dict(name="Blueberry", days=12, sell=211, seed=96, fruit=(156, 167, 184), shape="bush"),
    "raspberry": dict(name="Raspberry", days=13, sell=220, seed=100, fruit=(212, 191, 172), shape="stalk"),
    "blackberry": dict(name="Blackberry", days=14, sell=228, seed=104, fruit=(96, 207, 97), shape="bulb"),
    "cranberry": dict(name="Cranberry", days=3, sell=236, seed=108, fruit=(123, 72, 173), shape="pod"),
    "orange": dict(name="Orange", days=4, sell=245, seed=112, fruit=(116, 219, 149), shape="spike"),
    "lemon": dict(name="Lemon", days=5, sell=253, seed=116, fruit=(210, 96, 163), shape="round"),
    "peach": dict(name="Peach", days=6, sell=262, seed=120, fruit=(148, 91, 156), shape="root"),
    "plum": dict(name="Plum", days=7, sell=270, seed=124, fruit=(210, 199, 104), shape="wheat"),
    "cherry": dict(name="Cherry", days=8, sell=278, seed=128, fruit=(233, 162, 118), shape="big"),
    "pear": dict(name="Pear", days=9, sell=287, seed=132, fruit=(230, 225, 168), shape="leaf"),
    "kiwi": dict(name="Kiwi", days=10, sell=295, seed=136, fruit=(212, 162, 150), shape="bush"),
    "pineapple": dict(name="Pineapple", days=11, sell=304, seed=140, fruit=(141, 135, 108), shape="stalk"),
    "coffee_beans": dict(name="Coffee Beans", days=12, sell=312, seed=144, fruit=(92, 68, 78), shape="bulb"),
    "rice": dict(name="Rice", days=13, sell=320, seed=148, fruit=(242, 177, 173), shape="pod"),
    "barley": dict(name="Barley", days=14, sell=329, seed=152, fruit=(215, 152, 91), shape="spike"),
    "oats": dict(name="Oats", days=3, sell=337, seed=156, fruit=(156, 184, 159), shape="round"),
    "rye": dict(name="Rye", days=4, sell=346, seed=160, fruit=(220, 187, 151), shape="root"),
    "millet": dict(name="Millet", days=5, sell=354, seed=164, fruit=(232, 229, 48), shape="wheat"),
    "sorghum": dict(name="Sorghum", days=6, sell=362, seed=168, fruit=(164, 141, 157), shape="big"),
    "quinoa": dict(name="Quinoa", days=7, sell=371, seed=172, fruit=(115, 172, 171), shape="leaf"),
    "chili_pepper": dict(name="Chili Pepper", days=8, sell=379, seed=176, fruit=(156, 175, 86), shape="bush"),
    "bell_pepper": dict(name="Bell Pepper", days=9, sell=388, seed=180, fruit=(198, 182, 56), shape="stalk"),
    "ginger": dict(name="Ginger", days=10, sell=396, seed=184, fruit=(158, 187, 134), shape="bulb"),
    "sweet_potato": dict(name="Sweet Potato", days=11, sell=404, seed=188, fruit=(114, 109, 145), shape="pod"),
    "cassava": dict(name="Cassava", days=12, sell=413, seed=192, fruit=(127, 175, 43), shape="spike"),
    "yam": dict(name="Yam", days=13, sell=421, seed=196, fruit=(113, 60, 155), shape="round"),
    "sunflower": dict(name="Sunflower", days=14, sell=430, seed=200, fruit=(238, 199, 61), shape="root"),
    "lavender": dict(name="Lavender", days=3, sell=438, seed=204, fruit=(246, 110, 103), shape="wheat"),
    "hops": dict(name="Hops", days=4, sell=446, seed=208, fruit=(120, 218, 51), shape="big"),
    "cotton": dict(name="Cotton", days=5, sell=455, seed=212, fruit=(229, 128, 131), shape="leaf"),
    "cocoa": dict(name="Cocoa", days=6, sell=463, seed=216, fruit=(129, 61, 120), shape="bush"),
    "vanilla": dict(name="Vanilla", days=7, sell=472, seed=220, fruit=(239, 207, 165), shape="stalk"),
    "saffron": dict(name="Saffron", days=8, sell=480, seed=224, fruit=(124, 199, 97), shape="bulb"),
    "mint": dict(name="Mint", days=9, sell=488, seed=228, fruit=(211, 210, 73), shape="pod"),
    "basil": dict(name="Basil", days=10, sell=497, seed=232, fruit=(243, 189, 114), shape="spike"),
    "rosemary": dict(name="Rosemary", days=11, sell=505, seed=236, fruit=(111, 166, 80), shape="round"),
    "thyme": dict(name="Thyme", days=12, sell=514, seed=240, fruit=(124, 210, 118), shape="root"),
    "chamomile": dict(name="Chamomile", days=13, sell=522, seed=244, fruit=(219, 165, 139), shape="wheat"),
})

# ---------- fish species: weight is how common they are, tier is how rare (0 = common)
FISH = {
    "fish": dict(name="Fish", sell=45, weight=40, tier=0, color=(120, 150, 190)),
    "trout": dict(name="Trout", sell=70, weight=24, tier=1, color=(150, 200, 170)),
    "bass": dict(name="Bass", sell=95, weight=16, tier=1, color=(120, 170, 110)),
    "catfish": dict(name="Catfish", sell=130, weight=9, tier=2, color=(110, 110, 120)),
    "salmon": dict(name="Salmon", sell=180, weight=6, tier=2, color=(240, 130, 110)),
    "eel": dict(name="Eel", sell=200, weight=4, tier=3, color=(90, 110, 70)),
    "koi": dict(name="Koi", sell=420, weight=2, tier=4, color=(250, 140, 60)),
    "rare_fish": dict(name="Golden Carp", sell=320, weight=1, tier=4, color=(250, 200, 60)),
}
FISH.update({
    "perch": dict(name="Perch", sell=40, weight=28, tier=0, color=(118, 174, 174)),
    "pike": dict(name="Pike", sell=43, weight=28, tier=0, color=(154, 207, 129)),
    "common_carp": dict(name="Common Carp", sell=46, weight=28, tier=0, color=(146, 197, 70)),
    "sturgeon": dict(name="Sturgeon", sell=49, weight=28, tier=0, color=(174, 231, 219)),
    "sunfish": dict(name="Sunfish", sell=52, weight=28, tier=0, color=(200, 159, 213)),
    "bluegill": dict(name="Bluegill", sell=55, weight=28, tier=0, color=(133, 90, 89)),
    "crappie": dict(name="Crappie", sell=58, weight=28, tier=0, color=(237, 79, 145)),
    "walleye": dict(name="Walleye", sell=61, weight=28, tier=0, color=(86, 60, 224)),
    "muskie": dict(name="Muskie", sell=64, weight=28, tier=0, color=(207, 146, 133)),
    "tuna": dict(name="Tuna", sell=67, weight=28, tier=0, color=(209, 128, 87)),
    "mackerel": dict(name="Mackerel", sell=40, weight=28, tier=0, color=(221, 230, 113)),
    "sardine": dict(name="Sardine", sell=43, weight=28, tier=0, color=(139, 188, 92)),
    "anchovy": dict(name="Anchovy", sell=46, weight=28, tier=0, color=(166, 210, 68)),
    "herring": dict(name="Herring", sell=49, weight=28, tier=0, color=(149, 216, 97)),
    "cod": dict(name="Cod", sell=52, weight=28, tier=0, color=(207, 194, 79)),
    "haddock": dict(name="Haddock", sell=55, weight=28, tier=0, color=(199, 199, 229)),
    "halibut": dict(name="Halibut", sell=58, weight=28, tier=0, color=(130, 236, 187)),
    "flounder": dict(name="Flounder", sell=61, weight=28, tier=0, color=(84, 200, 175)),
    "sole": dict(name="Sole", sell=102, weight=14, tier=1, color=(103, 62, 172)),
    "red_snapper": dict(name="Red Snapper", sell=106, weight=14, tier=1, color=(125, 115, 228)),
    "grouper": dict(name="Grouper", sell=70, weight=14, tier=1, color=(204, 158, 82)),
    "mahi_mahi": dict(name="Mahi-Mahi", sell=74, weight=14, tier=1, color=(156, 105, 182)),
    "marlin": dict(name="Marlin", sell=78, weight=14, tier=1, color=(76, 197, 160)),
    "swordfish": dict(name="Swordfish", sell=82, weight=14, tier=1, color=(203, 141, 138)),
    "barracuda": dict(name="Barracuda", sell=86, weight=14, tier=1, color=(108, 84, 104)),
    "wahoo": dict(name="Wahoo", sell=90, weight=14, tier=1, color=(91, 201, 209)),
    "clownfish": dict(name="Clownfish", sell=94, weight=14, tier=1, color=(68, 61, 180)),
    "angelfish": dict(name="Angelfish", sell=98, weight=14, tier=1, color=(210, 127, 225)),
    "tang": dict(name="Tang", sell=102, weight=14, tier=1, color=(128, 62, 103)),
    "goby": dict(name="Goby", sell=106, weight=14, tier=1, color=(238, 90, 224)),
    "guppy": dict(name="Guppy", sell=70, weight=14, tier=1, color=(187, 158, 91)),
    "betta": dict(name="Betta", sell=74, weight=14, tier=1, color=(227, 229, 187)),
    "goldfish": dict(name="Goldfish", sell=132, weight=6, tier=2, color=(163, 168, 162)),
    "tetra": dict(name="Tetra", sell=138, weight=6, tier=2, color=(173, 147, 210)),
    "discus": dict(name="Discus", sell=144, weight=6, tier=2, color=(233, 223, 220)),
    "lamprey": dict(name="Lamprey", sell=150, weight=6, tier=2, color=(200, 151, 233)),
    "gar": dict(name="Gar", sell=156, weight=6, tier=2, color=(198, 214, 189)),
    "bowfin": dict(name="Bowfin", sell=162, weight=6, tier=2, color=(73, 216, 73)),
    "paddlefish": dict(name="Paddlefish", sell=168, weight=6, tier=2, color=(155, 133, 208)),
    "arowana": dict(name="Arowana", sell=174, weight=6, tier=2, color=(190, 238, 171)),
    "piranha": dict(name="Piranha", sell=200, weight=3, tier=3, color=(98, 233, 133)),
    "stingray": dict(name="Stingray", sell=208, weight=3, tier=3, color=(229, 185, 235)),
    "manta_ray": dict(name="Manta Ray", sell=216, weight=3, tier=3, color=(161, 63, 131)),
    "lungfish": dict(name="Lungfish", sell=224, weight=3, tier=3, color=(185, 151, 192)),
    "sea_bass": dict(name="Sea Bass", sell=232, weight=3, tier=3, color=(223, 182, 100)),
    "monkfish": dict(name="Monkfish", sell=240, weight=3, tier=3, color=(95, 143, 80)),
    "dorado": dict(name="Dorado", sell=400, weight=1, tier=4, color=(132, 128, 137)),
    "pollock": dict(name="Pollock", sell=420, weight=1, tier=4, color=(169, 100, 202)),
    "lingcod": dict(name="Lingcod", sell=320, weight=1, tier=4, color=(211, 173, 205)),
    "lake_trout": dict(name="Lake Trout", sell=340, weight=1, tier=4, color=(102, 82, 178)),
    "rainbow_trout": dict(name="Rainbow Trout", sell=360, weight=1, tier=4, color=(78, 146, 84)),
    "brook_trout": dict(name="Brook Trout", sell=380, weight=1, tier=4, color=(158, 230, 214)),
    "steelhead": dict(name="Steelhead", sell=400, weight=1, tier=4, color=(111, 217, 93)),
})
RECIPES = {
    "fried_egg": dict(name="Fried Egg", needs={"egg": 1}, energy=30, sell=50),
    "tea": dict(name="Wildflower Tea", needs={"flower": 2}, energy=25, sell=60),
    "bread": dict(name="Fresh Bread", needs={"wheat": 2}, energy=40, sell=100),
    "stew": dict(name="Parsnip Stew", needs={"parsnip": 2, "potato": 1}, energy=60, sell=220),
    "soup": dict(name="Tomato Soup", needs={"tomato": 2}, energy=65, sell=320),
    "pie": dict(name="Pumpkin Pie", needs={"pumpkin": 1, "wheat": 1, "egg": 1}, energy=100, sell=700),
}
RECIPES.update({
    "pancakes": dict(name="Pancakes", needs={"flour": 1, "egg": 1, "milk": 1}, energy=55, sell=150),
    "latte": dict(name="Flower Latte", needs={"flower": 2, "milk": 1}, energy=40, sell=140),
    "cake": dict(name="Honey Cake", needs={"flour": 2, "egg": 2, "sugar": 1, "milk": 1}, energy=80, sell=380),
    "pumpkin_latte": dict(name="Pumpkin Latte", needs={"pumpkin": 1, "milk": 1, "sugar": 1}, energy=70, sell=330),
    "grilled_fish": dict(name="Grilled Fish", needs={"fish": 1}, energy=50, sell=130),
    "fish_stew": dict(name="Fish Stew", needs={"fish": 1, "potato": 1, "tomato": 1}, energy=75, sell=300),
    "salad": dict(name="Garden Salad", needs={"cabbage": 2, "tomato": 1}, energy=45, sell=190),
    "ratatouille": dict(name="Ratatouille", needs={"eggplant": 1, "tomato": 1, "pumpkin": 1}, energy=110, sell=800),
    "corn_bread": dict(name="Corn Bread", needs={"corn": 2, "egg": 1}, energy=60, sell=240),
    "strawberry_tart": dict(name="Strawberry Tart", needs={"strawberry": 2, "flour": 1, "sugar": 1}, energy=75, sell=420),
    "fish_platter": dict(name="Fish Platter", needs={"salmon": 1, "trout": 1, "bass": 1}, energy=90, sell=520),
})
TOOLS = ["hoe", "can", "axe", "pick", "rod"]
TOOL_NAMES = {"hoe": "Hoe", "can": "Watering Can", "axe": "Axe", "pick": "Pickaxe", "rod": "Fishing Rod"}
TOOL_COST = {"hoe": 2, "can": 1, "axe": 3, "pick": 3, "rod": 2}

ITEMS = {}
for _t in TOOLS:
    ITEMS[_t] = dict(name=TOOL_NAMES[_t], kind="tool", sell=0)
for _k, _c in CROPS.items():
    ITEMS[_k + "_seed"] = dict(name=_c["name"] + " Seeds", kind="seed", sell=_c["seed"] // 2,
                               crop=_k, buy=_c["seed"])
for _k, _c in CROPS.items():
    ITEMS[_k] = dict(name=_c["name"], kind="crop", sell=_c["sell"])
ITEMS.update({
    "wood": dict(name="Wood", kind="mat", sell=6),
    "stone": dict(name="Stone", kind="mat", sell=6),
    "egg": dict(name="Egg", kind="mat", sell=25),
    "flower": dict(name="Wildflower", kind="mat", sell=12),
    "fish": dict(name="Fish", kind="mat", sell=45),
    "rare_fish": dict(name="Golden Carp", kind="mat", sell=320),
    "villager_house_kit": dict(name="Villager House Kit", kind="mat", sell=0),
    "scrap": dict(name="Scrap Metal", kind="mat", sell=14),
    "old_coin": dict(name="Old Coin", kind="mat", sell=90),
    "trout": dict(name="Trout", kind="mat", sell=70),
    "bass": dict(name="Bass", kind="mat", sell=95),
    "catfish": dict(name="Catfish", kind="mat", sell=130),
    "salmon": dict(name="Salmon", kind="mat", sell=180),
    "eel": dict(name="Eel", kind="mat", sell=200),
    "koi": dict(name="Koi", kind="mat", sell=420),
    "flour": dict(name="Flour", kind="mat", sell=15),
    "milk": dict(name="Milk", kind="mat", sell=18),
    "sugar": dict(name="Sugar", kind="mat", sell=12),
    "ticket": dict(name="Arcade Ticket", kind="mat", sell=0),
})
for _k, _r in RECIPES.items():
    ITEMS[_k] = dict(name=_r["name"], kind="food", sell=_r["sell"], energy=_r["energy"])
ITEMS["energy_bar"] = dict(name="Energy Bar", kind="food", sell=0, energy=60)
for _fk, _fv in FISH.items():                        # every fish is an item you can hold and sell
    if _fk not in ITEMS:
        ITEMS[_fk] = dict(name=_fv["name"], kind="mat", sell=_fv["sell"])

# ---- cafe / PC shop / arcade data
UNLOCKED_START = ["fried_egg", "tea", "bread"]
RECIPE_PRICE = {
    "salad": 200, "ratatouille": 900, "corn_bread": 260, "strawberry_tart": 480, "fish_platter": 550,"latte": 250, "grilled_fish": 150, "stew": 300, "pancakes": 350, "soup": 400,
                "fish_stew": 500, "pumpkin_latte": 600, "pie": 700, "cake": 800}
PANTRY = {"flour": 25, "milk": 30, "sugar": 20}
UPGRADES = {
    "table3": dict(name="Cafe table #3", price=600, desc="One more seat for hungry guests", icon="wood"),
    "table4": dict(name="Cafe table #4", price=1200, desc="A fourth table (needs table #3)", icon="wood"),
    "decor": dict(name="Cafe decor pack", price=500, desc="Guests tip 25% more", icon="flower"),
    "can2": dict(name="Big watering can", price=400, desc="Holds 40 water instead of 20", icon="can"),
    "tonic1": dict(name="Energy tonic I", price=500, desc="+25 max energy", icon="energy_bar"),
    "tonic2": dict(name="Energy tonic II", price=900, desc="+25 max energy (needs tonic I)", icon="energy_bar"),
    "tonic3": dict(name="Energy tonic III", price=1500, desc="+25 max energy (needs tonic II)", icon="energy_bar"),
    "tools": dict(name="Efficient tools", price=700, desc="Every tool costs 1 less energy", icon="pick"),
}
UPG_REQ = {"table4": "table3", "tonic2": "tonic1", "tonic3": "tonic2"}
MINI = {
    "veggie": dict(name="Veggie Catch", desc="Move the basket. Catch veggies, dodge rocks!", icon="tomato"),
    "weed": dict(name="Whack-a-Weed", desc="Tap the weeds. Spare the flowers!", icon="flower"),
    "memory": dict(name="Recipe Memory", desc="Repeat the ingredient order.", icon="egg"),
    "pyramid": dict(name="Pyramid Builder", desc="Egypt: stack blocks. Stay centered!", icon="stone"),
    "quiz": dict(name="Food History Quiz", desc="How well do you know food history?", icon="wheat"),
    "caravan": dict(name="Silk Road Caravan", desc="Collect spices, dodge bandits.", icon="sugar"),
}
PRIZES = {
    "p_seeds": dict(name="Mystery Seed Pack", cost=10, desc="3 random seed packets", icon="wheat_seed"),
    "p_bar": dict(name="Energy Bar", cost=6, desc="Restores 60 energy", icon="energy_bar"),
    "p_trophy": dict(name="Golden Fork Trophy", cost=40, desc="+15 cafe rating, guests pay 10% more", icon="coin"),
}
PLAY_COST = 20
MEM_CENTERS = [(450, 200), (580, 330), (450, 460), (320, 330)]
MEM_ICONS = ["tomato", "pumpkin", "egg", "wheat"]
MEM_COLS = [(220, 70, 60), (236, 130, 40), (240, 240, 230), (232, 196, 84)]

CRAZY_LINES = [
    "Hi! I made this whole game. Bring me every single item you can collect, and I'll make one of your wishes come true.",
    "Still collecting? Good. The more you bring me, the bigger the wish.",
    "I don't do refunds on wishes. Or on anything else.",
    "Shh. The fish in the harbour are my spies.",
]
PORTRAITS = {}                  # name -> picture shown in the dialog box, when we have one
CRAZY_ART_RECT = (270, 165, 205, 225)   # the drawn character inside crazy_dew.png
WISH_OPTIONS = [                # (key, title, what you get). Each wish can be made only once.
    ("gold", "A fortune", "+1500 gold"),
    ("stamina", "Iron stamina", "+40 max energy, fully rested"),
    ("recipes", "Master cook", "Every cafe recipe unlocked"),
    ("seeds", "Seed vault", "5 packets of every crop seed"),
    ("rare", "Golden hoard", "5 Golden Carp"),
    ("kits", "Village builder", "2 villager house kits"),
    ("skills", "Old wisdom", "+200 xp in farming, cooking and fishing"),
]
GUS_LINES = [
    "Flour on my apron, sugar in my heart. What are we baking today?",
    "Bread rises best when nobody watches it. Like children.",
    "Hit the golden spot on the oven and the crust comes out perfect.",
    "Honey cake for the cafe tomorrow. Shh, it's a secret.",
]
LILA_LINES = [
    "Every seed wants water and a little patience.",
    "The pumpkins are sulking. Bring them a little love?",
    "Pull the weeds before they start gossiping with the crops.",
    "I grew this sunflower from a pinch of dirt. Don't tell anyone.",
]
PIP_LINES = [
    "Can I pet the hens? Pleeease?",
    "I saw a golden fish in the river once. Maybe.",
    "Mabel says I'm not allowed near the bridge. I'm only a little allowed.",
    "Grown-ups count money. I count frogs.",
]
TOMAS_LINES = [
    "Good timber takes a season to dry. Patience, friend.",
    "Stone walls keep the wind out and the gossip in.",
    "This bridge has stood for years, mostly because I keep fixing it.",
    "Build a villager house with a kit and I'll help with the walls.",
]
DARIO_LINES = [
    "The ferry leaves when the tide says so. Also when I say so.",
    "Bring me an old coin and I'll row you across, friend.",
    "The river's calm today. Keep your hands inside the boat.",
    "Tell the old salt at the station I said hello. Or don't.",
]
SALT_LINES = [
    "Ruins are full of scrap if you dig deep enough.",
    "I've been searching these ruins for forty years. Still finding things.",
    "The sea took my ship. The ruins took my hat.",
    "Coins wash up after storms. Keep your eyes open.",
]
CORAL_LINES = [
    "Shells for sale? No? Keep looking, they're everywhere.",
    "The sun is wonderful here. Come and sit awhile.",
    "I cook trout in seaweed. Secret recipe.",
    "Don't step on the sand crabs. They're very proud.",
]


def _q(id, giver, title, text, offer, thanks, goal, gold=0, item=None, n=1):
    return dict(id=id, giver=giver, title=title, text=text, offer=offer, thanks=thanks,
                goal=goal, gold=gold, item=item, n=n)


# goal kinds: ("stat", counter, n) counts from the day the quest was taken,
# ("items", {item: n}) takes the items on turn-in, ("money", n), ("level", skill, n),
# ("fishkinds", n).
QUESTS = [
    _q("m1", "Mabel", "Seed Order", "Plant 6 seeds in the soil.",
       "Fresh seeds need fresh soil! Plant six of them and I'll pay you well.",
       "Look at those rows! Here's your pay.", ("stat", "plant", 6), gold=80),
    _q("m2", "Mabel", "Market Day", "Have 400 gold in your purse.",
       "Business is booming. Show me you can keep a purse full and I'll reward you.",
       "A fine bit of saving! Take these seeds on the house.", ("money", 400), gold=60,
       item="parsnip_seed", n=5),
    _q("m3", "Mabel", "Good Business", "Ship 10 items to the shipping bin.",
       "Ship goods to the bin by the house. Ten items, mind you.",
       "Shipping like a pro! Your reward is in the till.", ("stat", "ship", 10), gold=150),
    _q("f1", "Fern", "Wildflower Tea", "Bring Fern 4 wildflowers.",
       "Wildflower tea cures most things. Bring me four flowers and I'll share my recipe.",
       "Ah, lovely! The kettle is already warm. Take this for your trouble.",
       ("items", {"flower": 4}), gold=60),
    _q("f2", "Fern", "Harvest Season", "Harvest 12 crops from your fields.",
       "The fields want picking. Harvest twelve crops and the valley will smile.",
       "Twelve crops! You've got a farmer's hands.", ("stat", "harvest", 12), gold=120),
    _q("f3", "Fern", "Old Hands", "Reach Farming level 3.",
       "Good farming takes years. Work up to Farming level 3 and I'll teach you the old tricks.",
       "There it is, Farming level 3. Keep at it.", ("level", "farm", 3), gold=200),
    _q("fi1", "Fisherman", "First Catch", "Catch 3 fish in the river.",
       "Cast a line into the river, lad. Three fish and you're a fisher.",
       "Three fish! Welcome to the river club.", ("stat", "fish", 3), gold=60),
    _q("fi2", "Fisherman", "Bridge Watch", "Catch 10 fish in total.",
       "The river is full of fish if you're patient. Ten of them and I'll buy you tea.",
       "Ten! Your tea is on me, and this is for your trouble.", ("stat", "fish", 10), gold=200),
    _q("fi3", "Fisherman", "Fish Journal", "Catch 5 different kinds of fish.",
       "Every fish has a different story. Catch five kinds and I'll reward your curiosity.",
       "Five different kinds! The journal is getting thick.", ("fishkinds", 5), gold=350),
    _q("fm1", "Fish Master", "Pink Trade", "Bring the Fish Master a koi.",
       "Koi are rare and I collect them. Bring me one and I'll pay handsomely.",
       "Beautiful koi! Your reward, as promised.", ("items", {"koi": 1}), gold=250),
    _q("fm2", "Fish Master", "Steady Hands", "Reach Fishing level 3.",
       "A steady hand catches bigger fish. Get your Fishing up to level 3.",
       "Steady as the tide! Fishing level 3, well done.", ("level", "fish", 3), gold=300),
    _q("fm3", "Fish Master", "Sea Supper", "Bring the Fish Master 2 salmon and 1 eel.",
       "I want a proper supper: two salmon and an eel. Bring them and I'll pay.",
       "A feast! Thank you. Here's the gold.", ("items", {"salmon": 2, "eel": 1}), gold=400),
    _q("g1", "Gus", "Breakfast Shift", "Cook 3 meals in the kitchen.",
       "The breakfast rush starts at dawn! Cook three meals for me and I'll pay you.",
       "Lovely plates! Breakfast is saved.", ("stat", "cook", 3), gold=100),
    _q("g2", "Gus", "Golden Crust", "Get 2 perfect bakes (three stars).",
       "A perfect bake has a golden crust. Hit the golden spot twice and I'll reward you.",
       "Golden crusts, both of them! I'm proud.", ("stat", "perfect", 2), gold=250),
    _q("g3", "Gus", "Cafe Opening", "Serve 10 guests in your cafe.",
       "The cafe needs guests. Serve ten of them and the whole town will know your name.",
       "Ten guests served! The cafe is famous now.", ("stat", "serve", 10), gold=400),
    _q("l1", "Lila", "Watering Round", "Water your crops 10 times.",
       "A thirsty field is a sad field. Give the crops ten waterings.",
       "Sunny and green! Thanks for keeping them happy.", ("stat", "water", 10), gold=70),
    _q("l2", "Lila", "Pumpkin Patch", "Deliver 3 pumpkins to Lila.",
       "Pumpkins are my favourite. Bring three and I'll make it worth your while.",
       "Three fat pumpkins! What a harvest.", ("items", {"pumpkin": 3}), gold=300),
    _q("l3", "Lila", "Ripe Tomatoes", "Deliver 5 tomatoes to Lila.",
       "Tomatoes all ripen at once and then I can't keep up. Help me out with five?",
       "Juicy! That's my salad sorted.", ("items", {"tomato": 5}), gold=200),
    _q("p1", "Pip", "Chicken Friend", "Pet your hens 5 times.",
       "Can you help my hens feel loved? Pet them five times? Pleeease?",
       "Yay! The hens said thank you. Here's a treat.", ("stat", "pet", 5), gold=80),
    _q("p2", "Pip", "Egg Hunt", "Deliver 10 eggs to Pip.",
       "I'm collecting eggs for the big egg cake. Ten, please!",
       "Ten eggs! That's the biggest egg cake ever.", ("items", {"egg": 10}), gold=150),
    _q("p3", "Pip", "Savings Jar", "Have 1000 gold in your purse.",
       "My jar needs to be full before Mabel's birthday. Keep a thousand gold, that's a grown-up rule!",
       "Wow, a thousand! You're rich. Here, take a little back.", ("money", 1000), gold=200),
    _q("t1", "Tomas", "Lumber Run", "Deliver 20 wood to Tomas.",
       "Timber is the real gold of this valley. Bring me twenty wood.",
       "Solid timber! The workshop smells of pine now.", ("items", {"wood": 20}), gold=150),
    _q("t2", "Tomas", "Stone Walls", "Deliver 15 stone to Tomas.",
       "Stone walls don't rot. Bring fifteen stone and I'll build something tough.",
       "Good solid stone. I'll put it to work.", ("items", {"stone": 15}), gold=150),
    _q("t3", "Tomas", "Home Sweet Home", "Build a villager house on the east bank.",
       "Build a villager house with a kit, right here on the east bank. Watch the village grow.",
       "A house! The village grows one roof at a time.", ("stat", "house", 1), gold=500),
    _q("d1", "Dario", "Ferry Trips", "Take the ferry to the island 2 times.",
       "Boarding the ferry is simple: stand at the port and press E. Take two trips.",
       "You're a seasoned sailor now!", ("stat", "sail", 2), gold=120),
    _q("d2", "Dario", "Ruins Scout", "Search 4 ruins at the Ruined Station.",
       "The ruins hold things nobody else thought to look for. Search four.",
       "Four ruins searched! You're a natural.", ("stat", "ruin", 4), gold=300),
    _q("d3", "Dario", "Ferry Fare", "Deliver 3 old coins to Dario.",
       "Old coins make good fares. Bring me three and I'll row you anywhere.",
       "Three coins! Hop aboard any time.", ("items", {"old_coin": 3}), gold=250),
    _q("s1", "Old Salt", "Scrap Pile", "Deliver 10 scrap metal to Old Salt.",
       "I'm building a boat out of junk. Bring me ten scrap metal.",
       "Ten scraps! My boat is coming along.", ("items", {"scrap": 10}), gold=180),
    _q("s2", "Old Salt", "Ancient Coins", "Deliver 4 old coins to Old Salt.",
       "Old coins are older than my grandmother's stories. Bring me four.",
       "Four coins! Ancient treasure, shared.", ("items", {"old_coin": 4}), gold=400),
    _q("c1", "Coral", "Seashell Shelf", "Deliver 3 trout to Coral.",
       "Trout from the bay makes a lovely lunch. Bring me three.",
       "Trout! The shelf is coming along nicely.", ("items", {"trout": 3}), gold=180),
    _q("c2", "Coral", "Sunny Shore", "Reach Cooking level 3.",
       "Cooking on the sand is an art. Reach Cooking level 3 and I'll share my secret recipe.",
       "Level 3! You're a true cook now.", ("level", "cook", 3), gold=350),
]
CRAZY_QUESTS = [
    dict(_q("cd1", "Crazy Dew", "One of Every Crop", "Bring one of every crop you have grown.",
            "I'm making a list. One of every crop, please. Every single one!",
            "Every crop! You've got a whole garden in you. Make your wish.",
            ("items", {k: 1 for k in CROPS})), wish=True),
    dict(_q("cd2", "Crazy Dew", "One of Every Fish", "Bring one of every kind of fish.",
            "Now the river. One of every fish I've ever named, and a few I haven't.",
            "The whole river, in a bucket. Impressive. Make your wish.",
            ("items", {k: 1 for k in FISH})), wish=True),
    dict(_q("cd3", "Crazy Dew", "One of Every Dish", "Cook one of every dish in the recipe book.",
            "Every dish I've ever written down. Cook one of each, then come back.",
            "Every dish! My stomach is singing. Make your wish.",
            ("items", {k: 1 for k in RECIPES})), wish=True),
    dict(_q("cd4", "Crazy Dew", "Mountain of Materials", "Bring 50 stone, 50 wood, 30 scrap, 10 old coins, 30 flowers.",
            "Build me a mountain! Stone, wood, scrap, coins and flowers. Lots of each.",
            "A mountain indeed. Make your wish.",
            ("items", {"stone": 50, "wood": 50, "scrap": 30, "old_coin": 10, "flower": 30})), wish=True),
    dict(_q("cd5", "Crazy Dew", "Seed Hoard", "Bring 5 seed packets of every crop.",
            "Seeds, seeds, seeds! Five packets of every crop. Don't worry, I'll give some back.",
            "Five of each! The seed shelf is full. Make your wish.",
            ("items", {k + "_seed": 5 for k in CROPS})), wish=True),
    dict(_q("cd6", "Crazy Dew", "The Rarest Things", "Bring 1 Golden Carp, 1 Koi and 5 old coins.",
            "Last one. Only the rare things now. Golden Carp, a Koi, five old coins.",
            "You did it. All of it. Make your final wish.",
            ("items", {"rare_fish": 1, "koi": 1, "old_coin": 5})), wish=True),
]
QUESTS += CRAZY_QUESTS
QUEST_BY_ID = {q["id"]: q for q in QUESTS}

MABEL_LINES = [
    "Fresh seeds this morning! Parsnips are quick, pumpkins pay best.",
    "Cooked meals sell for far more than raw crops. Just saying.",
    "My knees say rain tomorrow. Rain means you can skip watering!",
    "A pumpkin pie is worth its weight in gold. Almost.",
    "Welcome in, welcome in! Mind the step.",
]
FERN_LINES = [
    "Sixty years in this valley and the sunsets still get me.",
    "Chickens lay an egg every morning. Be kind to them.",
    "Wildflower tea cures most things. Two flowers, one pot.",
    "I used to farm your land, you know. Good soil. Stubborn rocks.",
    "Don't stay up past midnight. The night air is for owls.",
]


# ============================================================ helpers
def sea_beach_x(y):
    """First beach column on row y. The shoreline wobbles gently so it looks like a real coast."""
    return SEA_SHORE + int(round(1 + 0.6 * math.sin(y / 5.5) + 0.4 * math.sin(y / 2.3)))


def river_center(y):
    """Column of the middle of the river on row y (the river winds left and right)."""
    return 89 + int(round(3 * math.sin(y / 8.5) + 1.5 * math.sin(y / 3.7)))


def east_clear(x, y):
    """East-bank village land: no rocks or flowers here (trees are removed by x >= 60)."""
    return 90 <= x <= 127 and 33 <= y <= 52


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fmt_time(h):
    hh = int(h)
    mm = int((h - hh) * 60) // 10 * 10
    suffix = "am" if (hh % 24) < 12 else "pm"
    return "%d:%02d %s" % (hh % 12 or 12, mm, suffix)


def surf(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


# ============================================================ sprite builders
SPR = {}


def draw_fish_icon(s, key, color, tier=0):
    """Draws one fish. The same key always gives the same fish; different keys look different."""
    rnd = random.Random(int(hashlib.md5(key.encode()).hexdigest()[:8], 16))
    base = color
    belly = lerp_col(base, (255, 255, 246), 0.5)
    dark = lerp_col(base, (24, 30, 46), 0.42)
    bw, bh = rnd.randrange(9, 13), rnd.randrange(5, 8)
    cx, cy = 7, 8
    tail = rnd.choice(("fork", "round", "fan"))
    fin = rnd.random() < 0.65
    pattern = rnd.choice(("plain", "stripes", "spots", "band"))
    tx = cx + bw // 2 - 1                          # the tail sits behind the body
    if tail == "fork":
        pygame.draw.polygon(s, dark, [(tx, cy), (tx + 4, cy - 4), (tx + 3, cy), (tx + 4, cy + 4)])
    elif tail == "round":
        pygame.draw.circle(s, base, (tx + 2, cy), 3)
    else:
        pygame.draw.polygon(s, base, [(tx, cy), (tx + 4, cy - 3), (tx + 4, cy + 3)])
    pygame.draw.ellipse(s, base, (cx - bw // 2, cy - bh // 2, bw, bh))
    pygame.draw.ellipse(s, belly, (cx - bw // 2 + 2, cy, bw - 4, bh // 2 + 1))
    if fin:
        pygame.draw.polygon(s, dark, [(cx - 1, cy - bh // 2), (cx + 2, cy - bh // 2 - 3), (cx + 3, cy - bh // 2)])
    if pattern == "stripes":
        for x in range(cx - bw // 2 + 3, cx + bw // 2 - 1, 3):
            s.fill(dark, (x, cy - bh // 2 + 1, 1, bh - 2))
    elif pattern == "spots":
        for _ in range(3):
            x = rnd.randrange(cx - bw // 2 + 2, cx + bw // 2 - 2)
            y = rnd.randrange(cy - bh // 2 + 1, cy + bh // 2 - 1)
            s.set_at((x, y), dark)
    elif pattern == "band":
        s.fill(dark, (cx - bw // 2, cy - 1, bw, 1))
    s.set_at((cx - bw // 2 + 2, cy - 1), (20, 20, 30))          # eye
    if tier >= 3:                                                # rare fish shine
        s.set_at((cx + 1, cy - bh // 2 + 1), (255, 250, 210))
        s.set_at((cx + 2, cy - bh // 2 + 1), (255, 250, 210))
    return (bw, bh, tail, fin, pattern, base)


TOOL_ICON_KEYS = ("hoe", "can", "axe", "pick", "rod")


def make_tool_icon(key):
    """Shaded tool icons. Drawn at 3x size with dark outlines, wood grain and steel
    highlights, then scaled down to 16x16 so the edges come out smooth."""
    S = 48
    big = surf(S, S)
    ink = (52, 36, 28)
    wood, wood_l, wood_d = (168, 118, 70), (210, 166, 110), (112, 74, 42)
    steel, steel_l, steel_d = (196, 204, 216), (244, 248, 252), (120, 130, 146)

    def handle(a, b, w):
        pygame.draw.line(big, ink, a, b, w + 4)
        pygame.draw.line(big, wood, a, b, w)
        pygame.draw.line(big, wood_l, (a[0] - 1, a[1] - 1), (b[0] - 1, b[1] - 1), max(1, w // 3))
        pygame.draw.line(big, wood_d, (a[0] + 2, a[1] + 2), (b[0] + 2, b[1] + 2), max(1, w // 3))

    def solid(pts, fill, edge=ink, w=3):
        pygame.draw.polygon(big, fill, pts)
        pygame.draw.polygon(big, edge, pts, w)

    def shine(a, b):
        pygame.draw.line(big, steel_l, a, b, 2)

    if key == "hoe":
        handle((8, 44), (26, 22), 5)
        solid([(22, 22), (40, 10), (46, 16), (36, 30), (26, 30)], steel)
        shine((41, 12), (45, 16))
        pygame.draw.line(big, steel_d, (27, 27), (36, 28), 3)
    elif key == "axe":
        handle((8, 44), (26, 20), 5)
        solid([(14, 20), (26, 6), (40, 8), (46, 16), (44, 30), (36, 40), (24, 36), (18, 28)], steel)
        shine((30, 9), (40, 9))
        shine((43, 17), (43, 28))
        pygame.draw.line(big, steel_d, (44, 30), (36, 39), 3)
    elif key == "pick":
        handle((8, 44), (30, 18), 5)
        solid([(3, 24), (12, 12), (24, 8), (38, 8), (46, 16), (42, 20), (36, 14), (26, 14), (18, 18), (10, 28)],
              steel)
        shine((14, 13), (24, 9))
        pygame.draw.line(big, steel_d, (30, 14), (40, 18), 2)
    elif key == "can":
        blue, blue_l, blue_d = (84, 140, 204), (138, 190, 240), (56, 98, 160)
        arch = [(12, 20), (14, 9), (24, 4), (32, 9), (34, 20)]
        pygame.draw.lines(big, ink, False, arch, 8)
        pygame.draw.lines(big, blue_d, False, arch, 5)
        pygame.draw.rect(big, ink, (8, 18, 28, 24), border_radius=7)
        pygame.draw.rect(big, blue, (10, 20, 24, 20), border_radius=6)
        pygame.draw.rect(big, blue_l, (12, 22, 6, 14), border_radius=3)
        pygame.draw.rect(big, blue_d, (10, 32, 24, 4))
        solid([(30, 28), (42, 12), (48, 16), (38, 34)], blue)
        pygame.draw.polygon(big, blue_l, [(42, 12), (48, 16), (46, 18), (41, 15)])
        pygame.draw.rect(big, ink, (41, 4, 8, 9), border_radius=2)
        for hx, hy in ((43, 6), (46, 8), (43, 10)):
            big.set_at((hx, hy), ink)
    elif key == "rod":
        pygame.draw.line(big, ink, (6, 44), (40, 8), 6)
        pygame.draw.line(big, wood, (6, 44), (40, 8), 3)
        pygame.draw.line(big, wood_l, (7, 42), (40, 9), 1)
        for t in (0.22, 0.3, 0.38):
            gx, gy = 6 + 34 * t, 44 - 36 * t
            pygame.draw.line(big, (190, 52, 46), (gx - 3, gy - 3), (gx + 3, gy + 3), 3)
        pygame.draw.circle(big, ink, (18, 34), 8)
        pygame.draw.circle(big, steel, (18, 34), 5)
        pygame.draw.line(big, steel_d, (18, 30), (18, 38), 2)
        pygame.draw.line(big, steel_d, (14, 34), (22, 34), 2)
        pygame.draw.line(big, (230, 230, 236), (40, 8), (44, 36), 1)
        pygame.draw.circle(big, ink, (44, 37), 5)
        pygame.draw.circle(big, (220, 60, 50), (44, 37), 4)
        pygame.draw.circle(big, (250, 250, 250), (44, 34), 2)
        pygame.draw.lines(big, steel_d, False, [(44, 42), (44, 45), (41, 46)], 2)
    return pygame.transform.smoothscale(big, (16, 16))


def make_icon(key):
    if key in TOOL_ICON_KEYS:
        return make_tool_icon(key)
    s = surf(16, 16)
    wood = (150, 104, 62)
    steel = (176, 184, 196)
    steel_d = (120, 128, 142)
    green = (86, 170, 72)

    def R(c, x, y, w, h):
        s.fill(c, (x, y, w, h))

    def C(c, x, y, r):
        pygame.draw.circle(s, c, (x, y), r)

    def P(c, pts):
        pygame.draw.polygon(s, c, pts)

    def L(c, a, b, w=1):
        pygame.draw.line(s, c, a, b, w)

    def E(c, x, y, w, h):
        pygame.draw.ellipse(s, c, (x, y, w, h))

    if key == "hoe":
        L(wood, (3, 14), (11, 5), 2)
        P(steel, [(9, 2), (14, 3), (14, 7), (11, 6)])
        L(steel_d, (10, 6), (14, 7))
    elif key == "can":
        R((84, 140, 204), 3, 7, 9, 6)
        R((124, 180, 232), 3, 7, 9, 2)
        L((84, 140, 204), (12, 9), (15, 5), 2)
        L((60, 100, 160), (3, 8), (1, 8))
        L((60, 100, 160), (1, 8), (1, 12))
        L((60, 100, 160), (1, 12), (3, 12))
        R((60, 100, 160), 3, 12, 9, 1)
    elif key == "axe":
        L(wood, (3, 14), (10, 4), 2)
        P(steel, [(8, 2), (14, 3), (14, 9), (10, 8)])
        L(steel_d, (8, 2), (10, 8))
    elif key == "pick":
        L(wood, (3, 14), (11, 5), 2)
        P(steel, [(3, 6), (8, 2), (14, 4), (15, 8), (12, 5), (8, 4), (5, 8)])
    elif key.endswith("_seed"):
        crop = key[:-5]
        R((240, 226, 188), 4, 2, 8, 12)
        R((196, 160, 110), 4, 2, 8, 2)
        pygame.draw.rect(s, (110, 80, 52), (4, 2, 8, 12), 1)
        C(CROPS[crop]["fruit"], 8, 9, 2)
        L(green, (8, 7), (8, 5))
    elif key == "parsnip":
        P(CROPS[key]["fruit"], [(6, 6), (10, 6), (9, 14), (8, 15), (7, 14)])
        L((220, 206, 170), (7, 8), (8, 13))
        for a in ((5, 1), (8, 0), (11, 1)):
            L(green, (8, 6), a)
    elif key == "wheat":
        for x in (4, 8, 12):
            L((200, 160, 60), (x, 15), (x, 5))
            R(CROPS[key]["fruit"], x - 1, 2, 3, 5)
            R((250, 226, 130), x, 2, 1, 5)
    elif key == "potato":
        E(CROPS[key]["fruit"], 2, 5, 12, 9)
        E((214, 176, 120), 3, 5, 8, 5)
        for p in ((5, 9), (9, 10), (11, 8)):
            s.set_at(p, (130, 96, 60))
    elif key == "tomato":
        C(CROPS[key]["fruit"], 8, 9, 6)
        C((240, 110, 96), 6, 7, 2)
        for a in ((4, 4), (12, 4), (8, 2), (5, 5), (11, 5)):
            L(green, (8, 4), a)
    elif key == "pumpkin":
        E((214, 108, 30), 1, 5, 8, 10)
        E((214, 108, 30), 7, 5, 8, 10)
        E(CROPS[key]["fruit"], 4, 4, 8, 11)
        L((200, 96, 26), (8, 5), (8, 14))
        R((90, 120, 50), 7, 2, 2, 3)
    elif key == "egg":
        E((226, 212, 190), 4, 3, 8, 11)
        E((255, 250, 240), 4, 3, 7, 9)
    elif key == "flower":
        L(green, (8, 15), (8, 8))
        for a in ((8, 5), (5, 7), (11, 7), (6, 4), (10, 4)):
            C((248, 176, 200), a[0], a[1], 2)
        C((250, 220, 90), 8, 6, 1)
    elif key == "wood":
        R((112, 76, 46), 1, 4, 14, 5)
        R((150, 104, 62), 1, 4, 14, 2)
        C((206, 164, 106), 2, 6, 2)
        R((112, 76, 46), 3, 9, 12, 5)
        R((150, 104, 62), 3, 9, 12, 2)
        C((206, 164, 106), 4, 11, 2)
    elif key == "stone":
        P((140, 144, 150), [(3, 13), (2, 8), (6, 4), (11, 4), (14, 8), (13, 13)])
        L((190, 194, 200), (5, 6), (10, 5))
        L((104, 108, 116), (4, 13), (13, 13))
    elif key == "coin":
        C((200, 140, 30), 8, 8, 7)
        C(GOLD, 8, 8, 6)
        C((252, 226, 120), 6, 6, 2)
        R((200, 140, 30), 7, 5, 2, 6)
    elif key in CROPS:
        C(CROPS[key]["fruit"], 8, 9, 6)
        C((255, 255, 255), 6, 7, 1)
        L(green, (8, 3), (8, 1))
    elif key == "villager_house_kit":
        P((230, 200, 150), [(8, 1), (15, 7), (1, 7)])
        R((230, 200, 150), 3, 7, 10, 8)
        R((190, 82, 62), 2, 5, 12, 2)
        R((120, 80, 50), 7, 10, 3, 5)
    elif key == "rod":
        L(wood, (2, 14), (12, 3), 2)
        L((220, 220, 226), (12, 3), (14, 4))
        L((230, 230, 236), (14, 4), (14, 11))
        C((220, 60, 50), 14, 12, 2)
    elif key in FISH:
        draw_fish_icon(s, key, FISH[key]["color"], FISH[key]["tier"])
    elif key == "flour":
        P((236, 226, 200), [(3, 6), (13, 6), (14, 14), (2, 14)])
        R((200, 186, 150), 5, 3, 6, 3)
        R((150, 120, 80), 6, 9, 4, 2)
    elif key == "milk":
        R((250, 250, 252), 4, 5, 8, 10)
        P((250, 250, 252), [(4, 5), (8, 1), (12, 5)])
        R((90, 150, 220), 4, 8, 8, 3)
        pygame.draw.rect(s, (110, 120, 140), (4, 5, 8, 10), 1)
    elif key == "sugar":
        R((250, 240, 245), 3, 6, 10, 8)
        R((240, 150, 180), 3, 6, 10, 2)
        for p in ((5, 9), (8, 11), (11, 9)):
            s.set_at(p, (200, 200, 210))
    elif key == "ticket":
        R((246, 150, 60), 1, 4, 14, 8)
        C((200, 100, 30), 1, 8, 2)
        C((200, 100, 30), 14, 8, 2)
        R((255, 220, 120), 4, 6, 8, 1)
        R((255, 220, 120), 4, 9, 8, 1)
    elif key == "energy_bar":
        R((90, 170, 90), 2, 5, 12, 7)
        R((250, 240, 200), 4, 6, 8, 5)
        R((220, 80, 60), 6, 7, 4, 3)
        L((60, 120, 60), (2, 5), (13, 5))
    elif ITEMS.get(key, {}).get("kind") == "food":
        plate = (238, 232, 222)
        plate_d = (190, 182, 170)
        if key in ("stew", "soup", "tea", "latte", "pumpkin_latte", "fish_stew"):
            E((120, 84, 60), 2, 6, 12, 9)
            E((160, 112, 80), 2, 5, 12, 8)
            col = {"stew": (206, 120, 56), "soup": (214, 64, 48), "tea": (176, 120, 70),
                   "latte": (236, 212, 176), "pumpkin_latte": (232, 144, 64), "fish_stew": (206, 110, 76)}[key]
            E(col, 3, 5, 10, 5)
            if key == "stew":
                for p in ((5, 7), (8, 6), (10, 8)):
                    s.set_at(p, (110, 170, 80))
            if key == "tea":
                L((240, 240, 236), (13, 7), (15, 9))
        else:
            E(plate_d, 1, 8, 14, 7)
            E(plate, 1, 7, 14, 7)
            if key == "fried_egg":
                E((255, 252, 244), 3, 7, 10, 6)
                C((248, 190, 40), 8, 9, 2)
            elif key == "bread":
                E((206, 146, 76), 3, 3, 10, 9)
                E((232, 178, 100), 3, 3, 10, 5)
                for x in (5, 8, 11):
                    L((170, 112, 56), (x, 4), (x + 1, 7))
            elif key == "pie":
                E((214, 160, 90), 2, 5, 12, 9)
                E((232, 128, 40), 4, 6, 8, 5)
                L((214, 160, 90), (4, 8), (12, 8))
                L((214, 160, 90), (8, 6), (8, 11))
            elif key == "pancakes":
                for yy, cc in ((8, (214, 160, 80)), (6, (232, 184, 100)), (4, (214, 160, 80))):
                    E(cc, 3, yy, 10, 4)
                R((255, 232, 120), 6, 3, 4, 2)
            elif key == "cake":
                P((250, 200, 210), [(2, 12), (14, 12), (12, 5), (4, 5)])
                R((255, 250, 240), 3, 8, 10, 2)
                C((220, 50, 70), 8, 4, 2)
            elif key == "grilled_fish":
                E((176, 120, 70), 2, 6, 11, 6)
                P((176, 120, 70), [(12, 9), (15, 6), (15, 12)])
                for xx in (5, 7, 9):
                    L((90, 60, 40), (xx, 6), (xx, 11))
    else:
        R((200, 60, 60), 4, 4, 8, 8)
    return s


EXTRA_SHAPES = ("leaf", "bush", "stalk", "bulb", "pod", "spike")


def draw_shape_extra(s, shape, fr, g1, g2):
    """Fully grown looks for the extra crop shapes (16x16 pixels)."""
    if shape == "leaf":                       # leafy head
        for x, y, r in ((5, 9, 4), (11, 9, 4), (8, 6, 4), (8, 11, 4)):
            pygame.draw.circle(s, g1, (x, y), r)
        pygame.draw.circle(s, lerp_col(g1, (255, 255, 255), 0.3), (8, 8), 2)
    elif shape == "bush":                     # berry bush
        pygame.draw.circle(s, g2, (8, 9), 6)
        pygame.draw.circle(s, g1, (7, 7), 5)
        for x, y in ((4, 9), (9, 6), (11, 10), (6, 12)):
            pygame.draw.circle(s, fr, (x, y), 1)
    elif shape == "stalk":                    # tall stalk with a bloom on top
        pygame.draw.line(s, g2, (8, 15), (8, 3), 2)
        for y in (6, 9, 12):
            pygame.draw.line(s, g1, (8, y), (5, y - 2), 1)
            pygame.draw.line(s, g1, (8, y), (11, y - 2), 1)
        pygame.draw.circle(s, fr, (8, 3), 3)
    elif shape == "bulb":                     # bulb with leaf tops
        pygame.draw.ellipse(s, fr, (4, 7, 9, 8))
        pygame.draw.line(s, g1, (8, 7), (5, 1), 1)
        pygame.draw.line(s, g1, (8, 7), (11, 1), 1)
        pygame.draw.line(s, g2, (8, 7), (8, 0), 1)
    elif shape == "pod":                      # hanging pods
        pygame.draw.ellipse(s, g1, (2, 4, 12, 9))
        for x, y in ((5, 8), (8, 9), (11, 7)):
            pygame.draw.line(s, g2, (x, y), (x, y + 6), 2)
            pygame.draw.circle(s, fr, (x, y + 7), 2)
    else:                                     # spike: a pointed tip
        pygame.draw.polygon(s, g1, [(8, 0), (14, 8), (8, 15), (2, 8)])
        pygame.draw.polygon(s, fr, [(8, 3), (11, 8), (8, 12), (5, 8)])


def make_crop_sprite(ck, stage):
    s = surf(16, 16)
    d = CROPS[ck]
    g1, g2, fr = (92, 176, 76), (58, 128, 56), d["fruit"]

    def L(c, a, b, w=1):
        pygame.draw.line(s, c, a, b, w)

    def E(c, x, y, w, h):
        pygame.draw.ellipse(s, c, (x, y, w, h))

    if stage == 0:
        E((112, 78, 54), 5, 11, 6, 4)
        s.set_at((7, 11), (150, 110, 76))
    elif stage == 1:
        L(g2, (8, 14), (8, 10))
        E(g1, 4, 8, 5, 3)
        E(g1, 8, 7, 5, 3)
    elif stage == 2:
        L(g2, (8, 14), (8, 6))
        E(g1, 3, 9, 6, 3)
        E(g1, 8, 8, 6, 3)
        E(g1, 5, 5, 6, 3)
    elif stage == 3:
        L(g2, (8, 14), (8, 4))
        E(g1, 2, 9, 6, 3)
        E(g1, 8, 9, 6, 3)
        E(g1, 4, 5, 7, 3)
        E(g2, 6, 3, 4, 3)
        pygame.draw.circle(s, fr, (8, 3), 1)
    else:
        shape = d["shape"]
        if shape == "root":
            for a in ((4, 3), (8, 1), (12, 3), (6, 2), (10, 2)):
                L(g1, (8, 10), a, 2)
            pygame.draw.circle(s, fr, (8, 12), 3)
            s.set_at((7, 11), (255, 252, 236))
        elif shape == "wheat":
            for x in (3, 6, 9, 12):
                L((196, 164, 70), (x, 15), (x, 4))
                s.fill(fr, (x - 1, 1, 3, 5))
                s.fill((252, 228, 130), (x, 1, 1, 5))
        elif shape == "round":
            E(g2, 1, 5, 14, 10)
            E(g1, 2, 4, 12, 9)
            for p in ((4, 8), (8, 6), (11, 9), (6, 11), (10, 12)):
                pygame.draw.circle(s, fr, p, 2)
                s.set_at((p[0] - 1, p[1] - 1), (255, 255, 255))
        elif shape in EXTRA_SHAPES:
            draw_shape_extra(s, shape, fr, g1, g2)
        else:
            for a in ((2, 8), (14, 8), (3, 4), (13, 4)):
                L(g2, (8, 8), a, 2)
            E((196, 98, 28), 1, 6, 8, 9)
            E((196, 98, 28), 7, 6, 8, 9)
            E(fr, 3, 5, 10, 10)
            L((200, 96, 26), (8, 6), (8, 14))
            L((200, 96, 26), (5, 7), (5, 13))
            L((200, 96, 26), (11, 7), (11, 13))
            s.fill((90, 120, 50), (7, 2, 2, 4))
    return s


def make_char(skin, hair, shirt, pants, hat=None, skirt=False, apron=False, bun=False):
    frames = {}
    shoe = (74, 52, 40)
    eye = (40, 28, 24)
    for d in ("down", "up", "right"):
        for f in range(4):
            s = surf(16, 24)
            step = (0, 1, 0, -1)[f]
            side = d == "right"
            if skirt:
                s.fill(shirt, (3, 17, 10, 5))
                s.fill(skin, (5, 21, 2, 2))
                s.fill(skin, (9, 21, 2, 2))
                s.fill(shoe, (5, 22, 2, 1))
                s.fill(shoe, (9, 22, 2, 1))
            elif side:
                s.fill(pants, (6 + step, 18, 3, 5))
                s.fill(pants, (8 - step, 18, 3, 5))
                s.fill(shoe, (6 + step, 22, 4, 1))
                s.fill(shoe, (8 - step, 22, 4, 1))
            else:
                ll = 5 - (1 if step == 1 else 0)
                lr = 5 - (1 if step == -1 else 0)
                s.fill(pants, (5, 18, 3, ll))
                s.fill(pants, (8, 18, 3, lr))
                s.fill(shoe, (5, 17 + ll, 3, 1))
                s.fill(shoe, (8, 17 + lr, 3, 1))
            s.fill(shirt, (4, 11, 8, 7))
            if apron:
                s.fill((244, 240, 230), (5, 13, 6, 5))
            if side:
                ax = 6 - step
                s.fill(shirt, (ax, 11, 3, 6))
                s.fill(skin, (ax, 16, 3, 1))
            else:
                al = 1 if step == 1 else 0
                ar = 1 if step == -1 else 0
                s.fill(shirt, (2, 11 + al, 2, 5))
                s.fill(shirt, (12, 11 + ar, 2, 5))
                s.fill(skin, (2, 16 + al, 2, 1))
                s.fill(skin, (12, 16 + ar, 2, 1))
            s.fill(skin, (4, 3, 8, 8))
            if d == "down":
                s.fill(hair, (4, 3, 8, 3))
                s.fill(hair, (4, 5, 1, 3))
                s.fill(hair, (11, 5, 1, 3))
                s.fill(eye, (6, 7, 1, 2))
                s.fill(eye, (9, 7, 1, 2))
                s.set_at((5, 9), (236, 160, 150))
                s.set_at((10, 9), (236, 160, 150))
            elif d == "up":
                s.fill(hair, (4, 3, 8, 8))
            else:
                s.fill(hair, (4, 3, 8, 3))
                s.fill(hair, (4, 5, 4, 5))
                s.fill(eye, (10, 7, 1, 2))
            if bun:
                s.fill(hair, (6, 1, 4, 3))
            if hat:
                s.fill(hat, (2, 4, 12, 2))
                s.fill(hat, (4, 1, 8, 4))
                s.fill((200, 70, 60), (4, 4, 8, 1))
            frames[(d, f)] = s
    for f in range(4):
        frames[("left", f)] = pygame.transform.flip(frames[("right", f)], True, False)
    return frames


def make_chicken(frame):
    s = surf(12, 12)
    body, shade = (246, 240, 226), (214, 206, 190)
    pygame.draw.ellipse(s, shade, (1, 4, 9, 7))
    pygame.draw.ellipse(s, body, (1, 3, 9, 7))
    s.fill(shade, (0, 4, 2, 2))
    if frame == 3:
        pygame.draw.circle(s, body, (10, 8), 2)
        s.set_at((11, 9), (240, 160, 40))
        s.set_at((10, 7), (200, 40, 40))
    else:
        pygame.draw.circle(s, body, (9, 3), 2)
        s.set_at((9, 0), (210, 50, 50))
        s.set_at((8, 1), (210, 50, 50))
        s.set_at((11, 3), (240, 160, 40))
        s.set_at((10, 3), (40, 28, 24))
    off = 1 if frame == 1 else 0
    s.set_at((4 + off, 11), (240, 160, 40))
    s.set_at((7 - off, 11), (240, 160, 40))
    return s


def make_glow(r):
    s = pygame.Surface((r * 2, r * 2))
    s.fill((0, 0, 0))
    for i in range(r, 0, -1):
        k = (1 - i / r) ** 1.6
        pygame.draw.circle(s, (int(255 * k), int(214 * k), int(140 * k)), (r, r), i)
    return s


VILLAGE_STYLES = {
    "village_house": dict(wall=(236, 222, 186), trim=(168, 134, 96), roof=(64, 128, 118),
                          roof_d=(42, 92, 86), door=(40, 90, 84), chimney=(150, 84, 72)),
    "village_house2": dict(wall=(176, 186, 202), trim=(84, 88, 104), roof=(108, 82, 142),
                           roof_d=(78, 56, 106), door=(124, 62, 52), chimney=(120, 110, 120)),
    "village_house3": dict(wall=(238, 206, 150), trim=(248, 242, 230), roof=(150, 86, 54),
                           roof_d=(110, 60, 36), door=(72, 122, 74), chimney=(120, 70, 60)),
    "player_house": dict(wall=(230, 200, 150), trim=(150, 112, 74), roof=(190, 82, 62),
                         roof_d=(140, 56, 42), door=(60, 100, 160), chimney=(110, 96, 90)),
}


def make_village_house(style):
    """A 6x5 tile house: gable roof with shingles, boarded walls, two windows, a door and a chimney."""
    p = VILLAGE_STYLES[style]
    s = surf(96, 80)
    wall, trim, roof, roof_d = p["wall"], p["trim"], p["roof"], p["roof_d"]
    wall_d = lerp_col(wall, (60, 44, 36), 0.25)
    s.fill(wall, (6, 36, 84, 40))
    for x in range(6, 90, 7):                        # vertical boards
        s.fill(wall_d, (x, 36, 1, 40))
    if style == "village_house2":                    # half-timbering
        for x in (6, 44, 88):
            s.fill(trim, (x, 36, 3, 40))
        s.fill(trim, (6, 56, 84, 3))
    s.fill((150, 150, 156), (4, 74, 88, 6))          # stone foundation
    for x in range(4, 92, 8):
        s.fill((118, 118, 124), (x, 74, 1, 6))
    s.fill(p["chimney"], (66, 4, 9, 22))
    s.fill(lerp_col(p["chimney"], (0, 0, 0), 0.3), (66, 4, 9, 2))
    roof_poly = [(0, 38), (96, 38), (48, 0)]         # gable roof with shingle rows
    pygame.draw.polygon(s, roof, roof_poly)
    for y in range(4, 38, 5):
        half = int(48 * y / 38)
        pygame.draw.line(s, roof_d, (48 - half, y), (48 + half, y), 1)
        offset = 0 if (y // 5) % 2 == 0 else 4
        for x in range(48 - half + offset, 48 + half, 8):
            s.fill(roof_d, (x, y, 1, 4))
    pygame.draw.polygon(s, roof_d, roof_poly, 2)
    for wx in (14, 68):                              # windows: frame, cross bars, sill
        s.fill(trim, (wx - 2, 44, 18, 18))
        s.fill((178, 218, 236), (wx, 46, 14, 14))
        s.fill(trim, (wx + 6, 46, 2, 14))
        s.fill(trim, (wx, 52, 14, 2))
        s.fill(trim, (wx - 3, 62, 20, 3))
    if style in ("village_house3", "player_house"):  # flower boxes under the windows
        for wx in (14, 68):
            s.fill((120, 74, 50), (wx - 2, 65, 18, 4))
            for i, c in enumerate(((236, 110, 140), (250, 220, 100), (200, 140, 240))):
                s.fill(c, (wx + i * 5, 63, 3, 2))
    s.fill(trim, (40, 52, 16, 22))                   # door: frame, panel line, handle
    s.fill(p["door"], (42, 54, 12, 20))
    s.fill(lerp_col(p["door"], (0, 0, 0), 0.25), (47, 54, 2, 20))
    s.set_at((51, 66), (240, 200, 80))
    s.fill((150, 150, 156), (38, 74, 20, 2))
    return s


def build_static_sprites():
    # --- house
    h = surf(96, 80)
    h.fill((222, 186, 132), (8, 34, 80, 42))
    for x in range(8, 88, 8):
        h.fill((190, 152, 100), (x, 34, 1, 42))
    h.fill((150, 150, 156), (8, 70, 80, 6))
    for x in range(8, 88, 10):
        h.fill((126, 126, 134), (x, 70, 1, 6))
    pygame.draw.rect(h, (120, 84, 56), (8, 34, 80, 42), 1)
    roof, roof_d, roof_l = (176, 72, 60), (140, 52, 48), (206, 100, 80)
    pts = [(2, 38), (94, 38), (76, 6), (20, 6)]
    pygame.draw.polygon(h, roof, pts)
    for y in range(12, 38, 6):
        xl = 20 - 0.6 * (y - 6)
        xr = 76 + 0.6 * (y - 6)
        pygame.draw.line(h, roof_d, (xl, y), (xr, y))
        off = 4 if (y // 6) % 2 else 0
        for x in range(int(xl) + off, int(xr), 8):
            pygame.draw.line(h, roof_d, (x, y), (x, y + 5))
    pygame.draw.line(h, roof_l, (20, 7), (76, 7), 2)
    pygame.draw.polygon(h, (96, 40, 36), pts, 2)
    h.fill((150, 96, 80), (58, 0, 10, 14))
    h.fill((120, 70, 60), (57, 0, 12, 3))
    h.fill((112, 72, 44), (42, 50, 12, 26))
    pygame.draw.rect(h, (80, 50, 30), (42, 50, 12, 26), 1)
    h.fill((92, 58, 34), (44, 52, 3, 10))
    h.fill((92, 58, 34), (49, 52, 3, 10))
    h.fill((240, 200, 80), (51, 64, 2, 2))
    for wx in (16, 62):
        h.fill((240, 236, 226), (wx, 46, 18, 16))
        h.fill((150, 206, 236), (wx + 2, 48, 14, 12))
        h.fill((240, 236, 226), (wx + 8, 48, 2, 12))
        h.fill((240, 236, 226), (wx + 2, 53, 14, 2))
        h.fill((120, 84, 56), (wx, 62, 18, 4))
        for i, c in enumerate(((236, 110, 140), (250, 220, 100), (200, 140, 240))):
            h.fill(c, (wx + 2 + i * 6, 61, 3, 2))
    SPR["house"] = h
    SPR["house_windows"] = [(18, 48, 14, 12), (64, 48, 14, 12)]
    SPR["village_windows"] = [(14, 46, 14, 14), (68, 46, 14, 14)]
    for style in VILLAGE_STYLES:
        SPR[style] = make_village_house(style)
    # --- kitchen
    k = surf(64, 48)
    k.fill((236, 222, 190), (4, 20, 56, 26))
    for x in range(4, 60, 7):
        k.fill((210, 194, 160), (x, 20, 1, 26))
    pygame.draw.rect(k, (150, 120, 84), (4, 20, 56, 26), 1)
    kp = [(0, 24), (64, 24), (54, 4), (10, 4)]
    pygame.draw.polygon(k, (72, 140, 132), kp)
    for y in range(9, 24, 5):
        xl = 10 - 0.42 * (y - 4)
        xr = 54 + 0.42 * (y - 4)
        pygame.draw.line(k, (50, 108, 102), (xl, y), (xr, y))
    pygame.draw.polygon(k, (36, 80, 78), kp, 2)
    k.fill((120, 110, 110), (42, 0, 8, 10))
    k.fill((90, 82, 82), (41, 0, 10, 2))
    k.fill((60, 40, 30), (10, 28, 24, 14))
    pygame.draw.rect(k, (240, 236, 226), (9, 27, 26, 16), 2)
    k.fill((120, 84, 56), (8, 43, 28, 3))
    k.fill((112, 72, 44), (42, 28, 12, 18))
    pygame.draw.rect(k, (80, 50, 30), (42, 28, 12, 18), 1)
    k.fill((240, 200, 80), (51, 38, 2, 2))
    k.fill((130, 90, 56), (55, 38, 7, 8))  # firewood
    for yy in (39, 42):
        k.fill((170, 120, 76), (56, yy, 5, 2))
    SPR["kitchen"] = k
    SPR["kitchen_window"] = (11, 29, 22, 12)
    # --- shipping bin
    b = surf(32, 24)
    b.fill((140, 98, 62), (2, 10, 28, 14))
    for x in range(2, 30, 5):
        b.fill((104, 70, 44), (x, 10, 1, 14))
    pygame.draw.rect(b, (80, 54, 34), (2, 10, 28, 14), 1)
    b.fill((60, 40, 30), (4, 6, 24, 5))
    pygame.draw.polygon(b, (176, 126, 80), [(1, 10), (31, 10), (29, 3), (3, 3)])
    pygame.draw.polygon(b, (100, 70, 44), [(1, 10), (31, 10), (29, 3), (3, 3)], 1)
    b.fill((170, 170, 180), (4, 14, 24, 2))
    SPR["bin"] = b
    # --- stall (back and front are drawn at different depths so Mabel stands behind the counter)
    sb = surf(80, 48)
    sb.fill((170, 126, 84), (4, 8, 72, 40))
    for x in range(4, 76, 6):
        sb.fill((140, 100, 66), (x, 8, 1, 40))
    for y in (22, 34):
        sb.fill((110, 76, 48), (6, y, 68, 3))
    rnd = random.Random(3)
    cols = [(220, 80, 70), (240, 200, 80), (110, 180, 90), (90, 150, 220), (230, 150, 70)]
    for y in (14, 26):
        for x in range(8, 70, 8):
            c = rnd.choice(cols)
            sb.fill(c, (x, y + 2, 5, 6))
            sb.fill((255, 255, 255), (x, y + 2, 1, 6))
    SPR["stall_back"] = sb
    sf = surf(80, 48)
    for i in range(10):
        c = (214, 70, 64) if i % 2 == 0 else (248, 240, 228)
        sf.fill(c, (i * 8, 0, 8, 11))
        pygame.draw.circle(sf, c, (i * 8 + 4, 11), 4)
    pygame.draw.line(sf, (110, 40, 36), (0, 0), (80, 0), 2)
    sf.fill((130, 92, 60), (1, 12, 3, 36))
    sf.fill((130, 92, 60), (76, 12, 3, 36))
    sf.fill((204, 156, 100), (0, 32, 80, 4))
    sf.fill((178, 130, 84), (0, 36, 80, 12))
    for x in range(0, 80, 8):
        sf.fill((140, 100, 66), (x, 36, 1, 12))
    for x, c in ((10, (220, 70, 60)), (24, (240, 200, 80)), (58, (236, 126, 40)), (70, (120, 180, 90))):
        pygame.draw.circle(sf, c, (x, 30), 3)
        pygame.draw.circle(sf, (255, 255, 255), (x - 1, 29), 1)
    SPR["stall_front"] = sf
    # --- coop
    c = surf(48, 32)
    c.fill((200, 150, 100), (4, 12, 40, 20))
    for x in range(4, 44, 6):
        c.fill((170, 120, 78), (x, 12, 1, 20))
    pygame.draw.rect(c, (110, 76, 48), (4, 12, 40, 20), 1)
    pygame.draw.polygon(c, (176, 72, 60), [(0, 14), (48, 14), (40, 2), (8, 2)])
    pygame.draw.polygon(c, (110, 44, 40), [(0, 14), (48, 14), (40, 2), (8, 2)], 1)
    c.fill((60, 40, 30), (18, 18, 10, 14))
    c.fill((236, 200, 110), (14, 29, 18, 3))
    SPR["coop"] = c
    # --- lamp
    lp = surf(16, 32)
    lp.fill((70, 64, 72), (7, 10, 2, 20))
    lp.fill((70, 64, 72), (5, 28, 6, 4))
    lp.fill((250, 220, 140), (5, 3, 6, 8))
    pygame.draw.rect(lp, (70, 64, 72), (4, 2, 8, 10), 1)
    pygame.draw.polygon(lp, (70, 64, 72), [(3, 3), (13, 3), (8, 0)])
    SPR["lamp"] = lp
    # --- characters
    SPR["player"] = make_char((244, 205, 170), (120, 76, 48), (86, 140, 200), (96, 84, 120),
                              hat=(236, 200, 110))
    SPR["mabel"] = make_char((240, 200, 164), (130, 80, 50), (190, 84, 90), (96, 70, 60), apron=True)
    SPR["fern"] = make_char((236, 200, 170), (232, 232, 238), (150, 110, 170), (96, 70, 60),
                            skirt=True, bun=True)
    SPR["chicken"] = [make_chicken(i) for i in range(4)]
    SPR["chicken_flip"] = [pygame.transform.flip(c, True, False) for c in SPR["chicken"]]
    # --- misc
    sh = surf(14, 6)
    pygame.draw.ellipse(sh, (0, 0, 0, 70), (0, 0, 14, 6))
    SPR["shadow"] = sh
    SPR["egg"] = pygame.transform.scale(make_icon("egg"), (8, 8))
    SPR["soil_dry"] = tex("soil_dry") or make_soil(False)
    SPR["soil_wet"] = tex("soil_wet") or make_soil(True)
    SPR["crops"] = {(ck, st): make_crop_sprite(ck, st) for ck in CROPS for st in range(5)}
    SPR["glow_s"] = make_glow(14)
    SPR["glow_m"] = make_glow(30)
    SPR["glow_l"] = make_glow(52)
    st = surf(16, 16)
    pygame.draw.ellipse(st, (110, 76, 48), (1, 6, 14, 10))
    pygame.draw.ellipse(st, (150, 104, 62), (1, 4, 14, 9))
    pygame.draw.ellipse(st, (206, 164, 106), (3, 5, 10, 6))
    pygame.draw.ellipse(st, (170, 128, 80), (5, 7, 6, 3), 1)
    SPR["stump"] = st
    SPR["trunk"] = make_trunk()
    SPR["rocks"] = [make_rock(i) for i in range(3)]
    SPR["fence"] = {}


def make_soil(wet):
    t = pygame.Surface((16, 16))
    base = (82, 56, 40) if wet else (122, 84, 54)
    furrow = (62, 42, 30) if wet else (100, 66, 44)
    hi = (100, 70, 50) if wet else (146, 104, 70)
    t.fill(base)
    for y in (3, 8, 13):
        t.fill(furrow, (0, y, 16, 2))
        t.fill(hi, (0, y - 1, 16, 1))
    pygame.draw.rect(t, (58, 38, 28) if wet else (96, 62, 40), (0, 0, 16, 16), 1)
    return t


def make_trunk():
    s = surf(16, 24)
    s.fill((110, 74, 48), (5, 6, 6, 18))
    s.fill((140, 100, 66), (6, 6, 1, 18))
    s.fill((86, 56, 38), (10, 6, 1, 18))
    s.fill((110, 74, 48), (3, 20, 10, 4))
    s.fill((86, 56, 38), (3, 23, 10, 1))
    for y in (10, 14, 18):
        s.fill((86, 56, 38), (7, y, 2, 1))
    return s


def make_rock(v):
    s = surf(16, 16)
    pts = [[(2, 14), (1, 9), (5, 4), (11, 3), (15, 8), (14, 14)],
           [(3, 14), (2, 10), (6, 6), (12, 7), (14, 11), (13, 14)],
           [(2, 14), (3, 8), (8, 3), (13, 6), (14, 14)]][v]
    pygame.draw.polygon(s, (128, 132, 140), pts)
    pygame.draw.polygon(s, (86, 90, 100), pts, 1)
    pygame.draw.line(s, (186, 190, 198), (pts[1][0] + 2, pts[1][1] - 1), (pts[2][0] + 1, pts[2][1] + 2))
    s.fill((150, 154, 162), (6, 7, 4, 2))
    return s


def build_season_sprites(season):
    pal = PAL[season]
    rnd = random.Random(7)
    SPR["grass"] = []
    # Fixed tuft positions per variant: calm, repeatable grass instead of random speckle.
    tufts = [[(3, 6), (9, 3), (13, 11)], [(6, 13), (11, 8), (2, 2)], [(4, 9), (14, 5), (8, 14)],
             [(10, 12), (1, 4), (12, 1)], [(7, 3), (3, 12), (14, 14)], [(12, 7), (5, 8), (9, 10)],
             [(2, 14), (8, 1), (13, 9)], [(6, 6), (10, 13), (15, 2)]]
    for v in range(8):
        t = pygame.Surface((16, 16))
        t.fill(pal["grass"])
        # soft two-tone mottling on a 4x4 grid: reads as ground, not noise
        for gy in range(0, 16, 4):
            for gx in range(0, 16, 4):
                if (gx // 4 + gy // 4 + v) % 3 == 0:
                    t.fill(pal["grass_l"], (gx + 1, gy + 1, 2, 2))
        for x, y in tufts[v]:
            t.set_at((x, y), pal["grass_d"])
            t.set_at((x - 1, y + 1), pal["grass_d"])
            t.set_at((x + 1, y + 1), pal["grass_d"])
            t.set_at((x, y + 1), pal["grass_l"])
        if v >= 6:
            fx, fy = tufts[v][0]
            t.set_at((fx, max(0, fy - 2)), pal["flower"][v % len(pal["flower"])])
        SPR["grass"].append(t)
    if tex("grass"):
        SPR["grass"] = [tex("grass")] * 8
    # Dirt path: hand-laid cobbles with a darker grout line
    SPR["path"] = []
    for v in range(4):
        t = pygame.Surface((16, 16))
        t.fill((150, 116, 76))
        tones = [(198, 162, 110), (190, 154, 104), (204, 168, 116), (194, 158, 106)]
        off = (v * 3) % 8
        for cy in (0, 8):
            for cx in (-8, 0, 8):
                x0, y0 = cx + off, cy
                tone = tones[(cx // 8 + cy // 8 + v) % len(tones)]
                t.fill(tone, (max(0, x0 + 1), y0 + 1, 6, 6))
        t.set_at(((v * 5) % 14 + 1, (v * 7) % 14 + 1), (226, 196, 146))
        SPR["path"].append(t)
    # Sand: fine ripples on the sandbanks
    SPR["sand"] = []
    for v in range(4):
        t = pygame.Surface((16, 16))
        t.fill((228, 210, 158))
        for y in (3, 8, 13):
            for x in range(((v * 2) + y) % 4, 15, 4):
                t.set_at((x, y), (240, 226, 180))
                t.set_at((x + 1, y + 1), (210, 190, 138))
        SPR["sand"].append(t)
    # Water: deep blue with moving light bands (4 frames)
    SPR["water"] = []
    for f in range(4):
        t = pygame.Surface((16, 16))
        t.fill((58, 128, 186))
        for band in range(3):
            y = (band * 6 + f * 2) % 16
            x0 = (band * 5 + f * 3) % 11
            t.fill((96, 168, 220), (x0, y, 5, 1))
            t.fill((78, 150, 204), ((x0 + 6) % 11, (y + 1) % 16, 2, 1))
        SPR["water"].append(t)
    # Open sea: deeper blue with white-capped waves
    SPR["sea"] = []
    for f in range(4):
        t = pygame.Surface((16, 16))
        t.fill((36, 98, 160))
        for band in range(3):
            y = (band * 5 + f * 3) % 16
            x0 = (band * 7 + f * 2) % 12
            t.fill((20, 74, 130), (x0, (y + 2) % 16, 6, 1))
            t.fill((84, 150, 206), (x0, y, 4, 1))
            t.fill((196, 226, 244), ((x0 + 1) % 14, y, 2, 1))
        SPR["sea"].append(t)
    # Bridge deck: planks with railings on the top and bottom rows
    SPR["bridge"] = []
    for row in ("top", "mid", "bottom"):
        t = pygame.Surface((16, 16))
        t.fill((150, 104, 64))
        for x in range(0, 16, 4):
            t.fill((112, 76, 46), (x, 0, 1, 16))
        if row == "top":
            t.fill((118, 80, 48), (0, 0, 16, 4))
            for x in (0, 8):
                t.fill((86, 56, 34), (x, 0, 2, 6))
        elif row == "bottom":
            t.fill((118, 80, 48), (0, 12, 16, 4))
            for x in (0, 8):
                t.fill((86, 56, 34), (x, 10, 2, 6))
        SPR["bridge"].append(t)
    # canopies
    d, m, l = pal["leaf_d"], pal["leaf"], pal["leaf_l"]
    SPR["canopy"] = []
    for v in range(2):
        s = surf(48, 40)
        blobs = [(24, 24, 15), (14, 22, 11), (34, 22, 11), (24, 14, 13), (16, 14, 9), (32, 14, 9)]
        for cx, cy, r in blobs:
            pygame.draw.circle(s, d, (cx, cy + 2), r)
        for cx, cy, r in blobs:
            pygame.draw.circle(s, m, (cx, cy), r)
        for cx, cy, r in ((18, 12, 5), (30, 14, 5), (24, 22, 6), (12, 20, 4)):
            pygame.draw.circle(s, l, (cx - 2, cy - 2), r)
        r2 = random.Random(v * 9 + 1)
        for _ in range(8 if season == "Spring" else 0):
            x, y = r2.randrange(10, 38), r2.randrange(6, 30)
            s.fill(pal["flower"][0], (x, y, 2, 2))
        for _ in range(7 if season == "Fall" else 0):
            x, y = r2.randrange(10, 38), r2.randrange(8, 30)
            s.fill((250, 214, 100), (x, y, 2, 2))
        SPR["canopy"].append(s)
    SPR["flowers"] = []
    for c in pal["flower"]:
        s = surf(16, 16)
        pygame.draw.line(s, (70, 140, 60), (8, 15), (8, 9))
        pygame.draw.line(s, (70, 140, 60), (8, 13), (11, 11))
        for dx, dy in ((0, -2), (-2, 0), (2, 0), (0, 2)):
            pygame.draw.circle(s, c, (8 + dx, 7 + dy), 2)
        pygame.draw.circle(s, (250, 224, 100), (8, 7), 1)
        SPR["flowers"].append(s)


def fence_sprite(l, r, u, d):
    key = (l, r, u, d)
    cache = SPR["fence"]
    if key in cache:
        return cache[key]
    s = surf(16, 16)
    rail = (196, 150, 98)
    rail_d = (140, 100, 66)
    if l:
        s.fill(rail, (0, 6, 8, 2))
        s.fill(rail, (0, 10, 8, 2))
    if r:
        s.fill(rail, (8, 6, 8, 2))
        s.fill(rail, (8, 10, 8, 2))
    if u:
        s.fill(rail, (7, 0, 2, 8))
    if d:
        s.fill(rail, (7, 8, 2, 8))
    s.fill(rail_d, (6, 4, 4, 11))
    s.fill((214, 170, 116), (6, 4, 4, 2))
    s.fill(rail_d, (9, 5, 1, 10))
    cache[key] = s
    return s


def load_crazy_dew_art():
    """Cuts Crazy Dew's drawing out of crazy_dew.png. Returns (sprite 16x24, portrait 96x104), or None
    when the picture is not next to the game. The white paper around the drawing becomes transparent."""
    path = None
    for folder in (APP_DIR, os.path.dirname(os.path.abspath(__file__))):
        if os.path.isfile(os.path.join(folder, "crazy_dew.png")):
            path = os.path.join(folder, "crazy_dew.png")
            break
    if path is None:
        return None
    try:
        img = pygame.image.load(path)
    except pygame.error:
        return None
    W, H = img.get_size()
    x, y, w, h = CRAZY_ART_RECT
    x, y = min(x, W - 1), min(y, H - 1)
    w, h = min(w, W - x), min(h, H - y)
    crop = img.subsurface(pygame.Rect(x, y, w, h)).copy().convert_alpha()
    cw, ch = crop.get_size()
    seen = bytearray(cw * ch)
    stack = [(i, 0) for i in range(cw)] + [(i, ch - 1) for i in range(cw)] + \
            [(0, j) for j in range(ch)] + [(cw - 1, j) for j in range(ch)]
    while stack:                                  # flood fill the outside paper from the edges inward
        px, py = stack.pop()
        if not (0 <= px < cw and 0 <= py < ch) or seen[py * cw + px]:
            continue
        seen[py * cw + px] = 1
        r, g, b, _a = crop.get_at((px, py))
        if r > 225 and g > 225 and b > 225:
            crop.set_at((px, py), (255, 255, 255, 0))
            stack += [(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)]
    sprite = pygame.transform.smoothscale(crop, (16, 24))
    portrait = pygame.transform.smoothscale(crop, (96, 104))
    return sprite, portrait


def build_extra_sprites():
    font = pygame.font.Font(None, 20)
    small = pygame.font.Font(None, 15)
    # --- cafe (8x4 tiles)
    c = surf(128, 64)
    c.fill((236, 214, 170), (4, 22, 120, 42))
    for x in range(4, 124, 8):
        c.fill((214, 190, 146), (x, 22, 1, 42))
    pygame.draw.rect(c, (140, 104, 70), (4, 22, 120, 42), 1)
    rp = [(0, 28), (128, 28), (116, 4), (12, 4)]
    pygame.draw.polygon(c, (150, 80, 70), rp)
    for y in range(9, 28, 5):
        c.fill((124, 62, 56), (12 - int((y - 4) * 0.5), y, 104 + int((y - 4)), 1))
    pygame.draw.polygon(c, (96, 46, 40), rp, 2)
    c.fill((92, 58, 34), (40, 8, 48, 14))
    pygame.draw.rect(c, (60, 38, 24), (40, 8, 48, 14), 1)
    t = font.render("CAFE", True, (255, 232, 170))
    c.blit(t, (64 - t.get_width() // 2, 10))
    for wx in (12, 92):
        c.fill((250, 214, 130), (wx, 36, 24, 18))
        pygame.draw.rect(c, (240, 236, 226), (wx - 1, 35, 26, 20), 2)
        c.fill((240, 236, 226), (wx + 11, 36, 2, 18))
        c.fill((120, 84, 56), (wx - 2, 55, 28, 3))
    c.fill((112, 72, 44), (56, 38, 16, 26))
    pygame.draw.rect(c, (80, 50, 30), (56, 38, 16, 26), 1)
    c.fill((240, 200, 80), (68, 52, 2, 2))
    for i in range(16):
        col = (214, 70, 64) if i % 2 == 0 else (248, 240, 228)
        c.fill(col, (i * 8, 26, 8, 8))
        pygame.draw.circle(c, col, (i * 8 + 4, 34), 4)
    SPR["cafe"] = c
    # --- table with chairs
    tb = surf(16, 16)
    tb.fill((140, 100, 66), (0, 6, 3, 8))
    tb.fill((140, 100, 66), (13, 6, 3, 8))
    tb.fill((110, 76, 48), (7, 12, 2, 4))
    pygame.draw.ellipse(tb, (200, 70, 64), (1, 5, 14, 8))
    pygame.draw.ellipse(tb, (248, 240, 228), (2, 5, 12, 6))
    for p in ((5, 7), (8, 6), (10, 8), (7, 9)):
        tb.fill((214, 70, 64), (p[0], p[1], 2, 2))
    SPR["table"] = tb
    # --- PC desk (2x1 tiles, monitor rises above)
    pc = surf(32, 32)
    pc.fill((150, 108, 70), (0, 20, 32, 5))
    pc.fill((196, 150, 100), (0, 20, 32, 2))
    pc.fill((120, 84, 54), (1, 25, 4, 7))
    pc.fill((120, 84, 54), (27, 25, 4, 7))
    pc.fill((50, 52, 64), (7, 2, 18, 14))
    pc.fill((96, 176, 236), (9, 4, 14, 10))
    pc.fill((255, 255, 255), (11, 6, 6, 1))
    pc.fill((255, 255, 255), (11, 8, 9, 1))
    pc.fill((250, 200, 60), (11, 10, 4, 2))
    pc.fill((50, 52, 64), (14, 16, 4, 3))
    pc.fill((222, 222, 230), (9, 21, 12, 3))
    pc.fill((240, 240, 246), (23, 21, 3, 3))
    SPR["pc"] = pc
    # --- arcade cabinet (2x1 tiles, 40px tall)
    ar = surf(32, 40)
    ar.fill((70, 50, 120), (2, 6, 28, 34))
    ar.fill((52, 36, 96), (2, 6, 3, 34))
    pygame.draw.rect(ar, (30, 20, 60), (2, 6, 28, 34), 1)
    ar.fill((240, 70, 140), (3, 0, 26, 8))
    tt = small.render("PLAY", True, (255, 240, 160))
    ar.blit(tt, (16 - tt.get_width() // 2, 1))
    ar.fill((20, 20, 36), (6, 11, 20, 14))
    pygame.draw.rect(ar, (140, 140, 170), (6, 11, 20, 14), 1)
    for p in ((9, 14), (14, 20), (20, 16), (22, 21)):
        ar.fill((90, 220, 250), (p[0], p[1], 2, 2))
    ar.fill((40, 30, 80), (4, 27, 24, 6))
    ar.fill((230, 60, 60), (9, 24, 3, 4))
    ar.fill((120, 120, 140), (10, 27, 1, 2))
    ar.fill((250, 220, 80), (17, 28, 3, 3))
    ar.fill((90, 200, 250), (22, 28, 3, 3))
    ar.fill((250, 200, 60), (14, 35, 4, 2))
    SPR["arcade"] = ar
    # --- cafe interior
    fl = surf(16, 16)
    fl.fill((176, 128, 84))
    for y in (0, 5, 10, 15):
        fl.fill((150, 106, 68), (0, y, 16, 1))
    for x in (3, 11):
        fl.fill((150, 106, 68), (x, 0, 1, 5))
        fl.fill((150, 106, 68), (x + 4, 5, 1, 5))
    SPR["wood_floor"] = fl
    wl = surf(16, 16)
    wl.fill((96, 70, 56))
    wl.fill((70, 50, 40), (0, 0, 16, 2))
    wl.fill((120, 90, 68), (2, 6, 12, 2))
    wl.fill((120, 90, 68), (2, 12, 12, 2))
    SPR["wall"] = wl
    st = surf(48, 20)
    st.fill((48, 48, 56), (0, 0, 48, 4))
    st.fill((80, 80, 88), (0, 4, 48, 16))
    for bx in (8, 24, 40):
        pygame.draw.circle(st, (40, 40, 44), (bx, 6), 4)
        pygame.draw.circle(st, (240, 110, 40), (bx, 6), 2)
    st.fill((60, 60, 66), (2, 12, 44, 3))
    SPR["fur_stove"] = st
    rg = surf(48, 20)
    rg.fill((160, 116, 76), (0, 6, 48, 14))
    rg.fill((120, 84, 54), (0, 6, 48, 2))
    rg.fill((70, 180, 170), (14, 0, 20, 8))
    rg.fill((40, 120, 112), (16, 2, 16, 2))
    rg.fill((250, 226, 140), (20, 4, 8, 2))
    SPR["fur_register"] = rg
    dr = surf(16, 20)
    dr.fill((120, 80, 50), (1, 2, 14, 18))
    dr.fill((90, 56, 34), (2, 3, 12, 6))
    dr.fill((90, 56, 34), (2, 11, 12, 8))
    dr.fill((240, 200, 80), (12, 11, 2, 2))
    dr.fill((255, 240, 180), (5, 0, 6, 2))
    SPR["fur_exitdoor"] = dr
    bd = surf(32, 20)
    bd.fill((150, 110, 80), (0, 4, 32, 16))
    bd.fill((200, 170, 120), (2, 6, 28, 10))
    bd.fill((236, 232, 220), (3, 6, 10, 9))
    bd.fill((236, 110, 140), (4, 8, 6, 3))
    bd.fill((210, 96, 60), (17, 6, 12, 9))
    bd.fill((248, 226, 150), (19, 8, 8, 2))
    SPR["fur_bed"] = bd
    cp = surf(32, 20)
    cp.fill((60, 56, 72), (4, 0, 24, 14))
    cp.fill((110, 200, 240), (6, 2, 20, 10))
    cp.fill((255, 255, 255), (8, 4, 8, 1))
    cp.fill((250, 210, 80), (8, 7, 4, 2))
    cp.fill((90, 80, 100), (14, 14, 4, 3))
    cp.fill((230, 230, 236), (6, 17, 20, 3))
    SPR["fur_computer"] = cp
    wb = surf(32, 20)
    wb.fill((140, 98, 62), (0, 6, 32, 14))
    wb.fill((190, 146, 96), (0, 6, 32, 3))
    wb.fill((110, 74, 46), (2, 10, 28, 1))
    for hx in (5, 15, 25):
        wb.fill((170, 170, 180), (hx, 3, 4, 3))
    wb.fill((96, 64, 40), (4, 16, 3, 4))
    wb.fill((96, 64, 40), (25, 16, 3, 4))
    SPR["fur_bench"] = wb
    dk = surf(32, 20)
    dk.fill((150, 110, 74), (0, 6, 32, 14))
    for x in range(0, 32, 6):
        dk.fill((120, 86, 56), (x, 6, 1, 14))
    dk.fill((90, 64, 40), (0, 4, 32, 2))
    dk.fill((70, 110, 170), (0, 16, 32, 4))
    SPR["fur_dock"] = dk
    SPR["fur_dock_back"] = dk
    SPR["fur_port"] = dk
    vp = surf(32, 20)                                  # ferry pier on the river bank
    vp.fill((70, 110, 170), (0, 12, 32, 8))            # river under the pier
    vp.fill((150, 110, 74), (0, 3, 32, 9))             # planks
    for x in range(0, 32, 6):
        vp.fill((120, 86, 56), (x, 3, 1, 9))
    vp.fill((90, 64, 40), (0, 1, 32, 2))               # top rail
    for x in (2, 27):
        vp.fill((80, 56, 36), (x, 10, 2, 9))           # posts standing in the water
    vp.fill((200, 60, 50), (8, 9, 12, 3))              # moored rowboat
    vp.fill((240, 240, 240), (11, 9, 4, 3))
    vp.fill((250, 200, 60), (22, 0, 3, 3))             # lantern
    SPR["fur_village_port"] = vp
    rn = surf(48, 36)                                  # a broken stone ruin
    rn.fill((132, 130, 128), (0, 12, 48, 24))
    for x in range(0, 48, 12):
        rn.fill((100, 98, 96), (x, 12, 1, 24))
    rn.fill((100, 98, 96), (0, 12, 48, 2))
    rn.fill((0, 0, 0, 0), (14, 0, 12, 12))            # broken top
    rn.fill((116, 114, 112), (0, 6, 14, 6))
    rn.fill((116, 114, 112), (34, 4, 14, 8))
    rn.fill((80, 120, 70), (4, 28, 10, 3))            # moss
    SPR["fur_ruin"] = rn
    SPR["remote"] = make_char((236, 196, 168), (60, 40, 30), (110, 150, 210), (80, 70, 100), hat=(120, 200, 120))
    SPR["fishmaster"] = make_char((214, 170, 130), (236, 236, 240), (40, 110, 140), (60, 60, 80), hat=(40, 110, 140))
    SPR["fisherman"] = make_char((212, 168, 128), (90, 60, 40), (70, 110, 90), (60, 60, 70), hat=(190, 150, 80))
    SPR["gus"] = make_char((236, 196, 160), (206, 206, 210), (246, 246, 238), (80, 80, 92), apron=True,
                           hat=(250, 250, 250))
    SPR["lila"] = make_char((200, 150, 110), (60, 30, 20), (120, 170, 80), (90, 70, 50), hat=(200, 160, 90))
    SPR["pip"] = make_char((246, 212, 184), (230, 180, 60), (240, 120, 120), (70, 90, 140), bun=True)
    SPR["tomas"] = make_char((222, 176, 136), (50, 36, 30), (160, 110, 70), (60, 64, 80), hat=(236, 196, 60))
    SPR["dario"] = make_char((170, 120, 90), (20, 20, 20), (210, 60, 50), (50, 60, 90), hat=(40, 40, 44))
    SPR["oldsalt"] = make_char((200, 160, 120), (200, 200, 210), (60, 90, 130), (70, 60, 60), hat=(60, 90, 130))
    SPR["coral"] = make_char((240, 200, 170), (200, 60, 90), (250, 200, 120), (90, 120, 160), skirt=True)
    art = load_crazy_dew_art()
    if art is not None:
        sprite, portrait = art
        SPR["crazy_dew"] = {(d, f): sprite for d in ("down", "up", "left", "right") for f in range(4)}
        PORTRAITS["Crazy Dew"] = portrait
    else:                                         # no picture: a plain stand-in
        SPR["crazy_dew"] = make_char((236, 236, 236), (40, 40, 40), (150, 216, 230), (80, 80, 110))
    # --- customers
    variants = [
        ((244, 205, 170), (60, 40, 30), (214, 90, 90), (80, 80, 110), {}),
        ((226, 180, 140), (30, 24, 24), (90, 160, 110), (70, 70, 90), {}),
        ((250, 216, 190), (190, 120, 60), (230, 190, 80), (100, 80, 70), {}),
        ((180, 130, 100), (40, 30, 26), (120, 100, 200), (60, 60, 80), {}),
        ((240, 200, 170), (230, 230, 236), (180, 90, 150), (90, 70, 60), dict(skirt=True, bun=True)),
        ((236, 190, 160), (120, 70, 40), (240, 130, 70), (70, 90, 120), dict(skirt=True)),
        ((210, 160, 120), (20, 20, 24), (70, 140, 200), (90, 90, 90), dict(hat=(190, 190, 200))),
        ((246, 210, 180), (250, 210, 100), (200, 70, 70), (60, 60, 70), {}),
    ]
    SPR["customers"] = [make_char(a, b, cc, d, **kw) for a, b, cc, d, kw in variants]


# ============================================================ entities
class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.dir = "down"
        self.moving = False
        self.anim = 0.0
        self.act = 0.0
        self.act_dur = 0.3
        self.act_tool = None


class Chicken:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.flip = False
        self.state = "idle"
        self.timer = random.uniform(0.5, 3)
        self.tx, self.ty = x, y
        self.anim = random.random() * 5


class NPC:
    def __init__(self, name, x, y, sprites, lines, wander=None):
        self.name, self.x, self.y = name, x, y
        self.sprites, self.lines, self.wander = sprites, lines, wander
        self.dir = "down"
        self.anim = 0.0
        self.moving = False
        self.timer = random.uniform(1, 4)
        self.tx, self.ty = x, y


# ============================================================ cafe, PC, arcade, fishing
class Customer:
    def __init__(self, table, order, sprites):
        self.table, self.order, self.sprites = table, order, sprites
        self.x = 63 * TILE + 8
        self.y = 20 * TILE + 12
        self.dir = "left"
        self.state = "arrive"
        self.anim = 0.0
        self.max_patience = 85.0
        self.patience = self.max_patience
        self.eat_t = 0.0


def draw_star(surface, cx, cy, r, color):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(surface, color, pts)


def draw_heart(surface, cx, cy, r, color):
    pygame.draw.circle(surface, color, (cx - r // 2, cy - r // 3), r // 2 + 1)
    pygame.draw.circle(surface, color, (cx + r // 2, cy - r // 3), r // 2 + 1)
    pygame.draw.polygon(surface, color, [(cx - r, cy - r // 6), (cx + r, cy - r // 6), (cx, cy + r)])


QUIZ = [
    ("Where were potatoes first domesticated?", ["The Andes (South America)", "Mexico", "China", "Ireland"], 0),
    ("Where was the tomato first domesticated?", ["Italy", "Mexico", "Egypt", "India"], 1),
    ("Which people are credited with brewing beer over 5,000 years ago?", ["The Romans", "The Sumerians", "The Vikings", "The Inca"], 1),
    ("Which ancient people are credited with early leavened bread?", ["The Egyptians", "The Greeks", "The Celts", "The Aztecs"], 0),
    ("Where does the wild origin of coffee lie?", ["Brazil", "Yemen", "Ethiopia", "Colombia"], 2),
    ("Sugar cane was first domesticated in which region?", ["Spain", "New Guinea", "Brazil", "Egypt"], 1),
    ("Rice was first cultivated in which country?", ["Japan", "India", "China", "Egypt"], 2),
    ("Which of these crops is native to the Americas?", ["Wheat", "Barley", "Rice", "Maize (corn)"], 3),
    ("Silk production began in which civilization?", ["Ancient China", "Ancient India", "Persia", "Rome"], 0),
    ("What fermented fish sauce did the Romans love?", ["Miso", "Garum", "Soy sauce", "Ketchup"], 1),
    ("The Columbian Exchange brought potatoes and tomatoes to which continent?", ["Africa", "Asia", "Europe", "Australia"], 2),
]
HISTORY_GAMES = ("pyramid", "quiz", "caravan")
CARAVAN_LANES = (300, 480, 660)
HI_DEFAULT = {"veggie": 0, "weed": 0, "memory": 0, "pyramid": 0, "quiz": 0, "caravan": 0}


def lan_ip():
    """The address other devices on the same WiFi can reach us on."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packet is actually sent
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def roll_fish(level, perfect, hook, master=False):
    """Picks a fish. Higher fishing level, a perfect cast, or a hook makes rarer fish more likely."""
    boost = 1 + 0.12 * (level - 1) + (0.6 if perfect else 0.0) + (0.2 if hook else 0.0) + (0.15 if master else 0.0)
    keys = list(FISH)
    weights = [FISH[k]["weight"] * boost ** FISH[k]["tier"] for k in keys]
    return random.choices(keys, weights)[0]


class NetServer:
    """Hosting side: accepts LAN clients, collects their positions, and sends everyone the list."""

    def __init__(self, port=NET_PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.listen(256)  # room for a crowd connecting at once
        self.sock.settimeout(0.5)
        self.lock = threading.Lock()
        self.clients = {}
        self.snapshot = []
        self.next_id = 1
        self.running = True
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            with self.lock:
                full = len(self.clients) >= MAX_PLAYERS
                if not full:
                    cid = self.next_id
                    self.next_id += 1
                    self.clients[cid] = dict(conn=conn, state=None)
            if full:
                try:
                    conn.sendall((json.dumps({"t": "full", "max": MAX_PLAYERS}) + "\n").encode())
                    conn.close()
                except OSError:
                    pass
                continue
            try:
                conn.sendall((json.dumps({"t": "hello", "id": cid}) + "\n").encode())
            except OSError:
                continue
            threading.Thread(target=self._reader, args=(cid, conn), daemon=True).start()

    def _reader(self, cid, conn):
        buf = b""
        while self.running:
            try:
                data = conn.recv(4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line.decode())
                except ValueError:
                    continue
                if msg.get("t") == "pos":
                    with self.lock:
                        if cid in self.clients:
                            self.clients[cid]["state"] = {k: v for k, v in msg.items() if k != "t"}
        with self.lock:
            self.clients.pop(cid, None)
        try:
            conn.close()
        except OSError:
            pass

    def broadcast(self, host_state):
        """Sends each client only the players in the same place who are close to them.
        Far-away players are off-screen anyway, so 100+ players stay affordable on WiFi."""
        with self.lock:
            clients = [(cid, c["state"], c["conn"]) for cid, c in self.clients.items()]
        host = dict(host_state, id=0)
        players = [dict(st, id=cid) for cid, st, _ in clients if st]
        self.snapshot = players + [host]
        by_place = {}
        for p in players + [host]:
            by_place.setdefault(p.get("loc", "farm"), []).append(p)
        for cid, st, conn in clients:
            place = st.get("loc", "farm") if st else "farm"
            mx, my = (st.get("x", 0), st.get("y", 0)) if st else (0, 0)
            near = [p for p in by_place.get(place, [])
                    if abs(p.get("x", 0) - mx) <= NEAR_DISTANCE and abs(p.get("y", 0) - my) <= NEAR_DISTANCE]
            try:
                conn.sendall((json.dumps({"t": "world", "players": near}) + "\n").encode())
            except OSError:
                pass

    def kick(self, cid):
        with self.lock:
            c = self.clients.pop(cid, None)
        if not c:
            return False
        try:
            c["conn"].sendall((json.dumps({"t": "kick"}) + "\n").encode())
            c["conn"].close()
        except OSError:
            pass
        return True

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass
        with self.lock:
            for c in self.clients.values():
                try:
                    c["conn"].close()
                except OSError:
                    pass
            self.clients.clear()


class ServerFull(OSError):
    pass


class NetClient:
    """Joining side: sends our position and keeps the latest list of players."""

    def __init__(self, host, port=NET_PORT):
        self.sock = socket.create_connection((host, port), timeout=4)
        self.my_id = None
        self.players = []
        self.alive = True
        self.kicked = False
        buf = self._handshake()
        self.sock.settimeout(None)
        threading.Thread(target=self._reader, args=(buf,), daemon=True).start()

    def _handshake(self):
        buf = b""
        while b"\n" not in buf:
            data = self.sock.recv(4096)
            if not data:
                raise OSError("the host closed the connection")
            buf += data
        line, rest = buf.split(b"\n", 1)
        msg = json.loads(line.decode())
        if msg.get("t") == "full":
            self.sock.close()
            raise ServerFull("That LAN game is full (%d players)." % msg.get("max", MAX_PLAYERS))
        if msg.get("t") != "hello":
            raise OSError("not a farming game server")
        self.my_id = msg.get("id")
        return rest

    def _reader(self, buf=b""):
        while self.alive:
            try:
                data = self.sock.recv(65536)
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line.decode())
                except ValueError:
                    continue
                if msg.get("t") == "hello":
                    self.my_id = msg.get("id")
                elif msg.get("t") == "world":
                    self.players = msg.get("players", [])
                elif msg.get("t") == "kick":
                    self.kicked = True
                    self.alive = False
        self.alive = False

    def send_state(self, state):
        if not self.alive:
            return
        try:
            self.sock.sendall((json.dumps(dict(state, t="pos")) + "\n").encode())
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


class Extras:
    """Cafe, PC shop, arcade mini-games, fishing and skills."""

    # ------------------------------------------------------- state and skills
    def init_extras(self):
        self.placing = None
        self.owned = set()
        self.fish_log = {}
        self.unlocked = list(UNLOCKED_START)
        self.menu_on = {}
        self.cafe_open = True
        self.rep = 20.0
        self.xp = {"farm": 0, "cook": 0, "fish": 0}
        self.pending = {}
        self.hi = dict(HI_DEFAULT)
        self.customers = []
        self.cust_timer = 10.0
        self.cafe_stats = dict(served=0, earned=0, tips=0, angry=0)
        self.tables = []
        self.location = "farm"
        self.farm_world = None
        self.qdone, self.qactive, self.qstats = set(), {}, {}   # quests done, active (id -> start), counters
        self.last_port, self.cg = "farm", None
        self.after_dialog, self.wish_idx, self.wishes_done, self.wish_opts = None, 0, set(), []
        self.warp = None
        self.island_world = None
        self.dungeon_enemies = []
        self.dungeon_wave = 0
        self.dungeon_floor = 1
        self.dungeon_best_floor = 1
        self.dungeon_kills = 0
        self.dungeon_attack_cd = 0.0
        self.dungeon_hit_flash = 0.0
        self.dungeon_boss_done = False
        if not hasattr(self, "net_server"):  # set once; new_game() must not drop a live connection
            self.net_server = None
            self.net_client = None
            self.remote = []
            self.join_text, self.join_msg = "192.168.", ""
            self.player_name = "Farmer%d" % random.randint(10, 99)
        self.fishing = None
        self.mini = None
        self.mini_result = None
        self.recalc()
        self.energy = float(self.max_energy)
        self.water = self.water_cap()

    def recalc(self):
        self.max_energy = 100 + 25 * sum(1 for t in ("tonic1", "tonic2", "tonic3") if t in self.owned)

    def water_cap(self):
        return 40 if "can2" in self.owned else 20

    def n_tables(self):
        return 2 + int("table3" in self.owned) + int("table4" in self.owned)

    def active_tables(self):
        return self.tables[: self.n_tables()]

    def level(self, skill):
        return min(10, 1 + int((self.xp[skill] / 25.0) ** 0.5))

    def gain_xp(self, skill, amt):
        before = self.level(skill)
        self.xp[skill] += amt
        after = self.level(skill)
        if after > before:
            names = {"farm": "Farming", "cook": "Cooking", "fish": "Fishing"}
            self.toast("%s level up! Lv %d" % (names[skill], after))
            self.sparkle(self.player.x, self.player.y - 16, 10)

    def cook_bonus(self):
        return 1 + 0.03 * (self.level("cook") - 1)

    def tip_mult(self):
        return 1.0 + (0.25 if "decor" in self.owned else 0.0) + (0.1 if "trophy" in self.owned else 0.0)

    def tool_cost(self, key):
        return max(1, TOOL_COST[key] - (1 if "tools" in self.owned else 0))

    def stars(self):
        return int(clamp(self.rep, 0, 100) // 20)

    def cafe_price(self, k):
        return int(ITEMS[k]["sell"] * 1.5 * self.cook_bonus())

    def cafe_menu(self):
        return [k for k in self.unlocked if self.menu_on.get(k, True)]

    # ------------------------------------------------------- cafe
    def update_cafe(self, dt):
        if self.location != "cafe":
            return
        t = self.time
        if self.cafe_open and 9.0 <= t < 21.0 and self.cafe_menu():
            self.cust_timer -= dt
            if self.cust_timer <= 0:
                free = [tb for tb in self.active_tables() if tb["cust"] is None]
                if free and len(self.customers) < 8:
                    self.spawn_customer(random.choice(free))
                    self.cust_timer = max(9.0, 34 - self.rep * 0.2) + random.uniform(0, 10)
                else:
                    self.cust_timer = 4.0
        for c in self.customers[:]:
            c.anim += dt * 8
            if c.state == "arrive":
                tx, ty = c.table["tx"] * TILE + 8, (c.table["ty"] + 1) * TILE + 4
                if self.walk_to(c, tx, ty, 40 * dt):
                    c.state, c.dir = "wait", "up"
            elif c.state == "wait":
                c.patience -= dt
                if c.patience <= 0:
                    self.rep = clamp(self.rep - 6, 0, 100)
                    self.cafe_stats["angry"] += 1
                    self.toast("A guest left unhappy...")
                    self.customer_leave(c)
            elif c.state == "eat":
                c.eat_t -= dt
                if c.eat_t <= 0:
                    self.customer_leave(c)
            else:
                if self.walk_to(c, CAFE_DOOR_IN[0], CAFE_DOOR_IN[1], 40 * dt):
                    self.customers.remove(c)

    def walk_to(self, c, x, y, step):
        dx, dy = x - c.x, y - c.y
        d = math.hypot(dx, dy)
        if d <= step + 0.5:
            c.x, c.y = x, y
            return True
        c.x += dx / d * step
        c.y += dy / d * step
        c.dir = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
        return False

    def spawn_customer(self, tb):
        c = Customer(tb, random.choice(self.cafe_menu()), random.choice(SPR["customers"]))
        c.x, c.y = CAFE_DOOR_IN
        tb["cust"] = c
        self.customers.append(c)

    def customer_leave(self, c):
        if c.table.get("cust") is c:
            c.table["cust"] = None
        c.state = "leave"

    def serve_table(self, tb):
        c = tb["cust"]
        if c is None:
            self.toast("This table is empty.")
            return
        if c.state != "wait":
            return
        if self.inv.get(c.order, 0) <= 0:
            self.toast("They want %s. Cook it in the Kitchen!" % ITEMS[c.order]["name"], c.order)
            return
        self.take_item(c.order)
        frac = c.patience / c.max_patience
        price = self.cafe_price(c.order)
        tip = int(price * (0.25 if frac > 0.66 else 0.1 if frac > 0.33 else 0.0) * self.tip_mult())
        total = price + tip
        self.money += total
        st = self.cafe_stats
        st["served"] += 1
        st["earned"] += total
        st["tips"] += tip
        self.rep = clamp(self.rep + (3 if frac > 0.33 else 1), 0, 100)
        c.state, c.eat_t = "eat", 4.0
        self.qinc("serve")
        self.gain_xp("cook", 8)
        self.heart(c.x, c.y - 26)
        self.sparkle(c.x, c.y - 12, 6)
        self.toast("Served %s: +%dg%s" % (ITEMS[c.order]["name"], total, (" (tip %dg)" % tip) if tip else ""), "coin")

    def draw_bubbles(self, surf_, cx, cy):
        for c in self.customers:
            if c.state != "wait":
                continue
            x, y = int(c.x - cx), int(c.y - cy)
            r = pygame.Rect(x - 11, y - 50, 22, 24)
            pygame.draw.rect(surf_, (255, 250, 240), r, border_radius=5)
            pygame.draw.rect(surf_, (60, 40, 30), r, 1, border_radius=5)
            pygame.draw.polygon(surf_, (255, 250, 240), [(x - 3, y - 27), (x + 3, y - 27), (x, y - 23)])
            surf_.blit(self.icons[c.order], (x - 8, y - 49))
            frac = clamp(c.patience / c.max_patience, 0, 1)
            surf_.fill((60, 40, 30), (x - 9, y - 31, 18, 3))
            surf_.fill(lerp_col((220, 70, 60), (110, 200, 80), frac), (x - 9, y - 31, int(18 * frac), 3))

    def draw_cafe_stars(self):
        scr = self.screen
        r = pygame.Rect(WIN_W - 196, 134, 184, 30)
        pygame.draw.rect(scr, INK, r.inflate(4, 4), border_radius=10)
        pygame.draw.rect(scr, (120, 84, 54), r, border_radius=8)
        self.text("Cafe", (r.x + 10, r.y + 6), self.f_s, CREAM)
        if not self.cafe_open:
            self.text("CLOSED", (r.right - 10, r.y + 6), self.f_s, (240, 120, 100), right=True)
            return
        st = self.stars()
        for i in range(5):
            draw_star(scr, r.right - 92 + i * 18, r.y + 15, 8, GOLD if i < st else (92, 64, 44))

    # ------------------------------------------------------- PC shop
    def pc_entries(self, tab):
        if tab == 0:
            return [k + "_seed" for k in CROPS]
        if tab == 1:
            return list(PANTRY)
        if tab == 2:
            return [k for k in RECIPE_PRICE if k not in self.unlocked]
        if tab == 3:
            return [k for k in UPGRADES if k not in self.owned]
        return self.trade_entries()

    def market_mult(self, k):
        """Today's market multiplier for an item: the same all day, different tomorrow."""
        rng = random.Random(self.day * 7919 + sum(ord(c) for c in k) * 31)
        return round(0.75 + rng.random() * 0.6, 2)

    def trade_price(self, kind, k):
        base = ITEMS[k]["sell"] * self.market_mult(k)
        return max(1, int(base)) if kind == "sell" else int(base * 1.25) + 1

    def trade_entries(self):
        sells = sorted(k for k, n in self.inv.items() if n > 0
                       and ITEMS.get(k, {}).get("kind") in ("crop", "mat", "food", "seed")
                       and ITEMS[k].get("sell", 0) > 0)
        buys = sorted(k for k, v in ITEMS.items()
                      if v.get("kind") in ("crop", "mat", "food") and v.get("sell", 0) > 0)
        return [("sell", k) for k in sells] + [("buy", k) for k in buys]

    def trade(self, kind, k, qty):
        price = self.trade_price(kind, k)
        name = ITEMS[k]["name"]
        if kind == "sell":
            n = min(qty, self.inv.get(k, 0))
            if n <= 0:
                self.toast("You have none of that to sell.")
                return
            self.take_item(k, n)
            self.money += price * n
            self.toast("Sold %d %s for %dg" % (n, name, price * n), "coin")
        else:
            if self.money < price * qty:
                self.toast("Not enough gold!")
                return
            self.money -= price * qty
            self.add_item(k, qty, quiet=True)
            self.toast("Bought %d %s for %dg" % (qty, name, price * qty), k)

    def trade_row(self, entry, rr):
        kind, k = entry
        price = self.trade_price(kind, k)
        self.icon(k, (rr.x + 10, rr.y + 7), 2)
        tag = "SELL" if kind == "sell" else "BUY"
        self.text("%s  %s" % (tag, ITEMS[k]["name"]), (rr.x + 54, rr.y + 4), self.f_m, TEXT)
        self.text("Market x%.2f.  You have %d." % (self.market_mult(k), self.inv.get(k, 0)),
                  (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
        ok = kind == "sell" or self.money >= price
        self.text("%dg" % price, (rr.right - 14, rr.y + 12), self.f_m, TEXT if ok else (170, 50, 40), right=True)

    def pc_price(self, tab, k):
        if tab == 0:
            return max(1, int(ITEMS[k]["buy"] * 0.85))
        if tab == 1:
            return PANTRY[k]
        if tab == 2:
            return RECIPE_PRICE[k]
        return UPGRADES[k]["price"]

    def pc_buy(self, tab, k, n):
        price = self.pc_price(tab, k)
        if tab in (0, 1):
            if self.money < price * n:
                self.toast("Not enough gold!")
                return
            self.money -= price * n
            self.pending[k] = self.pending.get(k, 0) + n
            self.toast("Ordered %d x %s. Arrives tomorrow!" % (n, ITEMS[k]["name"]), k)
        elif tab == 2:
            if self.money < price:
                self.toast("Not enough gold!")
                return
            self.money -= price
            self.unlocked = [r for r in RECIPES if r in self.unlocked or r == k]
            self.menu_on[k] = True
            self.toast("New recipe learned: %s!" % RECIPES[k]["name"], k)
        else:
            req = UPG_REQ.get(k)
            if req and req not in self.owned:
                self.toast("You need '%s' first." % UPGRADES[req]["name"])
                return
            if self.money < price:
                self.toast("Not enough gold!")
                return
            self.money -= price
            self.owned.add(k)
            self.recalc()
            if k == "can2":
                self.water = self.water_cap()
            if k.startswith("tonic"):
                self.energy = min(self.max_energy, self.energy + 25)
            if k.startswith("table"):
                self.rebuild_solid()
            self.toast("Bought: %s" % UPGRADES[k]["name"], UPGRADES[k]["icon"])

    def row_box(self, rr, sel):
        if sel:
            pygame.draw.rect(self.screen, (252, 224, 150), rr, border_radius=8)
            pygame.draw.rect(self.screen, GOLD, rr, 3, border_radius=8)
        else:
            pygame.draw.rect(self.screen, (236, 200, 144), rr, border_radius=8)

    def draw_rows(self, r, top, entries, m, rows, row_fn, row_h=52):
        m["idx"] = clamp(m["idx"], 0, max(0, len(entries) - 1))
        m["scroll"] = clamp(m.get("scroll", 0), max(0, m["idx"] - rows + 1), m["idx"])
        for vi in range(rows):
            i = m["scroll"] + vi
            if i >= len(entries):
                break
            rr = pygame.Rect(r.x + 20, top + vi * row_h, r.w - 40, row_h - 6)
            self.row_box(rr, i == m["idx"])
            row_fn(entries[i], rr)

    # ------------------------------------------------------- history mini-games
    def history_start(self, kind):
        m = dict(kind=kind, score=0, fx=[], t=0.0)
        if kind == "pyramid":
            m.update(lives=1, blocks=[(390.0, 570.0)], cx=480.0, osc=0.0, bonus=0)
        elif kind == "quiz":
            m.update(lives=3, qs=random.sample(QUIZ, 8), idx=0, timer=10.0, lock=0.0, picked=None)
        else:
            m.update(lives=3, time=60.0, lane=1, items=[], spawn=0.5)
        self.mini = m
        self.menu = {}
        self.state = "mini"

    def history_update(self, dt):
        m = self.mini
        m["t"] += dt
        for f in m["fx"]:
            f["t"] -= dt
        m["fx"] = [f for f in m["fx"] if f["t"] > 0]
        if m["kind"] == "pyramid":
            m["osc"] += dt * (1.5 + 0.08 * len(m["blocks"]))
            m["cx"] = 480 + math.sin(m["osc"]) * 230
        elif m["kind"] == "quiz":
            if m["lock"] > 0:
                m["lock"] -= dt
                if m["lock"] <= 0:
                    m["idx"] += 1
                    m["timer"], m["picked"] = 10.0, None
                    if m["idx"] >= len(m["qs"]) or m["lives"] <= 0:
                        self.end_mini()
                return
            m["timer"] -= dt
            if m["timer"] <= 0:
                self.quiz_answer(-1)
        else:
            m["time"] -= dt
            m["spawn"] -= dt
            if m["spawn"] <= 0:
                m["spawn"] = max(0.28, 0.6 - m["t"] * 0.003)
                r = random.random()
                kind = "bandit" if r < 0.25 else "silk" if r < 0.35 else "spice"
                m["items"].append(dict(lane=random.randrange(3), y=-20.0, kind=kind,
                                       sp=170 + m["t"] * 2.5))
            keep = []
            for it in m["items"]:
                it["y"] += it["sp"] * dt
                x = CARAVAN_LANES[it["lane"]]
                if 478 < it["y"] < 512 and it["lane"] == m["lane"]:
                    if it["kind"] == "bandit":
                        m["lives"] -= 1
                        self.pop_fx(x, 470, "Bandit!", (255, 120, 120))
                    else:
                        pts = 30 if it["kind"] == "silk" else 10
                        m["score"] += pts
                        self.pop_fx(x, 470, "+%d" % pts)
                    continue
                if it["y"] < 560:
                    keep.append(it)
            m["items"] = keep
            if m["lives"] <= 0 or m["time"] <= 0:
                self.end_mini()

    def pyramid_drop(self):
        m = self.mini
        l, r = m["blocks"][-1]
        w = r - l
        cx = m["cx"]
        nl, nr = max(cx - w / 2, l), min(cx + w / 2, r)
        if nr - nl < 6:
            self.end_mini()
            return
        if abs(cx - (l + r) / 2) < 4:
            m["bonus"] += 1
            self.pop_fx(480, 260, "Perfect!", GOLD)
        m["blocks"].append((nl, nr))
        m["score"] = len(m["blocks"]) - 1 + m["bonus"]

    def quiz_answer(self, choice):
        m = self.mini
        if m["lock"] > 0:
            return
        correct = m["qs"][m["idx"]][2]
        m["picked"] = choice
        if choice == correct:
            m["score"] += 10 + int(max(0, m["timer"]))
            self.pop_fx(480, 250, "Correct!", (150, 255, 150))
        else:
            m["lives"] -= 1
            self.pop_fx(480, 250, "Not quite!", (255, 140, 120))
        m["lock"] = 1.6

    def quiz_boxes(self):
        return [pygame.Rect(170, 300, 300, 92), pygame.Rect(490, 300, 300, 92),
                pygame.Rect(170, 408, 300, 92), pygame.Rect(490, 408, 300, 92)]

    def history_key(self, ev):
        m = self.mini
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.end_mini()
            return
        if m["kind"] == "pyramid":
            if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_UP):
                self.pyramid_drop()
        elif m["kind"] == "quiz":
            choice = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}.get(k)
            if choice is not None:
                self.quiz_answer(choice)
        else:
            if k in (pygame.K_LEFT, pygame.K_a):
                m["lane"] = clamp(m["lane"] - 1, 0, 2)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                m["lane"] = clamp(m["lane"] + 1, 0, 2)

    def history_tap(self, x, y):
        m = self.mini
        if m["kind"] == "pyramid":
            self.pyramid_drop()
        elif m["kind"] == "quiz":
            for i, rr in enumerate(self.quiz_boxes()):
                if rr.collidepoint(x, y):
                    self.quiz_answer(i)
                    return
        else:
            m["lane"] = clamp(m["lane"] + (-1 if x < 480 else 1), 0, 2)

    def wrap_text(self, text, width):
        lines, line = [], ""
        for w in text.split():
            test = (line + " " + w).strip()
            if line and self.f_m.size(test)[0] > width:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        return lines

    def history_draw(self):
        m = self.mini
        if m["kind"] == "pyramid":
            self.draw_pyramid()
        elif m["kind"] == "quiz":
            self.draw_quiz()
        else:
            self.draw_caravan()
        for f in m["fx"]:
            self.text(f["s"], (f["x"], f["y"] - (0.7 - f["t"]) * 60), self.f_m, f["c"], shadow=INK, center=True)

    def draw_pyramid(self):
        m = self.mini
        scr = self.screen
        for y in range(WIN_H):
            pygame.draw.line(scr, lerp_col((250, 220, 160), (226, 184, 116), y / WIN_H), (0, y), (WIN_W, y))
        pygame.draw.circle(scr, (255, 236, 170), (800, 90), 40)
        pygame.draw.polygon(scr, (206, 170, 112), [(40, 640), (330, 230), (620, 640)])
        pygame.draw.polygon(scr, (182, 146, 92), [(330, 230), (620, 640), (420, 640)])
        shift = max(0, (len(m["blocks"]) - 10) * 22)
        cols = [(196, 160, 100), (214, 180, 120), (182, 146, 90)]
        for k, (l, r) in enumerate(m["blocks"]):
            top = 560 - (k + 1) * 22 + shift
            rr = pygame.Rect(int(l), int(top), int(r - l), 20)
            pygame.draw.rect(scr, cols[k % 3], rr, border_radius=3)
            pygame.draw.rect(scr, (120, 88, 52), rr, 2, border_radius=3)
            pygame.draw.line(scr, (150, 116, 72), (rr.x + 6, rr.centery), (rr.right - 6, rr.centery), 1)
        w = m["blocks"][-1][1] - m["blocks"][-1][0]
        rr = pygame.Rect(int(m["cx"] - w / 2), 110, int(w), 20)
        pygame.draw.rect(scr, (240, 210, 140), rr, border_radius=3)
        pygame.draw.rect(scr, (120, 88, 52), rr, 2, border_radius=3)
        self.text("Pyramid Builder - Ancient Egypt", (WIN_W // 2, 16), self.f_l, (80, 50, 20), center=True)
        self.text("Space / Enter / tap: drop the block. Stay centered for Perfect!", (WIN_W // 2, 58), self.f_s, (80, 50, 20), center=True)
        self.text("Blocks %d   Perfect x%d   Score %d" % (len(m["blocks"]) - 1, m["bonus"], m["score"]), (20, 600), self.f_m, (80, 50, 20))

    def draw_quiz(self):
        m = self.mini
        scr = self.screen
        scr.fill((30, 40, 70))
        panel = pygame.Rect(110, 40, 740, 560)
        self.panel(panel)
        self.text("Food Through the Ages", (panel.centerx, panel.y + 16), self.f_l, TEXT, center=True)
        n = len(m["qs"])
        self.text("Question %d / %d" % (min(m["idx"] + 1, n), n), (panel.x + 24, panel.y + 56), self.f_s, PANEL_D)
        self.text("Score %d" % m["score"], (panel.right - 24, panel.y + 56), self.f_s, PANEL_D, right=True)
        for i in range(m["lives"]):
            draw_heart(scr, panel.x + 30 + i * 28, panel.y + 92, 9, (240, 90, 120))
        q, opts, correct = m["qs"][min(m["idx"], n - 1)]
        y = panel.y + 120
        for line in self.wrap_text(q, panel.w - 80):
            self.text(line, (panel.centerx, y), self.f_m, TEXT, center=True)
            y += 28
        for i, (rr, opt) in enumerate(zip(self.quiz_boxes(), opts)):
            col = PANEL_L
            if m["lock"] > 0:
                if i == correct:
                    col = (150, 220, 130)
                elif i == m["picked"]:
                    col = (240, 150, 140)
            pygame.draw.rect(scr, INK, rr.inflate(6, 6), border_radius=10)
            pygame.draw.rect(scr, col, rr, border_radius=8)
            lines = self.wrap_text("%d.  %s" % (i + 1, opt), rr.w - 24)
            yy = rr.centery - len(lines) * 12
            for line in lines:
                self.text(line, (rr.centerx, yy), self.f_m, TEXT, center=True)
                yy += 24
        if m["lock"] <= 0:
            frac = clamp(m["timer"] / 10.0, 0, 1)
            pygame.draw.rect(scr, (60, 50, 40), (panel.x + 24, panel.bottom - 30, panel.w - 48, 12), border_radius=6)
            pygame.draw.rect(scr, (240, 170, 60), (panel.x + 24, panel.bottom - 30, int((panel.w - 48) * frac), 12), border_radius=6)
        self.text("Press 1-4 or tap an answer", (panel.centerx, panel.bottom - 50), self.f_s, PANEL_D, center=True)

    def draw_caravan(self):
        m = self.mini
        scr = self.screen
        scr.fill((214, 186, 130))
        for i in range(6):
            pygame.draw.ellipse(scr, (200, 168, 112), (i * 190 - 50, 60 + (i % 2) * 90, 260, 90))
        pygame.draw.rect(scr, (232, 206, 150), (230, 0, 500, WIN_H))
        off = int(m["t"] * 120) % 50
        for y in range(-50, WIN_H, 50):
            pygame.draw.rect(scr, (200, 170, 118), (476, y + off, 8, 24))
        for lx in CARAVAN_LANES:
            for y in range(0, WIN_H, 24):
                pygame.draw.rect(scr, (220, 190, 136), (lx - 1, y, 2, 12))
        for it in m["items"]:
            x, y = CARAVAN_LANES[it["lane"]], int(it["y"])
            if it["kind"] == "spice":
                pygame.draw.circle(scr, (214, 110, 40), (x, y), 14)
                pygame.draw.circle(scr, (250, 190, 90), (x - 4, y - 4), 4)
            elif it["kind"] == "silk":
                pygame.draw.circle(scr, (240, 220, 120), (x, y), 14)
                pygame.draw.circle(scr, (255, 252, 236), (x - 4, y - 4), 4)
            else:
                pygame.draw.polygon(scr, (150, 40, 40), [(x - 16, y + 12), (x + 16, y + 12), (x, y - 14)])
                pygame.draw.circle(scr, (255, 255, 255), (x - 5, y + 2), 2)
                pygame.draw.circle(scr, (255, 255, 255), (x + 5, y + 2), 2)
        x = CARAVAN_LANES[m["lane"]]
        pygame.draw.ellipse(scr, (196, 150, 90), (x - 34, 486, 68, 30))
        pygame.draw.ellipse(scr, (196, 150, 90), (x - 14, 470, 26, 22))
        for lx in (x - 26, x + 20):
            pygame.draw.rect(scr, (176, 130, 78), (lx, 510, 6, 18))
        pygame.draw.circle(scr, (196, 150, 90), (x + 34, 484), 10)
        pygame.draw.rect(scr, (196, 150, 90), (x + 30, 486, 6, 16))
        self.text("Silk Road Caravan - Left/Right, A/D or tap a side", (WIN_W // 2, 16), self.f_m, (80, 50, 20), center=True)
        self.text("Time %d    Score %d" % (max(0, int(m["time"])), m["score"]), (20, 600), self.f_m, (80, 50, 20))
        for i in range(m["lives"]):
            draw_heart(scr, WIN_W - 30 - i * 28, 600, 9, (200, 60, 70))

    HOUSE_W, HOUSE_H = 6, 5

    def house_problem(self, tx, ty, check_player=True):
        """Why a villager house cannot go at tile (tx, ty), or None when it can."""
        if self.location != "farm":
            return "build on the farm"
        if tx < 2 or ty < 2 or tx + self.HOUSE_W > MAP_W - 2 or ty + self.HOUSE_H > MAP_H - 2:
            return "outside the map"
        ptile = (int(self.player.x) // TILE, int(self.player.y) // TILE)
        for yy in range(ty, ty + self.HOUSE_H):
            for xx in range(tx, tx + self.HOUSE_W):
                tt = self.tiles[yy][xx]
                if tt == WATER:
                    return "on the water"
                if tt == BRIDGE:
                    return "on the bridge"
                if tt in (WALL, WOOD_FLOOR):
                    return "inside another building"
                if (xx, yy) in self.bld_at:
                    return "another building is there"
                o = self.objs.get((xx, yy))
                if o and o["t"] in ("tree", "stump"):
                    return "a tree is in the way"
                if o and o["t"] == "rock":
                    return "a rock is in the way"
                if (xx, yy) in self.soil:
                    return "that is farm soil"
                if check_player and (xx, yy) == ptile:
                    return "you are standing there"
        for n in self.npcs:
            nx, ny = int(n.x) // TILE, int(n.y) // TILE
            if tx <= nx < tx + self.HOUSE_W and ty <= ny < ty + self.HOUSE_H:
                return "a villager is standing there"
        return None

    def add_building(self, tx, ty):
        """Adds a player-built house. Solid walls come from bld_at via rebuild_solid()."""
        house = dict(kind="player_villager_house", tx=tx, ty=ty, w=self.HOUSE_W, h=self.HOUSE_H, player_built=True)
        self.buildings.append(house)
        for yy in range(ty, ty + self.HOUSE_H):
            for xx in range(tx, tx + self.HOUSE_W):
                self.bld_at[(xx, yy)] = house
                self.objs.pop((xx, yy), None)     # only flowers can be under a valid spot
                self.reserved.add((xx, yy))
        self.rebuild_solid()

    def start_placing(self):
        if self.location != "farm":
            self.toast("Go back to the farm to build a house.")
            return
        if self.inv.get("villager_house_kit", 0) <= 0:
            self.toast("You need a Villager House Kit. Craft one at the workbench.")
            return
        px, py = int(self.player.x) // TILE, int(self.player.y) // TILE
        self.placing = dict(tx=px + 2, ty=py - 2, hold=(0, 0), timer=0.0)
        self.state = "place"
        self.toast("Choose a spot. Arrows move, Enter or Space builds, Esc cancels.")

    def cancel_placing(self):
        self.placing = None
        self.state = "play"
        self.toast("Building cancelled. Your house kit is still in your pack.")

    def place_house(self):
        p = self.placing
        if p is None:
            return False
        reason = self.house_problem(p["tx"], p["ty"])
        if reason:
            self.toast("Can't build there: %s." % reason)
            return False
        self.take_item("villager_house_kit", 1)
        self.add_building(p["tx"], p["ty"])
        self.placing = None
        self.state = "play"
        self.sparkle(p["tx"] * TILE + 48, p["ty"] * TILE + 40, 12)
        self.qinc("house")
        self.toast("Villager house built!")
        return True

    def placing_move(self, dx, dy):
        p = self.placing
        p["tx"] = clamp(p["tx"] + dx, 0, MAP_W - self.HOUSE_W)
        p["ty"] = clamp(p["ty"] + dy, 0, MAP_H - self.HOUSE_H)

    def placing_update(self, dt):
        p = self.placing
        if p is None:
            self.state = "play"
            return
        keys = pygame.key.get_pressed()
        dx = int(bool(keys[pygame.K_d] or keys[pygame.K_RIGHT])) - int(bool(keys[pygame.K_a] or keys[pygame.K_LEFT]))
        dy = int(bool(keys[pygame.K_s] or keys[pygame.K_DOWN])) - int(bool(keys[pygame.K_w] or keys[pygame.K_UP]))
        d = (dx, dy)
        if d == (0, 0):
            p["hold"], p["timer"] = d, 0.0
            return
        if d != p["hold"]:                       # first frame of a press: one step
            self.placing_move(dx, dy)
            p["hold"], p["timer"] = d, 0.25
            return
        p["timer"] -= dt                         # held: repeat steps
        if p["timer"] <= 0:
            self.placing_move(dx, dy)
            p["timer"] = 0.12

    def placing_key(self, ev):
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.cancel_placing()
        elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e):
            self.place_house()

    def placing_pointer(self, vx, vy, click=False):
        """Mouse or touch: the house follows the pointer and a click builds it."""
        if self.placing is None:
            return
        cam = self.camera()
        tx = int((vx / SCALE + cam[0]) // TILE) - self.HOUSE_W // 2
        ty = int((vy / SCALE + cam[1]) // TILE) - self.HOUSE_H // 2
        self.placing["tx"] = clamp(tx, 0, MAP_W - self.HOUSE_W)
        self.placing["ty"] = clamp(ty, 0, MAP_H - self.HOUSE_H)
        if click:
            self.place_house()

    def draw_placing(self):
        p = self.placing
        if p is None:
            return
        cam = self.camera()
        reason = self.house_problem(p["tx"], p["ty"])
        scr = self.screen
        x0 = (p["tx"] * TILE - cam[0]) * SCALE
        y0 = (p["ty"] * TILE - cam[1]) * SCALE
        w, h = self.HOUSE_W * TILE * SCALE, self.HOUSE_H * TILE * SCALE
        ghost = pygame.transform.scale(SPR["player_house"], (w, h))
        ghost.set_alpha(170)
        scr.blit(ghost, (x0, y0))
        pygame.draw.rect(scr, (110, 230, 110) if reason is None else (240, 90, 80), (x0, y0, w, h), 3, border_radius=6)
        self.panel(pygame.Rect(WIN_W // 2 - 300, 14, 600, 62))
        self.text("Build the Villager House", (WIN_W // 2, 22), self.f_m, TEXT, center=True)
        if reason is None:
            self.text("Good spot - press Enter or Space to build", (WIN_W // 2, 48), self.f_s, (60, 120, 60), center=True)
        else:
            self.text("Not here: %s" % reason, (WIN_W // 2, 48), self.f_s, (170, 50, 40), center=True)
        self.text("Arrows / WASD move     Enter or Space build     Esc cancel",
                  (WIN_W // 2, WIN_H - 26), self.f_s, CREAM, shadow=INK, center=True)

    def bench_craft(self, key):
        r = WORKBENCH[key]
        if key in self.owned:
            self.toast("You already have the %s." % r["name"])
            return
        if not all(self.inv.get(i, 0) >= n for i, n in r["needs"].items()):
            self.toast("Missing materials for the %s." % r["name"])
            return
        for i, n in r["needs"].items():
            self.take_item(i, n)
        if key == "villager_house":
            self.add_item("villager_house_kit", 1, quiet=True)
            self.toast("Villager House Kit crafted! Choose where to build it.")
            self.start_placing()
            return
        self.owned.add(key)
        if key == "can2":
            self.water = self.water_cap()
        self.gain_xp("farm", 10)
        self.toast("Crafted: %s" % r["name"])

    def draw_bench(self):
        m = self.menu
        r = pygame.Rect(WIN_W // 2 - 330, WIN_H // 2 - 250, 660, 500)
        self.panel(r)
        self.text("Workbench", (r.x + 24, r.y + 18), self.f_l, TEXT)
        self.text("Gather wood and stone on the farm, then craft here.", (r.x + 24, r.y + 56), self.f_s, PANEL_D)
        keys = list(WORKBENCH)

        def row(k, rr):
            rec = WORKBENCH[k]
            self.text(rec["name"], (rr.x + 14, rr.y + 4), self.f_m, TEXT)
            self.text(rec["desc"], (rr.x + 14, rr.y + 28), self.f_s, PANEL_D)
            x = rr.right - 14
            if k in self.owned:
                self.text("Built", (x, rr.y + 14), self.f_m, (50, 120, 50), right=True)
                return
            parts = ["%d %s" % (n, ITEMS[i]["name"]) for i, n in rec["needs"].items()]
            ok = all(self.inv.get(i, 0) >= n for i, n in rec["needs"].items())
            self.text(", ".join(parts), (x, rr.y + 14), self.f_s, TEXT if ok else (170, 50, 40), right=True)

        self.draw_rows(r, r.y + 90, keys, m, 6, row, row_h=60)
        self.text("Enter: craft     Esc: close", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def pause_items(self):
        items = ["Resume", "Save game", "Save and quit to title", "Help", "Fish journal"]
        if CAN_HOST:
            items += ["Host LAN game", "Stop hosting", "Admin panel"]
        return items

    def admin_actions(self):
        """(label, function) pairs for the host's admin panel."""
        def give_seeds():
            for k in CROPS:
                self.add_item(k + "_seed", 10, quiet=True)
            self.toast("Admin: 10 of every crop seed")

        def give_fish():
            for k in FISH:
                self.add_item(k, 5, quiet=True)
            self.toast("Admin: 5 of every fish")

        def give_gold():
            self.money += 500
            self.toast("Admin: +500g")

        def set_noon():
            self.time = 12.0
            self.toast("Admin: time set to 12:00")

        def refill():
            self.energy = float(self.max_energy)
            self.water = self.water_cap()
            self.toast("Admin: energy and water refilled")

        def toggle_rain():
            self.rain = not self.rain
            self.toast("Admin: rain %s" % ("on" if self.rain else "off"))

        actions = [("Give 10 of every crop seed", give_seeds), ("Give 5 of every fish", give_fish),
                   ("Give 500 gold", give_gold), ("Set time to 12:00", set_noon),
                   ("Refill energy and water", refill), ("Toggle rain", toggle_rain)]
        if self.net_server:
            for p in self.remote:
                pid, name = p.get("id"), p.get("name", "player")
                actions.append(("Teleport to " + name, (lambda p=p: self.admin_teleport(p))))
                actions.append(("Kick " + name, (lambda pid=pid, name=name: self.admin_kick(pid, name))))
        return actions

    def admin_teleport(self, p):
        if p.get("loc") != self.location:
            self.toast("That player is not in the same place as you.")
            return
        self.player.x, self.player.y = p["x"], p["y"]
        self.toast("Admin: teleported to %s" % p.get("name", "player"))

    def admin_kick(self, pid, name):
        if self.net_server and self.net_server.kick(pid):
            self.toast("Admin: kicked %s" % name)
            self.remote = [r for r in self.remote if r.get("id") != pid]

    def draw_admin_menu(self):
        m = self.menu
        entries = self.admin_actions()
        r = pygame.Rect(WIN_W // 2 - 300, WIN_H // 2 - 230, 600, 460)
        self.panel(r)
        self.text("Admin panel", (r.centerx, r.y + 18), self.f_l, TEXT, center=True)
        self.text("Only the host can see this. Esc closes it.", (r.centerx, r.y + 52), self.f_s, PANEL_D, center=True)
        m["idx"] = clamp(m["idx"], 0, max(0, len(entries) - 1))
        for i, (label, _) in enumerate(entries[:9]):
            rr = pygame.Rect(r.x + 30, r.y + 84 + i * 40, r.w - 60, 34)
            if m["idx"] == i:
                pygame.draw.rect(self.screen, GOLD, rr, border_radius=6)
            self.text(label, rr.center, self.f_m, TEXT, center=True)
        self.text("Up/Down + Enter", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def draw_journal(self):
        m = self.menu
        r = pygame.Rect(WIN_W // 2 - 300, WIN_H // 2 - 240, 600, 480)
        self.panel(r)
        n, title, bonus = self.fish_mastery()
        self.text("Fish Journal", (r.centerx, r.y + 16), self.f_l, TEXT, center=True)
        self.text("%s - %d of %d species caught (+%d%% fish sell)" % (title, n, len(FISH), int(bonus * 100)),
                  (r.centerx, r.y + 52), self.f_s, PANEL_D, center=True)
        keys = list(FISH)

        def row(k, rr):
            caught = self.fish_log.get(k, 0)
            self.icon(k, (rr.x + 10, rr.y + 7), 2)
            self.text(FISH[k]["name"] if caught else "???", (rr.x + 54, rr.y + 4), self.f_m, TEXT)
            sub = ("Caught %d - sells %dg" % (caught, FISH[k]["sell"])) if caught else "Not caught yet"
            self.text(sub, (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
            if FISH[k]["tier"] >= 3:
                self.text("RARE", (rr.right - 14, rr.y + 14), self.f_s, (200, 120, 40), right=True)

        self.draw_rows(r, r.y + 84, keys, m, 7, row)
        self.text("Up/Down to scroll. Esc to close.", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def admin_key(self, ev):
        m = self.menu
        entries = self.admin_actions()
        k = ev.key
        if k in (pygame.K_UP, pygame.K_w):
            m["idx"] = max(0, m["idx"] - 1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            m["idx"] = min(max(0, len(entries) - 1), m["idx"] + 1)
        elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER) and entries:
            entries[clamp(m["idx"], 0, len(entries) - 1)][1]()

    def draw_pc(self):
        m = self.menu
        tab = m["tab"]
        scr = self.screen
        r = pygame.Rect(WIN_W // 2 - 340, WIN_H // 2 - 270, 680, 540)
        pygame.draw.rect(scr, (30, 34, 44), r.inflate(28, 28), border_radius=16)
        pygame.draw.rect(scr, (222, 236, 248), r, border_radius=8)
        pygame.draw.rect(scr, (40, 90, 170), (r.x, r.y, r.w, 44), border_radius=8)
        self.text("FarmNet Shop", (r.x + 18, r.y + 10), self.f_l, (255, 255, 255))
        self.icon("coin", (r.right - 150, r.y + 6), 2)
        self.text("%sg" % format(self.money, ","), (r.right - 112, r.y + 12), self.f_m, (255, 255, 255))
        for i, nm in enumerate(("Seeds", "Pantry", "Recipes", "Upgrades", "Trading")):
            tr = pygame.Rect(r.x + 14 + i * 133, r.y + 54, 127, 34)
            pygame.draw.rect(scr, (255, 255, 255) if i == tab else (190, 206, 226), tr, border_radius=6)
            pygame.draw.rect(scr, (40, 90, 170), tr, 2, border_radius=6)
            self.text(nm, tr.center, self.f_m, (30, 60, 120), center=True)
        hints = ["Delivered tomorrow morning. 15% cheaper than the shop!",
                 "Ingredients for cafe recipes. Delivered tomorrow morning.",
                 "Learn new dishes. Guests will order them once unlocked.",
                 "Permanent upgrades. Effects apply immediately.",
                 "Sell goods at today's market price, or buy ingredients. Prices change every day."]
        self.text(hints[tab], (r.x + 20, r.y + 98), self.f_s, (60, 80, 120))
        entries = self.pc_entries(tab)
        if not entries:
            self.text("Everything in this tab is already yours!", (r.centerx, r.centery), self.f_m, (60, 80, 120), center=True)

        def row(k, rr):
            if tab == 4:
                self.trade_row(k, rr)
                return
            if tab == 0:
                c = CROPS[ITEMS[k]["crop"]]
                icon, name = k, ITEMS[k]["name"]
                sub = "Grows in %d days. Sells for %dg." % (c["days"], c["sell"])
            elif tab == 1:
                icon, name = k, ITEMS[k]["name"]
                sub = "You have %d." % self.inv.get(k, 0)
            elif tab == 2:
                icon, name = k, RECIPES[k]["name"]
                sub = "Needs: " + ", ".join("%d %s" % (n, ITEMS[i]["name"]) for i, n in RECIPES[k]["needs"].items())
            else:
                u = UPGRADES[k]
                icon, name, sub = u["icon"], u["name"], u["desc"]
            price = self.pc_price(tab, k)
            self.icon(icon, (rr.x + 10, rr.y + 7), 2)
            self.text(name, (rr.x + 54, rr.y + 4), self.f_m, TEXT)
            self.text(sub, (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
            self.text("%dg" % price, (rr.right - 14, rr.y + 12), self.f_m, TEXT if self.money >= price else (170, 50, 40), right=True)

        self.draw_rows(r, r.y + 126, entries, m, 6, row)
        n_mail = sum(self.pending.values())
        self.text("In the mail: %d item%s" % (n_mail, "" if n_mail == 1 else "s"), (r.x + 20, r.bottom - 34), self.f_s, (60, 80, 120))
        hint = "Left/Right: tab   Enter: sell or buy 1   Shift+Enter: x5   Esc: close"
        self.text(hint, (r.right - 20, r.bottom - 34), self.f_s, (60, 80, 120), right=True)

    # ------------------------------------------------------- cafe menu
    def draw_cafe_menu(self):
        m = self.menu
        r = pygame.Rect(WIN_W // 2 - 330, WIN_H // 2 - 250, 660, 500)
        self.panel(r)
        self.text("Your Cafe", (r.x + 24, r.y + 18), self.f_l, TEXT)
        st = self.stars()
        for i in range(5):
            draw_star(self.screen, r.right - 150 + i * 26, r.y + 34, 11, GOLD if i < st else (190, 150, 100))
        cs = self.cafe_stats
        self.text("Today: %d served, %dg earned (tips %dg), %d unhappy" % (cs["served"], cs["earned"], cs["tips"], cs["angry"]),
                  (r.x + 24, r.y + 56), self.f_s, PANEL_D)
        entries = ["__open__"] + list(self.unlocked)

        def row(k, rr):
            if k == "__open__":
                self.icon("coin", (rr.x + 10, rr.y + 7), 2)
                self.text("Cafe is %s" % ("OPEN" if self.cafe_open else "CLOSED"), (rr.x + 54, rr.y + 4), self.f_m, TEXT)
                self.text("Guests arrive 9am-9pm. Enter to toggle.", (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
            else:
                on = self.menu_on.get(k, True)
                self.icon(k, (rr.x + 10, rr.y + 7), 2)
                self.text(RECIPES[k]["name"], (rr.x + 54, rr.y + 4), self.f_m, TEXT)
                self.text("Guests pay %dg. You have %d." % (self.cafe_price(k), self.inv.get(k, 0)), (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
                self.text("ON" if on else "OFF", (rr.right - 14, rr.y + 12), self.f_m, (50, 120, 50) if on else (170, 50, 40), right=True)

        self.draw_rows(r, r.y + 84, entries, m, 7, row)
        self.text("Enter: toggle menu item   Esc: close", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    # ------------------------------------------------------- arcade menu
    def draw_arcade_menu(self):
        m = self.menu
        r = pygame.Rect(WIN_W // 2 - 330, WIN_H // 2 - 250, 660, 500)
        self.panel(r)
        self.text("Arcade", (r.x + 24, r.y + 18), self.f_l, TEXT)
        self.icon("ticket", (r.right - 190, r.y + 16), 2)
        self.text("x%d" % self.inv.get("ticket", 0), (r.right - 150, r.y + 24), self.f_m, TEXT)
        self.icon("coin", (r.right - 100, r.y + 16), 2)
        self.text("%dg" % self.money, (r.right - 62, r.y + 24), self.f_s, TEXT)
        self.text("Each game costs %dg. Score earns tickets and gold." % PLAY_COST, (r.x + 24, r.y + 56), self.f_s, PANEL_D)
        entries = list(MINI) + list(PRIZES)

        def row(k, rr):
            if k in MINI:
                g = MINI[k]
                self.icon(g["icon"], (rr.x + 10, rr.y + 7), 2)
                self.text(g["name"], (rr.x + 54, rr.y + 4), self.f_m, TEXT)
                self.text(g["desc"], (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
                self.text("Best %d" % self.hi.get(k, 0), (rr.right - 14, rr.y + 14), self.f_s, TEXT, right=True)
            else:
                p = PRIZES[k]
                self.icon(p["icon"], (rr.x + 10, rr.y + 7), 2)
                self.text(p["name"], (rr.x + 54, rr.y + 4), self.f_m, TEXT)
                self.text(p["desc"], (rr.x + 54, rr.y + 28), self.f_s, PANEL_D)
                ok = self.inv.get("ticket", 0) >= p["cost"]
                self.text("%d tickets" % p["cost"], (rr.right - 14, rr.y + 14), self.f_s, TEXT if ok else (170, 50, 40), right=True)

        self.draw_rows(r, r.y + 84, entries, m, 7, row)
        self.text("Enter: play / claim prize   Esc: leave", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def extra_menu_key(self, ev, ty):
        m = self.menu
        k = ev.key
        if ty == "journal":
            if k == pygame.K_UP:
                m["idx"] = max(0, m["idx"] - 1)
            elif k == pygame.K_DOWN:
                m["idx"] = min(len(FISH) - 1, m["idx"] + 1)
            elif k == pygame.K_ESCAPE:
                self.state, self.menu = "play", {}
            return
        if ty == "fishmaster":
            if k == pygame.K_ESCAPE and m.get("view") != "journal":
                self.state, self.menu = "play", {}
            else:
                self.fishmaster_key(ev)
            return
        if ty == "admin":
            if k == pygame.K_ESCAPE:
                self.state, self.menu = "play", {}
            else:
                self.admin_key(ev)
            return
        up = k in (pygame.K_UP, pygame.K_w)
        down = k in (pygame.K_DOWN, pygame.K_s)
        left = k in (pygame.K_LEFT, pygame.K_a)
        right = k in (pygame.K_RIGHT, pygame.K_d)
        ok = k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)
        shift = ev.mod & pygame.KMOD_SHIFT
        if k == pygame.K_ESCAPE:
            self.state, self.menu = "play", {}
            return
        if ty == "pc":
            if left or right:
                m["tab"] = (m["tab"] + (1 if right else -1)) % 5
                m["idx"], m["scroll"] = 0, 0
                return
            entries = self.pc_entries(m["tab"])
        elif ty == "cafe":
            entries = ["__open__"] + list(self.unlocked)
        elif ty == "bench":
            entries = list(WORKBENCH)
        else:
            entries = list(MINI) + list(PRIZES)
        if up:
            m["idx"] = max(0, m["idx"] - 1)
        elif down:
            m["idx"] = min(max(0, len(entries) - 1), m["idx"] + 1)
        elif ok and entries:
            key = entries[clamp(m["idx"], 0, len(entries) - 1)]
            if ty == "pc" and m["tab"] == 4:
                self.trade(key[0], key[1], 5 if shift else 1)
                m["idx"] = clamp(m["idx"], 0, max(0, len(self.pc_entries(4)) - 1))
            elif ty == "pc":
                self.pc_buy(m["tab"], key, 5 if (shift and m["tab"] in (0, 1)) else 1)
                m["idx"] = clamp(m["idx"], 0, max(0, len(self.pc_entries(m["tab"])) - 1))
            elif ty == "bench":
                self.bench_craft(key)
            elif ty == "cafe":
                if key == "__open__":
                    self.cafe_open = not self.cafe_open
                else:
                    self.menu_on[key] = not self.menu_on.get(key, True)
            elif key in MINI:
                self.start_mini(key)
            else:
                self.claim_prize(key)

    def claim_prize(self, k):
        p = PRIZES[k]
        if self.inv.get("ticket", 0) < p["cost"]:
            self.toast("Not enough tickets.")
            return
        if k == "p_trophy" and "trophy" in self.owned:
            self.toast("You already own the trophy!")
            return
        self.take_item("ticket", p["cost"])
        if k == "p_seeds":
            for _ in range(3):
                self.add_item(random.choice(list(CROPS)) + "_seed", 1)
        elif k == "p_bar":
            self.add_item("energy_bar")
        else:
            self.owned.add("trophy")
            self.rep = clamp(self.rep + 15, 0, 100)
            self.toast("You won the Golden Fork Trophy!", "coin")

    # ------------------------------------------------------- mini-games
    def start_mini(self, kind):
        if self.money < PLAY_COST:
            self.toast("You need %dg to play." % PLAY_COST)
            return
        self.money -= PLAY_COST
        if kind in HISTORY_GAMES:
            return self.history_start(kind)
        m = dict(kind=kind, t=0.0, score=0, lives=3, fx=[])
        if kind == "veggie":
            m.update(time=60.0, bx=450.0, items=[], spawn=0.5)
        elif kind == "weed":
            m.update(time=45.0, holes=[None] * 9, spawn=0.6, cur=4, combo=0)
        else:
            m.update(seq=[], show_t=-0.6, phase="show", pt=0.0, inp=0, flash=None, lives=1)
            self.memory_next_round(m)
        self.mini = m
        self.menu = {}
        self.state = "mini"

    def memory_next_round(self, m):
        m["seq"].append(random.randrange(4))
        m["phase"], m["show_t"], m["inp"], m["flash"] = "show", -0.6, 0, None

    def pop_fx(self, x, y, text, col=(255, 240, 150)):
        self.mini["fx"].append(dict(x=x, y=y, t=0.7, s=text, c=col))

    def weed_rect(self, i):
        return pygame.Rect(450 + (i % 3 - 1) * 200 - 80, 150 + (i // 3) * 135, 160, 100)

    def whack(self, i):
        m = self.mini
        h = m["holes"][i]
        if not h:
            return
        rr = self.weed_rect(i)
        if h["k"] == "weed":
            pts = 10 + m["combo"] * 2
            m["score"] += pts
            m["combo"] += 1
            self.pop_fx(rr.centerx, rr.y, "+%d" % pts)
        else:
            m["lives"] -= 1
            m["combo"] = 0
            self.pop_fx(rr.centerx, rr.y, "Oops!", (255, 120, 120))
        m["holes"][i] = None

    def memory_press(self, d):
        m = self.mini
        if m["phase"] != "input":
            return
        m["flash"] = dict(d=d, t=0.25)
        if d == m["seq"][m["inp"]]:
            m["inp"] += 1
            if m["inp"] >= len(m["seq"]):
                m["score"] += 10 * len(m["seq"])
                m["phase"], m["pt"] = "next", 0.7
        else:
            m["phase"], m["pt"] = "wrong", 1.0

    def mini_tap(self, x, y):
        m = self.mini
        if m and m["kind"] in HISTORY_GAMES:
            return self.history_tap(x, y)
        if self.state != "mini" or not m:
            return
        if m["kind"] == "weed":
            for i in range(9):
                if self.weed_rect(i).inflate(20, 40).collidepoint(x, y):
                    self.whack(i)
                    return
        elif m["kind"] == "memory":
            for d, c in enumerate(MEM_CENTERS):
                if abs(x - c[0]) < 70 and abs(y - c[1]) < 70:
                    self.memory_press(d)
                    return

    def mini_key(self, ev):
        m = self.mini
        if m["kind"] in HISTORY_GAMES:
            return self.history_key(ev)
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.end_mini()
            return
        dirs = {pygame.K_UP: 0, pygame.K_w: 0, pygame.K_RIGHT: 1, pygame.K_d: 1,
                pygame.K_DOWN: 2, pygame.K_s: 2, pygame.K_LEFT: 3, pygame.K_a: 3}
        if m["kind"] == "memory":
            if k in dirs:
                self.memory_press(dirs[k])
        elif m["kind"] == "weed":
            if k in dirs:
                d, c = dirs[k], m["cur"]
                if d == 0:
                    c = (c - 3) % 9
                elif d == 2:
                    c = (c + 3) % 9
                elif d == 1:
                    c = c - c % 3 + (c % 3 + 1) % 3
                else:
                    c = c - c % 3 + (c % 3 - 1) % 3
                m["cur"] = c
            elif k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.whack(m["cur"])

    def update_mini(self, dt):
        if self.mini["kind"] in HISTORY_GAMES:
            return self.history_update(dt)
        m = self.mini
        m["t"] += dt
        for f in m["fx"]:
            f["t"] -= dt
        m["fx"] = [f for f in m["fx"] if f["t"] > 0]
        kind = m["kind"]
        if kind == "veggie":
            m["time"] -= dt
            keys = pygame.key.get_pressed()
            dx = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
            v = dx if dx else self.touch.vec[0]
            m["bx"] = clamp(m["bx"] + v * 470 * dt, 170, 730)
            m["spawn"] -= dt
            if m["spawn"] <= 0:
                m["spawn"] = max(0.28, 0.6 - m["t"] * 0.006)
                r = random.random()
                k = "rock" if r < 0.22 else ("gold" if r < 0.28 else "veg")
                m["items"].append(dict(x=random.uniform(150, 750), y=100, k=k, v=random.choice(list(CROPS)),
                                       vy=170 + m["t"] * 4 + random.uniform(0, 40)))
            for it in m["items"][:]:
                it["y"] += it["vy"] * dt
                if abs(it["x"] - m["bx"]) < 56 and 480 < it["y"] < 520:
                    m["items"].remove(it)
                    if it["k"] == "rock":
                        m["lives"] -= 1
                        self.pop_fx(it["x"], 470, "Ouch!", (255, 120, 120))
                    else:
                        pts = 50 if it["k"] == "gold" else 10
                        m["score"] += pts
                        self.pop_fx(it["x"], 470, "+%d" % pts)
                elif it["y"] > 560:
                    m["items"].remove(it)
            if m["lives"] <= 0 or m["time"] <= 0:
                self.end_mini()
        elif kind == "weed":
            m["time"] -= dt
            for i, h in enumerate(m["holes"]):
                if h:
                    h["age"] += dt
                    if h["age"] > h["life"]:
                        if h["k"] == "weed":
                            m["combo"] = 0
                        m["holes"][i] = None
            m["spawn"] -= dt
            if m["spawn"] <= 0:
                m["spawn"] = max(0.35, 0.8 - m["t"] * 0.01)
                free = [i for i, h in enumerate(m["holes"]) if h is None]
                if free:
                    m["holes"][random.choice(free)] = dict(
                        k="weed" if random.random() < 0.75 else "flower", age=0.0,
                        life=max(0.7, random.uniform(1.0, 1.6) - m["t"] * 0.01))
            if m["lives"] <= 0 or m["time"] <= 0:
                self.end_mini()
        else:
            if m["phase"] == "show":
                m["show_t"] += dt
                if m["show_t"] >= len(m["seq"]) * 0.7:
                    m["phase"], m["inp"] = "input", 0
            if m["flash"]:
                m["flash"]["t"] -= dt
                if m["flash"]["t"] <= 0:
                    m["flash"] = None
            if m["phase"] == "wrong":
                m["pt"] -= dt
                if m["pt"] <= 0:
                    self.end_mini()
            elif m["phase"] == "next":
                m["pt"] -= dt
                if m["pt"] <= 0:
                    self.memory_next_round(m)

    def end_mini(self):
        m = self.mini
        score = m["score"]
        per = {"veggie": 30, "weed": 25, "memory": 20, "pyramid": 2, "quiz": 10, "caravan": 15}[m["kind"]]
        tickets, gold = score // per, score // 2
        self.money += gold
        if tickets:
            self.add_item("ticket", tickets, quiet=True)
        new = score > self.hi.get(m["kind"], 0)
        if new:
            self.hi[m["kind"]] = score
        self.mini_result = dict(kind=m["kind"], score=score, tickets=tickets, gold=gold, new=new)
        self.state = "mini_over"

    def draw_mini(self):
        scr = self.screen
        if self.state == "mini" and self.mini["kind"] in HISTORY_GAMES:
            return self.history_draw()
        scr.fill((18, 14, 36))
        for i in range(0, WIN_W, 40):
            pygame.draw.line(scr, (34, 28, 66), (i, 0), (i, WIN_H))
        for j in range(0, WIN_H, 40):
            pygame.draw.line(scr, (34, 28, 66), (0, j), (WIN_W, j))
        if self.state == "mini_over":
            self.draw_mini_over()
            return
        m = self.mini
        area = pygame.Rect(110, 70, 680, 500)
        pygame.draw.rect(scr, (30, 22, 60), area, border_radius=10)
        pygame.draw.rect(scr, (250, 80, 140), area, 4, border_radius=10)
        self.text(MINI[m["kind"]]["name"], (area.centerx, 78), self.f_l, (255, 230, 120), shadow=(120, 30, 70), center=True)
        self.text("Score %d" % m["score"], (area.x + 18, 90), self.f_m, (255, 255, 255))
        if "time" in m:
            self.text("Time %d" % max(0, int(m["time"])), (area.right - 18, 90), self.f_m, (255, 255, 255), right=True)
        if m["kind"] != "memory":
            for i in range(m["lives"]):
                draw_heart(scr, area.x + 30 + i * 28, 126, 9, (240, 90, 120))
        kind = m["kind"]
        if kind == "veggie":
            for it in m["items"]:
                x, y = int(it["x"]), int(it["y"])
                if it["k"] == "rock":
                    self.icon("stone", (x - 24, y - 24), 3)
                else:
                    if it["k"] == "gold":
                        pygame.draw.circle(scr, (250, 210, 70), (x, y), 30)
                        pygame.draw.circle(scr, (255, 244, 170), (x, y), 30, 3)
                    self.icon(it["v"], (x - 24, y - 24), 3)
            bx, by = int(m["bx"]), 500
            pts = [(bx - 52, by), (bx + 52, by), (bx + 40, by + 34), (bx - 40, by + 34)]
            pygame.draw.polygon(scr, (176, 126, 80), pts)
            pygame.draw.polygon(scr, (96, 64, 40), pts, 3)
            for k in (-26, 0, 26):
                pygame.draw.line(scr, (120, 84, 54), (bx + k, by + 4), (bx + int(k * 0.8), by + 30), 2)
            self.text("Move: A / D or arrows (touch: drag left side)", (area.centerx, area.bottom - 26), self.f_s, (200, 190, 240), center=True)
        elif kind == "weed":
            for i in range(9):
                rr = self.weed_rect(i)
                pygame.draw.ellipse(scr, (50, 34, 28), (rr.x, rr.bottom - 44, rr.w, 44))
                h = m["holes"][i]
                if h:
                    rise = min(1.0, h["age"] / 0.18)
                    left = h["life"] - h["age"]
                    if left < 0.2:
                        rise *= max(0.0, left / 0.2)
                    cx, cy = rr.centerx, rr.bottom - 26 - int(52 * rise)
                    if h["k"] == "weed":
                        pygame.draw.circle(scr, (90, 170, 70), (cx, cy), 28)
                        for a in (-40, 0, 40):
                            pygame.draw.line(scr, (60, 130, 50), (cx + a // 2, cy - 22), (cx + a, cy - 44), 5)
                        pygame.draw.circle(scr, (255, 255, 255), (cx - 10, cy - 4), 6)
                        pygame.draw.circle(scr, (255, 255, 255), (cx + 10, cy - 4), 6)
                        pygame.draw.circle(scr, (30, 30, 40), (cx - 10, cy - 4), 3)
                        pygame.draw.circle(scr, (30, 30, 40), (cx + 10, cy - 4), 3)
                    else:
                        for dx, dy in ((0, -16), (-16, 0), (16, 0), (0, 16)):
                            pygame.draw.circle(scr, (248, 176, 200), (cx + dx, cy + dy), 14)
                        pygame.draw.circle(scr, (250, 220, 90), (cx, cy), 10)
                pygame.draw.ellipse(scr, (96, 68, 48), (rr.x, rr.bottom - 44, rr.w, 44), 5)
            rr = self.weed_rect(m["cur"])
            pygame.draw.rect(scr, (255, 230, 120), rr, 3, border_radius=8)
            self.text("Arrows + Space, or just tap the weeds!", (area.centerx, area.bottom - 26), self.f_s, (200, 190, 240), center=True)
        else:
            lit = None
            if m["phase"] == "show" and m["show_t"] >= 0:
                idx = int(m["show_t"] / 0.7)
                if idx < len(m["seq"]) and (m["show_t"] % 0.7) < 0.45:
                    lit = m["seq"][idx]
            if m["flash"]:
                lit = m["flash"]["d"]
            for d in range(4):
                c = MEM_CENTERS[d]
                rr = pygame.Rect(0, 0, 124, 124)
                rr.center = c
                base = MEM_COLS[d]
                col = base if lit == d else tuple(int(v * 0.35) for v in base)
                pygame.draw.rect(scr, col, rr, border_radius=16)
                pygame.draw.rect(scr, (255, 255, 255) if lit == d else (90, 80, 110), rr, 4, border_radius=16)
                self.icon(MEM_ICONS[d], (c[0] - 40, c[1] - 40), 5)
            status = {"show": "Watch carefully...", "input": "Your turn!  %d / %d" % (m["inp"], len(m["seq"])),
                      "next": "Nice!", "wrong": "Wrong order!"}[m["phase"]]
            self.text(status, (area.centerx, 122), self.f_m, (255, 255, 255), center=True)
            self.text("Arrows / WASD, or tap the ingredients", (area.centerx, area.bottom - 26), self.f_s, (200, 190, 240), center=True)
        for f in m["fx"]:
            self.text(f["s"], (f["x"], f["y"] - (0.7 - f["t"]) * 60), self.f_m, f["c"], shadow=INK, center=True)

    def draw_mini_over(self):
        res = self.mini_result
        r = pygame.Rect(WIN_W // 2 - 260, 120, 520, 400)
        self.panel(r)
        self.text(MINI[res["kind"]]["name"], (r.centerx, r.y + 22), self.f_l, TEXT, center=True)
        self.text("Game over!", (r.centerx, r.y + 70), self.f_m, (150, 70, 40), center=True)
        self.text("Score: %d" % res["score"], (r.centerx, r.y + 120), self.f_l, TEXT, center=True)
        if res["new"]:
            self.text("New high score!", (r.centerx, r.y + 160), self.f_m, (60, 120, 50), center=True)
        self.icon("ticket", (r.centerx - 90, r.y + 200), 2)
        self.text("+%d tickets" % res["tickets"], (r.centerx - 50, r.y + 208), self.f_m, TEXT)
        self.icon("coin", (r.centerx - 90, r.y + 250), 2)
        self.text("+%dg" % res["gold"], (r.centerx - 50, r.y + 258), self.f_m, TEXT)
        self.text("Press Enter", (r.centerx, r.bottom - 36), self.f_s, PANEL_D, center=True)

    # ------------------------------------------------------- fishing
    def start_fishing(self, tx, ty):
        self.fishing = dict(tx=tx, ty=ty, phase="charge", power=0.0, dir=1, charging=False,
                            t=0.0, bite=0.0, perfect=False, holding=False, kind="fish")
        self.state = "fishing"

    def end_fishing(self):
        self.fishing = None
        self.state = "play"

    def fishing_down(self):
        """Action pressed: charge a cast, hook a bite, or lift the reel bar."""
        f = self.fishing
        if not f:
            return
        f["holding"] = True
        if f["phase"] == "charge":
            f["charging"] = True
        elif f["phase"] == "wait":
            self.toast("Too early! The fish got scared.")
            self.end_fishing()
        elif f["phase"] == "bite":
            kind = roll_fish(self.level("fish"), f["perfect"], "hook" in self.owned or self.location in ("island", "station"),
                             "master" in self.owned)
            tier = FISH[kind]["tier"]
            f.update(phase="reel", kind=kind, zh=max(0.16, 0.34 - 0.04 * tier),
                     speed=0.9 + 0.3 * tier + 0.05 * self.level("fish"),
                     fy=0.5, ftgt=0.5, ft=0.0, zy=0.5, zv=0.0, prog=0.35)

    def fishmaster_entries(self):
        n, title, bonus = self.fish_mastery()
        ents = [("sell", "Sell all my fish (+%d%% rank bonus)" % int(bonus * 100)),
                ("rank", "Your rank: %s (%d of %d species)" % (title, n, len(FISH)))]
        if "master" in self.owned:
            ents.append(("done", "You already own the Master Rod"))
        elif n == len(FISH):
            ents.append(("rod", "Claim the Master Rod!"))
        else:
            ents.append(("locked", "Master Rod: catch all %d species" % len(FISH)))
        return ents

    def fishmaster_act(self, key):
        if key == "sell":
            _, _, bonus = self.fish_mastery()
            base = sum(FISH[k]["sell"] * self.inv.get(k, 0) for k in FISH)
            if base == 0:
                self.toast("You have no fish to sell.")
                return
            for k in FISH:
                if self.inv.get(k):
                    self.take_item(k, self.inv[k])
            total = int(base * (1 + bonus))
            self.money += total
            self.toast("The Fish Master paid you %dg" % total, "coin")
        elif key == "rod":
            self.owned.add("master")
            self.toast("You earned the Master Rod! Rare fish bite more often now.")

    def draw_fishmaster(self):
        m = self.menu
        r = pygame.Rect(WIN_W // 2 - 300, WIN_H // 2 - 200, 600, 400)
        self.panel(r)
        self.text("The Fish Master", (r.centerx, r.y + 18), self.f_l, TEXT, center=True)
        if m.get("view") == "journal":
            self.draw_journal()
            return
        for i, (key, label) in enumerate(self.fishmaster_entries()):
            rr = pygame.Rect(r.x + 30, r.y + 80 + i * 44, r.w - 60, 36)
            if m["idx"] == i:
                pygame.draw.rect(self.screen, GOLD, rr, border_radius=6)
            col = TEXT if key not in ("locked", "done") else PANEL_D
            self.text(label, rr.center, self.f_m, col, center=True)
        self.text("Enter: choose     Esc: leave", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def fishmaster_key(self, ev):
        m = self.menu
        k = ev.key
        if m.get("view") == "journal":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
                m["view"] = "list"
            return
        ents = self.fishmaster_entries()
        if k in (pygame.K_UP, pygame.K_w):
            m["idx"] = max(0, m["idx"] - 1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            m["idx"] = min(len(ents) - 1, m["idx"] + 1)
        elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            key = ents[clamp(m["idx"], 0, len(ents) - 1)][0]
            if key == "rank":
                m["view"] = "journal"
            else:
                self.fishmaster_act(key)

    def fish_mastery(self):
        """(species caught, rank title, sell bonus) from the fish journal."""
        n = sum(1 for k in FISH if self.fish_log.get(k, 0) > 0)
        title, bonus = "No rank yet", 0.0
        for need, name, b in MASTERY:
            if n >= need:
                title, bonus = name, b
        return n, title, bonus

    def fishing_up(self):
        """Action released: a charging cast is thrown; while reeling, the bar falls."""
        f = self.fishing
        if not f:
            return
        f["holding"] = False
        if f["phase"] == "charge" and f["charging"]:
            f["charging"] = False
            f["perfect"] = 0.4 <= f["power"] <= 0.6
            f["phase"] = "wait"
            f["t"] = random.uniform(2.0, 4.5) - (0.8 if f["perfect"] else 0.0)
            if f["power"] < 0.15:
                f["t"] += 2.0

    def update_fishing(self, dt):
        f = self.fishing
        if not f:
            return
        ph = f["phase"]
        if ph == "charge":
            if f["charging"]:
                f["power"] += f["dir"] * dt * 1.5
                if f["power"] >= 1.0:
                    f["power"], f["dir"] = 1.0, -1
                elif f["power"] <= 0.0:
                    f["power"], f["dir"] = 0.0, 1
        elif ph == "wait":
            f["t"] -= dt
            if f["t"] <= 0:
                f["phase"] = "bite"
                f["bite"] = 0.85 + 0.04 * self.level("fish")
        elif ph == "bite":
            f["bite"] -= dt
            if f["bite"] <= 0:
                self.toast("It got away...")
                self.end_fishing()
        elif ph == "reel":
            self.update_reel(f, dt)

    def update_reel(self, f, dt):
        zh = f["zh"]
        accel = 2.6 if f["holding"] else -1.9
        f["zv"] = (f["zv"] + accel * dt) * (0.94 ** (dt * 60))
        f["zy"] += f["zv"] * dt
        lo, hi = zh / 2, 1 - zh / 2
        if f["zy"] < lo:
            f["zy"], f["zv"] = lo, 0.0
        if f["zy"] > hi:
            f["zy"], f["zv"] = hi, 0.0
        f["ft"] -= dt
        if f["ft"] <= 0:
            f["ftgt"] = random.uniform(0.08, 0.92)
            f["ft"] = random.uniform(0.5, 1.2)
        f["fy"] += (f["ftgt"] - f["fy"]) * min(1.0, dt * f["speed"] * 1.5)
        inside = abs(f["fy"] - f["zy"]) < zh / 2
        f["prog"] = clamp(f["prog"] + dt * (0.32 if inside else -0.22), 0.0, 1.0)
        if f["prog"] >= 1.0:
            self.add_item(f["kind"])
            self.qinc("fish")
            first = self.fish_log.get(f["kind"], 0) == 0
            self.fish_log[f["kind"]] = self.fish_log.get(f["kind"], 0) + 1
            if first:
                self.toast("New journal entry: %s!" % FISH[f["kind"]]["name"], f["kind"])
            self.gain_xp("fish", 8 + 6 * FISH[f["kind"]]["tier"])
            self.sparkle(f["tx"] * TILE + 8, f["ty"] * TILE + 4, 10)
            self.end_fishing()
        elif f["prog"] <= 0.0:
            self.toast("The fish got away!")
            self.end_fishing()

    def draw_fishing(self):
        f = self.fishing
        if not f:
            return
        cx, cy = self.camera()
        scr = self.screen
        ph = f["phase"]
        p = self.player
        px, py = (p.x - cx) * SCALE, (p.y - 14 - cy) * SCALE
        bx = (f["tx"] * TILE + 8 - cx) * SCALE
        by = (f["ty"] * TILE + 8 - cy) * SCALE
        if ph in ("wait", "bite", "reel"):
            bob = math.sin(self.t * 5) * 3
            if ph == "bite":
                bob += 10 if int(self.t * 12) % 2 == 0 else 0
            pygame.draw.line(scr, (240, 240, 245), (px, py), (bx, by + bob), 2)
            for i in range(2):
                rad = int(10 + ((self.t * 20 + i * 12) % 24))
                pygame.draw.circle(scr, (210, 236, 250), (int(bx), int(by + 6)), rad, 1)
            pygame.draw.circle(scr, (240, 70, 60), (int(bx), int(by + bob)), 8)
            pygame.draw.circle(scr, (255, 255, 255), (int(bx), int(by + bob - 3)), 4)
        if ph == "charge":
            bw, x0, y0 = 340, WIN_W // 2 - 170, WIN_H - 120
            pygame.draw.rect(scr, INK, (x0 - 4, y0 - 4, bw + 8, 30), border_radius=8)
            pygame.draw.rect(scr, (60, 52, 50), (x0, y0, bw, 22), border_radius=6)
            pygame.draw.rect(scr, (120, 200, 110), (x0 + int(bw * 0.4), y0, int(bw * 0.2), 22), border_radius=6)
            pygame.draw.rect(scr, (250, 200, 60), (x0, y0, int(bw * f["power"]), 22), border_radius=6)
            pygame.draw.rect(scr, (255, 255, 255), (x0 + int(bw * f["power"]) - 2, y0 - 4, 4, 30))
            self.text("Hold SPACE to charge. Release to cast. Green = perfect!", (WIN_W // 2, y0 - 24),
                      self.f_s, CREAM, shadow=INK, center=True)
        elif ph == "wait":
            self.text("Wait for a bite...", (px, py - 76), self.f_m, CREAM, shadow=INK, center=True)
        elif ph == "bite":
            pygame.draw.circle(scr, (255, 220, 80), (int(px), int(py - 70)), 26)
            pygame.draw.circle(scr, INK, (int(px), int(py - 70)), 26, 3)
            self.text("!", (px, py - 92), self.f_xl, (200, 40, 30), center=True)
            self.text("PRESS SPACE!", (WIN_W // 2, 60), self.f_l, (255, 230, 120), shadow=INK, center=True)
        elif ph == "reel":
            x0, y0, h = WIN_W - 150, 110, 400
            pygame.draw.rect(scr, INK, (x0 - 6, y0 - 6, 72, h + 12), border_radius=10)
            pygame.draw.rect(scr, (40, 36, 44), (x0, y0, 60, h), border_radius=8)
            zh_px = int(f["zh"] * h)
            zc = y0 + int((1 - f["zy"]) * h)
            pygame.draw.rect(scr, (110, 220, 100), (x0 + 4, zc - zh_px // 2, 52, zh_px), border_radius=6)
            fy = y0 + int((1 - f["fy"]) * h)
            col = FISH[f["kind"]]["color"]
            pygame.draw.circle(scr, col, (x0 + 30, fy), 10)
            pygame.draw.circle(scr, INK, (x0 + 30, fy), 10, 2)
            pygame.draw.rect(scr, INK, (x0 - 30, y0 - 6, 18, h + 12), border_radius=6)
            pygame.draw.rect(scr, (60, 52, 50), (x0 - 26, y0, 10, h), border_radius=4)
            pygame.draw.rect(scr, (120, 220, 120), (x0 - 26, y0 + int((1 - f["prog"]) * h), 10, int(f["prog"] * h)), border_radius=4)
            self.text("Hold SPACE to lift the bar. Keep the fish in the green!", (WIN_W // 2, 60),
                      self.f_m, CREAM, shadow=INK, center=True)

# ============================================================ the game
def make_app_icon(size=32):
    """Small pot-and-carrot icon drawn in code (used for the window icon)."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 32.0
    def R(c, x, y, w, h, r=0):
        pygame.draw.rect(s, c, (int(x * k), int(y * k), int(w * k), int(h * k)), border_radius=int(r * k))
    R((120, 170, 90), 0, 0, 32, 32, 7)
    R((250, 150, 60), 14, 14, 5, 12, 2)
    pygame.draw.polygon(s, (90, 160, 70), [(int(16 * k), int(14 * k)), (int(10 * k), int(6 * k)), (int(22 * k), int(6 * k))])
    R((70, 62, 60), 6, 16, 20, 11, 4)
    R((96, 88, 84), 8, 14, 16, 4, 2)
    R((240, 240, 236), 9, 6, 2, 6, 1)
    R((240, 240, 236), 13, 4, 2, 6, 1)
    return s


class Game(Extras):
    def __init__(self):
        pygame.display.set_caption("A Game About Farming and Cooking")
        pygame.display.set_icon(make_app_icon())
        pygame.display.set_caption("A Game About Farming and Cooking" + ("" if CAN_HOST else " - Player"))
        if ANDROID:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.screen = pygame.Surface((WIN_W, WIN_H))
        self.hotbar_rects = []
        self.disp_size = (WIN_W, WIN_H)
        self.dst = pygame.Rect(0, 0, WIN_W, WIN_H)
        self.dscale = 1.0
        self.layout_display()
        self.touch = TouchControls(self)
        self.view = pygame.Surface((VIEW_W, VIEW_H))
        self.clock = pygame.time.Clock()
        self.f_s = pygame.font.Font(None, 22)
        self.f_m = pygame.font.Font(None, 28)
        self.f_l = pygame.font.Font(None, 40)
        self.f_xl = pygame.font.Font(None, 76)
        build_static_sprites()
        build_extra_sprites()
        self.icons = {k: tex(k) or make_icon(k) for k in ITEMS}
        self.icons["coin"] = make_icon("coin")
        self.icons2 = {}
        self.season_built = None
        self.t = 0.0
        self.state = "title"
        self.title_idx = 0
        self.new_game()
        self.state = "title"

    # ------------------------------------------------------- setup
    # ------------------------------------------------------- quests
    def qinc(self, stat, n=1):
        self.qstats[stat] = self.qstats.get(stat, 0) + n

    def quest_progress(self, q, base=0):
        g = q["goal"]
        t = g[0]
        if t == "stat":
            return min(self.qstats.get(g[1], 0) - base, g[2]), g[2]
        if t == "items":
            need = sum(g[1].values())
            have = sum(min(self.inv.get(i, 0), n) for i, n in g[1].items())
            return have, need
        if t == "money":
            return min(self.money, g[1]), g[1]
        if t == "level":
            return min(self.level(g[1]), g[2]), g[2]
        if t == "fishkinds":
            kinds = sum(1 for v in self.fish_log.values() if v > 0)
            return min(kinds, g[1]), g[1]
        return 0, 1

    def quest_ready(self, q):
        cur, need = self.quest_progress(q, self.qactive.get(q["id"], 0))
        return cur >= need

    def quest_active_for(self, giver):
        for qid in self.qactive:
            if QUEST_BY_ID[qid]["giver"] == giver:
                return QUEST_BY_ID[qid]
        return None

    def quest_next(self, giver):
        for q in QUESTS:
            if q["giver"] == giver and q["id"] not in self.qdone and q["id"] not in self.qactive:
                return q
        return None

    def npc_wants_talk(self, name):
        act = self.quest_active_for(name)
        if act:
            return self.quest_ready(act)
        return self.quest_next(name) is not None

    def npc_marker(self, name):
        act = self.quest_active_for(name)
        if act:
            return "done" if self.quest_ready(act) else None
        return "new" if self.quest_next(name) else None

    def accept_quest(self, q):
        base = self.qstats.get(q["goal"][1], 0) if q["goal"][0] == "stat" else 0
        first = not self.qdone and not self.qactive
        self.qactive[q["id"]] = base
        self.toast("New quest: %s" % q["title"])
        if first:
            self.toast("Press J to open your quest journal.")

    def finish_quest(self, q):
        if q["goal"][0] == "items":
            for i, n in q["goal"][1].items():
                self.take_item(i, n)
        self.money += q["gold"]
        extra = ""
        if q["item"]:
            self.add_item(q["item"], q["n"], quiet=True)
            extra = " + %d %s" % (q["n"], ITEMS[q["item"]]["name"])
        self.qactive.pop(q["id"], None)
        self.qdone.add(q["id"])
        self.toast("Quest complete: %s! +%dg%s" % (q["title"], q["gold"], extra), "coin")
        self.sparkle(self.player.x, self.player.y - 10, 10)

    def npc_talk(self, n):
        act = self.quest_active_for(n.name)
        if act:
            cur, need = self.quest_progress(act, self.qactive[act["id"]])
            if cur >= need:
                self.finish_quest(act)
                self.say(n.name, act["thanks"])
                if act.get("wish"):
                    self.wish_opts = [w for w in WISH_OPTIONS if w[0] not in self.wishes_done]
                    self.wish_idx = 0
                    if self.wish_opts:
                        self.after_dialog = "wish"
            else:
                self.say(n.name, "%s  (%d / %d)" % (act["text"], cur, need))
            return
        nxt = self.quest_next(n.name)
        if nxt:
            self.accept_quest(nxt)
            self.say(n.name, nxt["offer"])
            return
        self.say(n.name, random.choice(n.lines))

    def draw_journal(self):
        scr = self.screen
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((24, 14, 10, 160))
        scr.blit(ov, (0, 0))
        r = pygame.Rect(90, 60, WIN_W - 180, WIN_H - 120)
        self.panel(r)
        self.text("Quest Journal", (r.x + 24, r.y + 16), self.f_l, TEXT)
        self.text("Completed %d / %d" % (len(self.qdone), len(QUESTS)), (r.right - 24, r.y + 24),
                  self.f_m, PANEL_D, right=True)
        y = r.y + 64
        if not self.qactive:
            self.text("No active quests. Talk to the villagers to find some!", (r.x + 24, y), self.f_m, PANEL_D)
        for qid in list(self.qactive)[:6]:
            q = QUEST_BY_ID[qid]
            cur, need = self.quest_progress(q, self.qactive[qid])
            self.text(q["title"], (r.x + 24, y), self.f_m, TEXT)
            self.text("from " + q["giver"], (r.right - 24, y + 4), self.f_s, PANEL_D, right=True)
            self.text(q["text"], (r.x + 24, y + 28), self.f_s, PANEL_D)
            bar = pygame.Rect(r.x + 24, y + 52, r.w - 48, 12)
            pygame.draw.rect(scr, (120, 84, 54), bar, border_radius=5)
            fill = bar.copy()
            fill.w = int(bar.w * clamp(cur / max(1, need), 0, 1))
            pygame.draw.rect(scr, (110, 190, 80) if cur >= need else (240, 180, 60), fill, border_radius=5)
            self.text("%d / %d" % (cur, need), (bar.right, y + 30), self.f_s, TEXT, right=True)
            y += 74
        self.text("J / Esc: close", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    # ------------------------------------------------------- cooking: order, bake, plate
    def start_cook(self, key):
        rec = RECIPES[key]
        if not all(self.inv.get(i, 0) >= n for i, n in rec["needs"].items()):
            self.toast("You're missing some ingredients.")
            return
        steps = []
        for ing, n in rec["needs"].items():
            steps += [ing] * n
        rnd = random.Random(self.day * 97 + len(key) * 13 + random.randrange(10000))
        self.cg = dict(key=key, steps=steps, buttons=list(rec["needs"].keys()), pos=0, mistakes=0,
                       phase="prep", t=0.0, m=0.0, center=rnd.uniform(0.3, 0.7), half=0.08,
                       stars=0, msg="", menu=dict(self.menu) if self.menu else dict(type="cook", idx=0, scroll=0))
        self.menu = {}
        self.state = "cookgame"

    def cook_leave(self):
        self.menu = self.cg["menu"]
        self.state = "menu"
        self.cg = None

    def cook_finish(self, stars):
        cg = self.cg
        key = cg["key"]
        cg["stars"], cg["phase"] = stars, "result"
        msg = {3: "Perfect golden crust!", 2: "Tasty and well timed.",
               1: "A little pale, but edible.", 0: "Burnt to a crisp. The ingredients are lost."}[stars]
        cg["msg"] = msg
        if stars == 0:
            self.toast("Burnt! Nothing to serve.")
            return
        portions = {1: 1, 2: 1, 3: 2}[stars]
        if random.random() < 0.05 * (self.level("cook") - 1):
            portions += 1
        self.add_item(key, portions, quiet=True)
        self.toast("%s x%d (%s)" % (RECIPES[key]["name"], portions, "*" * stars))
        self.gain_xp("cook", 4 + 3 * stars)
        self.qinc("cook")
        if stars == 3:
            self.qinc("perfect")

    def start_bake(self):
        self.cg["phase"] = "bake"
        self.cg["t"] = 0.0

    def cook_stop(self):
        cg = self.cg
        d = abs(cg["m"] - cg["center"])
        h = cg["half"]
        acc = 1.0 - 0.5 * d / h if d <= h else max(0.0, 0.5 - (d - h) * 4)
        prep = max(0.0, 1.0 - 0.2 * cg["mistakes"])
        score = 0.4 * prep + 0.6 * acc
        stars = 3 if score >= 0.85 else 2 if score >= 0.65 else 1 if score >= 0.4 else 0
        if acc < 0.2:                                  # a badly missed bake burns, however neat the prep
            stars = 0
        self.cook_finish(stars)

    def cookgame_key(self, ev):
        cg = self.cg
        k = ev.key
        nums = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6)
        if cg["phase"] == "prep":
            if k == pygame.K_ESCAPE:
                self.cook_leave()
            elif k in nums and nums.index(k) < len(cg["buttons"]):
                ing = cg["buttons"][nums.index(k)]
                if ing == cg["steps"][cg["pos"]]:
                    cg["pos"] += 1
                    if cg["pos"] >= len(cg["steps"]):
                        for i, n in RECIPES[cg["key"]]["needs"].items():
                            self.take_item(i, n)
                        self.start_bake()
                else:
                    cg["mistakes"] += 1
                    self.toast("Not that one! The ticket says %s." % ITEMS[cg["steps"][cg["pos"]]]["name"])
        elif cg["phase"] == "bake":
            if k == pygame.K_ESCAPE:
                self.cook_finish(0)
            elif k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e):
                self.cook_stop()
        elif cg["phase"] == "result":
            if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e, pygame.K_ESCAPE):
                self.cook_leave()

    def update_cookgame(self, dt):
        cg = self.cg
        if cg is None:
            return
        cg["t"] += dt
        if cg["phase"] == "bake":
            p = (cg["t"] * 0.85) % 1.0
            cg["m"] = 1.0 - abs(p * 2.0 - 1.0)        # the oven meter swings from 0 to 1 and back
        self.update_effects(dt)

    def draw_cookgame(self):
        cg = self.cg
        if cg is None:
            return
        scr = self.screen
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((24, 14, 10, 175))
        scr.blit(ov, (0, 0))
        rec = RECIPES[cg["key"]]
        r = pygame.Rect(WIN_W // 2 - 300, 40, 600, 560)
        self.panel(r)
        self.text(rec["name"], (r.x + 24, r.y + 14), self.f_l, TEXT)
        sub = {"prep": "Prep: add each ingredient in ticket order (keys 1-%d)" % len(cg["buttons"]),
               "bake": "Bake: press Space or E when the meter is in the golden zone",
               "result": "Space or E to return to the kitchen"}[cg["phase"]]
        self.text(sub, (r.x + 24, r.y + 50), self.f_s, PANEL_D)

        tk = pygame.Rect(r.x + 24, r.y + 84, 220, 300)
        pygame.draw.rect(scr, (250, 240, 214), tk, border_radius=8)
        pygame.draw.rect(scr, INK, tk, 2, border_radius=8)
        self.text("ORDER TICKET", (tk.x + 14, tk.y + 10), self.f_s, PANEL_D)
        y = tk.y + 40
        for i, ing in enumerate(cg["steps"]):
            done = i < cg["pos"]
            cur = i == cg["pos"] and cg["phase"] == "prep"
            col = (50, 120, 50) if done else (170, 50, 40) if cur else TEXT
            mark = "[x]" if done else ">" if cur else "[ ]"
            self.text("%s %s" % (mark, ITEMS[ing]["name"]), (tk.x + 14, y), self.f_m if cur else self.f_s, col)
            y += 30

        mx = tk.right + 30
        mw = r.right - 24 - mx
        self.text("Oven", (mx, tk.y + 10), self.f_s, PANEL_D)
        bar = pygame.Rect(mx, tk.y + 40, mw, 34)
        pygame.draw.rect(scr, (90, 60, 40), bar, border_radius=6)
        zone = pygame.Rect(bar.x + int((cg["center"] - cg["half"]) * bar.w), bar.y,
                           max(2, int(2 * cg["half"] * bar.w)), bar.h)
        pygame.draw.rect(scr, (250, 210, 80), zone, border_radius=4)
        mxp = bar.x + int(cg["m"] * bar.w)
        pygame.draw.rect(scr, (255, 255, 255), (mxp - 2, bar.y - 6, 4, bar.h + 12), border_radius=2)
        pygame.draw.rect(scr, INK, bar, 2, border_radius=6)
        if cg["phase"] == "prep":
            self.text("Oven waits for your ingredients...", (mx, bar.bottom + 14), self.f_s, PANEL_D)
        self.text("Mistakes: %d" % cg["mistakes"], (mx, bar.bottom + 40), self.f_s, TEXT)
        if cg["phase"] == "result":
            for i in range(3):
                draw_star(scr, mx + 30 + i * 52, bar.bottom + 110, 20, GOLD if i < cg["stars"] else (92, 64, 44))
            self.text(cg["msg"], (mx, bar.bottom + 150), self.f_m, TEXT)

        n = len(cg["buttons"])
        bw = min(140, (r.w - 48 - 8 * (n - 1)) // n)
        for i, ing in enumerate(cg["buttons"]):
            br = pygame.Rect(r.x + 24 + i * (bw + 8), r.bottom - 96, bw, 60)
            active = cg["phase"] == "prep" and cg["steps"][cg["pos"]] == ing
            pygame.draw.rect(scr, (255, 226, 150) if active else (255, 246, 226), br, border_radius=8)
            pygame.draw.rect(scr, INK, br, 2, border_radius=8)
            scr.blit(pygame.transform.scale(self.icons[ing], (32, 32)), (br.x + 8, br.y + 14))
            self.text("%d %s" % (i + 1, ITEMS[ing]["name"]), (br.x + 46, br.y + 8), self.f_s, TEXT)
            self.text("need %d" % RECIPES[cg["key"]]["needs"][ing], (br.x + 46, br.y + 32), self.f_s, PANEL_D)
        if cg["phase"] == "prep":
            self.text("Esc: leave", (r.right - 24, r.bottom - 22), self.f_s, PANEL_D, right=True)

    def new_game(self):
        self.day = 1
        self.time = WAKE_HOUR
        self.money = 250
        self.max_energy = 100
        self.energy = 100.0
        self.water = 20
        self.rain = False
        self.inv = {"parsnip_seed": 8, "wheat_seed": 5}
        self.bin = {}
        self.sel = 0
        self.sel_timer = 0.0
        self.soil = {}
        self.eggs = []
        self.particles = []
        self.toasts = []
        self.menu = {}
        self.dialog = None
        self.focus = None
        self.fade = 0.0
        self.summary = None
        self.passed_out = False
        self.smoke_t = 0.0
        self.rain_drops = [[random.uniform(0, VIEW_W), random.uniform(0, VIEW_H)] for _ in range(110)]
        self.init_extras()
        self.ensure_season()
        self.new_world()
        self.player = Player(30 * TILE, 14 * TILE + 8)
        self.crit = [self.new_critter() for _ in range(14)]

    def ensure_season(self):
        s = SEASONS[((self.day - 1) // DAYS_PER_SEASON) % len(SEASONS)]
        if s != self.season_built:
            build_season_sprites(s)
            self.season_built = s

    @property
    def season(self):
        return self.season_built

    @property
    def day_of_season(self):
        return (self.day - 1) % DAYS_PER_SEASON + 1

    @property
    def year(self):
        return 1 + (self.day - 1) // (DAYS_PER_SEASON * len(SEASONS))

    def new_world(self):
        self.location, self.farm_world, self.tables = "farm", None, []
        rnd = random.Random(1337)
        T = [[GRASS] * MAP_W for _ in range(MAP_H)]
        self.tiles = T

        def prect(x0, y0, x1, y1, tt=PATH):
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if 0 <= x < MAP_W and 0 <= y < MAP_H:
                        T[y][x] = tt

        prect(29, 10, 30, 21)
        prect(29, 20, 63, 21)
        prect(24, 12, 39, 12)
        prect(36, 11, 39, 11)
        prect(46, 17, 61, 23)
        # Road from the farm down to the bridge, the bridge's east approach, and the village street.
        prect(62, 22, 63, 44)
        prect(62, 44, 79, 45)
        prect(90, 44, 124, 45)
        for hx in (98, 106, 114):                 # a short lane to each village front door
            prect(hx + 2, 42, hx + 2, 43)
        # A winding river runs down the eastern side of the farm/village.
        # Keep just one broad wooden crossing, aligned with the Fish Master route.
        for y in range(MAP_H):
            center = river_center(y)
            for x in range(center - 3, center + 4):
                if 0 <= x < MAP_W:
                    T[y][x] = WATER
            for x in (center - 5, center - 4, center + 4, center + 5):
                if 0 <= x < MAP_W and T[y][x] == GRASS:
                    T[y][x] = SAND
        # One big bridge: wide enough to read as a main route, three tiles deep.
        bridge_y = 44
        bridge_center = river_center(bridge_y)
        for yy in range(BRIDGE_ROWS[0], BRIDGE_ROWS[1] + 1):
            for xx in range(bridge_center - 6, bridge_center + 7):
                if 0 <= xx < MAP_W:
                    T[yy][xx] = BRIDGE

        # The open sea runs the full height of the map along the east edge. A sandy beach with a
        # gently wavy shoreline separates it from the land.
        for y in range(MAP_H):
            beach = sea_beach_x(y)
            for x in range(beach, MAP_W):
                if x >= beach + 3:
                    T[y][x] = WATER
                elif T[y][x] == GRASS:
                    T[y][x] = SAND
        # The harbour is an inlet of the sea, past the secondary village. The ferry port sits on its north shore.
        for yy in range(44, 47):
            for xx in range(120, MAP_W):
                T[yy][xx] = WATER

        self.buildings = [
            dict(kind="house", tx=27, ty=5, w=6, h=5),
            dict(kind="village_house", tx=98, ty=37, w=6, h=5),
            dict(kind="village_house2", tx=106, ty=37, w=6, h=5),
            dict(kind="village_house3", tx=114, ty=37, w=6, h=5),
            dict(kind="kitchen", tx=36, ty=8, w=4, h=3),
            dict(kind="bin", tx=24, ty=11, w=2, h=1),
            dict(kind="stall", tx=50, ty=15, w=5, h=3),
            dict(kind="coop", tx=45, ty=26, w=3, h=2),
            dict(kind="cafe", tx=38, ty=15, w=8, h=4),
            dict(kind="bench", tx=35, ty=6, w=2, h=1),
            dict(kind="village_port", tx=VILLAGE_PORT_TX, ty=VILLAGE_PORT_TY, w=2, h=1),
            dict(kind="port_house", tx=PORT_HOUSE_TX, ty=PORT_HOUSE_TY, w=6, h=5),
            dict(kind="arcade", tx=57, ty=17, w=2, h=1),
        ]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        self.lamps = [(28, 11), (31, 11), (49, 18), (55, 18)]
        self.fences = set()
        for x in range(43, 54):
            for y in (25, 33):
                if not (y == 33 and x in (47, 48)):
                    self.fences.add((x, y))
        for y in range(25, 34):
            for x in (43, 53):
                self.fences.add((x, y))
        res = set()
        for (x, y) in self.bld_at:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    res.add((x + dx, y + dy))
        for y in range(MAP_H):
            for x in range(MAP_W):
                if T[y][x] != GRASS:
                    res.add((x, y))
        for x in range(42, 55):
            for y in range(24, 35):
                res.add((x, y))
        for l in self.lamps:
            res.add(l)
        for x in range(37, 47):
            res.add((x, 19))
        self.reserved = res
        self.objs = {}

        def put(x, y, t, **kw):
            self.objs[(x, y)] = dict(t=t, **kw)

        for y in range(MAP_H):
            for x in range(MAP_W):
                if (x, y) in res:
                    continue
                edge = min(x, MAP_W - 1 - x, y, MAP_H - 1 - y)
                if edge < 4 and rnd.random() < 0.7:
                    put(x, y, "tree", hp=4, v=rnd.randrange(2))

        def scatter(t, n, **kw):
            placed = tries = 0
            while placed < n and tries < n * 40:
                tries += 1
                x, y = rnd.randrange(5, FARM_W - 5), rnd.randrange(4, MAP_H - 4)
                if (x, y) in res or (x, y) in self.objs:
                    continue
                put(x, y, t, v=rnd.randrange(3 if t != "tree" else 2), **kw)
                placed += 1

        scatter("tree", 130, hp=4)
        # Keep the entire eastern side clear so the river and buildable village land are visible.
        for pos, obj in list(self.objs.items()):
            # Keep the river and the whole eastern bank free of trees so the
            # crafted villager-house area is open and reachable.
            if pos[0] >= 60 and obj["t"] == "tree":
                del self.objs[pos]
        scatter("rock", 85, hp=3)
        scatter("flower", 160)
        # Clear the east bank (river and village land) and every object standing on a road,
        # path, sand or water tile, so the bridge route and village land stay open.
        for pos in list(self.objs):
            x, y = pos
            if (x >= 60 and self.objs[pos]["t"] == "tree") or east_clear(x, y) or T[y][x] != GRASS:
                del self.objs[pos]
        for (x, y) in list(self.objs):
            if 20 <= x <= 42 and 13 <= y <= 26 and rnd.random() < 0.85:
                del self.objs[(x, y)]
        for y in range(15, 18):
            for x in range(33, 37):
                self.objs.pop((x, y), None)
                self.soil[(x, y)] = dict(wet=False, crop=None, age=0)
        self.rebuild_solid()
        self.chickens = [Chicken(45 * TILE + i * 28, 30 * TILE + (i % 2) * 14) for i in range(3)]
        mabel = NPC("Mabel", 52 * TILE + 8, 16 * TILE + 13, SPR["mabel"], MABEL_LINES)
        fern = NPC("Fern", 54 * TILE, 21 * TILE, SPR["fern"], FERN_LINES, wander=(47, 18, 60, 22))
        fisherman = NPC("Fisherman", 95 * TILE + 8, 46 * TILE + 8, SPR["fisherman"], FISHERMAN_LINES,
                        wander=(93, 46, 97, 49))

        def npc_at(name, tx, ty, sprite, lines, wander=None):
            self.objs.pop((tx, ty), None)            # nobody spawns inside a tree or rock
            return NPC(name, tx * TILE + 8, ty * TILE + 8, SPR[sprite], lines, wander=wander)

        for xx in range(VILLAGE_PORT_TX, VILLAGE_PORT_TX + 2):
            self.objs.pop((xx, VILLAGE_PORT_TY), None)
        for yy in range(PORT_HOUSE_TY, PORT_HOUSE_TY + 5):
            for xx in range(PORT_HOUSE_TX, PORT_HOUSE_TX + 6):
                self.objs.pop((xx, yy), None)
        self.npcs = [
            mabel, fern, fisherman,
            npc_at("Gus", 41, 11, "gus", GUS_LINES, wander=(39, 10, 45, 13)),
            npc_at("Lila", 26, 30, "lila", LILA_LINES, wander=(22, 28, 30, 34)),
            npc_at("Pip", 62, 27, "pip", PIP_LINES, wander=(60, 26, 68, 30)),
            npc_at("Tomas", 116, 43, "tomas", TOMAS_LINES, wander=(112, 42, 120, 46)),
            npc_at("Dario", 120, 42, "dario", DARIO_LINES, wander=(118, 42, 124, 42)),
        ]
        self.eggs = []

    def rebuild_solid(self):
        S = [[False] * MAP_W for _ in range(MAP_H)]
        for y in range(MAP_H):
            for x in range(MAP_W):
                if self.tiles[y][x] in (WATER, WALL):
                    S[y][x] = True
        for (x, y) in self.bld_at:
            S[y][x] = True
        for (x, y) in self.lamps:
            S[y][x] = True
        for (x, y) in self.fences:
            S[y][x] = True
        for (x, y), o in self.objs.items():
            if o["t"] in ("tree", "rock", "stump"):
                S[y][x] = True
        for tb in self.active_tables():
            S[tb["ty"]][tb["tx"]] = True
        self.solid = S

    def new_critter(self):
        return dict(x=random.uniform(0, VIEW_W), y=random.uniform(0, VIEW_H), a=random.uniform(0, 6.28),
                    ph=random.uniform(0, 6.28), c=random.choice([(250, 240, 120), (250, 160, 200), (160, 210, 250)]))

    # ------------------------------------------------------- save / load
    def has_save(self):
        return os.path.exists(SAVE_FILE)

    WORLD_KEYS = ("tiles", "solid", "objs", "buildings", "bld_at", "lamps", "fences",
                  "reserved", "soil", "chickens", "npcs", "eggs", "tables")

    def _save_src(self):
        if self.location != "farm" and self.farm_world:
            return dict(soil=self.farm_world["soil"], objs=self.farm_world["objs"])
        return dict(soil=self.soil, objs=self.objs)

    def _save_pos(self):
        if self.location in ("island", "station"):
            return FARM_DOCK_OUT
        if self.location == "portHouse":
            return PORT_HOUSE_OUT
        if self.location != "farm":
            return CAFE_EXIT_OUT
        return (self.player.x, self.player.y)

    def start_warp(self, target):
        self.warp = dict(target=target, t=0.0, switched=False)
        self.fade = 0.0
        self.state = "warp"

    def update_warp(self, dt):
        w = self.warp
        half = 0.35
        w["t"] += dt
        if not w["switched"]:
            self.fade = min(1.0, w["t"] / half)
            if w["t"] >= half:
                self.switch_location(w["target"])
                w["switched"], w["t"], self.fade = True, 0.0, 1.0
        else:
            self.fade = max(0.0, 1.0 - w["t"] / half)
            if w["t"] >= half:
                self.state, self.warp, self.fade = "play", None, 0.0
        self.update_effects(dt)

    def switch_location(self, target):
        # The dungeon is a sub-area of the fisherman's island. Preserve the island
        # world in memory so leaving the dungeon returns to the same island.
        if target == "dungeon" and self.location == "island":
            self.island_world = {k: getattr(self, k) for k in self.WORLD_KEYS}
            # Like Stardew Valley's mine elevator, every fifth cleared floor
            # becomes a checkpoint when the player leaves and returns.
            self.dungeon_floor = max(1, (self.dungeon_best_floor // 5) * 5)
            self.build_dungeon(self.dungeon_floor)
            self.location = "dungeon"
            self.player.x, self.player.y = (40 * TILE + 8, 70 * TILE + 8)
            self.player.dir = "down"
            self.toast("Fisherman's Catacombs — clear the rooms and find the exit!")
            self.focus = None
            self.rebuild_solid()
            return
        if target == "island" and self.location == "dungeon":
            if self.island_world:
                for k, v in self.island_world.items():
                    setattr(self, k, v)
            self.island_world = None
            self.location = "island"
            self.player.x, self.player.y = (58 * TILE + 8, 38 * TILE + 8)
            self.player.dir = "down"
            self.focus = None
            self.rebuild_solid()
            return
        if target != "farm" and self.location not in ("farm", target):
            self.switch_location("farm")          # sail back to the farm, then on to the new place
        if target != "farm" and self.location == "farm":
            self.farm_world = {k: getattr(self, k) for k in self.WORLD_KEYS}
            if target in ("island", "station"):
                self.qinc("sail")
            if target == "island":
                self.build_island()
                self.toast("Welcome to the island! Everyone who sails here can meet.")
                spawn, facing = ISLAND_SPAWN, "up"
            elif target == "station":
                self.build_station()
                self.toast("The Ruined Station. Search the ruins for scrap and old coins.")
                spawn, facing = STATION_SPAWN, "left"
            else:
                if target == "cafe":
                    self.build_cafe_interior()
                    self.toast("Welcome to your cafe!")
                elif target == "portHouse":
                    self.build_port_house_interior()
                    self.toast("The port house smells of salt and old magic.")
                else:
                    self.build_house_interior()
                    self.toast("Home sweet home.")
                spawn, facing = CAFE_DOOR_IN, "down"
            self.location = target
            self.player.x, self.player.y = spawn
            self.player.dir = facing
        elif target == "farm" and self.location != "farm":
            out = {"house": HOUSE_EXIT_OUT, "island": FARM_DOCK_OUT, "station": FARM_DOCK_OUT,
                   "portHouse": PORT_HOUSE_OUT}.get(self.location, CAFE_EXIT_OUT)
            if self.location == "island" and self.last_port == "village":
                out = VILLAGE_PORT_OUT             # the ferry brings you back to the port you left from
            self.last_port = "farm"
            self.customers = []
            for k, v in self.farm_world.items():
                setattr(self, k, v)
            self.farm_world = None
            self.location = "farm"
            self.player.x, self.player.y = out
            self.player.dir = "up"
        self.focus = None
        self.rebuild_solid()

    def build_island(self):
        """An island in the sea. Shared by everyone who sails there in multiplayer."""
        T = [[WATER] * MAP_W for _ in range(MAP_H)]
        cx, cy, rx, ry = 60, 46, 28, 22
        for y in range(MAP_H):
            for x in range(MAP_W):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if d <= 1.0:
                    T[y][x] = GRASS
                elif d <= 1.2:
                    T[y][x] = SAND
                if ((x - 70) / 4) ** 2 + ((y - 40) / 3) ** 2 <= 1.0:
                    T[y][x] = WATER
        self.tiles = T
        self.buildings = [dict(kind="dock_back", tx=34, ty=46, w=2, h=1),
                          dict(kind="port", tx=84, ty=44, w=2, h=1),
                          dict(kind="dungeon", tx=58, ty=34, w=2, h=2)]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        rnd = random.Random(77)
        self.objs = {}
        for y in range(MAP_H):
            for x in range(MAP_W):
                if T[y][x] != GRASS or abs(x - 34) < 3 and abs(y - 46) < 3 or abs(x - 84.5) < 2.5 and abs(y - 44) < 3 or (56 <= x <= 61 and 32 <= y <= 37):
                    continue
                r = rnd.random()
                if r < 0.05:
                    self.objs[(x, y)] = dict(t="tree", hp=4, v=rnd.randrange(2))
                elif r < 0.08:
                    self.objs[(x, y)] = dict(t="rock", hp=3, v=rnd.randrange(3))
                elif r < 0.25:
                    self.objs[(x, y)] = dict(t="flower", v=rnd.randrange(3))
        self.tables = []
        self.lamps, self.fences, self.reserved = [], set(), set()
        self.soil, self.chickens, self.eggs = {}, [], []
        self.npcs = [NPC("Fish Master", 58 * TILE + 8, 44 * TILE + 8, SPR["fishmaster"],
                         FISH_MASTER_LINES, wander=(56, 42, 62, 48)),
                      NPC("Coral", 46 * TILE + 8, 46 * TILE + 8, SPR["coral"], CORAL_LINES,
                          wander=(42, 42, 50, 50))]
        self.customers = []
        self.rebuild_solid()

    def build_dungeon(self, floor=None):
        """Generate a Stardew-like mine with themed floors, ore rocks and deeper challenges."""
        if floor is not None:
            self.dungeon_floor = max(1, min(40, int(floor)))
        floor = self.dungeon_floor
        rnd = random.Random(814 + floor * 97)
        T = [[WALL for _ in range(MAP_W)] for _ in range(MAP_H)]
        # A branching chain of chambers; each floor gets a slightly different layout.
        rooms = [(34, 65, 15, 12), (49, 64, 17, 13), (66, 64, 15, 13),
                 (49, 49, 18, 14), (34, 35, 16, 14), (51, 34, 17, 14), (68, 39, 13, 12)]
        for i, (x0, y0, w, h) in enumerate(rooms):
            # Small floor-to-floor variations without breaking the connecting paths.
            ox = rnd.randrange(-1, 2) if i in (1, 3, 5) else 0
            oy = rnd.randrange(-1, 2) if i in (2, 4, 6) else 0
            for y in range(y0+oy, y0+h+oy):
                for x in range(x0+ox, x0+w+ox):
                    if 1 <= x < MAP_W-1 and 1 <= y < MAP_H-1:
                        T[y][x] = WOOD_FLOOR
        # Corridors keep every chamber reachable.
        for y in range(64, 68):
            for x in range(47, 52): T[y][x] = WOOD_FLOOR
        for y in range(59, 66):
            for x in range(63, 68): T[y][x] = WOOD_FLOOR
        for y in range(48, 66):
            for x in range(56, 60): T[y][x] = WOOD_FLOOR
        for y in range(45, 51):
            for x in range(47, 54): T[y][x] = WOOD_FLOOR
        for y in range(39, 50):
            for x in range(43, 47): T[y][x] = WOOD_FLOOR
        for y in range(39, 44):
            for x in range(50, 54): T[y][x] = WOOD_FLOOR
        for y in range(43, 47):
            for x in range(66, 70): T[y][x] = WOOD_FLOOR
        # Entry chamber and return door.
        for y in range(69, 73):
            for x in range(38, 43): T[y][x] = WOOD_FLOOR
        self.tiles = T
        self.buildings = [dict(kind="exitdoor", tx=39, ty=71, w=2, h=1),
                          dict(kind="mine_down", tx=73, ty=67, w=1, h=1)]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        self.objs = {}
        self.tables, self.lamps, self.fences, self.reserved = [], [], set(), set()
        self.soil, self.chickens, self.eggs, self.npcs, self.customers = {}, [], [], [], []
        # Mineable rocks double as ore nodes; deeper floors have more valuable drops.
        for x0, y0, w, h in rooms:
            for _ in range(7 + min(8, floor // 3)):
                x, y = rnd.randrange(x0+1, x0+w-1), rnd.randrange(y0+1, y0+h-1)
                if T[y][x] == WOOD_FLOOR and (x, y) not in self.bld_at:
                    ore = "copper" if floor < 6 else "iron" if floor < 16 else "gold" if floor < 26 else "iridium"
                    self.objs[(x,y)] = dict(t="rock", hp=2 + floor//12, v=rnd.randrange(3), ore=ore)
        self.dungeon_wave = floor
        self.dungeon_kills = 0
        self.dungeon_boss_done = False
        self.dungeon_attack_cd = 0.0
        self.dungeon_hit_flash = 0.0
        self.dungeon_enemies = []
        # More enemies every few floors; every fifth floor ends with a tougher guardian.
        enemy_count = min(3 + floor // 2, 12)
        kinds = ["crawler", "crawler", "hound"]
        if floor >= 4: kinds += ["hound", "brute"]
        for i in range(enemy_count):
            room = rooms[1 + (i % (len(rooms)-1))]
            x = rnd.randrange(room[0]+2, room[0]+room[2]-2)
            y = rnd.randrange(room[1]+2, room[1]+room[3]-2)
            kind = "brute" if floor % 5 == 0 and i == enemy_count-1 else rnd.choice(kinds)
            hp = (3 if kind == "crawler" else 4 if kind == "hound" else 8) + floor//4
            self.dungeon_enemies.append(dict(x=x*TILE+8,y=y*TILE+8,hp=hp,maxhp=hp,kind=kind,
                                             speed=(24 if kind == "crawler" else 19 if kind == "hound" else 13) + min(8, floor//6),
                                             attack=0.0,flash=0.0,alive=True))
        self.rebuild_solid()

    def descend_mine(self):
        if any(e["alive"] for e in self.dungeon_enemies):
            self.toast("Defeat every monster to unlock the ladder!")
            return
        if self.dungeon_floor >= 40:
            self.toast("You reached the deepest mine floor! The treasure is yours.")
            self.add_item("old_coin", 20, quiet=True)
            return
        self.dungeon_floor += 1
        self.dungeon_best_floor = max(self.dungeon_best_floor, self.dungeon_floor)
        self.build_dungeon(self.dungeon_floor)
        self.player.x, self.player.y = 40*TILE+8, 70*TILE+8
        self.player.dir = "up"
        self.focus = None
        self.toast("Mine floor %d — deeper, darker and tougher!" % self.dungeon_floor)

    def dungeon_attack(self):
        if self.dungeon_attack_cd > 0:
            return
        self.dungeon_attack_cd = 0.38
        p = self.player
        dx, dy = DIRS[p.dir]
        p.act = p.act_dur = 0.22
        p.act_tool = None
        hit = False
        for e in self.dungeon_enemies:
            if not e["alive"]: continue
            vx, vy = e["x"]-p.x, e["y"]-p.y
            along = vx*dx + vy*dy
            side = abs(vx*dy - vy*dx)
            if 0 < along < 31 and side < 19:
                e["hp"] -= 2
                e["flash"] = 0.16
                hit = True
                if e["hp"] <= 0:
                    e["alive"] = False
                    self.dungeon_kills += 1
                    self.add_item("old_coin", 1, quiet=True)
                    if random.random() < 0.55: self.add_item("scrap", 1, quiet=True)
                    self.sparkle(e["x"], e["y"], 5)
        if hit:
            self.toast("Hit! + dungeon loot")
        else:
            self.toast("Slash!")

    def update_dungeon(self, dt):
        self.dungeon_attack_cd = max(0.0, self.dungeon_attack_cd-dt)
        self.dungeon_hit_flash = max(0.0, self.dungeon_hit_flash-dt)
        p = self.player
        for e in self.dungeon_enemies:
            if not e["alive"]: continue
            e["flash"] = max(0.0, e["flash"]-dt)
            dx, dy = p.x-e["x"], p.y-e["y"]
            dist = max(0.001, math.hypot(dx,dy))
            if dist < 155:
                step = min(e["speed"]*dt, max(0,dist-13))
                nx, ny = e["x"]+dx/dist*step, e["y"]+dy/dist*step
                if not self.box_blocked(nx,ny,5,4): e["x"],e["y"] = nx,ny
            e["attack"] = max(0.0,e["attack"]-dt)
            if dist < 17 and e["attack"] <= 0:
                e["attack"] = 1.15
                self.energy = max(0,self.energy-5)
                self.dungeon_hit_flash = 0.22
                self.toast("A monster hit you! -5 energy")
        if not any(e["alive"] for e in self.dungeon_enemies) and not self.dungeon_boss_done:
            self.dungeon_boss_done = True
            self.add_item("old_coin", 3 + self.dungeon_floor, quiet=True)
            if self.dungeon_floor % 5 == 0:
                self.add_item("rare_fish", 1, quiet=True)
                self.toast("Guardian defeated! Elevator checkpoint unlocked.")
            else:
                self.toast("Floor %d cleared! The ladder is unlocked." % self.dungeon_floor)

    def build_station(self):
        """The Ruined Station: an old sea port on a rocky shore. Searching the ruins finds scrap."""
        T = [[WATER] * MAP_W for _ in range(MAP_H)]
        cx, cy, rx, ry = 48, 36, 26, 20
        for y in range(MAP_H):
            for x in range(MAP_W):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if d <= 1.0:
                    T[y][x] = GRASS
                elif d <= 1.2:
                    T[y][x] = SAND
        self.tiles = T
        self.buildings = [
            dict(kind="dock_back", tx=23, ty=37, w=2, h=1),
            dict(kind="ruin", tx=34, ty=28, w=3, h=2),
            dict(kind="ruin", tx=44, ty=40, w=3, h=2),
            dict(kind="ruin", tx=56, ty=29, w=3, h=2),
            dict(kind="ruin", tx=60, ty=40, w=3, h=2),
        ]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        rnd = random.Random(1912)
        self.objs = {}
        for y in range(MAP_H):
            for x in range(MAP_W):
                if T[y][x] != GRASS or (abs(x - 23) < 3 and abs(y - 37) < 3) or (x, y) in self.bld_at:
                    continue
                r = rnd.random()
                if r < 0.06:
                    self.objs[(x, y)] = dict(t="rock", hp=3, v=rnd.randrange(3))
                elif r < 0.09:
                    self.objs[(x, y)] = dict(t="tree", hp=4, v=rnd.randrange(2))
        self.tables = []
        self.lamps, self.fences, self.reserved = [], set(), set()
        self.soil, self.chickens, self.eggs = {}, [], []
        self.npcs = [NPC("Old Salt", 29 * TILE + 8, 38 * TILE + 8, SPR["oldsalt"], SALT_LINES,
                         wander=(27, 35, 33, 40))]
        self.customers = []
        self.station_looted = set()
        self.rebuild_solid()

    def search_ruin(self, b):
        """Digs through a ruin. Each ruin can be searched once per visit."""
        spot = (b["tx"], b["ty"])
        if spot in self.station_looted:
            self.toast("Already searched. Nothing else is left here.")
            return
        self.station_looted.add(spot)
        rnd = random.Random(spot[0] * 131 + spot[1] * 7 + self.day)
        found = []
        for _ in range(rnd.randrange(2, 5)):
            roll = rnd.random()
            item = "scrap" if roll < 0.5 else "stone" if roll < 0.75 else "old_coin" if roll < 0.9 else "wood"
            n = rnd.randrange(1, 4)
            self.add_item(item, n, quiet=True)
            found.append("%d %s" % (n, ITEMS[item]["name"]))
        self.toast("Searched the ruins: " + ", ".join(found), "scrap")
        self.qinc("ruin")

    def build_port_house_interior(self):
        """Inside the port house: one room, Crazy Dew, and the door back to the harbour."""
        T = [[WALL] * MAP_W for _ in range(MAP_H)]
        for y in range(RY0 + 1, RY1):
            for x in range(RX0 + 1, RX1):
                T[y][x] = WOOD_FLOOR
        self.tiles = T
        self.buildings = [dict(kind="exitdoor", tx=32, ty=RY1, w=1, h=1)]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        self.tables = []
        self.lamps, self.fences, self.reserved = [], set(), set()
        self.objs, self.soil, self.chickens, self.eggs = {}, {}, [], []
        self.customers = []
        self.npcs = [NPC("Crazy Dew", 26 * TILE + 8, (RY0 + 4) * TILE + 8, SPR["crazy_dew"], CRAZY_LINES)]
        self.rebuild_solid()

    def build_house_interior(self):
        """The inside of your house: a bed to sleep in and the computer (once built)."""
        T = [[WALL] * MAP_W for _ in range(MAP_H)]
        for y in range(RY0 + 1, RY1):
            for x in range(RX0 + 1, RX1):
                T[y][x] = WOOD_FLOOR
        self.tiles = T
        self.buildings = [
            dict(kind="bed", tx=22, ty=RY0 + 2, w=2, h=1),
            dict(kind="computer", tx=28, ty=RY0 + 2, w=2, h=1),
            dict(kind="exitdoor", tx=32, ty=RY1, w=1, h=1),
        ]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        self.tables = []
        self.lamps, self.fences, self.reserved = [], set(), set()
        self.objs, self.soil, self.chickens, self.npcs, self.eggs = {}, {}, [], [], []
        self.customers = []
        self.rebuild_solid()

    def build_cafe_interior(self):
        T = [[WALL] * MAP_W for _ in range(MAP_H)]
        for y in range(RY0 + 1, RY1):
            for x in range(RX0 + 1, RX1):
                T[y][x] = WOOD_FLOOR
        self.tiles = T
        self.buildings = [
            dict(kind="stove", tx=23, ty=RY0 + 2, w=3, h=1),
            dict(kind="register", tx=29, ty=RY0 + 2, w=3, h=1),
            dict(kind="exitdoor", tx=32, ty=RY1, w=1, h=1),
        ]
        self.bld_at = {}
        for b in self.buildings:
            for yy in range(b["ty"], b["ty"] + b["h"]):
                for xx in range(b["tx"], b["tx"] + b["w"]):
                    self.bld_at[(xx, yy)] = b
        self.tables = [dict(tx=x, ty=22, cust=None) for x in (25, 30, 35, 40)]
        self.lamps, self.fences, self.reserved = [], set(), set()
        self.objs, self.soil, self.chickens, self.npcs, self.eggs = {}, {}, [], [], []
        self.customers = []
        self.cust_timer = 4.0
        self.rebuild_solid()

    def save_game(self):
        try:
            data = dict(day=self.day, time=self.time, money=self.money, energy=self.energy, water=self.water,
                        rain=self.rain, inv=self.inv, bin=self.bin,
                        soil=[[x, y, s["wet"], s["crop"], s["age"]] for (x, y), s in self._save_src()["soil"].items()],
                        objs=[[x, y, o["t"], o.get("hp", 1), o.get("v", 0)] for (x, y), o in self._save_src()["objs"].items()],
                        eggs=self.eggs, px=self._save_pos()[0], py=self._save_pos()[1],
                        owned=sorted(self.owned), unlocked=self.unlocked, menu_on=self.menu_on, rep=self.rep,
                        xp=self.xp, pending=self.pending, hi=self.hi, cafe_open=self.cafe_open,
                        fish_log=self.fish_log,
                        houses=[[b["tx"], b["ty"]] for b in self.buildings if b.get("player_built")],
                        qdone=sorted(self.qdone), qactive=self.qactive, qstats=self.qstats,
                        wishes=sorted(self.wishes_done))
            with open(SAVE_FILE, "w") as f:
                json.dump(data, f)
            return True
        except Exception:
            return False

    def load_game(self):
        try:
            with open(SAVE_FILE) as f:
                d = json.load(f)
        except Exception:
            return False
        self.new_game()
        self.day, self.time, self.money = d["day"], d["time"], d["money"]
        self.energy, self.water, self.rain = d["energy"], d["water"], d["rain"]
        self.inv, self.bin = d["inv"], d["bin"]
        self.soil = {(x, y): dict(wet=w, crop=c, age=a) for x, y, w, c, a in d["soil"]}
        self.objs = {(x, y): dict(t=t, hp=hp, v=v) for x, y, t, hp, v in d["objs"]}
        # Also clean older save files, which may still contain trees on the east bank.
        # Older saves may still hold trees or rocks on the cleared east bank, or objects on roads.
        self.objs = {pos: obj for pos, obj in self.objs.items()
                     if not (pos[0] >= 60 and obj.get("t") == "tree")
                     and not east_clear(*pos) and self.tiles[pos[1]][pos[0]] == GRASS}
        self.eggs = d.get("eggs", [])
        self.owned = set(d.get("owned", []))
        self.unlocked = d.get("unlocked", list(UNLOCKED_START))
        self.menu_on = d.get("menu_on", {})
        self.rep = d.get("rep", 20.0)
        self.xp = d.get("xp", {"farm": 0, "cook": 0, "fish": 0})
        self.pending = d.get("pending", {})
        self.hi = dict(HI_DEFAULT)
        self.hi.update(d.get("hi", {}))
        self.cafe_open = d.get("cafe_open", True)
        self.fish_log = d.get("fish_log", {})
        self.qdone = set(d.get("qdone", []))
        self.qactive = {k: int(v) for k, v in d.get("qactive", {}).items()}
        self.qstats = dict(d.get("qstats", {}))
        self.wishes_done = set(d.get("wishes", []))
        houses = d.get("houses")
        if houses is None and "villager_house" in self.owned:
            # Older save: the house used to be placed automatically, so hand back its kit instead.
            self.add_item("villager_house_kit", 1, quiet=True)
        self.owned.discard("villager_house")
        for tx, ty in houses or []:
            if self.house_problem(tx, ty, check_player=False) is None:
                self.add_building(tx, ty)
        self.recalc()
        self.player.x, self.player.y = d["px"], d["py"]
        self.ensure_season()
        self.rebuild_solid()
        self.unstick_player()
        return True

    def unstick_player(self):
        """Moves the player to the nearest free tile if they were saved on a tile that is now blocked."""
        p = self.player
        if not self.box_blocked(p.x, p.y):
            return
        tx, ty = int(p.x // TILE), int(p.y // TILE)
        for r in range(1, 40):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = (tx + dx) * TILE + 8, (ty + dy) * TILE + 8
                    if 0 < tx + dx < MAP_W and 0 < ty + dy < MAP_H and not self.box_blocked(x, y):
                        p.x, p.y = x, y
                        return

    # ------------------------------------------------------- inventory helpers
    def hotbar(self):
        keys = list(TOOLS)
        keys += [k for k in ITEMS if ITEMS[k]["kind"] == "seed" and self.inv.get(k, 0) > 0]
        keys += [k for k, v in ITEMS.items() if v["kind"] == "food" and self.inv.get(k, 0) > 0]
        if self.inv.get("villager_house_kit", 0) > 0:
            keys.append("villager_house_kit")
        return keys[:12]

    def add_item(self, key, n=1, quiet=False):
        self.inv[key] = self.inv.get(key, 0) + n
        if not quiet:
            self.toast("+%d %s" % (n, ITEMS[key]["name"]), key)

    def take_item(self, key, n=1):
        self.inv[key] = self.inv.get(key, 0) - n
        if self.inv[key] <= 0:
            del self.inv[key]

    def toast(self, text, icon=None):
        self.toasts.append(dict(text=text, icon=icon, t=3.2))
        self.toasts = self.toasts[-5:]

    # ------------------------------------------------------- particles
    def burst(self, x, y, color, n=8, speed=40, grav=120, life=0.6, size=2, up=20):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(speed * 0.3, speed)
            self.particles.append(dict(x=x, y=y, vx=math.cos(a) * sp, vy=math.sin(a) * sp - up,
                                       life=life * random.uniform(0.7, 1.2), max=life, c=color,
                                       size=size, g=grav, kind="dot"))

    def sparkle(self, x, y, n=6):
        for _ in range(n):
            self.particles.append(dict(x=x + random.uniform(-6, 6), y=y + random.uniform(-6, 6),
                                       vx=random.uniform(-8, 8), vy=random.uniform(-26, -8), life=0.8, max=0.8,
                                       c=(255, 240, 150), size=2, g=0, kind="star"))

    def heart(self, x, y):
        self.particles.append(dict(x=x, y=y, vx=0, vy=-20, life=1.0, max=1.0, c=(240, 90, 120),
                                   size=3, g=0, kind="heart"))

    # ------------------------------------------------------- world logic
    def facing_tile(self):
        p = self.player
        dx, dy = DIRS[p.dir]
        return int(p.x // TILE) + dx, int((p.y - 2) // TILE) + dy

    def is_ripe(self, s):
        return s["crop"] and s["age"] >= CROPS[s["crop"]]["days"]

    def crop_stage(self, s):
        days = CROPS[s["crop"]]["days"]
        if s["age"] >= days:
            return 4
        return min(3, int(s["age"] / days * 4))

    def px_solid(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if tx < 0 or ty < 0 or tx >= MAP_W or ty >= MAP_H:
            return True
        return self.solid[ty][tx]

    def box_blocked(self, x, y, hw=5, hh=4):
        for px in (x - hw, x + hw):
            for py in (y - hh, y):
                if self.px_solid(px, py):
                    return True
        return False

    def move_entity(self, e, dx, dy, hw=5, hh=4):
        nx = e.x + dx
        if not self.box_blocked(nx, e.y, hw, hh):
            e.x = nx
        ny = e.y + dy
        if not self.box_blocked(e.x, ny, hw, hh):
            e.y = ny
        e.x = clamp(e.x, 8, MAP_W * TILE - 8)
        e.y = clamp(e.y, 12, MAP_H * TILE - 2)

    def swing(self, tool):
        p = self.player
        p.act = p.act_dur = 0.32
        p.act_tool = tool

    def use_item(self):
        p = self.player
        if p.act > 0:
            return
        keys = self.hotbar()
        if not keys:
            return
        key = keys[clamp(self.sel, 0, len(keys) - 1)]
        if key == "villager_house_kit":
            self.start_placing()
            return
        tx, ty = self.facing_tile()
        s = self.soil.get((tx, ty))
        if s and self.is_ripe(s):
            self.harvest(tx, ty)
            return
        kind = ITEMS[key]["kind"]
        if kind == "tool":
            self.use_tool(key, tx, ty)
        elif kind == "seed":
            if s and not s["crop"]:
                s["crop"] = ITEMS[key]["crop"]
                s["age"] = 0
                self.take_item(key)
                self.qinc("plant")
                self.burst(tx * TILE + 8, ty * TILE + 8, (140, 100, 64), 6, 24, 80, 0.4, 1)
                self.swing(None)
            else:
                self.toast("Plant seeds on tilled soil (use the hoe on grass).")
        elif kind == "food":
            if self.energy >= self.max_energy - 1:
                self.toast("You're not tired right now.")
            else:
                self.eat(key)

    def eat(self, key):
        self.energy = min(self.max_energy, self.energy + ITEMS[key]["energy"])
        self.take_item(key)
        self.toast("Yum! +%d energy" % ITEMS[key]["energy"], key)
        self.heart(self.player.x, self.player.y - 22)
        self.sparkle(self.player.x, self.player.y - 14)

    def use_tool(self, key, tx, ty):
        if not (0 <= tx < MAP_W and 0 <= ty < MAP_H):
            return
        cx, cy = tx * TILE + 8, ty * TILE + 8
        o = self.objs.get((tx, ty))
        s = self.soil.get((tx, ty))
        tt = self.tiles[ty][tx]
        cost = self.tool_cost(key)
        self.swing(key)
        if key == "rod":
            if tt != WATER:
                self.toast("Cast your rod at the river or the sea.")
            elif self.energy < cost:
                self.toast("You're too tired! Eat something or go to sleep.")
            else:
                self.energy -= cost
                self.start_fishing(tx, ty)
            return
        if key == "can" and tt == WATER:
            self.water = self.water_cap()
            self.burst(cx, cy, (150, 200, 240), 10, 40, 100, 0.5)
            self.toast("Watering can refilled!")
            return
        possible = False
        if key == "hoe":
            possible = (tt == GRASS and not o and not s and (tx, ty) not in self.bld_at
                        and (tx, ty) not in self.fences and (tx, ty) not in self.lamps)
        elif key == "can":
            possible = s is not None and not s["wet"]
        elif key == "axe":
            possible = o is not None and o["t"] in ("tree", "stump")
        elif key == "pick":
            possible = (o is not None and o["t"] == "rock") or (s is not None and not s["crop"])
        if not possible:
            return
        if key == "can" and self.water <= 0:
            self.toast("The can is empty. Refill it at the river or the sea!")
            return
        if self.energy < cost:
            self.toast("You're too tired! Eat something or go to sleep.")
            return
        self.energy -= cost
        if key == "hoe":
            self.soil[(tx, ty)] = dict(wet=self.rain, crop=None, age=0)
            self.burst(cx, cy, (140, 100, 64), 9, 36, 110, 0.5)
        elif key == "can":
            s["wet"] = True
            self.water -= 1
            self.qinc("water")
            self.burst(cx, cy, (140, 190, 240), 10, 30, 90, 0.5)
        elif key == "axe":
            o["shake"] = 0.3
            o["hp"] -= 1
            self.burst(cx, cy, (160, 116, 70), 6, 40, 120, 0.5)
            if o["hp"] <= 0:
                if o["t"] == "tree":
                    o["t"], o["hp"] = "stump", 2
                    self.add_item("wood", 4)
                    self.burst(cx, cy - 20, PAL[self.season]["leaf_l"], 16, 50, 60, 1.0, 2)
                else:
                    del self.objs[(tx, ty)]
                    self.add_item("wood", 2)
                    self.rebuild_solid()
        elif key == "pick":
            if o:
                o["shake"] = 0.3
                o["hp"] -= 1
                self.burst(cx, cy, (190, 194, 202), 7, 44, 120, 0.5)
                if o["hp"] <= 0:
                    del self.objs[(tx, ty)]
                    self.add_item("stone", 2)
                    if self.location == "dungeon" and o.get("ore"):
                        self.add_item("scrap", 1 + (self.dungeon_floor // 10), quiet=True)
                        if random.random() < 0.35:
                            self.add_item("old_coin", 1, quiet=True)
                    self.rebuild_solid()
                    self.sparkle(cx, cy)
            else:
                del self.soil[(tx, ty)]
                self.burst(cx, cy, (140, 100, 64), 7, 30, 100, 0.4)

    def harvest(self, tx, ty):
        s = self.soil[(tx, ty)]
        crop = s["crop"]
        s["crop"], s["age"] = None, 0
        n = 2 if random.random() < 0.04 * (self.level("farm") - 1) else 1
        self.add_item(crop, n)
        self.qinc("harvest", n)
        self.gain_xp("farm", 3 + CROPS[crop]["days"])
        cx, cy = tx * TILE + 8, ty * TILE + 8
        self.burst(cx, cy, CROPS[crop]["fruit"], 8, 50, 120, 0.6)
        self.sparkle(cx, cy)
        self.swing(None)

    def compute_focus(self):
        tx, ty = self.facing_tile()
        self.focus = None
        cx, cy = tx * TILE + 8, ty * TILE + 8
        for n in self.npcs:
            if math.hypot(n.x - cx, n.y - 8 - cy) < 20:
                self.focus = ("npc", n)
                return
        for c in self.chickens:
            if math.hypot(c.x - cx, c.y - cy) < 14:
                self.focus = ("chicken", c)
                return
        for tb in self.active_tables():
            if (tx, ty) == (tb["tx"], tb["ty"]):
                self.focus = ("table", tb)
                return
        b = self.bld_at.get((tx, ty))
        if b:
            self.focus = ("bld", b)
            return
        s = self.soil.get((tx, ty))
        if s and self.is_ripe(s):
            self.focus = ("crop", (tx, ty))
            return
        o = self.objs.get((tx, ty))
        if o and o["t"] == "flower":
            self.focus = ("flower", (tx, ty))

    def prompt_text(self):
        if not self.focus:
            return None
        kind, data = self.focus
        if kind == "npc":
            return "E  Talk to %s" % data.name
        if kind == "chicken":
            return "E  Pet"
        if kind == "crop":
            return "E  Harvest"
        if kind == "flower":
            return "E  Pick"
        if kind == "table":
            c = data["cust"]
            return "E  Serve" if (c and c.state == "wait") else "E  Table"
        return {"dock": "E  Sail to the island", "dock_back": "E  Sail home",
                "village_port": "E  Board the ferry to the island", "port_house": "E  Enter the port house",
                "port": "E  Sail to the Ruined Station", "ruin": "E  Search the ruins",
                "dungeon": "E  Enter the mines", "mine_down": "E  Descend to the next floor",
                "house": "E  Enter house", "bed": "E  Sleep", "computer": "E  Use computer",
                "bench": "E  Workbench", "kitchen": "E  Cook", "bin": "E  Ship goods",
                "stall": "E  Shop", "coop": "E  Look", "cafe": "E  Enter cafe", "register": "E  Register", "stove": "E  Cook", "exitdoor": "E  Leave",
                "pc": "E  Use computer", "arcade": "E  Play arcade"}.get(data["kind"])

    def interact(self):
        if self.player.act > 0 or not self.focus:
            return
        kind, data = self.focus
        if kind == "crop":
            self.harvest(*data)
        elif kind == "flower":
            del self.objs[data]
            self.add_item("flower")
            self.sparkle(data[0] * TILE + 8, data[1] * TILE + 8, 4)
        elif kind == "npc" and data.name == "Fish Master" and not self.npc_wants_talk(data.name):
            self.menu = dict(type="fishmaster", idx=0, view="list")
            self.state = "menu"
        elif kind == "npc":
            self.npc_talk(data)
        elif kind == "chicken":
            self.qinc("pet")
            self.heart(data.x, data.y - 10)
            self.toast("Bwaaaak! Your hen seems happy.")
        elif kind == "table":
            self.serve_table(data)
        elif kind == "bld":
            k = data["kind"]
            if k == "house":
                self.start_warp("house")
            elif k == "bed":
                self.menu = dict(type="sleep", idx=1)
                self.state = "menu"
            elif k == "computer":
                if "computer" in self.owned:
                    self.menu = dict(type="pc", tab=0, idx=0, scroll=0)
                    self.state = "menu"
                else:
                    self.toast("Your computer is not built yet. Craft it at the workbench.")
            elif k == "bench":
                self.menu = dict(type="bench", idx=0, scroll=0)
                self.state = "menu"
            elif k == "dock":
                self.start_warp("island")
            elif k == "dock_back":
                self.start_warp("farm")
            elif k == "port":
                self.start_warp("station")
            elif k == "village_port":
                self.last_port = "village"
                self.start_warp("island")
            elif k == "port_house":
                self.start_warp("portHouse")
            elif k == "ruin":
                self.search_ruin(data)
            elif k == "dungeon":
                self.dungeon_floor = 1
                self.start_warp("dungeon")
            elif k == "mine_down":
                self.descend_mine()
            elif k == "kitchen":
                self.menu = dict(type="cook", idx=0, scroll=0)
                self.state = "menu"
            elif k == "bin":
                self.menu = dict(type="bin", idx=0, scroll=0)
                self.state = "menu"
            elif k == "stall":
                self.menu = dict(type="shop", idx=0, scroll=0, greet=random.choice(MABEL_LINES))
                self.state = "menu"
            elif k == "coop":
                self.toast("Your hens lay fresh eggs every morning.")
            elif k == "cafe":
                self.start_warp("cafe")
            elif k == "register":
                self.menu = dict(type="cafe", idx=0, scroll=0)
                self.state = "menu"
            elif k == "stove":
                self.menu = dict(type="cook", idx=0, scroll=0)
                self.state = "menu"
            elif k == "exitdoor":
                self.start_warp("island" if self.location == "dungeon" else "farm")
            elif k == "pc":
                self.menu = dict(type="pc", tab=0, idx=0, scroll=0)
                self.state = "menu"
            elif k == "arcade":
                self.menu = dict(type="arcade", idx=0, scroll=0)
                self.state = "menu"

    def say(self, name, text):
        self.dialog = dict(name=name, text=text, shown=0.0, portrait=PORTRAITS.get(name))
        self.state = "dialog"

    # ------------------------------------------------------- day cycle
    def start_end_day(self, passed):
        if self.location != "farm":
            self.switch_location("farm")
        self.passed_out = passed
        self.state = "fade_out"
        self.fade = 0.0

    def process_new_day(self):
        lines, earned = [], 0
        for k, n in list(self.bin.items()):
            v = int(ITEMS[k]["sell"] * n * (self.cook_bonus() if ITEMS[k]["kind"] == "food" else 1.0))
            if k in FISH:
                v = int(v * (1 + self.fish_mastery()[2]))
            lines.append((k, n, v))
            earned += v
        self.money += earned
        self.bin = {}
        for s in self.soil.values():
            if s["crop"] and s["wet"] and s["age"] < CROPS[s["crop"]]["days"]:
                s["age"] += 1
            s["wet"] = False
        deliveries = list(self.pending.items())
        for k, n in deliveries:
            self.inv[k] = self.inv.get(k, 0) + n
        self.pending = {}
        self.summary = dict(day=self.day, lines=lines, earned=earned, passed=self.passed_out,
                            cafe=dict(self.cafe_stats), deliveries=deliveries)
        self.cafe_stats = dict(served=0, earned=0, tips=0, angry=0)
        self.customers = []
        for tb in self.tables:
            tb["cust"] = None
        self.cust_timer = 10.0
        self.day += 1
        old = self.season_built
        self.ensure_season()
        self.new_season = old != self.season_built
        self.rain = self.day > 1 and random.random() < 0.25
        if self.rain:
            for s in self.soil.values():
                s["wet"] = True
        for _ in self.chickens:
            if len(self.eggs) < 9:
                self.eggs.append([random.randint(44 * TILE + 8, 52 * TILE - 8), random.randint(28 * TILE, 32 * TILE)])
        flowers = sum(1 for o in self.objs.values() if o["t"] == "flower")
        tries = 0
        while flowers < 200 and tries < 40:
            tries += 1
            x, y = random.randrange(5, FARM_W - 5), random.randrange(4, MAP_H - 4)
            if (x, y) in self.reserved or (x, y) in self.objs or (x, y) in self.soil:
                continue
            self.objs[(x, y)] = dict(t="flower", v=random.randrange(3))
            flowers += 1
            if flowers > 120 and random.random() < 0.3:
                break
        self.energy = self.max_energy * (0.6 if self.passed_out else 1.0)
        self.water = self.water_cap()
        self.time = WAKE_HOUR
        self.player.x, self.player.y = 30 * TILE, 10 * TILE + 10
        self.player.dir = "down"
        self.save_game()

    # ------------------------------------------------------- update
    def ambient(self):
        if self.location in ("cafe", "house"):
            return (250, 232, 200)
        keys = [(5.0, (70, 76, 128)), (6.5, (220, 170, 160)), (8.0, (255, 250, 240)),
                (16.5, (255, 248, 236)), (18.5, (255, 190, 140)), (20.0, (120, 110, 170)),
                (21.5, (72, 80, 134)), (26.0, (52, 58, 108))]
        t = clamp(self.time, 5.0, 26.0)
        col = keys[-1][1]
        for (t0, c0), (t1, c1) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                col = lerp_col(c0, c1, (t - t0) / (t1 - t0))
                break
        if self.rain:
            col = (int(col[0] * 0.78), int(col[1] * 0.82), int(col[2] * 0.92))
        return col

    def night_level(self):
        a = self.ambient()
        return clamp((250 - sum(a) / 3) / 150, 0, 1)

    def update_play(self, dt):
        p = self.player
        prev = self.time
        self.time += dt * MIN_PER_SEC / 60.0
        if prev < 24.0 <= self.time:
            self.toast("It's midnight. You should get some sleep...")
        if self.time >= PASSOUT_HOUR:
            self.start_end_day(True)
            return
        keys = pygame.key.get_pressed()
        mx = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        my = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP])
        touch_used, analog = False, 1.0
        tv = self.touch.vec
        if mx == 0 and my == 0 and (tv[0] or tv[1]):
            mx, my = tv
            touch_used = True
            analog = min(1.0, math.hypot(mx, my))
        p.moving = False
        if self.location == "dungeon":
            self.update_dungeon(dt)
        if p.act > 0:
            p.act -= dt
        elif mx or my:
            if touch_used:
                if abs(mx) > abs(my):
                    p.dir = "right" if mx > 0 else "left"
                else:
                    p.dir = "down" if my > 0 else "up"
            elif mx and not my:
                p.dir = "right" if mx > 0 else "left"
            elif my and not mx:
                p.dir = "down" if my > 0 else "up"
            elif p.dir in ("left", "right") and not mx:
                p.dir = "down" if my > 0 else "up"
            elif p.dir in ("up", "down") and not my:
                p.dir = "right" if mx > 0 else "left"
            run = 1.55 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) else 1.0
            sp = 62 * run * dt * analog
            ln = math.hypot(mx, my)
            self.move_entity(p, mx / ln * sp, my / ln * sp)
            p.moving = True
            p.anim += dt * 9 * run
        else:
            p.anim = 0
        self.compute_focus()
        for o in self.objs.values():
            if o.get("shake", 0) > 0:
                o["shake"] -= dt
        self.update_actors(dt)
        self.update_cafe(dt)
        self.update_effects(dt)
        for e in self.eggs[:]:
            if math.hypot(e[0] - p.x, e[1] - p.y) < 9:
                self.eggs.remove(e)
                self.add_item("egg")
                self.sparkle(e[0], e[1] - 4, 4)
        if self.sel_timer > 0:
            self.sel_timer -= dt

    def update_actors(self, dt):
        for c in self.chickens:
            c.anim += dt * 8
            c.timer -= dt
            if c.state == "idle":
                if c.timer <= 0:
                    if random.random() < 0.5:
                        c.state, c.timer = "peck", random.uniform(0.6, 1.4)
                    else:
                        c.state, c.timer = "walk", random.uniform(0.8, 2.0)
                        c.tx = random.uniform(44 * TILE + 8, 52 * TILE - 8)
                        c.ty = random.uniform(28 * TILE, 32 * TILE + 8)
            elif c.state == "peck":
                if c.timer <= 0:
                    c.state, c.timer = "idle", random.uniform(0.5, 2.5)
            else:
                dx, dy = c.tx - c.x, c.ty - c.y
                d = math.hypot(dx, dy)
                if d < 2 or c.timer <= 0:
                    c.state, c.timer = "idle", random.uniform(0.5, 2.5)
                else:
                    c.flip = dx < 0
                    nx, ny = c.x + dx / d * 20 * dt, c.y + dy / d * 20 * dt
                    if not self.box_blocked(nx, ny, 4, 3):
                        c.x, c.y = nx, ny
                    else:
                        c.state, c.timer = "idle", 0.5
        for n in self.npcs:
            if not n.wander:
                continue
            n.timer -= dt
            if n.moving:
                dx, dy = n.tx - n.x, n.ty - n.y
                d = math.hypot(dx, dy)
                if d < 2 or n.timer <= 0:
                    n.moving = False
                    n.timer = random.uniform(2, 5)
                else:
                    n.dir = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
                    ox, oy = n.x, n.y
                    self.move_entity(n, dx / d * 22 * dt, dy / d * 22 * dt)
                    n.anim += dt * 8
                    if abs(n.x - ox) + abs(n.y - oy) < 0.01:
                        n.moving = False
                        n.timer = 1.0
            elif n.timer <= 0:
                x0, y0, x1, y1 = n.wander
                n.tx = random.uniform(x0 * TILE, x1 * TILE)
                n.ty = random.uniform(y0 * TILE, y1 * TILE)
                n.moving = True
                n.timer = 6.0
                n.anim = 0

    def update_effects(self, dt):
        for pt in self.particles:
            pt["life"] -= dt
            pt["vy"] += pt["g"] * dt
            pt["x"] += pt["vx"] * dt
            pt["y"] += pt["vy"] * dt
        self.particles = [pt for pt in self.particles if pt["life"] > 0]
        self.smoke_t -= dt
        if self.smoke_t <= 0:
            self.smoke_t = 0.35
            for (wx, wy) in ((27 * TILE + 63, 5 * TILE + 2), (36 * TILE + 46, 8 * TILE + 2)):
                self.particles.append(dict(x=wx, y=wy, vx=random.uniform(2, 8), vy=-9, life=3.0, max=3.0,
                                           c=(226, 226, 232), size=3, g=-1.5, kind="smoke"))
        for tdict in self.toasts:
            tdict["t"] -= dt
        self.toasts = [x for x in self.toasts if x["t"] > 0]
        cam = self.camera()
        for c in self.crit:
            c["a"] += random.uniform(-3, 3) * dt
            c["x"] += math.cos(c["a"]) * 14 * dt
            c["y"] += math.sin(c["a"]) * 10 * dt - 2 * dt
            if not (-30 < c["x"] < VIEW_W + 30 and -30 < c["y"] < VIEW_H + 30):
                c["x"] = random.uniform(0, VIEW_W)
                c["y"] = random.uniform(0, VIEW_H)
        if self.rain:
            for d in self.rain_drops:
                d[1] += 260 * dt
                d[0] -= 50 * dt
                if d[1] > VIEW_H or d[0] < 0:
                    d[0] = random.uniform(0, VIEW_W + 60)
                    d[1] = random.uniform(-20, 0)

    def camera(self):
        p = self.player
        cx = clamp(int(p.x - VIEW_W / 2), 0, MAP_W * TILE - VIEW_W)
        cy = clamp(int(p.y - VIEW_H / 2), 0, MAP_H * TILE - VIEW_H)
        return cx, cy

    # ------------------------------------------------------- drawing: world
    def draw_world(self, surf_, cam):
        cx, cy = cam
        t = self.t
        tx0, ty0 = max(0, cx // TILE), max(0, cy // TILE)
        tx1, ty1 = min(MAP_W - 1, (cx + VIEW_W) // TILE), min(MAP_H - 1, (cy + VIEW_H) // TILE)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                tt = self.tiles[ty][tx]
                dx, dy = tx * TILE - cx, ty * TILE - cy
                h = (tx * 73856093 ^ ty * 19349663)
                if tt == WATER:
                    deep = self.location == "farm" and tx >= SEA_SHORE + 6
                    surf_.blit(SPR["sea" if deep else "water"][int(t * 2.2 + tx * 0.35 + ty * 0.2) % 4], (dx, dy))
                    for nx, ny, r in ((0, -1, (0, 0, 16, 2)), (0, 1, (0, 14, 16, 2)),
                                      (-1, 0, (0, 0, 2, 16)), (1, 0, (14, 0, 2, 16))):
                        xx, yy = tx + nx, ty + ny
                        if 0 <= xx < MAP_W and 0 <= yy < MAP_H and self.tiles[yy][xx] != WATER:
                            surf_.fill((200, 230, 246), (dx + r[0], dy + r[1], r[2], r[3]))
                elif tt == BRIDGE:
                    row = 0 if ty == BRIDGE_ROWS[0] else 2 if ty == BRIDGE_ROWS[1] else 1
                    surf_.blit(SPR["bridge"][row], (dx, dy))
                elif tt == WOOD_FLOOR:
                    surf_.blit(SPR["wood_floor"], (dx, dy))
                elif tt == WALL:
                    surf_.blit(SPR["wall"], (dx, dy))
                elif tt == PATH:
                    surf_.blit(SPR["path"][h % 4], (dx, dy))
                elif tt == SAND:
                    surf_.blit(SPR["sand"][h % 4], (dx, dy))
                else:
                    surf_.blit(SPR["grass"][h % 8], (dx, dy))
                s = self.soil.get((tx, ty))
                if s:
                    surf_.blit(SPR["soil_wet" if s["wet"] else "soil_dry"], (dx, dy))
        for e in self.eggs:
            surf_.blit(SPR["egg"], (e[0] - cx - 4, e[1] - cy - 6))
        ents = []
        mx0, mx1, my0, my1 = tx0 - 3, tx1 + 3, ty0 - 1, ty1 + 4
        for (x, y), o in self.objs.items():
            if mx0 <= x <= mx1 and my0 <= y <= my1:
                ents.append(((y + 1) * TILE, "obj", (x, y, o)))
        for (x, y), s in self.soil.items():
            if s["crop"] and tx0 - 1 <= x <= tx1 + 1 and ty0 - 1 <= y <= ty1 + 1:
                ents.append(((y + 1) * TILE - 1, "crop", (x, y, s)))
        for b in self.buildings:
            if b["tx"] - 2 <= tx1 and b["tx"] + b["w"] + 2 >= tx0 and b["ty"] - 2 <= ty1 and b["ty"] + b["h"] + 2 >= ty0:
                if b["kind"] == "stall":
                    ents.append((b["ty"] * TILE + 10, "bld", b))
                    ents.append(((b["ty"] + b["h"]) * TILE, "stall_front", b))
                else:
                    ents.append(((b["ty"] + b["h"]) * TILE, "bld", b))
        for (x, y) in self.lamps:
            ents.append(((y + 1) * TILE, "lamp", (x, y)))
        for (x, y) in self.fences:
            if tx0 - 1 <= x <= tx1 + 1 and ty0 - 1 <= y <= ty1 + 1:
                ents.append(((y + 1) * TILE - 2, "fence", (x, y)))
        for c in self.chickens:
            ents.append((c.y + 4, "chicken", c))
        for n in self.npcs:
            ents.append((n.y, "npc", n))
        for rp in self.remote:
            if rp.get("loc") == self.location and abs(rp["x"] - cx) < VIEW_W + 40 and abs(rp["y"] - cy) < VIEW_H + 40:
                ents.append((rp["y"], "remote", rp))
        for tb in self.active_tables():
            ents.append(((tb["ty"] + 1) * TILE, "table", tb))
        for cu in self.customers:
            ents.append((cu.y + (4 if cu.state in ("wait", "eat") else 0), "cust", cu))
        ents.append((self.player.y, "player", self.player))
        ents.sort(key=lambda e: e[0])
        for _, kind, data in ents:
            self.draw_entity(surf_, kind, data, cx, cy)
        self.draw_bubbles(surf_, cx, cy)

    def draw_entity(self, surf_, kind, d, cx, cy):
        t = self.t
        if kind == "obj":
            x, y, o = d
            dx, dy = x * TILE - cx, y * TILE - cy
            shake = math.sin(t * 60) * 1.5 if o.get("shake", 0) > 0 else 0
            if o["t"] == "tree":
                sway = math.sin(t * 1.3 + x * 0.7) * 1.5
                surf_.blit(SPR["trunk"], (dx + shake, dy - 8))
                surf_.blit(SPR["canopy"][o.get("v", 0) % 2], (dx - 16 + sway + shake, dy - 38))
            elif o["t"] == "stump":
                surf_.blit(SPR["stump"], (dx + shake, dy))
            elif o["t"] == "rock":
                surf_.blit(SPR["rocks"][o.get("v", 0) % 3], (dx + shake, dy))
            elif o["t"] == "flower":
                sw = int(round(math.sin(t * 2 + x) * 0.8))
                surf_.blit(SPR["flowers"][o.get("v", 0) % 3], (dx + sw, dy))
        elif kind == "crop":
            x, y, s = d
            st = self.crop_stage(s)
            sw = int(round(math.sin(t * 2 + x * 0.9 + y) * 0.7)) if st > 0 else 0
            bob = -1 if (st == 4 and int(t * 2 + x + y) % 3 == 0) else 0
            surf_.blit(SPR["crops"][(s["crop"], st)], (x * TILE - cx + sw, y * TILE - cy + bob))
            if st == 4 and int(t * 1.5 + x * 3 + y) % 7 == 0:
                surf_.fill((255, 255, 255), (x * TILE - cx + 10, y * TILE - cy + 2, 2, 2))
        elif kind == "bld":
            b = d
            if b["kind"] in ("house", "village_house", "village_house2", "village_house3", "player_villager_house",
                             "port_house"):
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy
                sprite_kind = {"player_villager_house": "player_house", "port_house": "village_house2"}.get(
                    b["kind"], b["kind"])
                surf_.blit(SPR[sprite_kind], (bx, by))
                wins = SPR["house_windows"] if b["kind"] == "house" else SPR["village_windows"]
                self.window_glow(surf_, bx, by, wins)
            elif b["kind"] == "kitchen":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy
                surf_.blit(SPR["kitchen"], (bx, by))
                w = SPR["kitchen_window"]
                gl = pygame.Surface((w[2], w[3]))
                f = 0.7 + 0.3 * math.sin(t * 9) * math.sin(t * 4.3)
                gl.fill((255, 150, 60))
                gl.set_alpha(int(150 * f))
                surf_.blit(gl, (bx + w[0], by + w[1]))
            elif b["kind"] == "bin":
                surf_.blit(SPR["bin"], (b["tx"] * TILE - cx, b["ty"] * TILE - cy - 8))
            elif b["kind"] == "stall":
                surf_.blit(SPR["stall_back"], (b["tx"] * TILE - cx, b["ty"] * TILE - cy))
            elif b["kind"] == "coop":
                surf_.blit(SPR["coop"], (b["tx"] * TILE - cx, b["ty"] * TILE - cy))
            elif b["kind"] == "cafe":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy
                surf_.blit(SPR["cafe"], (bx, by))
                self.window_glow(surf_, bx, by, [(12, 36, 24, 18), (92, 36, 24, 18)])
            elif b["kind"] == "dungeon":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy - 5
                pygame.draw.rect(surf_, (58, 48, 45), (bx-2, by+3, 36, 34))
                pygame.draw.rect(surf_, (110, 91, 77), (bx+2, by+7, 28, 27))
                pygame.draw.rect(surf_, (24, 22, 29), (bx+7, by+12, 18, 22))
                pygame.draw.arc(surf_, (180, 148, 105), (bx+7, by+7, 18, 17), 0, math.pi, 3)
                pygame.draw.rect(surf_, (190, 145, 78), (bx+2, by+30, 28, 3))
                self.text("DUNGEON", (bx+16, by-5), self.f_s, (245,220,170), center=True, shadow=(20,15,12))
            elif b["kind"] == "mine_down":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy
                unlocked = not any(e["alive"] for e in self.dungeon_enemies)
                pygame.draw.rect(surf_, (38, 30, 29), (bx-2, by-2, 22, 22))
                pygame.draw.rect(surf_, (150, 117, 78) if unlocked else (83, 75, 69), (bx+1, by+1, 16, 16), 2)
                pygame.draw.line(surf_, (185, 150, 100) if unlocked else (100, 95, 90), (bx+4,by+4), (bx+4,by+15), 2)
                pygame.draw.line(surf_, (185, 150, 100) if unlocked else (100, 95, 90), (bx+14,by+4), (bx+14,by+15), 2)
                for yy in (by+7, by+11): pygame.draw.line(surf_, (185,150,100), (bx+4,yy), (bx+14,yy), 2)
            elif b["kind"] in ("stove", "register", "exitdoor", "bed", "computer", "bench", "dock", "dock_back", "port", "ruin", "village_port"):
                surf_.blit(SPR["fur_" + b["kind"]], (b["tx"] * TILE - cx, b["ty"] * TILE - cy - 4))
            elif b["kind"] == "pc":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy - 16
                surf_.blit(SPR["pc"], (bx, by))
                if int(t * 2) % 2 == 0:
                    surf_.fill((255, 255, 255), (bx + 18, by + 11, 2, 2))
            elif b["kind"] == "arcade":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy - 24
                surf_.blit(SPR["arcade"], (bx, by))
                col = ((250, 80, 120), (80, 220, 250), (250, 220, 80), (120, 250, 120))[int(t * 3) % 4]
                surf_.fill(col, (bx + 8 + int(t * 10) % 14, by + 14, 3, 3))
        elif kind == "stall_front":
            surf_.blit(SPR["stall_front"], (d["tx"] * TILE - cx, d["ty"] * TILE - cy))
        elif kind == "lamp":
            surf_.blit(SPR["lamp"], (d[0] * TILE - cx, d[1] * TILE - cy - 16))
        elif kind == "fence":
            x, y = d
            f = self.fences
            surf_.blit(fence_sprite((x - 1, y) in f, (x + 1, y) in f, (y - 1) >= 0 and (x, y - 1) in f,
                                    (x, y + 1) in f), (x * TILE - cx, y * TILE - cy))
        elif kind == "chicken":
            c = d
            surf_.blit(SPR["shadow"], (c.x - cx - 7, c.y - cy - 1))
            fr = 3 if c.state == "peck" and int(c.anim) % 2 == 0 else (int(c.anim) % 2 + 1 if c.state == "walk" else 0)
            img = SPR["chicken_flip" if c.flip else "chicken"][fr]
            surf_.blit(img, (c.x - cx - 6, c.y - cy - 10))
        elif kind == "npc":
            n = d
            fr = int(n.anim) % 4 if n.moving else 0
            bob = -1 if fr in (1, 3) else 0
            if n.wander:
                surf_.blit(SPR["shadow"], (n.x - cx - 7, n.y - cy - 3))
            surf_.blit(n.sprites[(n.dir, fr)], (n.x - cx - 8, n.y - cy - 23 + bob))
            mk = self.npc_marker(n.name)
            mx_, my_ = int(n.x - cx), int(n.y - cy) - 38
            if mk == "new":                                   # a quest on offer
                pygame.draw.rect(surf_, GOLD, (mx_ - 1, my_, 3, 7))
                pygame.draw.rect(surf_, GOLD, (mx_ - 1, my_ + 9, 3, 3))
            elif mk == "done":                                # a quest ready to hand in
                draw_star(surf_, mx_, my_ + 4, 5, GOLD)
        elif kind == "player":
            self.draw_player(surf_, d, cx, cy)
        elif kind == "remote":
            img = SPR["remote"].get((d.get("d", "down"), int(d.get("f", 0)) % 4), SPR["remote"][("down", 0)])
            surf_.blit(SPR["shadow"], (d["x"] - cx - 7, d["y"] - cy - 3))
            surf_.blit(img, (d["x"] - cx - 8, d["y"] - cy - 23))
        elif kind == "table":
            surf_.blit(SPR["table"], (d["tx"] * TILE - cx, d["ty"] * TILE - cy))
        elif kind == "cust":
            moving = d.state in ("arrive", "leave")
            fr = int(d.anim) % 4 if moving else 0
            bob = -1 if ((d.state == "eat" and int(t * 3) % 2 == 0) or fr in (1, 3)) else 0
            if moving:
                surf_.blit(SPR["shadow"], (d.x - cx - 7, d.y - cy - 3))
            surf_.blit(d.sprites[(d.dir, fr)], (d.x - cx - 8, d.y - cy - 23 + bob))

    def window_glow(self, surf_, bx, by, wins):
        ln = self.night_level()
        if ln < 0.08:
            return
        for (wx, wy, ww, wh) in wins:
            g = pygame.Surface((ww, wh))
            g.fill((255, 214, 120))
            g.set_alpha(int(210 * ln))
            surf_.blit(g, (bx + wx, by + wy))

    def draw_player(self, surf_, p, cx, cy):
        fr = int(p.anim) % 4 if p.moving else 0
        bob = -1 if fr in (1, 3) else 0
        surf_.blit(SPR["shadow"], (p.x - cx - 7, p.y - cy - 3))
        img = SPR["player"][(p.dir, fr)]
        surf_.blit(img, (p.x - cx - 8, p.y - cy - 23 + bob))
        if p.act > 0 and p.act_tool in ICONS_TOOLS:
            prog = 1 - p.act / p.act_dur
            dx, dy = DIRS[p.dir]
            ang = {"right": -50 + 110 * prog, "left": 50 - 110 * prog,
                   "down": 60 - 120 * prog, "up": -60 + 120 * prog}[p.dir]
            icon = pygame.transform.rotate(pygame.transform.scale(self.icons[p.act_tool], (20, 20)), ang)
            ox, oy = p.x + dx * 11, p.y - 11 + dy * 7
            surf_.blit(icon, (ox - cx - icon.get_width() / 2, oy - cy - icon.get_height() / 2))

    def draw_particles(self, surf_, cam):
        cx, cy = cam
        for pt in self.particles:
            k = clamp(pt["life"] / pt["max"], 0, 1)
            x, y = pt["x"] - cx, pt["y"] - cy
            if pt["kind"] == "smoke":
                sz = int(pt["size"] + (1 - k) * 5)
                s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, pt["c"] + (int(150 * k),), (sz, sz), sz)
                surf_.blit(s, (x - sz, y - sz))
            elif pt["kind"] == "star":
                c = pt["c"]
                sz = 1 + int(k * 2)
                surf_.fill(c, (x - sz, y, sz * 2 + 1, 1))
                surf_.fill(c, (x, y - sz, 1, sz * 2 + 1))
            elif pt["kind"] == "heart":
                c = pt["c"]
                surf_.fill(c, (x - 3, y - 2, 3, 3))
                surf_.fill(c, (x + 1, y - 2, 3, 3))
                surf_.fill(c, (x - 3, y, 7, 2))
                surf_.fill(c, (x - 2, y + 2, 5, 1))
                surf_.fill(c, (x - 1, y + 3, 3, 1))
            else:
                sz = max(1, int(pt["size"] * (0.5 + k * 0.5)))
                surf_.fill(pt["c"], (x, y, sz, sz))

    def draw_critters(self, surf_):
        ln = self.night_level()
        if self.rain or self.location != "farm":
            return
        for c in self.crit:
            x, y = int(c["x"]), int(c["y"])
            if ln > 0.45:
                b = 0.5 + 0.5 * math.sin(self.t * 3 + c["ph"])
                if b > 0.25:
                    surf_.fill((255, 250, 150), (x, y, 2, 2))
            elif self.season != "Fall" or True:
                flap = int(math.sin(self.t * 18 + c["ph"]) * 1.5)
                surf_.fill(c["c"], (x - 2, y - abs(flap), 2, 2))
                surf_.fill(c["c"], (x + 1, y - abs(flap), 2, 2))
                surf_.fill((70, 50, 40), (x, y, 1, 2))

    def draw_lighting(self, surf_, cam):
        amb = self.ambient()
        if amb[0] > 250 and amb[1] > 245 and amb[2] > 232 and not self.rain:
            return
        cx, cy = cam
        dark = pygame.Surface((VIEW_W, VIEW_H))
        dark.fill(amb)
        ln = self.night_level()
        if ln > 0.05:
            def light(x, y, key):
                g = SPR[key]
                dark.blit(g, (x - cx - g.get_width() // 2, y - cy - g.get_height() // 2),
                          special_flags=pygame.BLEND_RGB_ADD)
            for (lx, ly) in self.lamps:
                light(lx * TILE + 8, ly * TILE - 6, "glow_l")
            light(27 * TILE + 25, 5 * TILE + 54, "glow_m")
            light(27 * TILE + 71, 5 * TILE + 54, "glow_m")
            light(36 * TILE + 22, 8 * TILE + 35, "glow_m")
            light(self.player.x, self.player.y - 10, "glow_m")
            light(38 * TILE + 24, 15 * TILE + 45, "glow_m")
            light(38 * TILE + 104, 15 * TILE + 45, "glow_m")
            light(57 * TILE + 16, 17 * TILE - 6, "glow_m")
            light(33 * TILE + 16, 9 * TILE - 6, "glow_s")
            if ln > 0.45 and not self.rain:
                for c in self.crit:
                    if math.sin(self.t * 3 + c["ph"]) > 0.25:
                        g = SPR["glow_s"]
                        dark.blit(g, (c["x"] - g.get_width() // 2 - 0, c["y"] - g.get_height() // 2),
                                  special_flags=pygame.BLEND_RGB_ADD)
        surf_.blit(dark, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def draw_rain(self, surf_):
        if not self.rain or self.location != "farm":
            return
        for d in self.rain_drops:
            pygame.draw.line(surf_, (190, 210, 240), (d[0], d[1]), (d[0] - 2, d[1] + 5))

    # ------------------------------------------------------- drawing: UI helpers
    def text(self, s, pos, font=None, color=TEXT, shadow=None, center=False, right=False):
        font = font or self.f_m
        if str(s) == "":
            return 0
        img = font.render(str(s), True, color)
        x, y = pos
        if center:
            x -= img.get_width() // 2
        if right:
            x -= img.get_width()
        if shadow:
            self.screen.blit(font.render(str(s), True, shadow), (x + 2, y + 2))
        self.screen.blit(img, (x, y))
        return img.get_width()

    def panel(self, rect, fill=PANEL):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, INK, rect.inflate(8, 8), border_radius=10)
        pygame.draw.rect(self.screen, PANEL_D, rect.inflate(4, 4), border_radius=9)
        pygame.draw.rect(self.screen, fill, rect, border_radius=7)
        pygame.draw.rect(self.screen, PANEL_L, rect.inflate(-8, -8), 1, border_radius=5)

    def icon(self, key, pos, scale=2):
        k = (key, scale)
        img = self.icons2.get(k)
        if img is None:
            img = pygame.transform.scale(self.icons[key], (16 * scale, 16 * scale))
            self.icons2[k] = img
        self.screen.blit(img, pos)

    def draw_hud(self, cam):
        if NO_HUD:
            return self.draw_minimal_hud(cam)
        scr = self.screen
        p = self.player
        # clock panel
        r = pygame.Rect(WIN_W - 196, 12, 184, 112)
        self.panel(r)
        self.text("%s %d" % (self.season, self.day_of_season), (r.x + 14, r.y + 10), self.f_m, TEXT)
        self.text("Year %d" % self.year, (r.right - 14, r.y + 13), self.f_s, PANEL_D, right=True)
        self.text(fmt_time(self.time), (r.x + 14, r.y + 36), self.f_l, TEXT)
        wx, wy = r.right - 34, r.y + 58
        if self.rain:
            pygame.draw.circle(scr, (150, 160, 180), (wx, wy), 9)
            pygame.draw.circle(scr, (150, 160, 180), (wx + 9, wy + 3), 7)
            pygame.draw.circle(scr, (150, 160, 180), (wx - 9, wy + 3), 6)
            for i in range(3):
                pygame.draw.line(scr, (90, 140, 210), (wx - 8 + i * 8, wy + 12), (wx - 10 + i * 8, wy + 18), 2)
        else:
            pygame.draw.circle(scr, (250, 200, 60), (wx, wy + 6), 9)
            for i in range(8):
                a = i * math.pi / 4 + self.t * 0.5
                pygame.draw.line(scr, (250, 200, 60), (wx + math.cos(a) * 12, wy + 6 + math.sin(a) * 12),
                                 (wx + math.cos(a) * 17, wy + 6 + math.sin(a) * 17), 2)
        self.icon("coin", (r.x + 12, r.y + 78), 1)
        self.text("%sg" % format(self.money, ","), (r.x + 34, r.y + 77), self.f_m, TEXT)
        self.draw_cafe_stars()
        # energy bar
        er = pygame.Rect(WIN_W - 46, WIN_H - 168, 34, 156)
        self.panel(er)
        frac = clamp(self.energy / self.max_energy, 0, 1)
        col = lerp_col((220, 70, 60), (110, 200, 80), frac) if frac < 0.5 else lerp_col((240, 200, 60), (110, 200, 80), (frac - 0.5) * 2)
        inner = pygame.Rect(er.x + 7, er.y + 8, 20, 120)
        pygame.draw.rect(scr, (70, 50, 40), inner, border_radius=3)
        fh = int(inner.height * frac)
        pygame.draw.rect(scr, col, (inner.x, inner.bottom - fh, inner.width, fh), border_radius=3)
        self.text("E", (er.centerx, er.bottom - 24), self.f_s, TEXT, center=True)
        # hotbar
        keys = self.hotbar()
        self.sel = clamp(self.sel, 0, max(0, len(keys) - 1))
        n = len(keys)
        size, gap = 50, 4
        total = n * (size + gap) - gap
        x0, y0 = WIN_W // 2 - total // 2, WIN_H - size - 16
        self.hotbar_rects = []
        for i, k in enumerate(keys):
            rr = pygame.Rect(x0 + i * (size + gap), y0, size, size)
            self.hotbar_rects.append((rr, i))
            sel = i == self.sel
            pygame.draw.rect(scr, INK, rr.inflate(6, 6), border_radius=8)
            pygame.draw.rect(scr, GOLD if sel else PANEL_D, rr.inflate(2, 2), border_radius=7)
            pygame.draw.rect(scr, (236, 200, 140) if sel else PANEL, rr, border_radius=6)
            self.icon(k, (rr.x + 9, rr.y + 9), 2)
            label = "-" if i == 10 else "=" if i == 11 else str((i + 1) % 10)
            self.text(label, (rr.x + 4, rr.y + 2), self.f_s, TEXT)
            if ITEMS[k]["kind"] != "tool":
                self.text(self.inv.get(k, 0), (rr.right - 4, rr.bottom - 16), self.f_s, TEXT, right=True)
            elif k == "can":
                pygame.draw.rect(scr, (70, 50, 40), (rr.x + 6, rr.bottom - 8, size - 12, 4))
                pygame.draw.rect(scr, (90, 160, 230), (rr.x + 6, rr.bottom - 8, int((size - 12) * self.water / self.water_cap()), 4))
        if keys:
            nm = ITEMS[keys[self.sel]]["name"]
            if self.sel_timer > 0 or True:
                self.text(nm, (WIN_W // 2, y0 - 22), self.f_s, CREAM, shadow=INK, center=True)
        # toasts
        for i, tdict in enumerate(reversed(self.toasts)):
            a = clamp(tdict["t"] / 0.5, 0, 1)
            tr = pygame.Rect(14, WIN_H - 124 - i * 40, 330, 32)
            ps = pygame.Surface((tr.w, tr.h), pygame.SRCALPHA)
            pygame.draw.rect(ps, (60, 40, 30, int(210 * a)), ps.get_rect(), border_radius=8)
            scr.blit(ps, tr)
            x = tr.x + 8
            if tdict["icon"]:
                self.icon(tdict["icon"], (tr.x + 6, tr.y + 0), 2)
                x = tr.x + 44
            img = self.f_s.render(tdict["text"], True, CREAM)
            img.set_alpha(int(255 * a))
            scr.blit(img, (x, tr.y + 9))
        # prompt
        pt = self.prompt_text()
        if pt and self.state == "play":
            sx, sy = (p.x - cam[0]) * SCALE, (p.y - 38 - cam[1]) * SCALE
            w = self.f_s.size(pt)[0] + 20
            rr = pygame.Rect(sx - w // 2, sy - 22, w, 26)
            pygame.draw.rect(scr, INK, rr.inflate(4, 4), border_radius=8)
            pygame.draw.rect(scr, PANEL_L, rr, border_radius=7)
            self.text(pt, rr.center, self.f_s, TEXT, center=True)

    def draw_minimal_hud(self, cam):
        """No-HUD mode: only interaction prompts and short messages on screen."""
        pt = self.prompt_text()
        if pt and self.state == "play":
            p = self.player
            sx, sy = (p.x - cam[0]) * SCALE, (p.y - 38 - cam[1]) * SCALE
            w = self.f_s.size(pt)[0] + 20
            rr = pygame.Rect(sx - w // 2, sy - 22, w, 26)
            pygame.draw.rect(self.screen, INK, rr.inflate(4, 4), border_radius=8)
            pygame.draw.rect(self.screen, PANEL_L, rr, border_radius=7)
            self.text(pt, rr.center, self.f_s, TEXT, center=True)
        for i, tdict in enumerate(reversed(self.toasts)):
            a = clamp(tdict["t"] / 0.5, 0, 1)
            img = self.f_s.render(tdict["text"], True, CREAM)
            img.set_alpha(int(255 * a))
            self.screen.blit(img, (WIN_W // 2 - img.get_width() // 2, WIN_H - 40 - i * 22))

    # ------------------------------------------------------- menus
    def list_for(self, kind):
        if kind == "shop":
            return [k + "_seed" for k in CROPS]
        if kind == "cook":
            return list(self.unlocked)
        if kind == "bin":
            return [k for k in ITEMS if self.inv.get(k, 0) > 0 and ITEMS[k]["kind"] != "tool" and ITEMS[k]["sell"] > 0]
        if kind == "inv":
            return [k for k in ITEMS if self.inv.get(k, 0) > 0 and ITEMS[k]["kind"] != "tool"]
        return []

    def draw_menu(self):
        m = self.menu
        ty = m["type"]
        shade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        shade.fill((20, 12, 8, 140))
        self.screen.blit(shade, (0, 0))
        if ty == "pc":
            self.draw_pc()
            return
        if ty == "cafe":
            self.draw_cafe_menu()
            return
        if ty == "arcade":
            self.draw_arcade_menu()
            return
        if ty == "bench":
            self.draw_bench()
            return
        if ty == "admin":
            self.draw_admin_menu()
            return
        if ty == "fishmaster":
            self.draw_fishmaster()
            return
        if ty == "journal":
            self.draw_journal()
            return
        if ty == "sleep":
            r = pygame.Rect(WIN_W // 2 - 220, WIN_H // 2 - 90, 440, 180)
            self.panel(r)
            self.text("Go to sleep for the night?", (r.centerx, r.y + 24), self.f_l, TEXT, center=True)
            for i, lab in enumerate(("Yes, good night!", "Not yet")):
                rr = pygame.Rect(r.x + 40, r.y + 80 + i * 40, 360, 34)
                if m["idx"] == i:
                    pygame.draw.rect(self.screen, GOLD, rr, border_radius=6)
                self.text(lab, rr.center, self.f_m, TEXT, center=True)
            return
        if ty == "pause":
            items = self.pause_items()
            r = pygame.Rect(WIN_W // 2 - 200, WIN_H // 2 - 165, 400, 120 + len(items) * 38)
            self.panel(r)
            self.text("Paused", (r.centerx, r.y + 22), self.f_l, TEXT, center=True)
            status = ("Room at %s:%d - %d / %d players" % (lan_ip(), NET_PORT, len(self.net_server.clients) + 1, ROOM_SIZE)) if self.net_server else (
                "Connected to a LAN game" if self.net_client else "Not in a LAN game")
            self.text(status, (r.centerx, r.y + 58), self.f_s, PANEL_D, center=True)
            for i, lab in enumerate(items):
                rr = pygame.Rect(r.x + 30, r.y + 84 + i * 38, 340, 32)
                if m["idx"] == i:
                    pygame.draw.rect(self.screen, GOLD, rr, border_radius=6)
                self.text(lab, rr.center, self.f_m, TEXT, center=True)
            return
        titles = {"shop": "Mabel's General Store", "cook": "Kitchen", "bin": "Shipping Bin", "inv": "Backpack"}
        entries = self.list_for(ty)
        r = pygame.Rect(WIN_W // 2 - 330, WIN_H // 2 - 250, 660, 500)
        self.panel(r)
        self.text(titles[ty], (r.x + 24, r.y + 18), self.f_l, TEXT)
        if ty in ("shop",):
            self.icon("coin", (r.right - 150, r.y + 18), 2)
            self.text("%sg" % format(self.money, ","), (r.right - 112, r.y + 24), self.f_m, TEXT)
        if ty == "shop":
            self.text("\"%s\"" % m.get("greet", ""), (r.x + 24, r.y + 56), self.f_s, PANEL_D)
        if ty == "bin":
            tot = sum(ITEMS[k]["sell"] * n for k, n in self.bin.items())
            self.text("In bin: %dg" % tot, (r.right - 24, r.y + 26), self.f_m, TEXT, right=True)
        if ty == "cook":
            self.text("Pick a recipe and press Enter", (r.x + 24, r.y + 56), self.f_s, PANEL_D)
        if ty == "inv":
            self.text("Enter: eat food", (r.x + 24, r.y + 56), self.f_s, PANEL_D)
            self.text("Farming Lv %d   Cooking Lv %d   Fishing Lv %d   Cafe %d stars" % (
                self.level("farm"), self.level("cook"), self.level("fish"), self.stars()),
                (r.right - 24, r.y + 60), self.f_s, TEXT, right=True)
        if not entries:
            self.text("Nothing here yet.", (r.centerx, r.centery), self.f_m, PANEL_D, center=True)
        rows, row_h = 7, 52
        m["idx"] = clamp(m["idx"], 0, max(0, len(entries) - 1))
        m["scroll"] = clamp(m.get("scroll", 0), max(0, m["idx"] - rows + 1), m["idx"])
        top = r.y + 84
        for vi in range(rows):
            i = m["scroll"] + vi
            if i >= len(entries):
                break
            k = entries[i]
            rr = pygame.Rect(r.x + 20, top + vi * row_h, r.w - 40, row_h - 6)
            if i == m["idx"]:
                pygame.draw.rect(self.screen, (252, 224, 150), rr, border_radius=8)
                pygame.draw.rect(self.screen, GOLD, rr, 3, border_radius=8)
            else:
                pygame.draw.rect(self.screen, (236, 200, 144), rr, border_radius=8)
            self.icon(k, (rr.x + 10, rr.y + 7), 2)
            it = ITEMS[k]
            if ty == "shop":
                c = CROPS[it["crop"]]
                self.text(it["name"], (rr.x + 54, rr.y + 4), self.f_m, TEXT)
                self.text("Grows in %d days. Sells for %dg." % (c["days"], c["sell"]), (rr.x + 54, rr.y + 26), self.f_s, PANEL_D)
                col = TEXT if self.money >= it["buy"] else (170, 50, 40)
                self.text("%dg" % it["buy"], (rr.right - 14, rr.y + 12), self.f_m, col, right=True)
            elif ty == "cook":
                rec = RECIPES[k]
                self.text(rec["name"], (rr.x + 54, rr.y + 4), self.f_m, TEXT)
                x = rr.x + 54
                for ing, need in rec["needs"].items():
                    have = self.inv.get(ing, 0)
                    col = (50, 120, 50) if have >= need else (170, 50, 40)
                    x += self.text("%s %d/%d" % (ITEMS[ing]["name"], have, need), (x, rr.y + 28), self.f_s, col) + 14
                self.text("+%d energy" % rec["energy"], (rr.right - 14, rr.y + 12), self.f_s, TEXT, right=True)
            elif ty == "bin":
                self.text(it["name"], (rr.x + 54, rr.y + 12), self.f_m, TEXT)
                self.text("x%d   %dg each" % (self.inv.get(k, 0), it["sell"]), (rr.right - 14, rr.y + 14), self.f_s, TEXT, right=True)
            else:
                self.text(it["name"], (rr.x + 54, rr.y + 12), self.f_m, TEXT)
                extra = "+%d energy   " % it["energy"] if it["kind"] == "food" else ""
                self.text("%sx%d" % (extra, self.inv.get(k, 0)), (rr.right - 14, rr.y + 14), self.f_s, TEXT, right=True)
        hint = {"shop": "Enter: buy 1   Shift+Enter: buy 5   Esc: leave",
                "cook": "Enter: start cooking   Esc: leave",
                "bin": "Enter: ship 1   Shift+Enter: ship all   Esc: leave",
                "inv": "Enter: eat   I / Esc: close"}[ty]
        self.text(hint, (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def menu_key(self, ev):
        m = self.menu
        ty = m["type"]
        k = ev.key
        up = k in (pygame.K_UP, pygame.K_w)
        down = k in (pygame.K_DOWN, pygame.K_s)
        ok = k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)
        shift = ev.mod & pygame.KMOD_SHIFT
        close = k == pygame.K_ESCAPE or (k in (pygame.K_i, pygame.K_TAB) and ty == "inv")
        if ty in ("pc", "cafe", "arcade", "bench", "admin", "journal", "fishmaster"):
            self.extra_menu_key(ev, ty)
            return
        if ty == "sleep":
            if up or down:
                m["idx"] = 1 - m["idx"]
            elif ok and m["idx"] == 0:
                self.menu = {}
                self.start_end_day(False)
            elif ok or close:
                self.state, self.menu = "play", {}
            return
        if ty == "pause":
            n = len(self.pause_items())
            if up:
                m["idx"] = (m["idx"] - 1) % n
            elif down:
                m["idx"] = (m["idx"] + 1) % n
            elif close:
                self.state, self.menu = "play", {}
            elif ok:
                item = self.pause_items()[m["idx"]]
                if item == "Save game":
                    self.toast("Game saved!" if self.save_game() else "Could not save the game.")
                    self.state, self.menu = "play", {}
                elif item == "Save and quit to title":
                    self.save_game()
                    self.net_close()
                    self.state, self.menu = "title", {}
                elif item == "Help":
                    self.state, self.menu = "help", {}
                elif item == "Fish journal":
                    self.menu = dict(type="journal", idx=0, scroll=0)
                elif item == "Host LAN game":
                    self.start_hosting()
                    self.state, self.menu = "play", {}
                elif item == "Stop hosting":
                    self.stop_hosting()
                    self.state, self.menu = "play", {}
                elif item == "Admin panel":
                    self.menu = dict(type="admin", idx=0, scroll=0)
                else:
                    self.state, self.menu = "play", {}
            return
        entries = self.list_for(ty)
        if close:
            self.state, self.menu = "play", {}
            return
        if up:
            m["idx"] = max(0, m["idx"] - 1)
        elif down:
            m["idx"] = min(max(0, len(entries) - 1), m["idx"] + 1)
        elif ok and entries:
            key = entries[clamp(m["idx"], 0, len(entries) - 1)]
            if ty == "shop":
                n = 5 if shift else 1
                price = ITEMS[key]["buy"] * n
                if self.money >= price:
                    self.money -= price
                    self.add_item(key, n)
                else:
                    self.toast("Not enough gold!")
            elif ty == "cook":
                self.start_cook(key)
                return
            elif ty == "bin":
                n = self.inv.get(key, 0) if shift else 1
                self.take_item(key, n)
                self.bin[key] = self.bin.get(key, 0) + n
                self.qinc("ship", n)
            elif ty == "inv":
                if ITEMS[key]["kind"] == "food":
                    if self.energy >= self.max_energy - 1:
                        self.toast("You're not tired right now.")
                    else:
                        self.eat(key)

    # ------------------------------------------------------- other screens
    def draw_dialog(self):
        d = self.dialog
        r = pygame.Rect(60, WIN_H - 190, WIN_W - 120, 150)
        self.panel(r)
        pic = d.get("portrait")
        left = r.x + 24
        width = r.w - 60
        if pic is not None:
            self.screen.blit(pic, (r.x + 14, r.y + (r.h - pic.get_height()) // 2))
            left = r.x + 130
            width -= 106
        self.text(d["name"], (left, r.y + 14), self.f_m, (140, 70, 40))
        shown = int(d["shown"])
        words, line, y = d["text"][:shown].split(" "), "", r.y + 50
        for w in words:
            if self.f_m.size(line + w)[0] > width:
                self.text(line, (left, y), self.f_m, TEXT)
                line, y = "", y + 30
            line += w + " "
        self.text(line, (left, y), self.f_m, TEXT)
        if shown >= len(d["text"]):
            self.text("Press E", (r.right - 24, r.bottom - 30), self.f_s, PANEL_D, right=True)

    def draw_wish(self):
        scr = self.screen
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((24, 14, 10, 165))
        scr.blit(ov, (0, 0))
        r = pygame.Rect(WIN_W // 2 - 300, 100, 600, 500)
        self.panel(r)
        self.text("Make a wish!", (r.centerx, r.y + 18), self.f_l, TEXT, center=True)
        self.text("Crazy Dew will grant one wish. Each wish can only be made once.", (r.centerx, r.y + 56),
                  self.f_s, PANEL_D, center=True)
        y = r.y + 96
        for i, (key, title, desc) in enumerate(self.wish_opts):
            row = pygame.Rect(r.x + 24, y, r.w - 48, 46)
            pygame.draw.rect(scr, (255, 226, 150) if i == self.wish_idx else (255, 246, 226), row, border_radius=8)
            pygame.draw.rect(scr, INK, row, 2, border_radius=8)
            self.text(title, (row.x + 14, row.y + 4), self.f_m, TEXT)
            self.text(desc, (row.x + 14, row.y + 26), self.f_s, PANEL_D)
            y += 54
        self.text("Up / Down to choose, Enter to wish", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)

    def wish_key(self, ev):
        k = ev.key
        opts = self.wish_opts
        if not opts:
            self.state = "play"
            return
        if k in (pygame.K_UP, pygame.K_w):
            self.wish_idx = (self.wish_idx - 1) % len(opts)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.wish_idx = (self.wish_idx + 1) % len(opts)
        elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e, pygame.K_KP_ENTER):
            key, title, _ = opts[self.wish_idx]
            self.apply_wish(key)
            self.wishes_done.add(key)
            self.wish_opts = []
            self.state = "play"

    def apply_wish(self, key):
        if key == "gold":
            self.money += 1500
        elif key == "stamina":
            self.max_energy += 40
            self.energy = float(self.max_energy)
        elif key == "recipes":
            self.unlocked = list(dict.fromkeys(self.unlocked + list(RECIPE_PRICE)))
        elif key == "seeds":
            for k in CROPS:
                self.add_item(k + "_seed", 5, quiet=True)
        elif key == "rare":
            self.add_item("rare_fish", 5, quiet=True)
        elif key == "kits":
            self.add_item("villager_house_kit", 2, quiet=True)
        elif key == "skills":
            for skill in ("farm", "cook", "fish"):
                self.gain_xp(skill, 200)
        title = next(t for k, t, _ in WISH_OPTIONS if k == key)
        self.toast("Wish granted: %s!" % title, "coin")

    def draw_help(self):
        shade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        shade.fill((20, 12, 8, 170))
        self.screen.blit(shade, (0, 0))
        r = pygame.Rect(WIN_W // 2 - 340, WIN_H // 2 - 270, 680, 540)
        self.panel(r)
        self.text("How to play", (r.centerx, r.y + 20), self.f_l, TEXT, center=True)
        lines = [
            ("WASD / Arrows", "Move  (hold Shift to run)"),
            ("Space / Click", "Use tool, plant seeds, eat food"),
            ("E / Right-click", "Interact: harvest, cook, shop, sleep"),
            ("1-9, 0, -, =", "Pick hotbar slot (Q / R / wheel cycles)"),
            ("I or Tab", "Backpack"),
            ("Esc", "Pause and save"),
            ("", ""),
            ("1. Hoe grass", "to make soil, then plant seeds"),
            ("2. Water daily", "Crops only grow on watered days"),
            ("3. Harvest (E)", "then cook at the teal Kitchen hut"),
            ("4. Ship goods", "in the wooden bin by your house"),
            ("5. Cafe", "Serve guests at the tables (E)"),
            ("6. PC + sleep", "PC: shop online. Sleep before 2am!"),
        ]
        if ANDROID:
            lines[:6] = [("Left thumb", "Drag on the left side to move"),
                         ("USE", "Use tool, plant seeds, eat food"),
                         ("E", "Interact: harvest, cook, shop, sleep"),
                         ("< >  or tap", "Change hotbar slot (or tap a slot)"),
                         ("BAG", "Backpack"),
                         ("MENU", "Pause and save")]
        for i, (a, b) in enumerate(lines):
            self.text(a, (r.x + 40, r.y + 76 + i * 30), self.f_m, (140, 70, 40))
            self.text(b, (r.x + 250, r.y + 76 + i * 30), self.f_m, TEXT)
        self.text("Press any key", (r.centerx, r.bottom - 34), self.f_s, PANEL_D, center=True)

    def draw_summary(self):
        self.screen.fill((14, 10, 12))
        s = self.summary
        r = pygame.Rect(WIN_W // 2 - 270, 60, 540, WIN_H - 120)
        self.panel(r)
        self.text("Day %d complete" % s["day"], (r.centerx, r.y + 20), self.f_l, TEXT, center=True)
        if s["passed"]:
            self.text("You passed out... a neighbor carried you home.", (r.centerx, r.y + 58), self.f_s, (150, 60, 40), center=True)
        y = r.y + 94
        if not s["lines"]:
            self.text("Nothing was shipped today.", (r.centerx, y + 20), self.f_m, PANEL_D, center=True)
        for k, n, v in s["lines"][:6]:
            self.icon(k, (r.x + 30, y), 2)
            self.text("%s x%d" % (ITEMS[k]["name"], n), (r.x + 74, y + 8), self.f_m, TEXT)
            self.text("%dg" % v, (r.right - 30, y + 8), self.f_m, TEXT, right=True)
            y += 36
        if not s["lines"]:
            y += 44
        cf = s.get("cafe")
        if cf and (cf["served"] or cf["angry"]):
            self.text("Cafe: %d served, %dg earned (tips %dg), %d unhappy" % (cf["served"], cf["earned"], cf["tips"], cf["angry"]),
                      (r.centerx, y + 8), self.f_s, TEXT, center=True)
            y += 28
        if s.get("deliveries"):
            names = ", ".join("%d %s" % (n, ITEMS[k]["name"]) for k, n in s["deliveries"][:4])
            self.text("Delivered: " + names, (r.centerx, y + 8), self.f_s, TEXT, center=True)
        self.text("Earned: %dg" % s["earned"], (r.centerx, r.bottom - 100), self.f_l, (60, 120, 50), center=True)
        self.text("You now have %sg" % format(self.money, ","), (r.centerx, r.bottom - 64), self.f_m, TEXT, center=True)
        self.text("Press Enter for the next day", (r.centerx, r.bottom - 30), self.f_s, PANEL_D, center=True)

    def draw_title(self):
        self.t += 0
        px = 27 * TILE + 48
        cam = (clamp(int(px - VIEW_W / 2 + math.sin(self.t * 0.15) * 70), 0, MAP_W * TILE - VIEW_W),
               clamp(int(5 * TILE - 40 + math.sin(self.t * 0.1) * 20), 0, MAP_H * TILE - VIEW_H))
        self.render_scene(cam, hud=False)
        shade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        shade.fill((30, 18, 10, 90))
        self.screen.blit(shade, (0, 0))
        bob = math.sin(self.t * 1.5) * 4
        self.text("A Game About", (WIN_W // 2, 60 + bob), self.f_l, CREAM, shadow=INK, center=True)
        self.text("Farming and Cooking", (WIN_W // 2, 96 + bob), self.f_xl, GOLD, shadow=INK, center=True)
        opts = self.title_options()
        self.title_idx = clamp(self.title_idx, 0, len(opts) - 1)
        save_exists = self.has_save()
        for i, o in enumerate(opts):
            rr = pygame.Rect(WIN_W // 2 - 160, 360 + i * 54, 320, 44)
            selected = i == self.title_idx
            self.panel(rr, (252, 224, 150) if selected else PANEL)
            label_color = TEXT if (o != "Continue Playing" or save_exists) else (135, 125, 110)
            self.text(o, rr.center, self.f_m, label_color, center=True)
        if not save_exists:
            self.text("No save file yet", (WIN_W // 2, 360 + 44 + 8), self.f_s, CREAM, shadow=INK, center=True)
        self.text("Up/Down + Enter, or tap", (WIN_W // 2, WIN_H - 28), self.f_s, CREAM, shadow=INK, center=True)

    def join_key(self, ev):
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.state = "title"
            return
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.join_connect(self.join_text.strip())
            return
        if k == pygame.K_BACKSPACE:
            self.join_text = self.join_text[:-1]
            return
        ch = getattr(ev, "unicode", "") or ""
        if ch and ch in "0123456789." and len(self.join_text) < 21:
            self.join_text += ch

    def join_connect(self, ip):
        try:
            self.net_client = NetClient(ip)
        except ServerFull as e:
            self.join_msg = str(e)
            return
        except (OSError, ValueError):
            self.join_msg = "Could not reach %s. Same WiFi? Is the host playing?" % ip
            return
        self.new_game()
        self.state = "play"
        self.toast("Joined the LAN game at %s" % ip)

    def draw_join(self):
        self.render_scene((0, 0), hud=False)
        shade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        shade.fill((30, 18, 10, 120))
        self.screen.blit(shade, (0, 0))
        r = pygame.Rect(WIN_W // 2 - 270, WIN_H // 2 - 150, 540, 300)
        self.panel(r)
        self.text("Join a LAN game", (r.centerx, r.y + 20), self.f_l, TEXT, center=True)
        self.text("Type the host's IP address (shown when they host).", (r.centerx, r.y + 70), self.f_s, PANEL_D, center=True)
        self.text("Both devices must be on the same WiFi.", (r.centerx, r.y + 92), self.f_s, PANEL_D, center=True)
        box = pygame.Rect(r.x + 40, r.y + 124, r.w - 80, 44)
        pygame.draw.rect(self.screen, (252, 224, 150), box, border_radius=8)
        pygame.draw.rect(self.screen, TEXT, box, 2, border_radius=8)
        cursor = "_" if int(self.t * 2) % 2 == 0 else " "
        self.text(self.join_text + cursor, (box.x + 14, box.y + 10), self.f_m, TEXT)
        if self.join_msg:
            self.text(self.join_msg, (r.centerx, r.y + 190), self.f_s, (150, 40, 30), center=True)
        self.text("Enter: connect     Backspace: erase     Esc: back", (r.centerx, r.bottom - 30), self.f_s, PANEL_D, center=True)

    # ------------------------------------------------------- LAN multiplayer
    def net_state(self):
        p = self.player
        return dict(name=self.player_name, x=int(p.x), y=int(p.y), d=p.dir,
                    f=int(p.anim) % 4 if p.moving else 0, loc=self.location)

    def net_tick(self, dt):
        if not (self.net_server or self.net_client):
            return
        self.net_timer = getattr(self, "net_timer", 0.0) - dt
        if self.net_timer > 0:
            return
        crowd = self.net_server is not None and len(self.net_server.clients) > 40
        self.net_timer = 0.2 if crowd else 0.1
        st = self.net_state()
        if self.net_client and self.net_client.kicked:
            self.toast("The host removed you from the LAN game.")
            self.net_client.close()
            self.net_client = None
            self.remote = []
            return
        if self.net_client and not self.net_client.alive:
            self.toast("Lost the connection to the LAN game.")
            self.net_client.close()
            self.net_client = None
            self.remote = []
            return
        if self.net_server:
            self.net_server.broadcast(st)
            self.remote = [p for p in self.net_server.snapshot if p.get("id") != 0]
        if self.net_client:
            self.net_client.send_state(st)
            me = self.net_client.my_id
            self.remote = [p for p in self.net_client.players if p.get("id") != me]

    def start_hosting(self):
        if not CAN_HOST:
            self.toast("This is the player version. You can only join games.")
            return
        if self.net_server:
            return
        if self.net_client:
            self.toast("You are already in someone else's LAN game.")
            return
        try:
            self.net_server = NetServer()
        except OSError:
            self.toast("Could not open port %d. Is another game hosting?" % NET_PORT)
            return
        self.toast("Room open at %s:%d (up to %d players)" % (lan_ip(), NET_PORT, ROOM_SIZE))

    def stop_hosting(self):
        if self.net_server:
            self.net_server.close()
            self.net_server = None
            self.toast("Stopped hosting.")
        self.remote = []

    def net_close(self):
        self.stop_hosting()
        if self.net_client:
            self.net_client.close()
            self.net_client = None
        self.remote = []

    def draw_remote_names(self, cam):
        for rp in self.remote:
            if rp.get("loc") != self.location:
                continue
            if abs(rp["x"] - cam[0]) > VIEW_W + 40 or abs(rp["y"] - cam[1]) > VIEW_H + 40:
                continue
            sx = (rp["x"] - cam[0]) * SCALE
            sy = (rp["y"] - 34 - cam[1]) * SCALE
            self.text(rp.get("name", "?"), (sx, sy), self.f_s, (255, 255, 255), shadow=INK, center=True)

    def title_options(self):
        # Always show Continue Playing so players know where saved games are resumed.
        return ["Continue Playing", "New Game", "Join LAN game", "Quit"]

    def title_click(self, x, y):
        for i, o in enumerate(self.title_options()):
            if pygame.Rect(WIN_W // 2 - 160, 360 + i * 54, 320, 44).collidepoint(x, y):
                self.title_idx = i
                self.title_key(_Key(pygame.K_RETURN))
                return True
        return False

    def title_key(self, ev):
        opts = self.title_options()
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.title_idx = (self.title_idx - 1) % len(opts)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.title_idx = (self.title_idx + 1) % len(opts)
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            o = opts[self.title_idx]
            if o == "Continue Playing":
                if self.load_game():
                    self.state = "play"
                    self.menu = {}
                    self.toast("Save loaded! Welcome back.")
                else:
                    self.toast("No save file found. Start a New Game first.")
            elif o == "New Game":
                self.new_game()
                self.state = "help"
            elif o == "Join LAN game":
                self.join_text, self.join_msg = "192.168.", ""
                self.state = "join"
                getattr(pygame.key, "start_text_input", lambda: None)()
            else:
                pygame.quit()
                sys.exit()

    # ------------------------------------------------------- scene + frame
    def render_scene(self, cam, hud=True):
        self.draw_world(self.view, cam)
        self.draw_critters(self.view)
        self.draw_particles(self.view, cam)
        self.draw_lighting(self.view, cam)
        self.draw_rain(self.view)
        pygame.transform.scale(self.view, (WIN_W, WIN_H), self.screen)
        if self.state == "play" or self.state == "fishing":
            self.draw_remote_names(cam)
        if hud:
            self.draw_hud(cam)

    def draw_dungeon_overlay(self, cam):
        cx, cy = cam
        # Pixel-art monsters with chunky outlines and simple hit flashes.
        for e in self.dungeon_enemies:
            if not e["alive"]: continue
            x, y = int((e["x"]-cx)*SCALE), int((e["y"]-cy)*SCALE)
            col = (255,225,170) if e["flash"] > 0 else ((170,65,82) if e["kind"] != "brute" else (125,70,150))
            pygame.draw.ellipse(self.screen, (18,15,22), (x-15,y+9,30,9))
            pygame.draw.rect(self.screen, (30,22,30), (x-12,y-13,24,25))
            pygame.draw.rect(self.screen, col, (x-10,y-15,20,22))
            pygame.draw.rect(self.screen, (235,75,70), (x-7,y-8,4,4))
            pygame.draw.rect(self.screen, (235,75,70), (x+3,y-8,4,4))
            pygame.draw.rect(self.screen, (25,20,26), (x-13,y-23,26,4))
            pygame.draw.rect(self.screen, (220,65,75), (x-12,y-22,int(24*max(0,e["hp"])/e["maxhp"]),2))
        # Souls-like compact combat status and a deliberately retro pixel HUD.
        panel = pygame.Rect(14, 12, 250, 43)
        pygame.draw.rect(self.screen, (18,15,24), panel, border_radius=5)
        pygame.draw.rect(self.screen, (135,105,84), panel, 2, border_radius=5)
        self.text("MINES  |  FLOOR %02d  |  FOES %d" % (self.dungeon_floor, sum(1 for e in self.dungeon_enemies if e["alive"])),
                  (24,19), self.f_s, (245,220,180))
        pygame.draw.rect(self.screen, (55,35,42), (24,37,210,8))
        pygame.draw.rect(self.screen, (180,55,65), (24,37,int(210*clamp(self.energy/max(1,self.max_energy),0,1)),8))
        self.text("SPACE: ATTACK   CLEAR FLOOR: DESCEND   E: EXIT", (WIN_W-16, 18), self.f_s, (255,235,195), right=True, shadow=(20,15,20))
        if self.dungeon_hit_flash > 0:
            veil = pygame.Surface((WIN_W,WIN_H),pygame.SRCALPHA)
            veil.fill((180,25,35,int(55*self.dungeon_hit_flash/0.22)))
            self.screen.blit(veil,(0,0))

    def draw(self):
        st = self.state
        if st == "title":
            self.draw_title()
        elif st == "join":
            self.draw_join()
        elif st == "summary":
            self.draw_summary()
        elif st in ("mini", "mini_over"):
            self.draw_mini()
        else:
            cam = self.camera()
            self.render_scene(cam)
            if self.location == "dungeon":
                self.draw_dungeon_overlay(cam)
            if st == "menu":
                self.draw_menu()
            elif st == "dialog":
                self.draw_dialog()
            elif st == "help":
                self.draw_help()
            elif st == "fishing":
                self.draw_fishing()
            elif st == "place":
                self.draw_placing()
            elif st == "cookgame":
                self.draw_cookgame()
            elif st == "journal":
                self.draw_journal()
            elif st == "wish":
                self.draw_wish()
            if st in ("fade_out", "fade_in", "warp"):
                ov = pygame.Surface((WIN_W, WIN_H))
                ov.fill((10, 8, 14))
                ov.set_alpha(int(255 * clamp(self.fade, 0, 1)))
                self.screen.blit(ov, (0, 0))

    def update(self, dt):
        self.t += dt
        self.net_tick(dt)
        st = self.state
        if st == "play":
            self.update_play(dt)
        elif st == "cookgame":
            self.update_cookgame(dt)
        elif st == "dialog":
            self.dialog["shown"] += dt * 55
            self.update_effects(dt)
        elif st == "fade_out":
            self.fade += dt / 0.9
            self.update_effects(dt)
            if self.fade >= 1:
                self.process_new_day()
                self.state = "summary"
        elif st == "fade_in":
            self.fade -= dt / 0.8
            self.update_effects(dt)
            if self.fade <= 0:
                self.state = "play"
        elif st == "title":
            self.update_effects(dt)
        elif st == "place":
            self.placing_update(dt)
            self.update_effects(dt)
        elif st == "warp":
            self.update_warp(dt)
        elif st == "fishing":
            self.update_fishing(dt)
            self.update_effects(dt)
        elif st == "mini":
            self.update_mini(dt)

    def key_up(self, ev):
        if self.state == "fishing" and ev.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_e, pygame.K_KP_ENTER):
            self.fishing_up()

    def key_down(self, ev):
        k = ev.key
        st = self.state
        if st == "title":
            self.title_key(ev)
        elif st == "join":
            self.join_key(ev)
        elif st == "help":
            self.state = "play"
        elif st == "menu":
            self.menu_key(ev)
        elif st == "dialog":
            d = self.dialog
            if int(d["shown"]) < len(d["text"]):
                d["shown"] = len(d["text"])
            elif k in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                self.state, self.dialog = (self.after_dialog or "play"), None
                self.after_dialog = None
        elif st == "summary":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.state = "fade_in"
                self.fade = 1.0
                if self.rain:
                    self.toast("It's raining today. Your crops are watered!")
                if getattr(self, "new_season", False):
                    self.toast("A new season begins: %s" % self.season)
        elif st == "fishing":
            if k == pygame.K_ESCAPE:
                self.end_fishing()
            elif k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_e):
                self.fishing_down()
        elif st == "place":
            self.placing_key(ev)
        elif st == "mini":
            self.mini_key(ev)
        elif st == "cookgame":
            self.cookgame_key(ev)
        elif st == "journal":
            if k in (pygame.K_j, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
                self.state = "play"
        elif st == "wish":
            self.wish_key(ev)
        elif st == "mini_over":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_KP_ENTER):
                self.menu = dict(type="arcade", idx=0, scroll=0)
                self.state = "menu"
        elif st == "play":
            if k == pygame.K_ESCAPE:
                self.menu = dict(type="pause", idx=0)
                self.state = "menu"
            elif k in (pygame.K_i, pygame.K_TAB):
                self.menu = dict(type="inv", idx=0, scroll=0)
                self.state = "menu"
            elif k == pygame.K_j:
                self.state = "journal"
            elif k == pygame.K_F1:
                self.state = "help"
            elif k == pygame.K_e:
                self.interact()
            elif k in (pygame.K_SPACE, pygame.K_RETURN):
                if self.location == "dungeon":
                    self.dungeon_attack()
                else:
                    self.use_item()
            elif k == pygame.K_q:
                self.cycle(-1)
            elif k == pygame.K_r:
                self.cycle(1)
            else:
                nums = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6,
                        pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0, pygame.K_MINUS, pygame.K_EQUALS]
                if k in nums:
                    i = nums.index(k)
                    if i < len(self.hotbar()):
                        self.sel = i
                        self.sel_timer = 2.0

    def cycle(self, d):
        n = len(self.hotbar())
        if n:
            self.sel = (self.sel + d) % n
            self.sel_timer = 2.0

    def send_key(self, key, mod=0):
        self.key_down(_Key(key, mod))

    def layout_display(self):
        disp = pygame.display.get_surface()
        dw, dh = disp.get_size()
        self.disp_size = (dw, dh)
        sc = min(dw / WIN_W, dh / WIN_H)
        w, h = max(1, int(WIN_W * sc)), max(1, int(WIN_H * sc))
        self.dst = pygame.Rect((dw - w) // 2, (dh - h) // 2, w, h)
        self.dscale = sc

    def present(self):
        disp = pygame.display.get_surface()
        if disp.get_size() != self.disp_size:
            self.layout_display()
        disp.fill((0, 0, 0))
        pygame.transform.scale(self.screen, self.dst.size, disp.subsurface(self.dst))

    def autosave(self):
        if self.state in ("play", "menu", "dialog", "help"):
            self.save_game()

    def run(self):
        bg_events = tuple(getattr(pygame, n) for n in ("APP_WILLENTERBACKGROUND", "APP_TERMINATING")
                          if hasattr(pygame, n))
        back_key = getattr(pygame, "K_AC_BACK", None)
        finger_events = (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP)
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    if self.state not in ("title", "summary", "fade_out", "fade_in"):
                        self.save_game()
                    self.net_close()
                    pygame.quit()
                    sys.exit()
                elif ev.type == pygame.KEYDOWN:
                    if back_key is not None and ev.key == back_key:
                        self.send_key(pygame.K_ESCAPE)
                    else:
                        self.key_down(ev)
                elif ev.type == pygame.KEYUP:
                    self.key_up(ev)
                elif ev.type in finger_events:
                    self.touch.handle(ev)
                elif ev.type in bg_events:
                    self.autosave()
                elif ANDROID:
                    continue  # touch also fakes mouse events on Android; we use finger events only
                elif ev.type == pygame.MOUSEWHEEL and self.state == "play":
                    self.cycle(-ev.y)
                elif self.state == "place" and ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                    self.placing_pointer((ev.pos[0] - self.dst.x) / self.dscale,
                                         (ev.pos[1] - self.dst.y) / self.dscale,
                                         click=(ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1))
                elif ev.type == pygame.MOUSEBUTTONDOWN and self.state == "mini":
                    self.mini_tap((ev.pos[0] - self.dst.x) / self.dscale, (ev.pos[1] - self.dst.y) / self.dscale)
                elif ev.type == pygame.MOUSEBUTTONDOWN and self.state == "play":
                    if ev.button == 1:
                        self.use_item()
                    elif ev.button == 3:
                        self.interact()
            self.update(dt)
            self.draw()
            self.touch.draw()
            self.present()
            pygame.display.flip()


class _Key:
    def __init__(self, key, mod=0):
        self.key, self.mod, self.unicode = key, mod, ""


class TouchControls:
    """Floating thumb-stick on the left, buttons on the right. Fingers arrive as 0..1 screen
    coordinates and are mapped onto the 960x640 virtual screen the game draws to."""
    STICK_R = 70
    REST = (140, 450)

    def __init__(self, game):
        self.g = game
        self.vec = (0.0, 0.0)
        self.fingers = {}
        self.pressed = set()
        self.center = self.REST
        self.knob = None
        self.cache = {}

    def buttons(self):
        g = self.g
        st = g.state
        K = pygame
        if st == "play":
            return [("use", "USE", 840, 440, 56, K.K_SPACE), ("act", "E", 730, 500, 44, K.K_e),
                    ("prev", "<", 740, 390, 26, K.K_q), ("next", ">", 800, 350, 26, K.K_r),
                    ("bag", "BAG", 52, 52, 32, K.K_i), ("menu", "MENU", 122, 52, 32, K.K_ESCAPE)]
        if st in ("menu", "title"):
            b = [("up", "UP", 880, 250, 44, K.K_UP), ("down", "DOWN", 880, 370, 44, K.K_DOWN),
                 ("ok", "OK", 880, 490, 44, K.K_RETURN)]
            if st == "menu":
                b.append(("back", "BACK", 80, 490, 44, K.K_ESCAPE))
                ty = g.menu.get("type")
                if ty in ("shop", "bin", "pc"):
                    b.append(("alt", "x5/ALL", 80, 370, 44, K.K_RETURN))
                if ty == "pc":
                    b += [("left", "<", 60, 190, 34, K.K_LEFT), ("right", ">", 60, 262, 34, K.K_RIGHT)]
            return b
        if st in ("dialog", "help", "summary", "mini_over"):
            return [("ok", "OK", 880, 490, 44, K.K_RETURN)]
        if st == "place":
            return [("use", "BUILD", 840, 440, 56, K.K_SPACE), ("back", "BACK", 80, 490, 44, K.K_ESCAPE)]
        if st == "fishing":
            return [("use", "REEL", 840, 440, 56, K.K_SPACE), ("back", "BACK", 80, 490, 44, K.K_ESCAPE)]
        if st == "mini":
            b = [("back", "QUIT", 60, 580, 36, K.K_ESCAPE)]
            if g.mini and g.mini["kind"] == "memory":
                b += [("up", "UP", 850, 370, 38, K.K_UP), ("down", "DOWN", 850, 510, 38, K.K_DOWN),
                      ("left", "LEFT", 780, 440, 38, K.K_LEFT), ("right", "RIGHT", 920, 440, 38, K.K_RIGHT)]
            return b
        return []

    def to_virtual(self, nx, ny):
        g = self.g
        dw, dh = g.disp_size
        return (nx * dw - g.dst.x) / g.dscale, (ny * dh - g.dst.y) / g.dscale

    def handle(self, ev):
        x, y = self.to_virtual(ev.x, ev.y)
        fid = ev.finger_id
        if ev.type == pygame.FINGERDOWN:
            self.down(fid, x, y)
        elif ev.type == pygame.FINGERMOTION:
            if self.fingers.get(fid) == "stick":
                self.drag(x, y)
        else:
            self.up(fid)

    def down(self, fid, x, y):
        g = self.g
        if g.state == "title" and g.title_click(x, y):
            return
        if g.state == "place":
            g.placing_pointer(x, y, click=False)
            return
        for name, label, bx, by, r, key in self.buttons():
            if math.hypot(x - bx, y - by) <= r + 8:
                self.fingers[fid] = name
                self.pressed.add(name)
                g.send_key(key, pygame.KMOD_SHIFT if name == "alt" else 0)
                return
        if g.state == "play":
            for rr, i in g.hotbar_rects:
                if rr.inflate(6, 6).collidepoint(x, y):
                    g.sel = i
                    return
            if x < WIN_W * 0.45 and y > 130:
                self.fingers[fid] = "stick"
                self.center = (x, y)
                self.drag(x, y)
        elif g.state == "mini":
            if g.mini["kind"] == "veggie":
                if x < WIN_W * 0.5:
                    self.fingers[fid] = "stick"
                    self.center = (x, y)
                    self.drag(x, y)
            else:
                g.mini_tap(x, y)
        elif g.state in ("dialog", "help", "summary", "mini_over"):
            g.send_key(pygame.K_RETURN)

    def drag(self, x, y):
        cx, cy = self.center
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d > self.STICK_R:
            dx, dy = dx / d * self.STICK_R, dy / d * self.STICK_R
        self.knob = (cx + dx, cy + dy)
        vx, vy = dx / self.STICK_R, dy / self.STICK_R
        self.vec = (vx, vy) if math.hypot(vx, vy) > 0.22 else (0.0, 0.0)

    def up(self, fid):
        what = self.fingers.pop(fid, None)
        if what == "stick":
            self.vec, self.knob, self.center = (0.0, 0.0), None, self.REST
        elif what:
            self.pressed.discard(what)
            if what == "use" and self.g.state == "fishing":
                self.g.fishing_up()

    def circle(self, r, alpha):
        s = self.cache.get((r, alpha))
        if s is None:
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 244, 220, alpha), (r + 2, r + 2), r)
            pygame.draw.circle(s, (52, 36, 28, 190), (r + 2, r + 2), r, 3)
            self.cache[(r, alpha)] = s
        return s

    def draw(self):
        g = self.g
        if g.state in ("fade_out", "fade_in"):
            return
        if g.state == "play" or (g.state == "mini" and g.mini and g.mini["kind"] == "veggie"):
            c = self.center
            g.screen.blit(self.circle(self.STICK_R, 50), (c[0] - self.STICK_R - 2, c[1] - self.STICK_R - 2))
            k = self.knob or c
            g.screen.blit(self.circle(30, 130 if self.knob else 70), (k[0] - 32, k[1] - 32))
        for name, label, bx, by, r, key in self.buttons():
            g.screen.blit(self.circle(r, 150 if name in self.pressed else 80), (bx - r - 2, by - r - 2))
            g.text(label, (bx, by - 8), g.f_s, (52, 36, 28), center=True)

ICONS_TOOLS = set(TOOLS)


def main():
    pygame.init()
    loaded = load_mods()
    if loaded:
        print("Loaded mods:", ", ".join(loaded))
    Game().run()


if __name__ == "__main__":
    main()