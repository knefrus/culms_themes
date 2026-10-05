"""Пиксельный крабик: пак зацикленных анимаций.

Рисуем на логической сетке 40×40 (1 «пиксель» краба из оригинала = 2 клетки),
потом масштабируем без сглаживания:
  gif/      — 480×480, прозрачный фон
  emoji/    — 100×100 VP9 WEBM с альфой (кастомные эмодзи Telegram)
  stickers/ — 512×512 VP9 WEBM с альфой (видеостикеры Telegram)
Все анимации ≤ 3 с и 12.5 fps — в лимитах Telegram.

Запуск: python3 make_crabs.py [out_dir] [имя ...]   (по умолчанию out_dir = текущая папка)
Нужны Pillow и ffmpeg с libvpx-vp9.
"""
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

W = 40                 # логический холст
FRAME_MS = 80          # 12.5 fps — темп как у оригинала
GROUND = 36            # низ ножек

BODY = (216, 112, 80, 255)
SHADE = (184, 104, 72, 255)
ANGRY = (204, 82, 60, 255)
EYE = (0, 0, 0, 255)
GRAY = (136, 136, 136, 255)
GRAY_D = (104, 104, 104, 255)
GRAY_L = (196, 196, 196, 255)
WHITE = (255, 255, 255, 255)
RED = (226, 64, 78, 255)
RED_D = (176, 40, 56, 255)
PINK = (240, 150, 150, 255)
BLUE = (96, 170, 236, 255)
BLUE_L = (170, 214, 250, 255)
CUP = (244, 240, 232, 255)
TEA = (150, 92, 54, 255)
STEAM = (210, 210, 210, 255)
PLAID = (98, 112, 196, 255)
PLAID_D = (72, 84, 160, 255)
PLAID_L = (150, 162, 226, 255)
STAR = (255, 205, 80, 255)


class F:
    """Один кадр: список прямоугольников (x0, y0, x1, y1, цвет), x1/y1 не включительно."""

    def __init__(self):
        self.ops = []

    def r(self, x0, y0, x1, y1, c):
        self.ops.append((x0, y0, x1, y1, c))

    def px(self, x, y, c):
        self.r(x, y, x + 1, y + 1, c)

    def img(self, dx=0):
        im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for x0, y0, x1, y1, c in self.ops:
            if x1 > x0 and y1 > y0:
                d.rectangle([x0 + dx, y0, x1 - 1 + dx, y1 - 1], fill=c)
        return im


# ---------------------------------------------------------------- краб
def crab(f, cx=20, lift=0, squash=0, stretch=0, arms=('out', 'out'), eyes='open',
         look=(0, 0), color=BODY, legs='stand', shade=None, step=0):
    """cx — центр тела по x, lift — высота прыжка, squash/stretch — сплющивание.
    Возвращает словарь с координатами тела, чтобы дорисовывать предметы."""
    bh = 12 - squash + stretch
    lh = 4 if legs == 'stand' else 2
    if squash >= 2:
        lh = 3
    bx = cx - 8
    by = GROUND - lh - bh - lift
    # тело
    f.r(bx, by, bx + 16, by + bh, color)
    if shade == 'left':
        f.r(bx, by, bx + 2, by + bh, SHADE)
    elif shade == 'right':
        f.r(bx + 14, by, bx + 16, by + bh, SHADE)
    # ножки
    ly = by + bh
    for i, lx in enumerate((0, 4, 10, 14)):
        off = 0
        if legs == 'walk':
            off = 1 if (i + step) % 2 else 0
        f.r(bx + lx, ly, bx + lx + 2, ly + lh - off, color if shade != 'left' or i else SHADE)
    # ручки
    for side, pose in (('l', arms[0]), ('r', arms[1])):
        for x0, y0, x1, y1 in arm_rects(pose):
            if side == 'r':
                f.r(bx + 16 + x0, by + y0, bx + 16 + x1, by + y1, color)
            else:
                f.r(bx - x1, by + y0, bx - x0, by + y1, color)
    draw_eyes(f, bx, by, eyes, look)
    return {'bx': bx, 'by': by, 'bh': bh, 'cx': cx}


