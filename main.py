import pygame
import sys
import random
import os
import asyncio
from game.config import *
from game.state import GameState
from game.systems import ItemSystem, MapSystem, WeatherSystem, EventSystem
from game.ui import UI, EFFECT_TRANSLATIONS

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        
        self.state = GameState()
        self.item_system = ItemSystem()
        self.map_system = MapSystem()
        self.weather_system = WeatherSystem()
        self.event_system = EventSystem()
        self.ui = UI(self.screen)
        
        self.game_phase = "MENU" # MENU, SHOP, EXPLORE, EVENT, EVENT_RESULT, GAME_OVER
        self.current_event = None
        self.event_result_data = {} # {text: str, changes: [{icon: str, text: str}]}
        
        # Shop state
        self.cart = {} # item_id: count
        self.selected_shop_item = None
        self.shop_scroll_x = 0
        self.shop_slider = None
        
        self.setup_menu()

    def setup_menu(self):
        self.ui.clear_buttons()
        self.ui.add_button("开始新游戏", self.start_setup_phase, SCREEN_WIDTH//2 - 100, 300, color=GREEN)
        
        # Check for save game
        if os.path.exists("savegame.json"):
            self.ui.add_button("继续游戏", self.load_and_start, SCREEN_WIDTH//2 - 100, 360, color=BLUE)
            
        self.ui.add_button("退出", self.quit_game, SCREEN_WIDTH//2 - 100, 420, color=RED)

    def load_and_start(self):
        if self.state.load_game():
            self.game_phase = "EXPLORE"
            self.setup_explore_ui()
            self.ui.add_message("存档已加载。")
        else:
            self.ui.add_message("加载存档失败！")

    # --- SETUP PHASE (Character & Season) ---
    
    def start_setup_phase(self):
        self.game_phase = "SETUP"
        self.state.reset()
        self.setup_selection_ui()
        
    def setup_selection_ui(self):
        self.ui.clear_buttons()
        
        # Character Selection
        y = 150
        self.ui.add_button("选择角色:", None, 50, y, 200, 40, color=BG_COLOR)
        y += 50
        
        char_x = 50
        for cid, cdata in CHARACTERS.items():
            color = GREEN if self.state.character_id == cid else BLUE
            self.ui.add_button(cdata['name'], lambda c=cid: self.select_character(c), char_x, y, 200, 50, color=color)
            char_x += 220
            
        # Character Description
        desc = CHARACTERS[self.state.character_id]['desc']
        self.ui.add_button(desc, None, 50, y + 60, 800, 40, color=PANEL_COLOR)
        
        # Season Selection
        y += 150
        self.ui.add_button("选择季节:", None, 50, y, 200, 40, color=BG_COLOR)
        y += 50
        
        season_x = 50
        for sid, sdata in SEASONS.items():
            color = ORANGE if self.state.season == sid else BLUE
            self.ui.add_button(sdata['name'], lambda s=sid: self.select_season(s), season_x, y, 200, 50, color=color)
            season_x += 220
            
        # Season Description
        s_desc = SEASONS[self.state.season]['desc']
        self.ui.add_button(s_desc, None, 50, y + 60, 800, 40, color=PANEL_COLOR)
        
        # Confirm Button
        self.ui.add_button("确认并进入商店", self.confirm_setup, SCREEN_WIDTH - 250, SCREEN_HEIGHT - 80, 200, 50, color=GREEN)
        self.ui.add_button("返回", self.setup_menu, 50, SCREEN_HEIGHT - 80, 150, 50, color=RED)

    def select_character(self, char_id):
        self.state.character_id = char_id
        self.setup_selection_ui()
        
    def select_season(self, season_id):
        self.state.season = season_id
        self.setup_selection_ui()
        
    def confirm_setup(self):
        # Apply Character Buffs
        char_data = CHARACTERS[self.state.character_id]
        buffs = char_data['buffs']
        
        if 'max_stamina' in buffs:
            self.state.stamina = buffs['max_stamina']
            # Note: MAX_STAMINA constant is global, so we might need to handle cap logic carefully
            # For now, let's just set current stamina. 
            # Ideally, we should have self.state.max_stamina.
            
        # Apply Season Effects
        season_data = SEASONS[self.state.season]
        self.state.env_temp = season_data['base_temp']
        
        self.start_shop_phase()

    # --- SHOP PHASE ---

    def start_shop_phase(self):
        self.game_phase = "SHOP"
        self.state.reset()
        # Load last cart if exists
        self.cart = self.state.load_cart()
        # Validate cart (ensure items still exist and we have enough money)
        valid_cart = {}
        total_cost = 0
        for i_id, count in self.cart.items():
            item = self.item_system.get_item(i_id)
            if item:
                total_cost += item['price'] * count
                valid_cart[i_id] = count
        
        if total_cost > self.state.money:
            valid_cart = {} # Reset if too expensive
            
        self.cart = valid_cart
        self.selected_shop_item = None
        self.shop_scroll_x = 0
        self.ui.clear_buttons() # Clear everything including old sliders
        self.shop_slider = None
        self.setup_shop_ui()
        self.ui.add_message("进入物资采购阶段。请合理分配预算。")

    def setup_shop_ui(self):
        self.ui.clear_buttons_only() # Only clear buttons, keep slider
        
        # Item List - Use all items
        items_to_show = list(self.item_system.items.keys())
        
        # Layout Constants
        # List starts below Details Panel (140+180=320) + Padding = 330
        start_y = 340
        item_h = 40
        col_w = 420
        # Calculate items per column based on available height
        # Bottom buttons at SCREEN_HEIGHT - 80
        # Slider at SCREEN_HEIGHT - 110
        # Available height = (SCREEN_HEIGHT - 120) - start_y
        list_h = SCREEN_HEIGHT - 120 - start_y
        items_per_col = list_h // item_h
        
        # Viewport
        vp_x = 20
        vp_w = SCREEN_WIDTH - 40
        vp_right = vp_x + vp_w
        
        # Calculate total width needed
        import math
        num_cols = math.ceil(len(items_to_show) / items_per_col)
        total_content_w = num_cols * col_w
        max_scroll = max(0, total_content_w - vp_w)
        
        # Add Slider if needed
        if max_scroll > 0:
            if self.shop_slider is None:
                slider_x = vp_x
                slider_y = SCREEN_HEIGHT - 110
                slider_w = vp_w
                slider_h = 20
                self.shop_slider = self.ui.add_slider(slider_x, slider_y, slider_w, slider_h, 0, max_scroll, self.shop_scroll_x)
            else:
                # Update slider range if content changed
                self.shop_slider.max_val = max_scroll
        else:
            self.shop_scroll_x = 0
            # If slider exists but not needed, we should probably hide it or reset it.
            # For now, let's just leave it if it exists, or maybe we need a remove_slider method.
            pass

        # Draw Items
        current_col = 0
        current_row = 0
        
        
        for item_id in items_to_show:
            item = self.item_system.get_item(item_id)
            if not item: continue
            
            # Calculate position relative to content start
            rel_x = current_col * col_w
            rel_y = start_y + current_row * item_h
            
            # Apply scroll
            screen_x = vp_x + rel_x - self.shop_scroll_x
            screen_y = rel_y
            
            # Check visibility (Horizontal only, vertical is fixed)
            if screen_x + col_w > vp_x - 100 and screen_x < vp_right:
                # Add buttons
                
                # Select Item (Click name to see details)
                text = f"{item['name']}"
                color = ACCENT_COLOR if self.selected_shop_item == item_id else PANEL_COLOR
                # Pass icon separately
                self.ui.add_button(text, lambda i=item_id: self.select_shop_item(i), screen_x, screen_y, 160, 35, color=color, icon=item.get('icon'))
                
                # Price
                self.ui.add_button(str(item['price']), None, screen_x + 165, screen_y, 60, 35, color=DARK_GRAY)
                
                # Weight
                self.ui.add_button(f"{item['weight']}kg", None, screen_x + 230, screen_y, 60, 35, color=DARK_GRAY)
                
                # Controls
                current_in_cart = self.cart.get(item_id, 0)
                
                # Minus
                self.ui.add_button("-", lambda i=item_id: self.update_cart(i, -1), screen_x + 295, screen_y, 30, 35, color=RED)
                
                # Count
                self.ui.add_button(str(current_in_cart), None, screen_x + 330, screen_y, 35, 35, color=DARK_GRAY)
                
                # Plus
                self.ui.add_button("+", lambda i=item_id: self.update_cart(i, 1), screen_x + 370, screen_y, 30, 35, color=GREEN)

            # Advance grid
            current_row += 1
            if current_row >= items_per_col:
                current_row = 0
                current_col += 1

        # Checkout Button (Fixed position)
        self.ui.add_button("结账出发", self.checkout, SCREEN_WIDTH - 250, SCREEN_HEIGHT - 80, color=GREEN, icon="💳")
        self.ui.add_button("清空购物车", self.clear_cart, SCREEN_WIDTH - 460, SCREEN_HEIGHT - 80, color=RED, icon="❌")

    def select_shop_item(self, item_id):
        self.selected_shop_item = item_id
        self.setup_shop_ui()

    def update_cart(self, item_id, change):
        # Check modifiers
        keys = pygame.key.get_pressed()
        multiplier = 1
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            multiplier = 10
        elif keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
            multiplier = 50

        change *= multiplier

        current = self.cart.get(item_id, 0)
        target_val = current + change
        if target_val < 0: target_val = 0
        
        actual_change = target_val - current
        if actual_change == 0: return

        item = self.item_system.get_item(item_id)
        
        # Check budget
        if actual_change > 0:
            cost_diff = item['price'] * actual_change
            current_cost = sum(self.item_system.get_item(i)['price'] * c for i, c in self.cart.items())
            
            if current_cost + cost_diff > self.state.money:
                remaining_money = self.state.money - current_cost
                max_affordable = int(remaining_money // item['price'])
                actual_change = min(actual_change, max_affordable)
                if actual_change == 0:
                    self.ui.add_message("预算不足！")
                    return
                self.ui.add_message(f"预算限制，购买了 {actual_change} 个。")
                
            # Check Weight
            def get_max_w(inv_items, cart_items):
                max_w = MAX_WEIGHT_BASE
                for i_id in inv_items:
                    it = self.item_system.get_item(i_id)
                    if it: max_w = max(max_w, MAX_WEIGHT_BASE + it['effects'].get('capacity_bonus', 0))
                for i_id in cart_items:
                    it = self.item_system.get_item(i_id)
                    if it: max_w = max(max_w, MAX_WEIGHT_BASE + it['effects'].get('capacity_bonus', 0))
                return max_w

            temp_cart = self.cart.copy()
            temp_cart[item_id] = current + actual_change
            
            max_w = get_max_w(self.state.inventory, temp_cart)
            current_w = self.item_system.calculate_weight(self.state.inventory)
            cart_w = sum(self.item_system.get_item(i)['weight'] * c for i, c in temp_cart.items())
            
            if current_w + cart_w > max_w:
                self.ui.add_message("负重超过背包上限！")
                return

        new_val = current + actual_change
        if new_val <= 0:
                del self.cart[item_id]
        else:
            self.cart[item_id] = new_val
            
        self.setup_shop_ui()

    def clear_cart(self):
        self.cart = {}
        self.setup_shop_ui()

    def checkout(self):
        total_cost = sum(self.item_system.get_item(i)['price'] * c for i, c in self.cart.items())
        if total_cost > self.state.money:
            self.ui.add_message("预算不足，无法结账！")
            return
            
        if not self.cart:
            self.ui.add_message("购物车为空！")
            # Allow starting without items? Maybe warn.
            
        # Deduct money and add items
        self.state.money -= total_cost
        for item_id, count in self.cart.items():
            self.state.add_item(item_id, count)
        
        # Save cart for next time
        self.state.save_cart(self.cart)
            
        self.start_explore_phase()

    # --- EXPLORE PHASE ---

    def update_environment(self):
        node = self.map_system.get_node(self.state.current_node_id)
        if not node: return
        
        altitude = node['altitude']
        
        # Temp: Base 20C, -6.5C per 1000m
        # Season Base Temp
        season_base = SEASONS[self.state.season]['base_temp']
        base_temp = season_base - (altitude / 1000.0) * 6.5
        
        # Weather effect
        weather_effects = self.weather_system.get_weather_effects(self.state.weather)
        weather_temp = weather_effects.get('temp', 0)
        
        # Time of day effect (Night is colder)
        time_temp = 0
        if self.state.day_time < 6 or self.state.day_time > 20:
            time_temp = -5
            
        self.state.env_temp = base_temp + weather_temp + time_temp
        
        # Logic: If temp < 0 and raining, turn to snow
        if self.state.env_temp < 0 and self.state.weather == 'rain':
            self.state.weather = 'snow'
            # Re-calculate weather effects since weather changed
            weather_effects = self.weather_system.get_weather_effects(self.state.weather)
            weather_temp = weather_effects.get('temp', 0)
            self.state.env_temp = base_temp + weather_temp + time_temp

        # Wind
        base_wind = 1
        if altitude > 2500: base_wind += 1
        if altitude > 3000: base_wind += 1
        if altitude > 3400: base_wind += 1
        
        if self.state.weather == "storm": base_wind += 4
        elif self.state.weather == "snow": base_wind += 2
        elif self.state.weather == "rain": base_wind += 1
        
        self.state.wind_level = min(10, base_wind)

        # Update Body Temp & Sanity
        # Calculate gear warmth based on items in inventory
        total_protection = 0
        for item_id in self.state.inventory:
            item = self.item_system.get_item(item_id)
            if item and 'temp_protection' in item.get('effects', {}):
                total_protection += item['effects']['temp_protection']
        
        # Base comfort threshold is 10C. Gear lowers this threshold.
        gear_warmth = 10.0 - total_protection
        
        self.state.update_body_temp(self.state.env_temp, gear_warmth)
        self.state.update_sanity_drain()

    def start_explore_phase(self):
        self.game_phase = "EXPLORE"
        self.ui.add_message("徒步开始！")
        
        # Initialize distance for the first node
        current_node = self.map_system.get_node(self.state.current_node_id)
        if current_node and 'distance_to_next' in current_node:
            self.state.distance_to_next_node = current_node['distance_to_next']
        else:
            self.state.distance_to_next_node = 0
            
        self.update_environment()
        self.setup_explore_ui()

    def setup_explore_ui(self):
        self.ui.clear_buttons()
        
        # Actions Panel (Right Side)
        # Panel starts at x=720, y=180, w=550
        # Center buttons in panel
        panel_x = 720
        panel_w = SCREEN_WIDTH - 730
        btn_w = 350
        btn_x = panel_x + (panel_w - btn_w) // 2
        
        y = 240 # Start below header
        
        # Hiking Controls
        if self.state.distance_to_next_node > 0:
            self.ui.add_button("继续徒步 (1h)", self.hike, btn_x, y, btn_w, 50, color=GREEN, icon="🚶")
            y += 60
            
            # Student Teleport Ability
            if self.state.character_id == "student" and not self.state.teleport_used:
                self.ui.add_button("发动瞬移 (1次)", self.use_teleport, btn_x, y, btn_w, 40, color=PURPLE, icon="✨")
                y += 50
                
        else:
            # Arrived, show next destinations
            connections = self.map_system.get_connections(self.state.current_node_id)
            if connections:
                self.ui.add_button("前往下一站:", None, btn_x, y, btn_w, 30, color=BG_COLOR)
                y += 40
                for node in connections:
                    text = f"{node['name']}"
                    self.ui.add_button(text, lambda n=node['node_id']: self.travel_to_node(n), btn_x, y, btn_w, 40, color=GREEN, icon="👉")
                    y += 50
            else:
                self.ui.add_button("终点已到达！", self.finish_game, btn_x, y, btn_w, 50, color=GOLD, icon="🏁")
                y += 60

        # Save Game Button
        self.ui.add_button("保存进度", self.manual_save, btn_x, 660, btn_w, 40, color=BLUE, icon="💾")
        self.ui.add_button("返回主菜单", self.setup_menu_phase, btn_x, 710, btn_w, 40, color=RED, icon="🏠")

        # Rest & Camp (Split width)
        y += 20
        half_w = (btn_w - 10) // 2
        
        if self.state.action_points > 0:
            self.ui.add_button("休息 (1h)", self.rest, btn_x, y, half_w, 40, color=BLUE, icon="💤")
        else:
            self.ui.add_button("休息 (1h)", lambda: None, btn_x, y, half_w, 40, color=GRAY, icon="💤")
            
        self.ui.add_button("扎营 (过夜)", self.camp, btn_x + half_w + 10, y, half_w, 40, color=PURPLE, icon="⛺")
        
        y += 50
        
        # Eat Snow (Conditional)
        if self.state.thirst <= 30:
            # Check if snow is available (Weather is snow/storm OR Altitude > 3000 OR Terrain is snow-related?)
            # Simplified: Altitude > 3000 usually has snow, or weather is snow/storm
            node = self.map_system.get_node(self.state.current_node_id)
            has_snow = self.state.weather in ["snow", "storm"] or node['altitude'] > 3000
            
            if has_snow:
                self.ui.add_button("吃雪解渴", self.confirm_eat_snow, btn_x, y, btn_w, 40, color=CYAN, icon="❄️")
                y += 50

        # Inventory (Right Bottom)
        y += 20
        
        consumables = []
        for item_id, count in self.state.inventory.items():
            item = self.item_system.get_item(item_id)
            if item and ('hunger' in item['effects'] or 'thirst' in item['effects'] or 'heal' in item['effects'] or 'sanity' in item['effects']):
                consumables.append(item_id)
        
        for item_id in consumables:
            item = self.item_system.get_item(item_id)
            count = self.state.inventory.get(item_id, 0)
            text = f"{item['name']} (x{count})"
            
            # Tooltip
            tooltip = f"{item['description']}\n"
            for k, v in item['effects'].items():
                k_cn = EFFECT_TRANSLATIONS.get(k, k)
                tooltip += f"{k_cn}: {v}\n"
            
            self.ui.add_button(text, lambda i=item_id: self.use_item(i), btn_x, y, btn_w, 35, color=ORANGE, icon=item.get('icon'), tooltip=tooltip)
            y += 40
            if y > 750: break

    def confirm_eat_snow(self):
        self.game_phase = "EAT_SNOW_CONFIRM"
        self.setup_eat_snow_ui()

    def setup_eat_snow_ui(self):
        self.ui.clear_buttons()
        panel_w = 400
        panel_h = 250
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 250
        
        btn_y = panel_y + 150
        self.ui.add_button("确定吃雪", self.perform_eat_snow, panel_x + 30, btn_y, 150, 40, color=RED)
        self.ui.add_button("取消", self.cancel_eat_snow, panel_x + 220, btn_y, 150, 40, color=GRAY)

    def cancel_eat_snow(self):
        self.game_phase = "EXPLORE"
        self.setup_explore_ui()

    def perform_eat_snow(self):
        self.state.thirst = min(self.state.thirst + 20, MAX_THIRST)
        self.state.temperature -= 2.0
        self.state.health -= 5
        self.state.sanity -= 10
        self.ui.add_message("你吃了一口雪，解了渴，但身体冻得发抖。")
        self.check_turn_end()
        if self.game_phase != "GAME_OVER":
            self.game_phase = "EXPLORE"
            self.setup_explore_ui()

    def use_item(self, item_id):
        # Special handling for dried noodles
        if item_id == "food_dried_noodles":
            has_stove = "stove" in self.state.inventory
            has_pot = "pot" in self.state.inventory
            has_gas = "gas" in self.state.inventory
            
            if has_stove and has_pot and has_gas:
                # Ask to cook
                self.game_phase = "COOKING_CHOICE"
                self.cooking_item = item_id
                self.setup_cooking_ui()
                return
            else:
                # Eat raw
                self.consume_item(item_id, cooked=False)
                self.ui.add_message("没有炊具，你只能干嚼挂面，效果减半。")
                return

        self.consume_item(item_id)

    def setup_cooking_ui(self):
        self.ui.clear_buttons()
        panel_w = 400
        panel_h = 200
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 250
        
        btn_y = panel_y + 120
        self.ui.add_button("煮熟食用", lambda: self.finish_cooking(True), panel_x + 30, btn_y, 150, 40, color=GREEN)
        self.ui.add_button("直接干吃", lambda: self.finish_cooking(False), panel_x + 220, btn_y, 150, 40, color=GRAY)

    def finish_cooking(self, cooked):
        if cooked:
            self.consume_item(self.cooking_item, cooked=True)
            self.ui.add_message("你煮了一碗热腾腾的面，真香！")
            # Consume gas? Maybe small chance or just assume usage
        else:
            self.consume_item(self.cooking_item, cooked=False)
            self.ui.add_message("你选择干吃挂面，口感很差。")
        
        self.game_phase = "EXPLORE"
        self.setup_explore_ui()

    def consume_item(self, item_id, cooked=True):
        item = self.item_system.get_item(item_id)
        if self.state.consume_item(item):
            self.state.remove_item(item_id)
            
            # Apply cooked modifier if false
            if not cooked:
                # Revert and re-apply half? Or just hack the stats?
                # Since state.consume_item already applied full effects, we need to undo half
                # This is tricky. Better to modify state.consume_item or handle effects manually here.
                # Let's manually adjust for now since consume_item is generic.
                # Actually, state.consume_item returns True if used.
                # We can check the item effects and reverse half.
                for effect, value in item['effects'].items():
                    if isinstance(value, (int, float)) and effect in ['hunger', 'sanity', 'health', 'stamina']:
                        # Reverse half of the gain (so we only get half)
                        # e.g. hunger +80. We want +40. So we subtract 40.
                        half_val = value * 0.5
                        if effect == 'hunger': self.state.hunger -= half_val
                        elif effect == 'sanity': self.state.sanity -= half_val
                        elif effect == 'health': self.state.health -= half_val
                        elif effect == 'stamina': self.state.stamina -= half_val
            
            self.ui.add_message(f"使用了 {item['name']}")
            self.setup_explore_ui()

    def eat_snow(self):
        self.state.thirst = min(self.state.thirst + 20, MAX_THIRST)
        self.state.temperature -= 2
        self.state.health -= 2
        self.state.sanity -= 2
        self.state.action_points -= 0.5 # Takes 30 mins?
        self.ui.add_message("你抓了一把雪塞进嘴里，透心凉。")
        self.check_turn_end()
        if self.game_phase != "GAME_OVER":
            self.setup_explore_ui()

    def scavenge(self):
        # This is now triggered by an event, so AP/Time cost is handled by the event description or here?
        # The event says "Consume 1h". So we should deduct here.
        # But if called from event, we might want to be careful about double deduction if event effects also deduct.
        # The event JSON says "special_action": "scavenge", but NO other effects like action_points: -1.
        # So we deduct here.
        
        if self.state.action_points < 1:
            self.ui.add_message("行动点不足！")
            return
            
        self.state.action_points -= 1
        self.state.update_time(1)
        
        # Karma affects luck
        # Karma ranges roughly -10 to 50?
        # Add karma * 0.005 to the roll. 20 Karma = +0.1
        luck_modifier = self.state.karma * 0.005
        roll = random.random() + luck_modifier
        
        found_item = None
        
        if roll < 0.1:
            self.ui.add_message("你搜寻了一番，什么也没找到。")
        elif roll < 0.5: # 40% Common
            common_items = ["water_bottle", "food_instant_noodles", "food_naan", "candy"]
            found_item = random.choice(common_items)
        elif roll < 0.8: # 30% Rare
            rare_items = ["gas", "batteries", "medicine", "food_beef_jerky"]
            found_item = random.choice(rare_items)
        else: # 20% Precious
            precious_items = ["first_aid_kit", "liquor", "food_high_energy"] 
            found_item = random.choice(precious_items)
            
        if found_item:
            item = self.item_system.get_item(found_item)
            self.state.add_item(found_item)
            self.ui.add_message(f"你找到了: {item['name']}！")
            
        self.check_turn_end()
        # Return to explore UI
        if self.game_phase != "GAME_OVER":
            self.game_phase = "EXPLORE" # Force explore phase
            self.setup_explore_ui()

    def confirm_retreat(self):
        self.game_phase = "RETREAT_CONFIRM"
        self.setup_retreat_ui()

    def setup_retreat_ui(self):
        self.ui.clear_buttons()
        panel_w = 400
        panel_h = 200
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 250
        
        btn_y = panel_y + 120
        self.ui.add_button("确定下撤", self.retreat, panel_x + 30, btn_y, 150, 40, color=RED)
        self.ui.add_button("取消", self.cancel_retreat, panel_x + 220, btn_y, 150, 40, color=GRAY)

    def cancel_retreat(self):
        self.game_phase = "EXPLORE"
        self.setup_explore_ui()

    def retreat(self):
        self.state.game_won = True # Technically survived
        self.state.status_message = f"你选择了下撤，保住了性命。剩余资金 {self.state.money} 已保存。"
        self.game_phase = "GAME_OVER"
        self.setup_game_over_ui()

    def hike(self):
        if self.state.action_points <= 0:
            self.ui.add_message("行动点不足，请休息或扎营。")
            return
            
        if self.state.stamina <= 10:
            self.ui.add_message("体力耗尽，无法继续前行！")
            return

        # Character Buffs: Stamina Cost
        stamina_cost = 10
        char_buffs = CHARACTERS[self.state.character_id]['buffs']
        if 'stamina_cost_mult' in char_buffs:
            stamina_cost *= char_buffs['stamina_cost_mult']
            
        # Warning Check
        if not getattr(self, 'warning_confirmed', False):
            warnings = []
            if self.state.health < 30: warnings.append("健康值过低")
            if self.state.stamina < 20: warnings.append("体力过低") # Use fixed threshold for warning
            if self.state.sanity < 20: warnings.append("SAN值过低")
            
            if warnings:
                # Show warning dialog logic
                # Since we don't have a modal system, we can use a special phase or just a message + flag
                # Let's use a simple toggle button approach or a message
                # Better: Switch to a WARNING phase
                self.game_phase = "WARNING"
                self.warning_msg = f"警告: {', '.join(warnings)}！\n强行赶路可能导致死亡。"
                self.setup_warning_ui()
                return

        self.warning_confirmed = False # Reset for next time

        # Calculate distance
        base_speed = 2.0 # km/h (Reduced from 3.0)
        
        # Modifiers
        current_node = self.map_system.get_node(self.state.current_node_id)
        terrain = current_node.get('terrain', 'normal')
        altitude = current_node.get('altitude', 2000)
        
        terrain_factor = 1.0
        if terrain == 'forest': terrain_factor = 0.8
        elif terrain == 'rocky': terrain_factor = 0.6
        elif terrain == 'ridge': terrain_factor = 0.5
        elif terrain == 'danger': terrain_factor = 0.4
        elif terrain == 'meadow': terrain_factor = 1.0
        
        altitude_factor = max(0.5, 1.0 - (max(0, altitude - 2500) / 5000))
        
        weight = self.item_system.calculate_weight(self.state.inventory)
        weight_factor = 1.0
        if weight > MAX_WEIGHT_BASE:
            overweight = weight - MAX_WEIGHT_BASE
            weight_factor = max(0.5, 1.0 - (overweight * 0.05))
            
        weather_effects = self.weather_system.get_weather_effects(self.state.weather)
        
        # Wind Factor
        wind_factor = 1.0
        if self.state.wind_level >= 6: wind_factor = 0.8
        if self.state.wind_level >= 8: wind_factor = 0.5
        
        # Temp Factor
        temp_factor = 1.0
        if self.state.env_temp < -10: temp_factor = 0.9
        if self.state.env_temp < -20: temp_factor = 0.7
        
        # Weight Bonus/Penalty
        # If weight is low, give bonus
        if weight < MAX_WEIGHT_BASE * 0.8:
            weight_factor = 1.1 # 10% faster if light
        
        # Random Factor (0.8 - 1.2)
        random_factor = random.uniform(0.8, 1.2)
        
        # Status Factor
        status_factor = 1.0
        if self.state.health > 80 and self.state.stamina > 80:
            status_factor += 0.2
        if self.state.health < 50:
            status_factor -= 0.2
        if self.state.hunger < 30:
            status_factor -= 0.1
        if self.state.thirst < 30:
            status_factor -= 0.1
            
        # Character Buffs: Move Speed
        char_buffs = CHARACTERS[self.state.character_id]['buffs']
        if 'move_speed_mult' in char_buffs:
            status_factor *= char_buffs['move_speed_mult']

        dist = base_speed * terrain_factor * altitude_factor * weight_factor * wind_factor * temp_factor * random_factor * status_factor
        
        # Update State
        self.state.distance_to_next_node -= dist
        if self.state.distance_to_next_node < 0: self.state.distance_to_next_node = 0
        
        # Stamina Cost
        wind_cost = 1.0 + (self.state.wind_level * 0.05)
        cold_cost = 1.0
        if self.state.env_temp < 0: cold_cost += abs(self.state.env_temp) * 0.02
        
        stamina_cost = 15 * (1.0 + (1.0 - terrain_factor) + (1.0 - altitude_factor)) * weather_effects.get('stamina_cost', 1.0) * wind_cost * cold_cost
        
        # Character Buffs: Stamina Cost (Apply again here for calculation)
        if 'stamina_cost_mult' in char_buffs:
            stamina_cost *= char_buffs['stamina_cost_mult']
            
        self.state.stamina -= stamina_cost
        self.state.action_points -= 1
        self.state.update_time(1)
        self.update_environment()
        
        self.ui.add_message(f"徒步1小时，前进了 {dist:.1f}km。")
        
        # Check Events
        event = self.event_system.check_event(self.state, self.map_system, context={'phase': 'hike'})
        if event:
            self.trigger_event(event)
        else:
            self.check_turn_end()
            if self.game_phase != "GAME_OVER":
                self.setup_explore_ui()

    def setup_warning_ui(self):
        self.ui.clear_buttons()
        
        panel_w = 500
        panel_h = 300
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 200
        
        # We need to draw this in the run loop
        # Add buttons
        btn_y = panel_y + 200
        self.ui.add_button("取消", self.cancel_hike, panel_x + 50, btn_y, 150, 40, color=GREEN)
        self.ui.add_button("确定继续", self.confirm_hike, panel_x + 300, btn_y, 150, 40, color=RED)

    def cancel_hike(self):
        self.game_phase = "EXPLORE"
        self.setup_explore_ui()

    def confirm_hike(self):
        self.warning_confirmed = True
        self.game_phase = "EXPLORE"
        self.hike() # Call hike again, this time it will pass the check

    def travel_to_node(self, node_id):
        # Arrive at the node logic
        target_node = self.map_system.get_node(node_id)
        self.state.current_node_id = node_id
        
        # Set up next leg
        if 'distance_to_next' in target_node:
            self.state.distance_to_next_node = target_node['distance_to_next']
        else:
            self.state.distance_to_next_node = 0
            
        self.ui.add_message(f"抵达 {target_node['name']}。")
        
        # Check for 2800 Camp Retreat Prompt
        if "2800" in target_node['name']:
            self.confirm_retreat() # Reuse the confirm retreat logic which sets up the UI
            return

        self.setup_explore_ui()

    def finish_game(self):
        self.state.game_won = True
        self.state.status_message = "恭喜你完成了鳌太穿越！"
        self.game_phase = "GAME_OVER"
        self.setup_game_over_ui()

    def rest(self):
        if self.state.action_points <= 0:
            self.ui.add_message("行动点不足，无法休息。")
            return

        self.state.stamina = min(self.state.stamina + 15, MAX_STAMINA)
        # Rest restores some body temp if not starving
        if self.state.hunger > 30:
            self.state.temperature = min(self.state.temperature + 0.5, 37.0)
            
        self.state.update_time(1)
        self.update_environment()
        self.state.action_points -= 1
        self.ui.add_message("休息了一会儿，体力恢复。")
        
        # Check for events (Rest phase)
        event = self.event_system.check_event(self.state, self.map_system, context={'phase': 'rest'})
        if event:
            self.trigger_event(event)
            return

        self.check_turn_end()
        if self.game_phase != "GAME_OVER":
            self.setup_explore_ui()

    def camp(self):
        if not self.state.has_item("tent"):
            self.ui.add_message("没有帐篷，无法扎营！")
            return
            
        self.state.stamina = min(self.state.stamina + 50, MAX_STAMINA)
        self.state.sanity = min(self.state.sanity + 20, MAX_SANITY)
        
        # Camping in a tent restores body temp to normal
        if self.state.hunger > 20:
            self.state.temperature = 37.0
            self.ui.add_message("帐篷内很温暖，体温恢复正常。")
        
        # Sleep for 12 hours
        hours_to_sleep = 12
        
        self.state.update_time(hours_to_sleep)
        self.update_environment()
        self.state.weather = self.weather_system.next_weather(self.state.weather, self.state.season)
        self.state.action_points = DAILY_ACTION_POINTS
        
        # Daily Spoilage Check
        spoiled_items = []
        for item_id in list(self.state.inventory.keys()):
            item = self.item_system.get_item(item_id)
            if item and 'spoil_chance' in item['effects']:
                chance = item['effects']['spoil_chance']
                if random.random() < chance:
                    self.state.remove_item(item_id, 1)
                    spoiled_items.append(item['name'])
        
        msg = f"扎营休息了{hours_to_sleep}小时。"
        if spoiled_items:
            msg += f"\n注意：{', '.join(spoiled_items)} 变质了，已丢弃。"
        
        self.ui.add_message(msg)
        
        # Check for events (Camp phase)
        event = self.event_system.check_event(self.state, self.map_system, context={'phase': 'camp'})
        if event:
            self.trigger_event(event)
            return
            
        self.check_turn_end()
        if self.game_phase != "GAME_OVER":
            self.setup_explore_ui()

    def check_turn_end(self):
        # Passive drain
        hunger_drain = 2
        thirst_drain = 3
        
        # Character Buffs: Hunger Drain
        char_buffs = CHARACTERS[self.state.character_id]['buffs']
        if 'hunger_drain_mult' in char_buffs:
            hunger_drain *= char_buffs['hunger_drain_mult']
            
        self.state.hunger -= hunger_drain
        self.state.thirst -= thirst_drain
        self.state.clamp_stats()
        
        # Spoilage Check (Daily or per turn? "Daily spoil chance" implies daily)
        # But check_turn_end runs often. Let's do it when day changes in camp/rest?
        # Or just small chance every turn?
        # Let's do it on day change.
        
        if self.state.check_game_over():
            self.game_phase = "GAME_OVER"
            self.setup_game_over_ui()

    def trigger_event(self, event):
        self.game_phase = "EVENT"
        self.current_event = event
        self.state.triggered_events.add(event['event_id'])
        self.setup_event_ui()

    def setup_event_ui(self):
        self.ui.clear_buttons()
        
        # Center buttons in the event panel
        panel_w = 800
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 150
        
        btn_w = 600
        btn_x = panel_x + (panel_w - btn_w) // 2
        y = panel_y + 250
        
        for choice in self.current_event['choices']:
            # Check requirements
            reqs = choice.get('requirements', {})
            can_choose = True
            if 'items' in reqs:
                for item_id in reqs['items']:
                    if not self.state.has_item(item_id):
                        can_choose = False
                        break
            
            if can_choose:
                self.ui.add_button(choice['text'], lambda c=choice: self.handle_event_choice(c), btn_x, y, btn_w, 50, color=BLUE)
            else:
                self.ui.add_button(choice['text'] + " (条件不足)", lambda: None, btn_x, y, btn_w, 50, color=GRAY)
            
            y += 60

    def handle_event_choice(self, choice):
        effects = choice.get('effects', {})
        
        # Special Action: Scavenge
        if effects.get('special_action') == 'scavenge':
            self.scavenge()
            # scavenge handles UI updates, but we are in EVENT phase.
            # We need to transition back to EXPLORE or show result.
            # scavenge() calls setup_explore_ui() at the end.
            # But we are currently in EVENT phase loop.
            # We should probably let scavenge run, then set phase to EVENT_RESULT to show what we found?
            # Or just let scavenge show a message and return to explore.
            # The issue is scavenge() sets phase to EXPLORE.
            # But we want to see the result.
            # Let's modify scavenge to return the item found, and we display it here.
            # OR, we just let scavenge do its thing and we exit the event.
            # But scavenge() checks turn end and updates time.
            # Let's just call it. It will switch phase to EXPLORE.
            # But we might want to see "Event Result" screen.
            # Actually, scavenge() prints a message to the log.
            # If we switch to EXPLORE immediately, the user sees the log.
            # That's acceptable.
            return

        # Build detailed result message
        changes = []
        
        if 'stamina' in effects: 
            val = effects['stamina']
            self.state.stamina += val
            changes.append({'icon': '⚡', 'text': f"体力 {'+' if val>0 else ''}{val}"})
            
        if 'sanity' in effects: 
            val = effects['sanity']
            self.state.sanity += val
            changes.append({'icon': '🧠', 'text': f"SAN值 {'+' if val>0 else ''}{val}"})
            
        if 'health' in effects:
            val = effects['health']
            self.state.health += val
            changes.append({'icon': '❤️', 'text': f"健康 {'+' if val>0 else ''}{val}"})
            
        if 'thirst' in effects:
            val = effects['thirst']
            self.state.thirst += val
            changes.append({'icon': '💧', 'text': f"口渴 {'+' if val>0 else ''}{val}"})
            
        if 'hunger' in effects:
            val = effects['hunger']
            self.state.hunger += val
            changes.append({'icon': '🍗', 'text': f"饥饿 {'+' if val>0 else ''}{val}"})
            
        if 'karma' in effects: 
            val = effects['karma']
            self.state.karma += val
            changes.append({'icon': '🌟', 'text': f"人品 {'+' if val>0 else ''}{val}"})
            
        if 'remove_item' in effects:
            item_id = effects['remove_item']
            item = self.item_system.get_item(item_id)
            if item:
                self.state.remove_item(item_id)
                changes.append({'icon': '🗑️', 'text': f"失去物品: {item['name']}"})
        
        if 'change_weather' in effects:
            new_weather = effects['change_weather']
            self.state.weather = new_weather
            self.update_environment()
            changes.append({'icon': '☁️', 'text': f"天气变为: {new_weather}"})
                
        if 'action_points' in effects:
            val = effects['action_points']
            self.state.action_points += val # Usually negative
            changes.append({'icon': '👣', 'text': f"行动点 {'+' if val>0 else ''}{val}"})
            
        if 'stamina_cost_multiplier' in effects:
            changes.append({'icon': '⚠️', 'text': "体力消耗增加"})

        narrative = effects.get('message', "发生了什么？")
        
        self.event_result_data = {
            'text': narrative,
            'changes': changes
        }
            
        self.game_phase = "EVENT_RESULT"
        self.setup_event_result_ui()

    def setup_event_result_ui(self):
        self.ui.clear_buttons()
        self.ui.add_button("确定", self.close_event_result, SCREEN_WIDTH//2 - 100, 450, color=GREEN)

    def close_event_result(self):
        self.game_phase = "EXPLORE"
        self.current_event = None
        self.check_turn_end()
        if self.game_phase != "GAME_OVER":
            self.setup_explore_ui()

    def setup_game_over_ui(self):
        self.ui.clear_buttons()
        # Moved button down to avoid overlap with summary stats
        self.ui.add_button("返回主菜单", self.setup_menu_phase, SCREEN_WIDTH//2 - 100, 550, color=BLUE)

    def manual_save(self):
        if self.state.save_game():
            self.ui.add_message("进度已保存。")
        else:
            self.ui.add_message("保存失败！")

    def check_explore_clicks(self, pos):
        x, y = pos
        # Coordinates based on ui.py draw_main_view
        # Content Y = 180
        # Info Line Y = 250 (180+70)
        # Env Line Y = 285 (250+35)
        
        # Altitude: x ~40-180, y ~250-280
        if 40 <= x <= 180 and 250 <= y <= 280:
            self.show_altitude_info()
        # Terrain: x ~200-350, y ~250-280
        elif 200 <= x <= 350 and 240 <= y <= 280:
            self.show_terrain_info()
        # Weather: x ~380-530, y ~250-280
        elif 380 <= x <= 530 and 240 <= y <= 280:
            self.show_weather_info()
        # Temp: x ~40-180, y ~285-315
        elif 40 <= x <= 180 and 280 <= y <= 320:
            self.show_temp_info()
        # Wind: x ~200-350, y ~285-315
        elif 200 <= x <= 350 and 280 <= y <= 320:
            self.show_wind_info()

    def show_altitude_info(self):
        node = self.map_system.get_node(self.state.current_node_id)
        alt = node.get('altitude', 0)
        msg = f"当前海拔: {alt}m。"
        if alt > 3000:
            msg += " 高海拔区域，气温较低，容易引发高原反应。"
        elif alt > 2500:
            msg += " 海拔较高，注意保暖。"
        else:
            msg += " 海拔适中，含氧量充足。"
        self.ui.add_message(f"【海拔】{msg}")

    def show_terrain_info(self):
        node = self.map_system.get_node(self.state.current_node_id)
        terrain = node.get('terrain', 'normal')
        info = {
            "forest": "森林: 移动速度一般，体力消耗正常。",
            "rocky": "乱石坡: 移动困难，体力消耗增加，易受伤。",
            "ridge": "山脊: 视野开阔，但风大，体力消耗略增。",
            "danger": "危险路段: 极难通行，体力消耗极大，需小心。",
            "meadow": "草甸: 地势平缓，移动较快。",
            "normal": "平路: 标准移动速度。"
        }
        self.ui.add_message(f"【地形】{info.get(terrain, terrain)}")

    def show_weather_info(self):
        weather = self.state.weather
        info = {
            "sunny": "晴朗: 视野好，气温较高，体力消耗正常。",
            "cloudy": "多云: 气温适宜。",
            "fog": "大雾: 视野受限，容易迷路，气温略低。",
            "rain": "小雨: 湿滑，气温降低，体力消耗增加。",
            "snow": "大雪: 积雪难行，极寒，体力消耗大。",
            "storm": "暴风雪: 极度危险！气温骤降，寸步难行，请立即扎营！"
        }
        self.ui.add_message(f"【天气】{info.get(weather, weather)}")

    def show_temp_info(self):
        temp = self.state.env_temp
        msg = f"当前气温 {temp:.1f}°C。"
        if temp < -20: msg += " 极寒！面临严重失温风险，体力流失极快！"
        elif temp < -10: msg += " 严寒。需注意保暖，体力消耗增加。"
        elif temp < 0: msg += " 寒冷。气温在冰点以下。"
        elif temp > 30: msg += " 炎热。注意防暑补水。"
        else: msg += " 气温尚可。"
        self.ui.add_message(f"【气温】{msg}")

    def show_wind_info(self):
        wind = self.state.wind_level
        msg = f"当前风力 {wind}级。"
        if wind >= 8: msg += " 狂风！行走极其困难，体感温度极低！"
        elif wind >= 6: msg += " 强风。阻力大，消耗更多体力。"
        elif wind >= 4: msg += " 和风。有明显阻力。"
        else: msg += " 微风。对行动影响不大。"
        self.ui.add_message(f"【风力】{msg}")

    def setup_menu_phase(self):
        self.game_phase = "MENU"
        self.setup_menu()

    # --- Character Abilities ---
    
    def use_teleport(self):
        if self.state.teleport_used:
            self.ui.add_message("瞬移能力已使用过！")
            return
            
        # Find next node
        current_node = self.map_system.get_node(self.state.current_node_id)
        connections = self.map_system.get_connections(self.state.current_node_id)
        
        if not connections:
            self.ui.add_message("没有下一站可以传送！")
            return
            
        # Teleport to first connection (usually only one in linear path)
        target_node_id = connections[0]['node_id']
        
        self.state.teleport_used = True
        self.ui.add_message("发动超能力！瞬间移动！")
        self.travel_to_node(target_node_id)

    def quit_game(self):
        pygame.quit()
        sys.exit()

    async def run(self):
        while True:
            self.clock.tick(FPS)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_game()
                self.ui.handle_input(event)
                
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.game_phase == "EXPLORE":
                        self.check_explore_clicks(event.pos)
            
            # Handle Slider Updates
            if self.game_phase == "SHOP" and self.shop_slider:
                if abs(self.shop_slider.value - self.shop_scroll_x) > 1:
                    self.shop_scroll_x = self.shop_slider.value
                    self.setup_shop_ui()

            self.screen.fill(BG_COLOR)
            
            if self.game_phase == "MENU":
                self.ui.draw_text(TITLE, SCREEN_WIDTH//2, 150, self.ui.title_font, center=True)
                self.ui.draw_text("一款硬核生存策略游戏", SCREEN_WIDTH//2, 200, self.ui.font, center=True)
            
            elif self.game_phase == "SHOP":
                self.ui.draw_status_panel(self.state, self.item_system)
                self.ui.draw_shop_view(self.state, self.item_system, self.cart, self.selected_shop_item)
                
            elif self.game_phase == "EXPLORE":
                self.ui.draw_status_panel(self.state, self.item_system)
                self.ui.draw_main_view(self.state, self.map_system)
                
            elif self.game_phase == "EVENT":
                self.ui.draw_status_panel(self.state, self.item_system)
                # Draw Event Panel (Centered)
                panel_w = 800
                panel_x = (SCREEN_WIDTH - panel_w) // 2
                panel_y = 150
                panel_h = 500
                self.ui.draw_panel(panel_x, panel_y, panel_w, panel_h)

            # ... rest of the draw logic ... (I should be careful not to skip too much)
            # Actually I'll just add the await at the end of the loop in a separate replacement
            # and change the def run(self) to async def run(self)
                
                # Header
                icon_w = self.ui.draw_emoji("⚠️", panel_x + 30, panel_y + 30, 48)
                self.ui.draw_text(f"事件: {self.current_event['name']}", panel_x + 30 + icon_w + 10, panel_y + 40, self.ui.title_font, color=ORANGE)
                
                # Description
                self.ui.draw_text(self.current_event['description'], panel_x + 40, panel_y + 100, self.ui.large_font)
                
            elif self.game_phase == "EVENT_RESULT":
                self.ui.draw_status_panel(self.state, self.item_system)
                self.ui.draw_event_result(self.event_result_data)

            elif self.game_phase == "WARNING":
                self.ui.draw_status_panel(self.state, self.item_system)
                
                panel_w = 500
                panel_h = 300
                panel_x = (SCREEN_WIDTH - panel_w) // 2
                panel_y = 200
                
                self.ui.draw_panel(panel_x, panel_y, panel_w, panel_h, color=(50, 0, 0), border_color=RED)
                
                self.ui.draw_emoji("⚠️", panel_x + 220, panel_y + 30, 64)
                self.ui.draw_text("生命警告", panel_x + 250, panel_y + 110, self.ui.title_font, color=RED, center=True)
                
                # Draw multiline warning message
                lines = self.warning_msg.split('\n')
                y_off = 160
                for line in lines:
                    self.ui.draw_text(line, panel_x + 250, panel_y + y_off, self.ui.large_font, color=WHITE, center=True)
                    y_off += 30

            elif self.game_phase == "COOKING_CHOICE":
                self.ui.draw_status_panel(self.state, self.item_system)
                
                panel_w = 400
                panel_h = 200
                panel_x = (SCREEN_WIDTH - panel_w) // 2
                panel_y = 250
                
                self.ui.draw_panel(panel_x, panel_y, panel_w, panel_h, color=PANEL_COLOR, border_color=GREEN)
                self.ui.draw_text("烹饪选择", panel_x + 200, panel_y + 30, self.ui.title_font, center=True)
                self.ui.draw_text("你有全套炊具，是否煮熟食用？", panel_x + 200, panel_y + 70, self.ui.font, center=True)

            elif self.game_phase == "RETREAT_CONFIRM":
                self.ui.draw_status_panel(self.state, self.item_system)
                
                panel_w = 400
                panel_h = 200
                panel_x = (SCREEN_WIDTH - panel_w) // 2
                panel_y = 250
                
                self.ui.draw_panel(panel_x, panel_y, panel_w, panel_h, color=PANEL_COLOR, border_color=RED)
                self.ui.draw_text("下撤确认", panel_x + 200, panel_y + 30, self.ui.title_font, center=True)
                self.ui.draw_text("确定要结束游戏并下撤吗？", panel_x + 200, panel_y + 70, self.ui.font, center=True)
                self.ui.draw_text("当前进度将保存为存活结局。", panel_x + 200, panel_y + 95, self.ui.small_font, color=GRAY, center=True)

            elif self.game_phase == "EAT_SNOW_CONFIRM":
                self.ui.draw_status_panel(self.state, self.item_system)
                
                panel_w = 400
                panel_h = 250
                panel_x = (SCREEN_WIDTH - panel_w) // 2
                panel_y = 250
                
                self.ui.draw_panel(panel_x, panel_y, panel_w, panel_h, color=PANEL_COLOR, border_color=CYAN)
                self.ui.draw_text("吃雪确认", panel_x + 200, panel_y + 30, self.ui.title_font, center=True)
                self.ui.draw_text("直接吃雪会导致体温骤降！", panel_x + 200, panel_y + 70, self.ui.font, center=True, color=RED)
                self.ui.draw_text("体温-2, 健康-5, SAN-10", panel_x + 200, panel_y + 100, self.ui.font, center=True)

            elif self.game_phase == "GAME_OVER":
                self.ui.draw_game_over(self.state)

            self.ui.draw_buttons()
            pygame.display.flip()
            await asyncio.sleep(0)

async def main():
    print("Initializing game...")
    game = Game()
    print("Starting main loop...")
    await game.run()

if __name__ == "__main__":
    asyncio.run(main())
