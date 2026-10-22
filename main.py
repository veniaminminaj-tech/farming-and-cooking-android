# Android build trigger: pinned Buildozer and pygame-ce recipe
#!//usr/bin/env python3
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
  5. Buy new seeds from Mabel's stall in the village (east along the path).
  6. Chop trees (axe) and mine rocks (pickaxe) to clear land.
  7. Sleep in your house before 2am or you will pass out!
"""
import json
import math
import os
import random
import sys

import pygame

# ============================================================ config
TILE = 16
VIEW_W, VIEW_H = 480, 320
SCALE = 2
WIN_W, WIN_H = VIEW_W * SCALE, VIEW_H * SCALE
MAP_W, MAP_H = 64, 48
FPS = 60
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "farm_cooking_save.json")
MIN_PER_SEC = 3.0            # game minutes per real second
WAKE_HOUR, PASSOUT_HOUR = 6.0, 26.0
SEASONS = ["Spring", "Summer", "Fall"]
DAYS_PER_SEASON = 10
GRASS, PATH, WATER, SAND = 0, 1, 2, 3
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
}
RECIPES = {
    "fried_egg": dict(name="Fried Egg", needs={"egg": 1}, energy=30, sell=50),
    "tea": dict(name="Wildflower Tea", needs={"flower": 2}, energy=25, sell=60),
    "bread": dict(name="Fresh Bread", needs={"wheat": 2}, energy=40, sell=100),
    "stew": dict(name="Parsnip Stew", needs={"parsnip": 2, "potato": 1}, energy=60, sell=220),
    "soup": dict(name="Tomato Soup", needs={"tomato": 2}, energy=65, sell=320),
    "pie": dict(name="Pumpkin Pie", needs={"pumpkin": 1, "wheat": 1, "egg": 1}, energy=100, sell=700),
}
TOOLS = ["hoe", "can", "axe", "pick"]
TOOL_NAMES = {"hoe": "Hoe", "can": "Watering Can", "axe": "Axe", "pick": "Pickaxe"}
TOOL_COST = {"hoe": 2, "can": 1, "axe": 3, "pick": 3}

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
})
for _k, _r in RECIPES.items():
    ITEMS[_k] = dict(name=_r["name"], kind="food", sell=_r["sell"], energy=_r["energy"])

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


def make_icon(key):
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
    elif ITEMS.get(key, {}).get("kind") == "food":
        plate = (238, 232, 222)
        plate_d = (190, 182, 170)
        if key in ("stew", "soup", "tea"):
            E((120, 84, 60), 2, 6, 12, 9)
            E((160, 112, 80), 2, 5, 12, 8)
            col = {"stew": (206, 120, 56), "soup": (214, 64, 48), "tea": (176, 120, 70)}[key]
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
    else:
        R((200, 60, 60), 4, 4, 8, 8)
    return s


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
    SPR["soil_dry"] = make_soil(False)
    SPR["soil_wet"] = make_soil(True)
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
    for v in range(8):
        t = pygame.Surface((16, 16))
        t.fill(pal["grass"])
        for _ in range(16):
            t.set_at((rnd.randrange(16), rnd.randrange(16)),
                     pal["grass_d"] if rnd.random() < 0.55 else pal["grass_l"])
        if v >= 4:
            x, y = rnd.randrange(3, 12), rnd.randrange(5, 13)
            for dx, dy in ((0, 0), (0, -1), (1, 0), (1, -1), (1, -2), (2, 0), (2, -1)):
                t.set_at((x + dx, y + dy), pal["grass_l"] if dx == 1 else pal["grass_d"])
        SPR["grass"].append(t)
    SPR["path"] = []
    SPR["sand"] = []
    for base, lst in (((200, 170, 116), SPR["path"]), ((226, 206, 152), SPR["sand"])):
        for v in range(4):
            t = pygame.Surface((16, 16))
            t.fill(base)
            for _ in range(18):
                c = lerp_col(base, (150, 120, 80), 0.3) if rnd.random() < 0.5 else lerp_col(base, (255, 240, 200), 0.3)
                t.set_at((rnd.randrange(16), rnd.randrange(16)), c)
            for _ in range(3):
                x, y = rnd.randrange(1, 14), rnd.randrange(2, 14)
                t.fill(lerp_col(base, (110, 90, 60), 0.4), (x, y, 2, 1))
                t.fill(lerp_col(base, (255, 245, 210), 0.5), (x, y - 1, 2, 1))
            lst.append(t)
    SPR["water"] = []
    for f in range(4):
        t = pygame.Surface((16, 16))
        t.fill((64, 138, 196))
        for i in range(3):
            y = (i * 6 + f * 2) % 16
            t.fill((112, 184, 230), (2 + (i * 5 + f * 3) % 9, y, 5, 1))
            t.fill((88, 160, 214), ((i * 7 + f * 2) % 11, (y + 3) % 16, 3, 1))
        SPR["water"].append(t)
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


# ============================================================ the game
class Game:
    def __init__(self):
        pygame.display.set_caption("A Game About Farming and Cooking")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.view = pygame.Surface((VIEW_W, VIEW_H))
        self.clock = pygame.time.Clock()
        # Android touch state: directional keys are held while the virtual stick is held.
        self.touch_keys = set()
        self.joystick_finger = None
        self.joystick_vector = (0, 0)
        self.touch_buttons = {}
        self.last_touch_time = 0
        self.f_s = pygame.font.Font(None, 22)
        self.f_m = pygame.font.Font(None, 28)
        self.f_l = pygame.font.Font(None, 40)
        self.f_xl = pygame.font.Font(None, 76)
        build_static_sprites()
        self.icons = {k: make_icon(k) for k in ITEMS}
        self.icons["coin"] = make_icon("coin")
        self.icons2 = {}
        self.season_built = None
        self.t = 0.0
        self.state = "title"
        self.title_idx = 0
        self.new_game()
        self.state = "title"

    # ------------------------------------------------------- setup
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
        self.cafe_served = 0
        self.cafe_rating = 1
        self.cafe_order = None
        self.arcade_score = 0
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
        cx, cy, rx, ry = 11, 30, 6, 4
        for y in range(MAP_H):
            for x in range(MAP_W):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if d <= 1.0:
                    T[y][x] = WATER
                elif d <= 1.7 and T[y][x] == GRASS:
                    T[y][x] = SAND
        self.buildings = [
            dict(kind="house", tx=27, ty=5, w=6, h=5),
            dict(kind="kitchen", tx=36, ty=8, w=4, h=3),
            dict(kind="bin", tx=24, ty=11, w=2, h=1),
            dict(kind="stall", tx=50, ty=15, w=5, h=3),
            dict(kind="coop", tx=45, ty=26, w=3, h=2),
            dict(kind="cafe", tx=39, ty=15, w=4, h=3),
            dict(kind="computer", tx=34, ty=13, w=3, h=2),
            dict(kind="arcade", tx=40, ty=9, w=3, h=2),
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
                x, y = rnd.randrange(5, MAP_W - 5), rnd.randrange(4, MAP_H - 4)
                if (x, y) in res or (x, y) in self.objs:
                    continue
                put(x, y, t, v=rnd.randrange(3 if t != "tree" else 2), **kw)
                placed += 1

        scatter("tree", 26, hp=4)
        scatter("rock", 30, hp=3)
        scatter("flower", 42)
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
        self.npcs = [mabel, fern]
        self.eggs = []

    def rebuild_solid(self):
        S = [[False] * MAP_W for _ in range(MAP_H)]
        for y in range(MAP_H):
            for x in range(MAP_W):
                if self.tiles[y][x] == WATER:
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
        self.solid = S

    def new_critter(self):
        return dict(x=random.uniform(0, VIEW_W), y=random.uniform(0, VIEW_H), a=random.uniform(0, 6.28),
                    ph=random.uniform(0, 6.28), c=random.choice([(250, 240, 120), (250, 160, 200), (160, 210, 250)]))

    # ------------------------------------------------------- save / load
    def has_save(self):
        return os.path.exists(SAVE_FILE)

    def save_game(self):
        try:
            data = dict(day=self.day, time=self.time, money=self.money, energy=self.energy, water=self.water,
                        rain=self.rain, inv=self.inv, bin=self.bin,
                        soil=[[x, y, s["wet"], s["crop"], s["age"]] for (x, y), s in self.soil.items()],
                        objs=[[x, y, o["t"], o.get("hp", 1), o.get("v", 0)] for (x, y), o in self.objs.items()],
                        eggs=self.eggs, px=self.player.x, py=self.player.y)
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
        self.eggs = d.get("eggs", [])
        self.player.x, self.player.y = d["px"], d["py"]
        self.ensure_season()
        self.rebuild_solid()
        return True

    # ------------------------------------------------------- inventory helpers
    def hotbar(self):
        keys = list(TOOLS)
        keys += [k for k in ITEMS if ITEMS[k]["kind"] == "seed" and self.inv.get(k, 0) > 0]
        keys += [k for k in RECIPES if self.inv.get(k, 0) > 0]
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
        cost = TOOL_COST[key]
        self.swing(key)
        if key == "can" and tt == WATER:
            self.water = 20
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
            self.toast("The can is empty. Refill it at the pond!")
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
                    self.rebuild_solid()
                    self.sparkle(cx, cy)
            else:
                del self.soil[(tx, ty)]
                self.burst(cx, cy, (140, 100, 64), 7, 30, 100, 0.4)

    def harvest(self, tx, ty):
        s = self.soil[(tx, ty)]
        crop = s["crop"]
        s["crop"], s["age"] = None, 0
        self.add_item(crop)
        cx, cy = tx * TILE + 8, ty * TILE + 8
        self.burst(cx, cy, CROPS[crop]["fruit"], 8, 50, 120, 0.6)
        self.sparkle(cx, cy)
        self.swing(None)

    def compute_focus(self):
        tx, ty = self.facing_tile()
        self.focus = None
        cx, cy = tx * TILE + 8, ty * TILE + 8
        for n in self.npcs:
            if n.wander and math.hypot(n.x - cx, n.y - 8 - cy) < 20:
                self.focus = ("npc", n)
                return
        for c in self.chickens:
            if math.hypot(c.x - cx, c.y - cy) < 14:
                self.focus = ("chicken", c)
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
            return "E  Talk"
        if kind == "chicken":
            return "E  Pet"
        if kind == "crop":
            return "E  Harvest"
        if kind == "flower":
            return "E  Pick"
        return {"house": "E  Sleep", "kitchen": "E  Cook", "bin": "E  Ship goods",
                "stall": "E  Shop", "coop": "E  Look", "cafe": "E  Cafe orders",
                "computer": "E  Farm computer", "arcade": "E  Arcade"}[data["kind"]]

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
        elif kind == "npc":
            self.say(data.name, random.choice(data.lines))
        elif kind == "chicken":
            self.heart(data.x, data.y - 10)
            self.toast("Bwaaaak! Your hen seems happy.")
        elif kind == "bld":
            k = data["kind"]
            if k == "house":
                self.menu = dict(type="sleep", idx=1)
                self.state = "menu"
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
                self.menu = dict(type="cafe", idx=0, scroll=0)
                self.state = "menu"
            elif k == "computer":
                self.menu = dict(type="computer", idx=0, scroll=0)
                self.state = "menu"
            elif k == "arcade":
                self.menu = dict(type="arcade", idx=0, scroll=0)
                self.state = "menu"

    def say(self, name, text):
        self.dialog = dict(name=name, text=text, shown=0.0)
        self.state = "dialog"

    # ------------------------------------------------------- day cycle
    def start_end_day(self, passed):
        self.passed_out = passed
        self.state = "fade_out"
        self.fade = 0.0

    def process_new_day(self):
        lines, earned = [], 0
        for k, n in list(self.bin.items()):
            v = ITEMS[k]["sell"] * n
            lines.append((k, n, v))
            earned += v
        self.money += earned
        self.bin = {}
        for s in self.soil.values():
            if s["crop"] and s["wet"] and s["age"] < CROPS[s["crop"]]["days"]:
                s["age"] += 1
            s["wet"] = False
        self.summary = dict(day=self.day, lines=lines, earned=earned, passed=self.passed_out)
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
        while flowers < 60 and tries < 40:
            tries += 1
            x, y = random.randrange(5, MAP_W - 5), random.randrange(4, MAP_H - 4)
            if (x, y) in self.reserved or (x, y) in self.objs or (x, y) in self.soil:
                continue
            self.objs[(x, y)] = dict(t="flower", v=random.randrange(3))
            flowers += 1
            if flowers > 40 and random.random() < 0.3:
                break
        self.energy = self.max_energy * (0.6 if self.passed_out else 1.0)
        self.water = 20
        self.time = WAKE_HOUR
        self.player.x, self.player.y = 30 * TILE, 10 * TILE + 10
        self.player.dir = "down"
        self.save_game()

    # ------------------------------------------------------- update
    def ambient(self):
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
        mx = int(keys[pygame.K_d] or keys[pygame.K_RIGHT] or pygame.K_RIGHT in self.touch_keys) - int(keys[pygame.K_a] or keys[pygame.K_LEFT] or pygame.K_LEFT in self.touch_keys)
        my = int(keys[pygame.K_s] or keys[pygame.K_DOWN] or pygame.K_DOWN in self.touch_keys) - int(keys[pygame.K_w] or keys[pygame.K_UP] or pygame.K_UP in self.touch_keys)
        p.moving = False
        if p.act > 0:
            p.act -= dt
        elif mx or my:
            if mx and not my:
                p.dir = "right" if mx > 0 else "left"
            elif my and not mx:
                p.dir = "down" if my > 0 else "up"
            elif p.dir in ("left", "right") and not mx:
                p.dir = "down" if my > 0 else "up"
            elif p.dir in ("up", "down") and not my:
                p.dir = "right" if mx > 0 else "left"
            run = 1.55 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or pygame.K_LSHIFT in self.touch_keys) else 1.0
            sp = 62 * run * dt
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
                    surf_.blit(SPR["water"][int(t * 2.2 + tx * 0.35 + ty * 0.2) % 4], (dx, dy))
                    for nx, ny, r in ((0, -1, (0, 0, 16, 2)), (0, 1, (0, 14, 16, 2)),
                                      (-1, 0, (0, 0, 2, 16)), (1, 0, (14, 0, 2, 16))):
                        xx, yy = tx + nx, ty + ny
                        if 0 <= xx < MAP_W and 0 <= yy < MAP_H and self.tiles[yy][xx] != WATER:
                            surf_.fill((200, 230, 246), (dx + r[0], dy + r[1], r[2], r[3]))
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
        ents.append((self.player.y, "player", self.player))
        ents.sort(key=lambda e: e[0])
        for _, kind, data in ents:
            self.draw_entity(surf_, kind, data, cx, cy)

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
            if b["kind"] == "house":
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy
                surf_.blit(SPR["house"], (bx, by))
                self.window_glow(surf_, bx, by, SPR["house_windows"])
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
            elif b["kind"] in ("cafe", "computer", "arcade"):
                bx, by = b["tx"] * TILE - cx, b["ty"] * TILE - cy
                body = {"cafe": (222, 172, 116), "computer": (156, 176, 186), "arcade": (160, 116, 176)}[b["kind"]]
                roof = {"cafe": (176, 72, 60), "computer": (74, 116, 132), "arcade": (78, 62, 120)}[b["kind"]]
                pygame.draw.rect(surf_, body, (bx + 2, by + 12, b["w"] * TILE - 4, b["h"] * TILE - 12))
                pygame.draw.rect(surf_, roof, (bx, by + 4, b["w"] * TILE, 12))
                pygame.draw.rect(surf_, (90, 60, 40), (bx + 4, by + 20, 12, 18))
                pygame.draw.rect(surf_, (120, 196, 220), (bx + 22, by + 20, 18, 12))
                label = {"cafe": "CAFE", "computer": "PC", "arcade": "PLAY"}[b["kind"]]
                self.text(label, (bx + b["w"] * TILE // 2, by + 8), self.f_s, CREAM, center=True)
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
        elif kind == "player":
            self.draw_player(surf_, d, cx, cy)

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
        if self.rain:
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
            if ln > 0.45 and not self.rain:
                for c in self.crit:
                    if math.sin(self.t * 3 + c["ph"]) > 0.25:
                        g = SPR["glow_s"]
                        dark.blit(g, (c["x"] - g.get_width() // 2 - 0, c["y"] - g.get_height() // 2),
                                  special_flags=pygame.BLEND_RGB_ADD)
        surf_.blit(dark, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def draw_rain(self, surf_):
        if not self.rain:
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
        for i, k in enumerate(keys):
            rr = pygame.Rect(x0 + i * (size + gap), y0, size, size)
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
                pygame.draw.rect(scr, (90, 160, 230), (rr.x + 6, rr.bottom - 8, int((size - 12) * self.water / 20), 4))
        if keys:
            nm = ITEMS[keys[self.sel]]["name"]
            if self.sel_timer > 0 or True:
                self.text(nm, (WIN_W // 2, y0 - 22), self.f_s, CREAM, shadow=INK, center=True)
        # toasts
        for i, tdict in enumerate(reversed(self.toasts)):
            a = clamp(tdict["t"] / 0.5, 0, 1)
            tr = pygame.Rect(14, WIN_H - 92 - i * 40, 330, 32)
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

    # ------------------------------------------------------- menus
    def list_for(self, kind):
        if kind == "shop":
            return [k + "_seed" for k in CROPS]
        if kind == "cafe":
            return ["order", "serve", "upgrade"]
        if kind == "computer":
            return ["parsnip_seed", "wheat_seed", "potato_seed", "tomato_seed", "pumpkin_seed", "upgrade_bag", "upgrade_energy"]
        if kind == "arcade":
            return ["harvest_game", "kitchen_game", "fishing_game"]
        if kind == "cook":
            return list(RECIPES)
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
            r = pygame.Rect(WIN_W // 2 - 200, WIN_H // 2 - 130, 400, 260)
            self.panel(r)
            self.text("Paused", (r.centerx, r.y + 22), self.f_l, TEXT, center=True)
            for i, lab in enumerate(("Resume", "Save game", "Save and quit to title", "Help")):
                rr = pygame.Rect(r.x + 30, r.y + 80 + i * 40, 340, 34)
                if m["idx"] == i:
                    pygame.draw.rect(self.screen, GOLD, rr, border_radius=6)
                self.text(lab, rr.center, self.f_m, TEXT, center=True)
            return
        titles = {"shop": "Mabel's General Store", "cook": "Kitchen", "bin": "Shipping Bin", "inv": "Backpack",
                  "cafe": "Little Cafe", "computer": "Farm Computer", "arcade": "Game Arcade"}
        entries = self.list_for(ty)
        if ty in ("cafe", "computer", "arcade"):
            r = pygame.Rect(WIN_W // 2 - 330, WIN_H // 2 - 250, 660, 500)
            self.panel(r)
            self.text(titles[ty], (r.x + 24, r.y + 18), self.f_l, TEXT)
            if ty == "arcade_round":
                game = m.get("game", "Harvest Dash")
                key_label = {"Harvest Dash": "SPACE", "Kitchen Rush": "ENTER", "Fishing Catch": "F"}[game]
                self.text("Game: " + game, (r.x + 24, r.y + 70), self.f_l, PANEL_D)
                self.text("Press " + key_label + " five times to finish.", (r.x + 24, r.y + 150), self.f_m, TEXT)
                self.text("Progress: %d / 5" % m.get("taps", 0), (r.centerx, r.y + 230), self.f_l, TEXT, center=True)
                self.text("Esc: quit mini-game", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)
                return
            if ty == "cafe":
                self.text("Orders served: %d   Cafe rating: %d/5" % (self.cafe_served, self.cafe_rating),
                          (r.x + 24, r.y + 58), self.f_m, PANEL_D)
                if self.cafe_order:
                    self.text("Current order: " + RECIPES[self.cafe_order]["name"], (r.x + 24, r.y + 82), self.f_s, PANEL_D)
                labels = ["Get a customer order", "Serve the current order", "Upgrade cafe (300g)"]
            elif ty == "computer":
                labels = ["Buy Parsnip Seeds (20g)", "Buy Wheat Seeds (15g)", "Buy Potato Seeds (40g)",
                          "Buy Tomato Seeds (60g)", "Buy Pumpkin Seeds (100g)", "Upgrade backpack (200g)",
                          "Increase max energy (250g)"]
                self.text("Spend your farm earnings on supplies and upgrades.", (r.x + 24, r.y + 58), self.f_s, PANEL_D)
            else:
                labels = ["Harvest Dash - win 10-35g", "Kitchen Rush - win 10-35g", "Fishing Catch - win 10-35g"]
                self.text("Pick a mini-game, then press Enter to play a round.", (r.x + 24, r.y + 58), self.f_s, PANEL_D)
            for i, label in enumerate(labels):
                rr = pygame.Rect(r.x + 24, r.y + 108 + i * 54, r.w - 48, 44)
                if i == m["idx"]:
                    pygame.draw.rect(self.screen, (252, 224, 150), rr, border_radius=8)
                    pygame.draw.rect(self.screen, GOLD, rr, 3, border_radius=8)
                else:
                    pygame.draw.rect(self.screen, (236, 200, 144), rr, border_radius=8)
                self.text(label, (rr.x + 16, rr.centery), self.f_m, TEXT)
            if ty == "arcade":
                self.text("Last score: %d" % self.arcade_score, (r.centerx, r.bottom - 62), self.f_m, TEXT, center=True)
            self.text("Up/Down select   Enter confirm   Esc leave", (r.centerx, r.bottom - 26), self.f_s, PANEL_D, center=True)
            return
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
                "cook": "Enter: cook   Esc: leave",
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
            if up:
                m["idx"] = (m["idx"] - 1) % 4
            elif down:
                m["idx"] = (m["idx"] + 1) % 4
            elif close:
                self.state, self.menu = "play", {}
            elif ok:
                i = m["idx"]
                if i == 0:
                    self.state, self.menu = "play", {}
                elif i == 1:
                    self.toast("Game saved!" if self.save_game() else "Could not save the game.")
                    self.state, self.menu = "play", {}
                elif i == 2:
                    self.save_game()
                    self.state, self.menu = "title", {}
                else:
                    self.state, self.menu = "help", {}
            return
        if ty == "arcade_round":
            if close:
                self.state, self.menu = "play", {}
                return
            expected = {"Harvest Dash": pygame.K_SPACE, "Kitchen Rush": pygame.K_RETURN, "Fishing Catch": pygame.K_f}.get(m.get("game"))
            if k == expected:
                m["taps"] = m.get("taps", 0) + 1
                if m["taps"] >= 5:
                    self.arcade_score = random.randint(10, 35)
                    self.money += self.arcade_score
                    self.toast("Mini-game won! +%dg" % self.arcade_score)
                    self.state, self.menu = "play", {}
            return
        entries = self.list_for(ty)
        if close:
            self.state, self.menu = "play", {}
            return
        if ty in ("cafe", "computer", "arcade"):
            if up:
                m["idx"] = (m["idx"] - 1) % len(entries)
            elif down:
                m["idx"] = (m["idx"] + 1) % len(entries)
            elif ok:
                i = m["idx"]
                if ty == "cafe":
                    if i == 0:
                        self.cafe_order = random.choice(list(RECIPES))
                        self.toast("Customer wants: " + RECIPES[self.cafe_order]["name"])
                    elif i == 1:
                        if not self.cafe_order:
                            self.toast("Get a customer order first.")
                        elif self.inv.get(self.cafe_order, 0) <= 0:
                            self.toast("You need to cook " + RECIPES[self.cafe_order]["name"] + " first.")
                        else:
                            key = self.cafe_order
                            self.take_item(key)
                            reward = int(RECIPES[key]["sell"] * (1.0 + self.cafe_rating * 0.1))
                            self.money += reward
                            self.cafe_served += 1
                            self.cafe_rating = min(5, 1 + self.cafe_served // 3)
                            self.cafe_order = None
                            self.toast("Order served! +%dg" % reward)
                    elif i == 2:
                        if self.cafe_rating >= 5:
                            self.toast("Your cafe is already fully upgraded.")
                        elif self.money >= 300:
                            self.money -= 300
                            self.cafe_rating = min(5, self.cafe_rating + 1)
                            self.toast("Cafe upgraded! Rating %d/5" % self.cafe_rating)
                        else:
                            self.toast("You need 300g to upgrade the cafe.")
                elif ty == "computer":
                    seeds = ["parsnip_seed", "wheat_seed", "potato_seed", "tomato_seed", "pumpkin_seed"]
                    if i < len(seeds):
                        key = seeds[i]
                        price = ITEMS[key]["buy"]
                        if self.money >= price:
                            self.money -= price
                            self.add_item(key)
                        else:
                            self.toast("Not enough gold!")
                    elif i == 5:
                        if getattr(self, "bag_upgraded", False):
                            self.toast("Backpack already upgraded.")
                        elif self.money >= 200:
                            self.money -= 200
                            self.bag_upgraded = True
                            self.toast("Backpack upgraded! More hotbar room.")
                        else:
                            self.toast("You need 200g.")
                    else:
                        if self.max_energy >= 180:
                            self.toast("Energy is already maxed out.")
                        elif self.money >= 250:
                            self.money -= 250
                            self.max_energy += 20
                            self.energy = min(self.max_energy, self.energy + 20)
                            self.toast("Max energy increased!")
                        else:
                            self.toast("You need 250g.")
                else:
                    games = ["Harvest Dash", "Kitchen Rush", "Fishing Catch"]
                    self.menu = dict(type="arcade_round", game=games[i], taps=0)
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
                rec = RECIPES[key]
                if all(self.inv.get(i, 0) >= n for i, n in rec["needs"].items()):
                    for i, n in rec["needs"].items():
                        self.take_item(i, n)
                    self.add_item(key)
                    self.sparkle(36 * TILE + 30, 10 * TILE, 8)
                else:
                    self.toast("You're missing some ingredients.")
            elif ty == "bin":
                n = self.inv.get(key, 0) if shift else 1
                self.take_item(key, n)
                self.bin[key] = self.bin.get(key, 0) + n
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
        self.text(d["name"], (r.x + 24, r.y + 14), self.f_m, (140, 70, 40))
        shown = int(d["shown"])
        words, line, y = d["text"][:shown].split(" "), "", r.y + 50
        for w in words:
            if self.f_m.size(line + w)[0] > r.w - 60:
                self.text(line, (r.x + 24, y), self.f_m, TEXT)
                line, y = "", y + 30
            line += w + " "
        self.text(line, (r.x + 24, y), self.f_m, TEXT)
        if shown >= len(d["text"]):
            self.text("Press E", (r.right - 24, r.bottom - 30), self.f_s, PANEL_D, right=True)

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
            ("5. Shop east", "Mabel sells seeds in the village"),
            ("6. Sleep", "in your house before 2am!"),
        ]
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
        for k, n, v in s["lines"][:8]:
            self.icon(k, (r.x + 30, y), 2)
            self.text("%s x%d" % (ITEMS[k]["name"], n), (r.x + 74, y + 8), self.f_m, TEXT)
            self.text("%dg" % v, (r.right - 30, y + 8), self.f_m, TEXT, right=True)
            y += 36
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
        opts = (["Continue"] if self.has_save() else []) + ["New Game", "Quit"]
        self.title_idx = clamp(self.title_idx, 0, len(opts) - 1)
        for i, o in enumerate(opts):
            rr = pygame.Rect(WIN_W // 2 - 140, 380 + i * 54, 280, 44)
            self.panel(rr, (252, 224, 150) if i == self.title_idx else PANEL)
            self.text(o, rr.center, self.f_m, TEXT, center=True)
        self.text("Up/Down + Enter", (WIN_W // 2, WIN_H - 28), self.f_s, CREAM, shadow=INK, center=True)

    def title_key(self, ev):
        opts = (["Continue"] if self.has_save() else []) + ["New Game", "Quit"]
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.title_idx = (self.title_idx - 1) % len(opts)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.title_idx = (self.title_idx + 1) % len(opts)
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            o = opts[self.title_idx]
            if o == "Continue":
                if self.load_game():
                    self.state = "play"
            elif o == "New Game":
                self.new_game()
                self.state = "help"
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
        if hud:
            self.draw_hud(cam)

    def draw(self):
        st = self.state
        if st == "title":
            self.draw_title()
        elif st == "summary":
            self.draw_summary()
        else:
            cam = self.camera()
            self.render_scene(cam)
            if st == "menu":
                self.draw_menu()
            elif st == "dialog":
                self.draw_dialog()
            elif st == "help":
                self.draw_help()
            if st in ("fade_out", "fade_in"):
                ov = pygame.Surface((WIN_W, WIN_H))
                ov.fill((10, 8, 14))
                ov.set_alpha(int(255 * clamp(self.fade, 0, 1)))
                self.screen.blit(ov, (0, 0))
        if st == "play":
            self.draw_touch_controls()

    def draw_touch_controls(self):
        """Translucent mobile controls, drawn over the existing game without assets."""
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        cx, cy, r = 112, WIN_H - 116, 66
        pygame.draw.circle(overlay, (20, 26, 24, 105), (cx, cy), r + 8)
        pygame.draw.circle(overlay, (235, 235, 210, 105), (cx, cy), r, 3)
        vx, vy = self.joystick_vector
        knob = (int(cx + vx * 37), int(cy + vy * 37))
        pygame.draw.circle(overlay, (245, 222, 164, 175), knob, 27)
        buttons = [
            (WIN_W - 105, WIN_H - 105, 43, "USE"),
            (WIN_W - 210, WIN_H - 175, 39, "TALK"),
            (WIN_W - 235, WIN_H - 75, 31, "RUN"),
            (WIN_W - 65, 68, 27, "BAG"),
        ]
        for x, y, radius, label in buttons:
            pressed = label.lower() in self.touch_buttons.values()
            fill = (255, 211, 116, 205) if pressed else (35, 43, 38, 145)
            pygame.draw.circle(overlay, fill, (x, y), radius)
            pygame.draw.circle(overlay, (255, 242, 205, 200), (x, y), radius, 2)
            surf = self.f_s.render(label, True, (255, 250, 225))
            overlay.blit(surf, surf.get_rect(center=(x, y)))
        self.screen.blit(overlay, (0, 0))

    def touch_position(self, ev):
        return (int(ev.x * WIN_W), int(ev.y * WIN_H))

    def handle_touch_down(self, ev):
        pos = self.touch_position(ev)
        x, y = pos
        self.last_touch_time = pygame.time.get_ticks()
        if self.state != "play":
            # Let the game menus respond to a tap as a click/confirm.
            self.handle_tap_outside_play(pos)
            return
        jx, jy, jr = 112, WIN_H - 116, 76
        if math.hypot(x - jx, y - jy) <= jr + 10 and self.joystick_finger is None:
            self.joystick_finger = ev.finger_id
            self.update_joystick(pos)
            return
        targets = [
            (WIN_W - 105, WIN_H - 105, 48, "use"),
            (WIN_W - 210, WIN_H - 175, 44, "interact"),
            (WIN_W - 235, WIN_H - 75, 37, "run"),
            (WIN_W - 65, 68, 32, "inventory"),
        ]
        for bx, by, br, action in targets:
            if math.hypot(x - bx, y - by) <= br:
                self.touch_buttons[ev.finger_id] = action
                if action == "use": self.use_item()
                elif action == "interact": self.interact()
                elif action == "run": self.touch_keys.add(pygame.K_LSHIFT)
                elif action == "inventory":
                    self.menu = dict(type="inv", idx=0, scroll=0)
                    self.state = "menu"
                return

    def update_joystick(self, pos):
        dx, dy = pos[0] - 112, pos[1] - (WIN_H - 116)
        length = math.hypot(dx, dy)
        if length > 66:
            dx, dy = dx * 66 / length, dy * 66 / length
            length = 66
        vx, vy = dx / 66, dy / 66
        self.joystick_vector = (vx, vy)
        dead = 0.28
        self.touch_keys.difference_update((pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN))
        if abs(vx) > dead: self.touch_keys.add(pygame.K_RIGHT if vx > 0 else pygame.K_LEFT)
        if abs(vy) > dead: self.touch_keys.add(pygame.K_DOWN if vy > 0 else pygame.K_UP)

    def handle_tap_outside_play(self, pos):
        x, y = pos
        if self.state == "title":
            opts = ( ["Continue"] if self.has_save() else [] ) + ["New Game", "Quit"]
            for i, option in enumerate(opts):
                rect = pygame.Rect(WIN_W // 2 - 140, 380 + i * 54, 280, 44)
                if rect.collidepoint(x, y):
                    if option == "Continue":
                        if self.load_game(): self.state = "play"
                    elif option == "New Game":
                        self.new_game(); self.state = "help"
                    else:
                        pygame.quit(); sys.exit()
                    return
            self.title_idx = min(len(opts) - 1, max(0, (y - 380) // 54))
        elif self.state == "help":
            self.state = "play"
        elif self.state == "dialog":
            d = self.dialog
            if int(d["shown"]) < len(d["text"]): d["shown"] = len(d["text"])
            else: self.state, self.dialog = "play", None
        elif self.state == "summary":
            self.state = "fade_in"; self.fade = 1.0
        elif self.state == "menu":
            self.menu_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))

    def update(self, dt):
        self.t += dt
        st = self.state
        if st == "play":
            self.update_play(dt)
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

    def key_down(self, ev):
        k = ev.key
        st = self.state
        if st == "title":
            self.title_key(ev)
        elif st == "help":
            self.state = "play"
        elif st == "menu":
            self.menu_key(ev)
        elif st == "dialog":
            d = self.dialog
            if int(d["shown"]) < len(d["text"]):
                d["shown"] = len(d["text"])
            elif k in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                self.state, self.dialog = "play", None
        elif st == "summary":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.state = "fade_in"
                self.fade = 1.0
                if self.rain:
                    self.toast("It's raining today. Your crops are watered!")
                if getattr(self, "new_season", False):
                    self.toast("A new season begins: %s" % self.season)
        elif st == "play":
            if k == pygame.K_ESCAPE:
                self.menu = dict(type="pause", idx=0)
                self.state = "menu"
            elif k in (pygame.K_i, pygame.K_TAB):
                self.menu = dict(type="inv", idx=0, scroll=0)
                self.state = "menu"
            elif k == pygame.K_F1:
                self.state = "help"
            elif k == pygame.K_e:
                self.interact()
            elif k in (pygame.K_SPACE, pygame.K_RETURN):
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

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    if self.state not in ("title", "summary", "fade_out", "fade_in"):
                        self.save_game()
                    pygame.quit()
                    sys.exit()
                elif ev.type == pygame.KEYDOWN:
                    self.key_down(ev)
                elif ev.type == pygame.FINGERDOWN:
                    self.handle_touch_down(ev)
                elif ev.type == pygame.FINGERMOTION:
                    if ev.finger_id == self.joystick_finger:
                        self.update_joystick(self.touch_position(ev))
                elif ev.type == pygame.FINGERUP:
                    self.last_touch_time = pygame.time.get_ticks()
                    if ev.finger_id == self.joystick_finger:
                        self.joystick_finger = None
                        self.joystick_vector = (0, 0)
                        self.touch_keys.difference_update((pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN))
                    action = self.touch_buttons.pop(ev.finger_id, None)
                    if action == "run": self.touch_keys.discard(pygame.K_LSHIFT)
                elif ev.type == pygame.MOUSEWHEEL and self.state == "play":
                    self.cycle(-ev.y)
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    # SDL may emit a mouse event alongside a finger event on Android.
                    if pygame.time.get_ticks() - self.last_touch_time < 250:
                        continue
                    if self.state == "play":
                        if ev.button == 1: self.use_item()
                        elif ev.button == 3: self.interact()
                    elif ev.button == 1:
                        self.handle_tap_outside_play(ev.pos)
            self.update(dt)
            self.draw()
            pygame.display.flip()


ICONS_TOOLS = set(TOOLS)


def main():
    pygame.init()
    Game().run()


if __name__ == "__main__":
    main()