def arm_rects(pose):
    """Прямоугольники правой ручки относительно правого края тела (x=0) и верха тела."""
    return {
        'out': [(0, 4, 4, 8)],
        'down': [(0, 6, 4, 10)],
        'low': [(0, 7, 3, 11)],
        'up': [(0, -3, 4, 3)],
        'wave': [(1, -6, 5, 0), (0, 0, 3, 3)],
        'high': [(-2, -4, 2, 0)],
        'front': [(-4, 6, 0, 10)],          # прижата к телу спереди
        'face': [(-5, 2, 0, 6)],            # у лица (часы, чашка)
        'type': [(0, 6, 6, 9)],             # тянется к клавиатуре
        'type2': [(0, 7, 6, 10)],
        'hold': [(0, 5, 3, 9)],
        'none': [],
    }[pose]


def draw_eyes(f, bx, by, kind, look=(0, 0)):
    lx, ly = bx + 2 + look[0], by + 2 + look[1]
    rx = bx + 12 + look[0]
    if kind == 'open':
        f.r(lx, ly, lx + 2, ly + 2, EYE); f.r(rx, ly, rx + 2, ly + 2, EYE)
    elif kind == 'wide':   # испуг: глаза больше, с бликом
        for x in (lx - 1, rx - 1):
            f.r(x, ly - 1, x + 3, ly + 2, EYE); f.px(x, ly - 1, WHITE)
    elif kind == 'blink':
        f.r(lx, ly + 1, lx + 2, ly + 2, EYE); f.r(rx, ly + 1, rx + 2, ly + 2, EYE)
    elif kind == 'happy':  # ^ ^
        for x in (lx - 1, rx - 1):
            f.px(x, ly + 1, EYE); f.px(x + 1, ly, EYE); f.px(x + 2, ly + 1, EYE)
    elif kind == 'angry':  # брови к центру
        f.r(lx, ly, lx + 2, ly + 2, EYE); f.r(rx, ly, rx + 2, ly + 2, EYE)
        f.px(lx - 1, ly - 2, EYE); f.px(lx, ly - 2, EYE); f.px(lx + 1, ly - 1, EYE); f.px(lx + 2, ly - 1, EYE)
        f.px(rx + 2, ly - 2, EYE); f.px(rx + 1, ly - 2, EYE); f.px(rx, ly - 1, EYE); f.px(rx - 1, ly - 1, EYE)
    elif kind == 'sad':    # брови домиком
        f.r(lx, ly, lx + 2, ly + 2, EYE); f.r(rx, ly, rx + 2, ly + 2, EYE)
        f.px(lx + 1, ly - 2, EYE); f.px(lx + 2, ly - 2, EYE); f.px(lx, ly - 1, EYE)
        f.px(rx - 1, ly - 2, EYE); f.px(rx, ly - 2, EYE); f.px(rx + 2, ly - 1, EYE)
    elif kind == 'cry':    # зажмурился
        for x in (lx - 1, rx - 1):
            f.px(x, ly, EYE); f.px(x + 1, ly + 1, EYE); f.px(x + 2, ly, EYE)
    elif kind == 'shut':
        f.r(lx - 1, ly + 1, lx + 3, ly + 2, EYE); f.r(rx - 1, ly + 1, rx + 3, ly + 2, EYE)


def blush(f, c):
    f.r(c['bx'] + 1, c['by'] + 5, c['bx'] + 4, c['by'] + 6, PINK)
    f.r(c['bx'] + 12, c['by'] + 5, c['bx'] + 15, c['by'] + 6, PINK)


