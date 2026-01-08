import pygame
import os
from .config import *
from .visualizer import EnvironmentVisualizer

EFFECT_TRANSLATIONS = {
    "night_temperature_loss": "夜间失温减少",
    "sanity_recovery_night": "夜间SAN值恢复",
    "can_camp": "允许扎营",
    "can_cook": "允许烹饪",
    "fuel": "燃料值",
    "move_cost_snow": "雪地移动消耗减少",
    "capacity_bonus": "负重上限增加",
    "hunger": "饥饿恢复",
    "thirst": "口渴恢复",
    "stamina": "体力恢复",
    "sanity": "SAN值恢复",
    "sanity_recovery": "SAN值恢复",
    "heal": "健康恢复",
    "warmth": "保暖效果",
    "thirst_recovery_bonus": "口渴恢复加成",
    "can_start_fire": "允许生火",
    "temp_protection": "保暖等级",
    "rain_protection": "防雨等级",
    "stamina_cost_reduction": "体力消耗减少",
    "can_move_night": "允许夜行",
    "power": "电量",
    "status_cure": "治愈状态",
    "lost_chance_reduction": "迷路概率降低",
    "repair_bonus": "修复效果",
    "temp": "体温恢复",
    "needs_cooking": "需要烹饪",
    "spoil_chance": "每日腐坏概率"
}

TERRAIN_TRANSLATIONS = {
    "forest": "森林",
    "rocky": "乱石坡",
    "ridge": "山脊",
    "danger": "危险路段",
    "meadow": "草甸",
    "normal": "平路"
}

WEATHER_TRANSLATIONS = {
    "sunny": "晴朗",
    "cloudy": "多云",
    "fog": "大雾",
    "rain": "小雨",
    "snow": "大雪",
    "storm": "暴风雪"
}

