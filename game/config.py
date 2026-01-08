import pygame

# Screen settings
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 768
FPS = 60
TITLE = "鳌太行者 (Aotai Walker)"

# Colors (Modern Palette)
WHITE = (236, 240, 241)
BLACK = (44, 62, 80)
GRAY = (149, 165, 166)
DARK_GRAY = (52, 73, 94)
LIGHT_GRAY = (189, 195, 199)

RED = (231, 76, 60)
GREEN = (46, 204, 113)
BLUE = (52, 152, 219)
YELLOW = (241, 196, 15)
ORANGE = (230, 126, 34)
PURPLE = (155, 89, 182)
GOLD = (255, 215, 0)
CYAN = (0, 255, 255)

BG_COLOR = (44, 62, 80)      # Dark Blue-Gray
PANEL_COLOR = (52, 73, 94)   # Slightly lighter
TEXT_COLOR = (236, 240, 241) # Off-white
ACCENT_COLOR = (26, 188, 156) # Teal

# Fonts
FONT_NAME = "SimHei" # Use a font that supports Chinese
FONT_SIZE_NORMAL = 20
FONT_SIZE_TITLE = 40
FONT_SIZE_SMALL = 16
FONT_SIZE_LARGE = 28

# Game Constants
EMOJI_DIR = "openmoji-svg-color"
START_MONEY = 10000
MAX_WEIGHT_BASE = 10.0
DAILY_ACTION_POINTS = 10

# Stats Limits
MAX_STAMINA = 100
MAX_HUNGER = 100
MAX_THIRST = 100
MAX_SANITY = 100
MAX_HEALTH = 100
MIN_TEMP = 35.0
MAX_TEMP = 40.0

# Characters
CHARACTERS = {
    "xiaomou": {
        "name": "小牟",
        "desc": "户外强驴，体力充沛。体力上限150，体力消耗-10%。",
        "buffs": {"max_stamina": 150, "stamina_cost_mult": 0.9}
    },
    "xiaochen": {
        "name": "小陈",
        "desc": "耐饿奇人。饥饿消耗减半。",
        "buffs": {"hunger_drain_mult": 0.5}
    },
    "menglong": {
        "name": "猛龙过江",
        "desc": "骑行大佬。拥有单车，移动速度快，体力消耗少。",
        "buffs": {"move_speed_mult": 1.2, "stamina_cost_mult": 0.8}
    },
    "student": {
        "name": "女大学生",
        "desc": "拥有一次瞬间移动到下一站的能力。",
        "buffs": {"special_ability": "teleport"}
    }
}

# Seasons
SEASONS = {
    "spring": {"name": "春季", "desc": "万物复苏，气温适宜。", "base_temp": 15},
    "summer": {"name": "夏季", "desc": "酷热难耐，多雷雨。", "base_temp": 25},
    "autumn": {"name": "秋季", "desc": "秋高气爽，景色宜人。", "base_temp": 10},
    "winter": {"name": "冬季", "desc": "寒风刺骨，大雪封山。", "base_temp": -5}
}