# ---------------------------------------------------------------- предметы
def laptop_side(f, x, open_=True, y=GROUND):
    """Ноутбук в профиль, как в оригинале: основание + наклонённый экран, шарнир справа."""
    f.r(x, y - 1, x + 11, y, GRAY)
    if open_:
        for i in range(5):
            f.r(x + 10 + i, y - 3 - 2 * i, x + 11 + i, y - 1 - 2 * i, GRAY)
    else:
        f.r(x, y - 2, x + 11, y - 1, GRAY_D)


def laptop_flat(f, cx, y, crushed=0):
    """Закрытый ноутбук спереди (лежит плашмя), crushed — насколько помят."""
    w = 22 + crushed * 2
    h = 3 - min(crushed, 1)
    f.r(cx - w // 2, y - h, cx + w // 2, y, GRAY)
    f.r(cx - w // 2, y - h, cx + w // 2, y - h + 1, GRAY_L)
    if crushed:
        f.px(cx - 3, y - h, GRAY_D); f.px(cx + 4, y - h, GRAY_D); f.px(cx + 1, y - h + 1, GRAY_D)


def heart(f, x, y, big=False):
    rows = (['.##.##.', '#######', '#######', '.#####.', '..###..', '...#...'] if not big else
            ['.###.###.', '#########', '#########', '#########', '.#######.', '..#####..', '...###...', '....#....'])
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == '#':
                f.px(x + i, y + j, RED)
    f.px(x + 1, y + 1, WHITE)


def small_heart(f, x, y, c=RED):
    for i, j in ((0, 0), (2, 0), (0, 1), (1, 1), (2, 1), (1, 2)):
        f.px(x + i, y + j, c)


def cup(f, x, y, sip=False):
    """Чашка 6×5 с ручкой справа; y — низ."""
    f.r(x, y - 5, x + 6, y, CUP)
    f.r(x + 1, y - 5, x + 5, y - 4, TEA)
    f.r(x + 6, y - 4, x + 8, y - 3, CUP); f.r(x + 7, y - 4, x + 8, y - 1, CUP); f.r(x + 6, y - 2, x + 8, y - 1, CUP)


def steam(f, x, y, t):
    """Струйка пара, t — фаза (сдвиг вверх)."""
    for k in range(3):
        yy = y - ((t + k * 3) % 9)
        if yy < y - 8:
            continue
        xx = x + (1 if (yy // 2) % 2 else 0)
        f.r(xx, yy, xx + 1, yy + 2, STEAM)


def clock_on_arm(f, x, y):
    f.r(x, y, x + 4, y + 4, GRAY_D)
    f.r(x + 1, y + 1, x + 3, y + 3, WHITE)
    f.px(x + 1, y + 1, EYE)


def wall_clock(f, x, y, t):
    """Часы-будильник 7×7, стрелка крутится (t — 0..7)."""
    for i, row in enumerate(['.#####.', '#.....#', '#.....#', '#.....#', '#.....#', '#.....#', '.#####.']):
        for j, ch in enumerate(row):
            if ch == '#':
                f.px(x + j, y + i, GRAY_D)
    f.r(x + 1, y + 1, x + 6, y + 6, WHITE)
    f.px(x + 3, y + 3, EYE)
    hands = [(0, -2), (1, -2), (2, 0), (1, 2), (0, 2), (-1, 2), (-2, 0), (-1, -2)]
    hx, hy = hands[t % 8]
    f.px(x + 3 + (hx > 0) - (hx < 0), y + 3 + (hy > 0) - (hy < 0), EYE)
    f.px(x + 3 + hx, y + 3 + hy, EYE)
    f.r(x, y - 1, x + 2, y, GRAY_D); f.r(x + 5, y - 1, x + 7, y, GRAY_D)


def puff(f, x, y, s):
    """Облачко злости/пара, s — 0..2 размер."""
    c = STEAM
    if s == 0:
        f.r(x, y, x + 2, y + 2, c)
    elif s == 1:
        f.r(x - 1, y, x + 3, y + 2, c); f.r(x, y - 1, x + 2, y + 3, c)
    else:
        f.r(x - 2, y, x + 4, y + 2, c); f.r(x - 1, y - 1, x + 3, y + 3, c); f.r(x, y - 2, x + 2, y + 4, c)


def sparkle(f, x, y, s, c=STAR):
    if s == 0:
        f.px(x, y, c)
    else:
        f.px(x, y, c); f.px(x - 1, y, c); f.px(x + 1, y, c); f.px(x, y - 1, c); f.px(x, y + 1, c)


# ---------------------------------------------------------------- анимации
JUMP = [  # (lift, squash, stretch, legs) — прыжок с пружинкой
    (0, 2, 0, 'stand'), (0, 1, 0, 'stand'), (3, 0, 1, 'tuck'), (7, 0, 1, 'tuck'), (9, 0, 0, 'tuck'),
    (9, 0, 0, 'tuck'), (7, 0, 0, 'tuck'), (3, 0, 1, 'tuck'), (0, 2, 0, 'stand'), (0, 1, 0, 'stand'),
    (0, 0, 0, 'stand'), (0, 0, 0, 'stand'),
]


def anim_happy():
    frames = []
    for rep in range(3):
        for i, (lift, sq, st, legs) in enumerate(JUMP):
            f = F()
            arms = ('high', 'high') if lift >= 3 else (('out', 'out') if sq == 0 else ('down', 'down'))
            c = crab(f, lift=lift, squash=sq, stretch=st, legs=legs, arms=arms, eyes='happy')
            if lift >= 7:
                sparkle(f, 4, 8 - (i % 2), i % 2)
                sparkle(f, 35, 6 + (i % 2), (i + 1) % 2)
            frames.append(f)
    return frames


def anim_hello():
    frames = []
    seq = ['wave', 'up', 'wave', 'up', 'wave', 'up', 'wave', 'up']
    eyes = ['open'] * 30
    eyes[20] = eyes[21] = 'blink'
    for i in range(30):
        f = F()
        pose = seq[(i // 2) % len(seq)] if i < 22 else 'out'
        bob = 1 if (i // 4) % 2 and i < 22 else 0
        crab(f, squash=bob, arms=('out', pose), eyes='happy' if i < 22 and (i // 6) % 2 else eyes[i])
        frames.append(f)
    return frames


def anim_heart():
    frames = []
    beat = [0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0]
    for i in range(36):
        f = F()
        b = beat[i % 12]
        c = crab(f, squash=1 if b and i % 12 in (1, 5) else 0, arms=('front', 'front'), eyes='happy')
        blush(f, c)
        cx = c['cx']
        if b:
            heart(f, cx - 4, c['by'] + 4, big=True)
        else:
            heart(f, cx - 3, c['by'] + 5)
        # маленькие сердечки улетают вверх
        for k, (sx, ph) in enumerate(((3, 0), (34, 12), (7, 24))):
            t = (i - ph) % 36
            if t < 18:
                small_heart(f, sx + (1 if (t // 3) % 2 else 0), 22 - t, PINK if t > 12 else RED)
        frames.append(f)
    return frames


def anim_cry():
    frames = []
    for i in range(32):
        f = F()
        sob = 1 if i % 8 in (2, 3, 6, 7) else 0
        c = crab(f, squash=sob, arms=('low', 'low') if sob else ('down', 'down'), eyes='cry')
        bx, by = c['bx'], c['by']
        # ручьи слёз: капли бегут вниз и разлетаются в стороны
        for ex, side in ((bx + 2, -1), (bx + 13, 1)):
            for k in range(3):
                t = (i + k * 4) % 12
                x = ex + side * (t // 3)
                y = by + 4 + t
                f.r(x, y, x + 1, y + 2, BLUE if t < 8 else BLUE_L)
        # лужица растёт и сбрасывается
        p = (i % 32) // 8
        f.r(20 - 6 - p * 2, GROUND, 20 + 6 + p * 2, GROUND + 1, BLUE_L)
        if i % 8 < 4:
            f.r(bx + 6, by + 8, bx + 10, by + 9, EYE)   # всхлип — ротик
        frames.append(f)
    return frames


def anim_angry():
    frames = []
    for i in range(30):
        f = F()
        stomp = i % 6
        lift = (0, 2, 3, 2, 0, 0)[stomp]
        c = crab(f, lift=lift, squash=2 if stomp == 4 else 0, legs='tuck' if lift else 'stand',
                 arms=('up', 'up') if (i // 3) % 2 else ('high', 'high'),
                 eyes='angry', color=ANGRY if (i // 3) % 2 else BODY)
        by = c['by']
        # пар из макушки
        for k, (px_, ph) in enumerate(((14, 0), (26, 5))):
            t = (i + ph) % 10
            if t < 8:
                puff(f, px_ + (k * 2 - 1) * (t // 3), by - 3 - t, min(t // 3, 2))
        if stomp == 4:  # пыль от удара
            f.r(4, GROUND - 1, 7, GROUND, STEAM); f.r(33, GROUND - 1, 36, GROUND, STEAM)
            f.px(2, GROUND - 3, STEAM); f.px(37, GROUND - 3, STEAM)
        frames.append(f)
    return frames


def anim_scared():
    frames = []
    shake = [-1, 1, -1, 1, 0, -1, 1, -1, 1, -1, 1, 0, 0, 0, -1, 1, -1, 1, -1, 1, 0, 0, 1, -1]
    for i in range(24):
        f = F()
        dx = shake[i]
        bx, top = 20 - 11 + dx, 14
        # плед: купол поверх краба, торчат только глаза и ножки
        f.r(bx + 5, top - 1, bx + 17, top, PLAID)
        f.r(bx + 2, top, bx + 20, top + 2, PLAID)
        f.r(bx, top + 2, bx + 22, GROUND - 5, PLAID)
        f.r(bx - 1, GROUND - 5, bx + 23, GROUND - 3, PLAID)
        for k in (3, 9, 13, 19):   # клетка
            f.r(bx + k, top + (1 if 3 < k < 19 else 3), bx + k + 1, GROUND - 3, PLAID_D)
        for yy in (top + 3, top + 12, top + 17):
            f.r(bx + (0 if yy > top + 2 else 2), yy, bx + 22, yy + 1, PLAID_D)
        f.r(bx + 5, top - 1, bx + 17, top, PLAID_L)
        f.r(bx + 2, top, bx + 5, top + 1, PLAID_L)
        f.r(bx - 1, GROUND - 4, bx + 23, GROUND - 3, PLAID_D)   # край
        for k in range(0, 24, 3):  # бахрома
            f.r(bx - 1 + k, GROUND - 3, bx + k, GROUND - 2, PLAID_L)
        # щель, из которой смотрят глаза
        f.r(bx + 4, top + 5, bx + 18, top + 9, (24, 20, 40, 255))
        look = (1 if (i // 6) % 2 else -1)
        blinking = i in (12, 13)
        for ex in (bx + 6 + look, bx + 14 + look):
            if blinking:
                f.r(ex, top + 7, ex + 2, top + 8, WHITE)
            else:
                f.r(ex, top + 6, ex + 2, top + 8, WHITE)
                f.px(ex + (1 if look > 0 else 0), top + 7, EYE)
        # ножки дрожат
        for k, lx in enumerate((4, 8, 14, 18)):
            off = (i + k) % 2
            f.r(bx + lx - 1 + dx * 0, GROUND - 3, bx + lx + 1, GROUND - off, BODY)
        if i % 12 in (0, 1, 2):   # капелька пота
            f.r(bx + 22, top + 2 + i % 12, bx + 23, top + 4 + i % 12, BLUE_L)
        frames.append(f)
    return frames


def anim_tea():
    frames = []
    # 0-11 держит у пояса, 12-15 поднимает, 16-23 пьёт, 24-27 опускает, 28-35 «ах» с закрытыми глазами
    for i in range(36):
        f = F()
        if i < 12 or i >= 28:
            phase = 'hold'
        elif i < 16 or 24 <= i < 28:
            phase = 'mid'
        else:
            phase = 'sip'
        eyes = 'open' if i < 12 else ('shut' if phase != 'hold' else 'happy')
        if i in (6, 7):
            eyes = 'blink'
        arm = {'hold': 'front', 'mid': 'face', 'sip': 'face'}[phase]
        c = crab(f, arms=('out', arm), eyes=eyes, squash=1 if 28 <= i < 31 else 0)
        bx, by = c['bx'], c['by']
        if phase == 'hold':
            cup(f, bx + 9, by + 11)
            steam(f, bx + 11, by + 5, i)
        elif phase == 'mid':
            cup(f, bx + 7, by + 10)
            steam(f, bx + 9, by + 4, i)
        else:
            cup(f, bx + 5, by + 9)
        if 28 <= i < 36:
            blush(f, c)
            if i >= 30:
                small_heart(f, bx + 18 + (i - 30) // 2, by - 2 - (i - 30), PINK)
        frames.append(f)
    return frames


def anim_laptop():
    """Сидит за ноутбуком и печатает, иногда моргает и радуется."""
    frames = []
    for i in range(32):
        f = F()
        tap = i % 2
        eyes = 'open'
        if i in (10, 11):
            eyes = 'blink'
        if 24 <= i < 28:
            eyes = 'happy'
        c = crab(f, cx=14, arms=('out', 'type2' if tap else 'type'), eyes=eyes, look=(1, 0), shade='left')
        laptop_side(f, 25)
        # «код» вылетает из экрана
        for k in range(3):
            t = (i * 2 + k * 5) % 15
            if t < 12:
                col = (GRAY_L, STAR, BLUE)[k]
                f.r(34 + k * 2, 22 - t, 35 + k * 2, 23 - t, col)
        frames.append(f)
    return frames


def anim_watch():
    """Смотрит на часы — пишет код — снова часы — снова пишет (по кругу)."""
    frames = []
    for i in range(36):
        f = F()
        ph = i % 18
        watching = ph < 7
        if watching:
            raised = 1 <= ph <= 5
            look = (-1, -1) if raised else (0, 0)
            c = crab(f, cx=14, arms=('up' if raised else 'out', 'out'), eyes='open', look=look, shade='left')
            if raised:
                clock_on_arm(f, c['bx'] - 4, c['by'] - 1)
                if ph in (3, 4):  # «!» над головой
                    f.r(c['cx'] - 1, c['by'] - 8, c['cx'] + 1, c['by'] - 4, RED)
                    f.r(c['cx'] - 1, c['by'] - 3, c['cx'] + 1, c['by'] - 2, RED)
        else:
            tap = ph % 2
            c = crab(f, cx=14, arms=('out', 'type2' if tap else 'type'), eyes='blink' if ph == 12 else 'open',
                     look=(1, 1), shade='left')
            for k in range(2):
                t = (ph * 2 + k * 6) % 12
                if t < 9:
                    f.r(35 + k * 2, 22 - t, 36 + k * 2, 23 - t, (GRAY_L, BLUE)[k])
            if ph >= 13:  # пот — торопится
                f.r(c['bx'] - 1, c['by'] + (ph - 13), c['bx'], c['by'] + 2 + (ph - 13), BLUE_L)
        laptop_side(f, 25)
        frames.append(f)
    return frames


def anim_rage_laptop():
    """Злой достаёт ноутбук, бросает, прыгает по нему, поднимает — и по новой."""
    frames = []
    # 0-5: достаёт из-за спины, 6-7: бросает, 8-27: три прыжка, 28-35: поднимает и прячет
    for i in range(36):
        f = F()
        crushed = 0
        if i < 6:
            # ноутбук выезжает из-за спины (рисуем до краба — он сзади)
            g = F()
            c = crab(g, arms=('out', 'hold'), eyes='angry')
            x = c['bx'] + 18 - max(0, 5 - i) * 2
            f.r(x, c['by'] + 1, x + 2, c['by'] + 10, GRAY)
            f.r(x + 1, c['by'] + 1, x + 2, c['by'] + 10, GRAY_L)
            f.ops += g.ops
        elif i < 8:
            c = crab(f, arms=('out', 'down'), eyes='angry', squash=1)
            laptop_flat(f, 20, GROUND if i == 7 else GROUND - 4)
        elif i < 28:
            k = i - 8
            j = k % 7
            lift = (0, 4, 8, 9, 6, 0, 0)[j]
            sq = 2 if j == 5 else 0
            crushed = min(2, (k + 2) // 7)
            c = crab(f, lift=lift + 3, squash=sq, legs='tuck' if lift else 'stand',
                     arms=('high', 'high') if lift else ('down', 'down'),
                     eyes='angry', color=ANGRY if j in (4, 5) else BODY)
            laptop_flat(f, 20, GROUND, crushed=crushed if j >= 5 or k >= 7 else max(0, crushed - 1))
            if j == 5:   # искры
                for sx, sy in ((3, 33), (36, 32), (6, 29), (34, 28)):
                    sparkle(f, sx, sy, 1, STAR)
        else:
            k = i - 28
            g = F()
            c = crab(g, lift=3 if k < 3 else 0, arms=('out', 'down' if k < 4 else 'hold'), eyes='angry')
            if k < 4:
                f.ops += g.ops
                laptop_flat(f, 20, GROUND, crushed=2)
            else:  # убирает обратно за спину
                x = c['bx'] + 18 - (k - 4) * 2
                f.r(x, c['by'] + 1, x + 2, c['by'] + 10, GRAY)
                f.r(x + 1, c['by'] + 1, x + 2, c['by'] + 10, GRAY_L)
                f.ops += g.ops
        frames.append(f)
    return frames


ANIMS = {
    'happy': anim_happy,
    'hello': anim_hello,
    'heart': anim_heart,
    'cry': anim_cry,
    'angry': anim_angry,
    'scared': anim_scared,
    'tea': anim_tea,
    'laptop': anim_laptop,
    'watch-code': anim_watch,
    'rage-laptop': anim_rage_laptop,
}


# ---------------------------------------------------------------- вывод
def render(frames, scale, size=None):
    out = []
    for fr in frames:
        im = fr.img().resize((W * scale, W * scale), Image.NEAREST)
        if size and size < W * scale:   # эмодзи: крупно рисуем и аккуратно уменьшаем
            out.append(im.resize((size, size), Image.LANCZOS))
            continue
        if size and size != W * scale:
            canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            o = (size - W * scale) // 2
            canvas.paste(im, (o, o))
            im = canvas
        out.append(im)
    return out


def save_gif(frames, path):
    ims = render(frames, 12)
    conv = ims
    conv[0].save(path, save_all=True, append_images=conv[1:], duration=FRAME_MS, loop=0,
                 disposal=2, transparency=0, optimize=False)


def save_webm(frames, path, scale, size, crf):
    ims = render(frames, scale, size)
    with tempfile.TemporaryDirectory() as d:
        for i, im in enumerate(ims):
            im.save(os.path.join(d, f'{i:03d}.png'))
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(1000 / FRAME_MS),
                        '-i', os.path.join(d, '%03d.png'), '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p',
                        '-b:v', '0', '-crf', str(crf), '-an', '-auto-alt-ref', '0', path], check=True)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    names = sys.argv[2:] or list(ANIMS)
    for sub in ('gif', 'emoji', 'stickers'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    for name in names:
        frames = ANIMS[name]()
        assert len(frames) * FRAME_MS <= 3000, (name, len(frames))
        save_gif(frames, os.path.join(out, 'gif', f'{name}.gif'))
        save_webm(frames, os.path.join(out, 'emoji', f'{name}.webm'), 10, 100, 30)
        save_webm(frames, os.path.join(out, 'stickers', f'{name}.webm'), 12, 512, 30)
        print(name, len(frames), 'frames')


if __name__ == '__main__':
    main()