class Button:
    def __init__(self, x, y, width, height, text, callback, color=PANEL_COLOR, hover_color=ACCENT_COLOR, text_color=TEXT_COLOR, icon=None, tooltip=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.icon = icon
        self.tooltip = tooltip
        self.is_hovered = False
        self.icon_surf = None

    def draw(self, screen, font, ui_ref=None):
        color = self.hover_color if self.is_hovered else self.color
        # Draw rounded rect
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, LIGHT_GRAY, self.rect, 2, border_radius=8) # Border
        
        text_x_offset = 0
        if self.icon and ui_ref:
            emoji_surf = ui_ref.get_emoji_surface(self.icon, 24)
            if emoji_surf:
                screen.blit(emoji_surf, (self.rect.x + 10, self.rect.centery - 12))
                text_x_offset = 30

        # Handle multiline text (simple wrap)
        if len(self.text) > 20 and " " not in self.text: # Simple heuristic for long Chinese text
             # Just render as is for now, or use smaller font?
             # Let's just render centered.
             pass
             
        text_surf = font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=(self.rect.centerx + text_x_offset // 2, self.rect.centery))
        screen.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered and event.button == 1:
                if self.callback:
                    self.callback()
                return True
        return False

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, initial_val=0):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.dragging = False
        self.handle_rect = pygame.Rect(x, y, 20, h)
        self.update_handle()

    def update_handle(self):
        range_val = self.max_val - self.min_val
        if range_val == 0:
            pct = 0
        else:
            pct = (self.value - self.min_val) / range_val
        
        handle_x = self.rect.x + pct * (self.rect.width - self.handle_rect.width)
        self.handle_rect.x = handle_x

    def draw(self, screen):
        # Track
        pygame.draw.rect(screen, DARK_GRAY, self.rect, border_radius=4)
        pygame.draw.rect(screen, GRAY, self.rect, 1, border_radius=4)
        
        # Handle
        color = ACCENT_COLOR if self.dragging else LIGHT_GRAY
        pygame.draw.rect(screen, color, self.handle_rect, border_radius=4)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.dragging = True
                return True
            elif self.rect.collidepoint(event.pos):
                self.dragging = True
                self.update_value_from_pos(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.update_value_from_pos(event.pos[0])
                return True
        return False

    def update_value_from_pos(self, x):
        rel_x = x - self.rect.x - self.handle_rect.width / 2
        pct = max(0, min(1, rel_x / (self.rect.width - self.handle_rect.width)))
        self.value = self.min_val + pct * (self.max_val - self.min_val)
        self.update_handle()

class UI:
    def __init__(self, screen):
        self.screen = screen
        
        # Font initialization with web/local fallback
        font_paths = ["simhei.ttf", "msyh.ttc", "arial.ttf"]
        self.font = None
        
        # Try local files first (essential for web)
        for path in font_paths:
            if os.path.exists(path):
                try:
                    self.font = pygame.font.Font(path, FONT_SIZE_NORMAL)
                    self.title_font = pygame.font.Font(path, FONT_SIZE_TITLE)
                    self.small_font = pygame.font.Font(path, FONT_SIZE_SMALL)
                    self.large_font = pygame.font.Font(path, FONT_SIZE_LARGE)
                    break
                except:
                    continue
        
        if not self.font:
            try:
                # Try to load a font that supports Chinese from system
                self.font = pygame.font.SysFont("Microsoft YaHei", FONT_SIZE_NORMAL)
                self.title_font = pygame.font.SysFont("Microsoft YaHei", FONT_SIZE_TITLE, bold=True)
                self.small_font = pygame.font.SysFont("Microsoft YaHei", FONT_SIZE_SMALL)
                self.large_font = pygame.font.SysFont("Microsoft YaHei", FONT_SIZE_LARGE)
            except:
                self.font = pygame.font.SysFont("SimHei", FONT_SIZE_NORMAL)
                self.title_font = pygame.font.SysFont("SimHei", FONT_SIZE_TITLE)
                self.small_font = pygame.font.SysFont("SimHei", FONT_SIZE_SMALL)
                self.large_font = pygame.font.SysFont("SimHei", FONT_SIZE_LARGE)
            
        self.buttons = []
        self.sliders = []
        self.message_log = []
        self.emoji_cache = {} # (emoji_str, size) -> surface
        
        # Initialize Visualizer
        # Position will be updated in draw_main_view if needed, but we set initial here
        self.visualizer = EnvironmentVisualizer(40, 320, 640, 150)

    def get_emoji_surface(self, emoji_str, size=24):
        cache_key = (emoji_str, size)
        if cache_key in self.emoji_cache:
            return self.emoji_cache[cache_key]

        # Convert emoji to hex string
        # OpenMoji format: HEX-HEX.svg (uppercase)
        # We try with and without FE0F (variation selector)
        
        def char_to_hex(c):
            return f"{ord(c):X}"

        hex_parts = [char_to_hex(c) for c in emoji_str]
        
        # Try combinations
        filenames = [
            "-".join(hex_parts), # Full sequence
            "-".join([h for h in hex_parts if h != "FE0F"]) # Without variation selector
        ]
        
        for fname in filenames:
            path = os.path.join(EMOJI_DIR, f"{fname}.svg")
            if os.path.exists(path):
                try:
                    surf = pygame.image.load(path)
                    surf = pygame.transform.smoothscale(surf, (size, size))
                    self.emoji_cache[cache_key] = surf
                    return surf
                except:
                    continue
        
        return None

    def draw_emoji(self, emoji, x, y, size=24):
        surf = self.get_emoji_surface(emoji, size)
        if surf:
            self.screen.blit(surf, (x, y))
            return size + 5
        return 0

    def add_message(self, message):
        self.message_log.append(message)
        if len(self.message_log) > 8:
            self.message_log.pop(0)

    def draw_text(self, text, x, y, font=None, color=TEXT_COLOR, center=False):
        if font is None:
            font = self.font
        try:
            surf = font.render(text, True, color)
        except:
            surf = self.font.render(text, True, color)
            
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surf, rect)

    def draw_progress_bar(self, x, y, w, h, current, max_val, color, label=None, icon=None):
        # Background
        pygame.draw.rect(self.screen, DARK_GRAY, (x, y, w, h), border_radius=4)
        
        # Fill
        ratio = max(0, min(1, current / max_val)) if max_val > 0 else 0
        fill_w = int(w * ratio)
        pygame.draw.rect(self.screen, color, (x, y, fill_w, h), border_radius=4)
        
        # Border
        pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, w, h), 1, border_radius=4)
        
        # Label
        if label:
            offset = 0
            if icon:
                offset = self.draw_emoji(icon, x, y - 25, 20)
            
            self.draw_text(label, x + offset + 5, y - 20, self.small_font, color=color)
            val_text = f"{int(current)}/{int(max_val)}"
            self.draw_text(val_text, x + w - 60, y - 20, self.small_font, color=WHITE)

    def draw_panel(self, x, y, w, h, color=PANEL_COLOR, border_color=DARK_GRAY):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=10)

    def draw_status_panel(self, game_state, item_system):
        # Top Bar
        self.draw_panel(10, 10, SCREEN_WIDTH - 20, 100, PANEL_COLOR)

        # Stats with Progress Bars
        y = 40
        bar_w = 140
        bar_h = 10
        gap = 200
        
        # Row 1: Bars
        self.draw_progress_bar(30, y, bar_w, bar_h, game_state.stamina, MAX_STAMINA, YELLOW, "体力", "⚡")
        self.draw_progress_bar(30 + gap, y, bar_w, bar_h, game_state.hunger, MAX_HUNGER, ORANGE, "饥饿", "🍗")
        self.draw_progress_bar(30 + gap*2, y, bar_w, bar_h, game_state.thirst, MAX_THIRST, BLUE, "口渴", "💧")
        self.draw_progress_bar(30 + gap*3, y, bar_w, bar_h, game_state.sanity, MAX_SANITY, PURPLE, "SAN", "🧠")
        self.draw_progress_bar(30 + gap*4, y, bar_w, bar_h, game_state.health, MAX_HEALTH, GREEN, "健康", "❤️")
        
        # Temperature - Text only mode (Placed at the end)
        t_icon = "🌡️"
        t_w = self.draw_emoji(t_icon, 30 + gap*5, y - 5, 20)
        self.draw_text("体温", 30 + gap*5 + t_w + 5, y, self.small_font, color=RED)
        
        # Color code temperature
        temp_color = GREEN
        if game_state.temperature < 35.0: temp_color = RED
        elif game_state.temperature < 36.5: temp_color = ORANGE
        
        self.draw_text(f"{game_state.temperature:.1f}°C", 30 + gap*5 + 70, y, self.small_font, color=temp_color)

        # Row 2: Info
        y = 75
        info_gap = 220
        
        self.draw_emoji("📅", 30, y - 5, 20)
        self.draw_text(f"Day {game_state.game_time} {game_state.day_time}:00", 55, y, self.small_font)
        
        self.draw_emoji("🌤️", 30 + info_gap, y - 5, 20)
        weather_cn = WEATHER_TRANSLATIONS.get(game_state.weather, game_state.weather)
        self.draw_text(f"天气: {weather_cn}", 55 + info_gap, y, self.small_font)
        
        # Draw Money Bag
        money_icon_w = self.draw_emoji("💰", 30 + info_gap*2, y - 5, 20)
        if not money_icon_w: # Fallback if SVG not found
             self.draw_text("💰", 30 + info_gap*2, y, self.small_font)
        self.draw_text(f"资金: {game_state.money}", 55 + info_gap*2, y, self.small_font)
        
        # Calculate max weight for display
        # We need item_system to check backpack bonus
        # But draw_status_panel receives item_system
        max_w = MAX_WEIGHT_BASE
        for i_id in game_state.inventory:
            item = item_system.get_item(i_id)
            if item:
                max_w = max(max_w, MAX_WEIGHT_BASE + item['effects'].get('capacity_bonus', 0))

        weight = item_system.calculate_weight(game_state.inventory)
        color_w = RED if weight > max_w else TEXT_COLOR
        self.draw_emoji("🎒", 30 + info_gap*3, y - 5, 20)
        self.draw_text(f"负重: {weight:.1f}/{max_w:.0f}kg", 55 + info_gap*3, y, self.small_font, color=color_w)
        
        self.draw_emoji("👣", 30 + info_gap*4, y - 5, 20)
        self.draw_text(f"行动点: {game_state.action_points}", 55 + info_gap*4, y, self.small_font)
        
        # Karma
        self.draw_emoji("🌟", 30 + info_gap*5, y - 5, 20)
        self.draw_text(f"人品: {game_state.karma}", 55 + info_gap*5, y, self.small_font)

    def draw_main_view(self, game_state, map_system):
        # Top: Journey Progress (Full Width)
        # Status panel is 0-100.
        # Progress bar: 110-170 (60px height)
        self.draw_journey_progress(game_state, map_system, 10, 110, SCREEN_WIDTH - 20)

        # Main Content Area starts at 180
        content_y = 180
        content_h = SCREEN_HEIGHT - content_y - 10
        
        # Left Panel: Location & Description & Log
        left_w = 700
        self.draw_panel(10, content_y, left_w, content_h)
        
        node = map_system.get_node(game_state.current_node_id)
        if node:
            # Location Header
            # Pin Icon
            self.draw_emoji("📍", 40, content_y + 20, 40)
            # Name
            self.draw_text(f"{node['name']}", 90, content_y + 25, self.title_font, center=False)
            
            # Info Line (Icons separated)
            y_info = content_y + 70
            
            # Altitude
            w = self.draw_emoji("⛰️", 40, y_info, 24)
            self.draw_text(f"海拔: {node['altitude']}m", 40 + w + 5, y_info, self.font)
            
            # Terrain
            x_terrain = 200
            terrain_cn = TERRAIN_TRANSLATIONS.get(node['terrain'], node['terrain'])
            w = self.draw_emoji("🌲", x_terrain, y_info, 24)
            self.draw_text(f"地形: {terrain_cn}", x_terrain + w + 5, y_info, self.font)
            
            # Weather
            x_weather = 380
            weather_cn = WEATHER_TRANSLATIONS.get(game_state.weather, game_state.weather)
            w = self.draw_emoji("🌤️", x_weather, y_info, 24)
            self.draw_text(f"天气: {weather_cn}", x_weather + w + 5, y_info, self.font)

            # Row 2: Wind & Temp
            y_env = y_info + 35
            
            # Env Temp
            env_temp = getattr(game_state, 'env_temp', 20.0)
            w = self.draw_emoji("🌡️", 40, y_env, 24)
            self.draw_text(f"气温: {env_temp:.1f}°C", 40 + w + 5, y_env, self.font)
            
            # Wind
            wind_level = getattr(game_state, 'wind_level', 1)
            w = self.draw_emoji("💨", 200, y_env, 24)
            self.draw_text(f"风力: {wind_level}级", 200 + w + 5, y_env, self.font)
            
            # Hint - Removed as requested (now hover)
            # self.draw_text("(点击图标查看环境影响)", 380, y_env, self.small_font, color=GRAY)
            
            # Visualizer Scene
            viz_y = content_y + 140
            viz_h = 150
            self.visualizer.rect.y = viz_y
            self.visualizer.rect.height = viz_h
            self.visualizer.draw(self.screen, game_state, map_system)
            
            # Description Overlay (Semi-transparent bottom)
            desc_h = 40
            desc_y = viz_y + viz_h - desc_h
            s = pygame.Surface((640, desc_h))
            s.set_alpha(180)
            s.fill((0, 0, 0))
            self.screen.blit(s, (40, desc_y))
            
            # Description Text
            words = node['description']
            self.draw_text(words, 50, desc_y + 10, self.font, color=WHITE)
            
            # Status Message
            self.draw_text(game_state.status_message, 360, viz_y + viz_h + 10, self.font, color=RED, center=True)

        # Check hovers for tooltips
        mx, my = pygame.mouse.get_pos()
        tooltip_text = None
        
        # Altitude: x ~40-180, y ~250-280 (Same as Terrain Y range, but X is left)
        # Wait, in draw_main_view:
        # Altitude: y_info = content_y + 70 = 180 + 70 = 250.
        # x = 40.
        # So Altitude is at (40, 250).
        if 40 <= mx <= 180 and 250 <= my <= 280:
            node = map_system.get_node(game_state.current_node_id)
            alt = node.get('altitude', 0)
            msg = f"当前海拔: {alt}m。"
            if alt > 3000:
                msg += "\n高海拔区域，气温较低，容易引发高原反应。"
            elif alt > 2500:
                msg += "\n海拔较高，注意保暖。"
            else:
                msg += "\n海拔适中，含氧量充足。"
            tooltip_text = f"【海拔】{msg}"

        # Terrain: x ~200-350, y ~250-280
        elif 200 <= mx <= 350 and 250 <= my <= 280:
            node = map_system.get_node(game_state.current_node_id)
            terrain = node.get('terrain', 'normal')
            info = {
                "forest": "森林: 移动速度一般，体力消耗正常。",
                "rocky": "乱石坡: 移动困难，体力消耗增加，易受伤。",
                "ridge": "山脊: 视野开阔，但风大，体力消耗略增。",
                "danger": "危险路段: 极难通行，体力消耗极大，需小心。",
                "meadow": "草甸: 地势平缓，移动较快。",
                "normal": "平路: 标准移动速度。"
            }
            tooltip_text = f"【地形】{info.get(terrain, terrain)}"
            
        # Weather: x ~380-530, y ~250-280
        elif 380 <= mx <= 530 and 250 <= my <= 280:
            weather = game_state.weather
            info = {
                "sunny": "晴朗: 视野好，气温较高，体力消耗正常。",
                "cloudy": "多云: 气温适宜。",
                "fog": "大雾: 视野受限，容易迷路，气温略低。",
                "rain": "小雨: 湿滑，气温降低，体力消耗增加。",
                "snow": "大雪: 积雪难行，极寒，体力消耗大。",
                "storm": "暴风雪: 极度危险！气温骤降，寸步难行，请立即扎营！"
            }
            tooltip_text = f"【天气】{info.get(weather, weather)}"
            
        # Temp: x ~40-180, y ~285-315
        elif 40 <= mx <= 180 and 285 <= my <= 315:
            temp = getattr(game_state, 'env_temp', 20.0)
            msg = f"当前气温 {temp:.1f}°C。"
            if temp < -20: msg += "\n极寒！面临严重失温风险，体力流失极快！"
            elif temp < -10: msg += "\n严寒。需注意保暖，体力消耗增加。"
            elif temp < 0: msg += "\n寒冷。气温在冰点以下。"
            elif temp > 30: msg += "\n炎热。注意防暑补水。"
            else: msg += "\n气温尚可。"
            tooltip_text = f"【气温】{msg}"
            
        # Wind: x ~200-350, y ~285-315
        elif 200 <= mx <= 350 and 285 <= my <= 315:
            wind = getattr(game_state, 'wind_level', 1)
            msg = f"当前风力 {wind}级。"
            if wind >= 8: msg += "\n狂风！行走极其困难，体感温度极低！"
            elif wind >= 6: msg += "\n强风。阻力大，消耗更多体力。"
            elif wind >= 4: msg += "\n和风。有明显阻力。"
            else: msg += "\n微风。对行动影响不大。"
            tooltip_text = f"【风力】{msg}"
            
        if tooltip_text:
            self.draw_tooltip(tooltip_text, mx + 15, my + 15)

        # Log Section (Bottom of Left Panel)
        log_y = content_y + 330
        # Separator
        pygame.draw.line(self.screen, GRAY, (30, log_y), (690, log_y), 2)
        
        # Log Header
        w = self.draw_emoji("📜", 30, log_y + 10, 24)
        self.draw_text("消息记录", 30 + w + 5, log_y + 10, color=ACCENT_COLOR)
        
        msg_y = log_y + 40
        for msg in reversed(self.message_log):
            # Using plain dash instead of bullet chart to ensure rendering
            self.draw_text(f"- {msg}", 30, msg_y, self.small_font)
            msg_y += 20
            if msg_y > content_y + content_h - 20: break

        # Right Panel: Actions & Inventory
        right_x = 720
        right_w = SCREEN_WIDTH - 730
        self.draw_panel(right_x, content_y, right_w, content_h)
        
        # Header with Icon
        header_x = right_x + right_w//2
        # Draw icon and text centered together is tricky without pre-calc.
        # Let's just draw icon left of text.
        text_w = 150 # approx
        icon_x = header_x - text_w//2 - 40 # Moved left a bit more
        self.draw_emoji("🛠️", icon_x, content_y + 20, 32)
        self.draw_text("行动 & 背包", header_x, content_y + 25, self.large_font, center=True)

    def draw_shop_view(self, game_state, item_system, cart, selected_item_id):
        # Layout:
        # Top: Title & Budget
        # Upper Middle: Item Details (Full Width)
        # Lower Middle: Item List (Scrolling)
        # Bottom: Checkout Buttons

        # 1. Title & Budget
        self.draw_panel(10, 10, SCREEN_WIDTH - 20, 120)
        
        # Title with Icon
        # Center roughly
        center_x = SCREEN_WIDTH // 2
        icon_w = self.draw_emoji("🛒", center_x - 140, 20, 40)
        self.draw_text("物资采购中心", center_x - 140 + icon_w + 10, 25, self.title_font)
        
        cart_total = 0
        cart_weight = 0
        for i_id, count in cart.items():
            item = item_system.get_item(i_id)
            cart_total += item['price'] * count
            cart_weight += item['weight'] * count
            
        # Calculate Max Weight (Base + Backpacks in Inventory OR Cart)
        max_w = MAX_WEIGHT_BASE
        
        def get_bonus(i_id):
            it = item_system.get_item(i_id)
            return it['effects'].get('capacity_bonus', 0) if it else 0
            
        # Check owned items
        for i_id in game_state.inventory:
            max_w = max(max_w, MAX_WEIGHT_BASE + get_bonus(i_id))
            
        # Check cart items
        for i_id in cart:
            max_w = max(max_w, MAX_WEIGHT_BASE + get_bonus(i_id))
            
        current_weight = item_system.calculate_weight(game_state.inventory) + cart_weight
        
        remaining = game_state.money - cart_total
        color_money = YELLOW if remaining >= 0 else RED
        color_weight = RED if current_weight > max_w else TEXT_COLOR
        
        self.draw_text(f"预算: ¥{game_state.money} - 购物车: ¥{cart_total} = 剩余: ¥{remaining}", SCREEN_WIDTH//2, 85, self.large_font, color=color_money, center=True)
        
        # Weight Display
        self.draw_text(f"负重: {current_weight:.1f}/{max_w:.1f}kg", SCREEN_WIDTH - 220, 85, self.large_font, color=color_weight)

        # 2. Item Details Panel (Fixed at Top)
        details_y = 140
        details_h = 180
        self.draw_panel(10, details_y, SCREEN_WIDTH - 20, details_h)
        
        if selected_item_id:
            item = item_system.get_item(selected_item_id)
            
            # Icon & Name
            icon_w = self.draw_emoji(item.get('icon', '📦'), 40, details_y + 20, 64)
            self.draw_text(f"{item['name']}", 40 + icon_w + 15, details_y + 30, self.title_font)
            self.draw_text(f"类型: {item['type']}  |  重量: {item['weight']}kg  |  单价: ¥{item['price']}", 40 + icon_w + 15, details_y + 80, self.font, color=GRAY)
            
            # Description & Effects
            # Split width: Description left, Effects right
            desc_w = (SCREEN_WIDTH - 150) * 0.6
            
            # Description
            words = item['description']
            self.draw_text(words, 40, details_y + 110, self.font)
            
            # Effects
            effects_x = 40 + desc_w
            self.draw_text("效果:", effects_x, details_y + 30, self.large_font, color=YELLOW)
            dy = details_y + 70
            for k, v in item['effects'].items():
                key_text = EFFECT_TRANSLATIONS.get(k, k)
                self.draw_text(f"• {key_text}: {v}", effects_x, dy, self.font)
                dy += 25
        else:
            self.draw_text("请选择下方物品查看详情", SCREEN_WIDTH//2, details_y + details_h//2, self.large_font, color=GRAY, center=True)

        # 3. Item List Area (Background)
        list_y = details_y + details_h + 10
        list_h = SCREEN_HEIGHT - list_y - 90 # Leave space for bottom buttons
        self.draw_panel(10, list_y, SCREEN_WIDTH - 20, list_h)
        # The scroll area starts at y=250. Headers are at 210.
        # But the items scroll horizontally? No, user said "slide right to buy items", implying horizontal scroll.
        # If horizontal scroll, headers should probably scroll too or be fixed per column?
        # If we have multiple columns, headers are tricky.
        # Let's assume a single long horizontal list or columns that move.
        # If we have columns, we need headers for each column?
        # Or just one set of headers and the content scrolls?
        # If content scrolls horizontally, the headers "Item", "Price", etc. only make sense if the layout is tabular.
        # Let's keep headers fixed and assume the scroll moves the *columns* of items.
        


    def draw_journey_progress(self, game_state, map_system, x, y, w):
        # Background Line
        line_y = y + 30
        pygame.draw.line(self.screen, GRAY, (x + 20, line_y), (x + w - 20, line_y), 4)
        
        nodes = map_system.node_list
        total_nodes = len(nodes)
        if total_nodes < 2: return

        # Find current index
        current_idx = 0
        for i, node in enumerate(nodes):
            if node['node_id'] == game_state.current_node_id:
                current_idx = i
                break
        
        # Draw Nodes
        for i, node in enumerate(nodes):
            px = x + 20 + int((i / (total_nodes - 1)) * (w - 40))
            py = line_y
            
            # Color based on visited
            if i < current_idx:
                color = GREEN # Visited
                status = "passed"
            elif i == current_idx:
                color = YELLOW # Current
                status = "current"
            else:
                color = GRAY # Future
                status = "future"
            
            # Draw Node Point
            if status == "passed":
                pygame.draw.circle(self.screen, GREEN, (px, py), 6)
            elif status == "current":
                # Current Node Highlight
                pygame.draw.circle(self.screen, YELLOW, (px, py), 8)
                pygame.draw.circle(self.screen, WHITE, (px, py), 10, 2)
                
                # Flag (Raised)
                flag_h = 30
                pygame.draw.line(self.screen, WHITE, (px, py), (px, py - flag_h), 2)
                pygame.draw.polygon(self.screen, RED, [(px, py - flag_h), (px + 15, py - flag_h + 5), (px, py - flag_h + 10)])
                
            else:
                pygame.draw.circle(self.screen, GRAY, (px, py), 4)
            
            # Draw Walker (Between nodes)
            if i == current_idx and i < total_nodes - 1:
                if game_state.distance_to_next_node > 0:
                    next_node = nodes[i+1]
                    total_dist = node.get('distance_to_next', 10)
                    if total_dist > 0:
                        # Progress is inverted (distance_to_next decreases as we get closer)
                        progress = 1.0 - (game_state.distance_to_next_node / total_dist)
                        next_px = x + 20 + int(((i + 1) / (total_nodes - 1)) * (w - 40))
                        walker_x = px + int((next_px - px) * progress)
                        
                        # Draw Pixel Art Walker
                        self.visualizer.draw_mini_character(self.screen, walker_x, py)

            # Draw Name (Staggered)
            # Show ALL nodes as requested
            if i % 2 == 0:
                text_y = py + 15
            else:
                text_y = py - 25
                if status == "current": text_y -= 20 # Avoid flag
            
            # Small font for names to fit
            name = node['name']
            # If name is too long, maybe truncate?
            self.draw_text(name, px, text_y, self.small_font, color=color, center=True)

    def draw_event_result(self, result_data):
        # Draw Result Panel
        panel_w = 600
        panel_h = 400
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 150
        self.draw_panel(panel_x, panel_y, panel_w, panel_h)
        
        self.draw_text("事件结果", SCREEN_WIDTH//2, panel_y + 30, self.title_font, center=True)
        
        # Narrative
        narrative = result_data.get('text', '')
        # Wrap text
        words = narrative
        # Simple wrap for now
        self.draw_text(words, panel_x + 40, panel_y + 80, self.large_font)
        
        # Changes
        changes = result_data.get('changes', [])
        y = panel_y + 150
        for change in changes:
            icon = change.get('icon', '')
            text = change.get('text', '')
            
            icon_w = 0
            if icon:
                icon_w = self.draw_emoji(icon, panel_x + 60, y, 32)
            
            self.draw_text(text, panel_x + 60 + icon_w + 10, y + 5, self.font)
            y += 40

    def draw_game_over(self, game_state):
        color = GREEN if game_state.game_won else RED
        
        # Title with Icon
        center_x = SCREEN_WIDTH // 2
        icon = "🎉" if game_state.game_won else "💀"
        title = "穿越成功！" if game_state.game_won else "游戏结束"
        
        icon_w = self.draw_emoji(icon, center_x - 100, 150, 48)
        self.draw_text(title, center_x - 100 + icon_w + 10, 160, self.title_font, color=color)
        
        self.draw_text(game_state.status_message, center_x, 240, self.large_font, center=True)
        
        # Summary Stats
        y = 300
        self.draw_text("--- 徒步总结 ---", center_x, y, self.font, center=True, color=GRAY)
        y += 40
        
        stats = [
            f"存活天数: {game_state.game_time} 天",
            f"最低体温: {getattr(game_state, 'lowest_temp', 36.5):.1f}°C",
            f"最低SAN值: {getattr(game_state, 'lowest_sanity', 100)}",
            f"剩余资金: ¥{game_state.money}"
        ]
        
        for stat in stats:
            self.draw_text(stat, center_x, y, self.font, center=True)
            y += 30
            
        # Rank/Title
        y += 20
        rank = "菜鸟驴友"
        if game_state.game_won:
            rank = "鳌太传奇"
            if game_state.game_time <= 5: rank = "速穿大神"
        else:
            if game_state.game_time > 3: rank = "坚强行者"
            if getattr(game_state, 'lowest_temp', 36.5) < 34: rank = "失温遇难者"
            
        self.draw_text(f"获得称号: 【{rank}】", center_x, y, self.large_font, center=True, color=GOLD)

    def clear_buttons(self):
        self.buttons = []
        self.sliders = []

    def clear_buttons_only(self):
        self.buttons = []

    def add_button(self, text, callback, x, y, w=200, h=40, color=PANEL_COLOR, text_color=TEXT_COLOR, icon=None, tooltip=None):
        btn = Button(x, y, w, h, text, callback, color=color, text_color=text_color, icon=icon, tooltip=tooltip)
        self.buttons.append(btn)

    def add_slider(self, x, y, w, h, min_val, max_val, initial_val):
        slider = Slider(x, y, w, h, min_val, max_val, initial_val)
        self.sliders.append(slider)
        return slider

    def draw_buttons(self):
        tooltip_to_draw = None
        for btn in self.buttons:
            btn.draw(self.screen, self.font, self)
            if btn.is_hovered and btn.tooltip:
                tooltip_to_draw = btn.tooltip
        
        for slider in self.sliders:
            slider.draw(self.screen)
            
        if tooltip_to_draw:
            mx, my = pygame.mouse.get_pos()
            self.draw_tooltip(tooltip_to_draw, mx + 15, my + 15)

    def draw_tooltip(self, text, x, y):
        # Split text by newlines
        lines = text.split('\n')
        
        # Calculate size
        max_w = 0
        h = 0
        surfs = []
        for line in lines:
            s = self.small_font.render(line, True, WHITE)
            max_w = max(max_w, s.get_width())
            h += s.get_height() + 5
            surfs.append(s)
        
        w = max_w + 20
        h += 15
        
        # Keep on screen
        if x + w > SCREEN_WIDTH: x = SCREEN_WIDTH - w - 5
        if y + h > SCREEN_HEIGHT: y = SCREEN_HEIGHT - h - 5
        
        # Draw
        pygame.draw.rect(self.screen, BLACK, (x, y, w, h), border_radius=5)
        pygame.draw.rect(self.screen, WHITE, (x, y, w, h), 1, border_radius=5)
        
        curr_y = y + 10
        for s in surfs:
            self.screen.blit(s, (x + 10, curr_y))
            curr_y += s.get_height() + 5

    def handle_input(self, event):
        input_handled = False
        for btn in self.buttons:
            if btn.handle_event(event):
                input_handled = True
        
        for slider in self.sliders:
            if slider.handle_event(event):
                input_handled = True
                
        return input_handled
