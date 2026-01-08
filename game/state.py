import json
import os
from .config import *

class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        # Player Stats
        self.stamina = MAX_STAMINA
        self.hunger = MAX_HUNGER
        self.thirst = MAX_THIRST
        self.temperature = 36.5
        self.sanity = MAX_SANITY
        self.health = MAX_HEALTH
        
        # Game Progress
        self.current_node_id = "start"
        self.distance_traveled = 0 # Distance traveled towards next node
        self.distance_to_next_node = 0 # Remaining distance to next node
        self.total_distance = 0 # Total distance traveled
        self.action_points = DAILY_ACTION_POINTS
        self.money = START_MONEY
        self.karma = 0
        self.game_time = 0 # In days
        self.day_time = 8 # Hour of day (8:00 start)
        
        # Inventory
        self.inventory = {} # item_id: count
        self.equipment = [] # List of equipped item ids
        
        # Environment
        self.weather = "sunny"
        self.weather_duration = 0
        self.env_temp = 20.0
        self.wind_level = 1
        
        # Flags
        self.game_over = False
        self.game_won = False
        self.status_message = "游戏开始。请做好准备。"
        self.triggered_events = set() # Set of event_ids that have been triggered
        
        # Character & Season
        self.character_id = "xiaomou" # Default
        self.season = "spring" # Default
        self.teleport_used = False # For student ability
        
        # Statistics for Game Over
        self.max_altitude = 0
        self.lowest_temp = 100
        self.lowest_sanity = 100
        self.days_survived = 0

    def get_max_weight(self, item_system):
        max_w = MAX_WEIGHT_BASE
        # Check inventory for backpacks
        # Since we can have multiple items, we should probably take the best backpack
        # or sum them? Usually you wear one.
        # Let's assume the best backpack applies.
        best_bonus = 0
        for item_id in self.inventory:
            item = item_system.get_item(item_id)
            if item and 'capacity_bonus' in item['effects']:
                bonus = item['effects']['capacity_bonus']
                if bonus > best_bonus:
                    best_bonus = bonus
        return max_w + best_bonus

    def update_body_temp(self, env_temp, gear_warmth):
        # Target temp is 37.0
        target = 37.0
        
        # If env_temp < gear_warmth, we lose heat
        # gear_warmth is effectively the minimum temp we can withstand without losing heat
        # e.g. sleeping bag -15 means we are fine down to -15?
        # Or is it a bonus?
        # Let's assume gear_warmth is a threshold.
        # Actually, usually gear has a "warmth rating".
        # Let's say effective_temp = env_temp + gear_warmth
        # If effective_temp < 20 (room temp), we start cooling?
        # Simplified:
        # diff = env_temp - gear_warmth (if gear_warmth is negative rating like -15)
        # Let's assume gear_warmth is positive insulation value.
        # But items.json has "night_temperature_loss": -2.0. That's a modifier to loss.
        
        # Let's use a simpler model based on the user request:
        # "If hunger rises or temp < warm gear, move -> temp drop"
        
        # We'll calculate a heat_loss factor
        heat_loss = 0
        
        # Cold factor
        # Assume gear_warmth is the temperature limit (e.g. -10).
        # If env_temp < gear_warmth, we lose heat.
        if env_temp < gear_warmth:
            heat_loss += (gear_warmth - env_temp) * 0.02 # Reduced from 0.05
            
        # Hunger factor
        # User Request: Hunger < 20, slow drop.
        if self.hunger < 20:
            heat_loss += 0.05 # Reduced from 0.1
        if self.hunger <= 0:
            heat_loss += 0.1 # Reduced from 0.2
            
        # Apply loss
        if heat_loss > 0:
            self.temperature -= heat_loss
            # Even if losing heat, if we are very well fed, we might offset it slightly
            if self.hunger > 80:
                self.temperature += 0.02
        else:
            # Recover if warm OR well fed
            recover_rate = 0
            if self.temperature < 37.0:
                # Base recovery if in comfortable environment
                if env_temp >= gear_warmth:
                    recover_rate += 0.1 # Increased from 0.05
                
                # Bonus recovery from food energy
                if self.hunger > 70:
                    recover_rate += 0.1 # Increased from 0.05
                if self.hunger > 90:
                    recover_rate += 0.1 # Extra boost
            
            self.temperature += recover_rate
                
        self.clamp_stats()
        
        # Update stats
        if self.temperature < self.lowest_temp:
            self.lowest_temp = self.temperature

    def update_sanity_drain(self):
        drain = 0
        if self.temperature < 35: drain += 2
        if self.temperature < 34: drain += 5
        if self.health < 50: drain += 1
        if self.hunger < 20: drain += 1
        if self.thirst < 20: drain += 1
        
        if drain > 0:
            self.sanity -= drain
        else:
            # Recover SAN if well fed, hydrated and warm
            if self.hunger > 80 and self.thirst > 80 and self.temperature >= 36.5:
                self.sanity += 1
            
        if self.sanity < self.lowest_sanity:
            self.lowest_sanity = self.sanity

    def add_item(self, item_id, count=1):
        if item_id in self.inventory:
            self.inventory[item_id] += count
        else:
            self.inventory[item_id] = count

    def remove_item(self, item_id, count=1):
        if item_id in self.inventory:
            self.inventory[item_id] -= count
            if self.inventory[item_id] <= 0:
                del self.inventory[item_id]
            return True
        return False

    def has_item(self, item_id):
        return item_id in self.inventory and self.inventory[item_id] > 0

    def update_time(self, hours):
        self.day_time += hours
        if self.day_time >= 24:
            self.day_time -= 24
            self.game_time += 1
            self.action_points = DAILY_ACTION_POINTS # Reset AP on new day
            return True # New day
        return False

    def clamp_stats(self):
        self.stamina = max(0, min(MAX_STAMINA, self.stamina))
        self.hunger = max(0, min(MAX_HUNGER, self.hunger))
        self.thirst = max(0, min(MAX_THIRST, self.thirst))
        self.sanity = max(0, min(MAX_SANITY, self.sanity))
        self.health = max(0, min(MAX_HEALTH, self.health))
        self.temperature = max(30.0, min(MAX_TEMP, self.temperature))

    def check_game_over(self):
        self.clamp_stats()
        if self.health <= 0:
            self.game_over = True
            self.status_message = "你因健康耗尽而倒下。"
        elif self.sanity <= 0:
            self.game_over = True
            self.status_message = "你的精神崩溃了。"
        elif self.temperature < 32: # Lowered slightly
            self.game_over = True
            self.status_message = "你死于失温。"
        elif self.hunger <= 0:
            self.game_over = True
            self.status_message = "你饿死了。"
        elif self.thirst <= 0:
            self.game_over = True
            self.status_message = "你渴死了。"
        elif self.current_node_id == "end":
            self.game_over = True
            self.game_won = True
            self.status_message = "恭喜！你成功穿越了鳌太线！"
        
        return self.game_over

    def save_game(self, filename="savegame.json"):
        data = {
            "stamina": self.stamina,
            "hunger": self.hunger,
            "thirst": self.thirst,
            "temperature": self.temperature,
            "sanity": self.sanity,
            "health": self.health,
            "current_node_id": self.current_node_id,
            "distance_traveled": self.distance_traveled,
            "distance_to_next_node": self.distance_to_next_node,
            "total_distance": self.total_distance,
            "action_points": self.action_points,
            "money": self.money,
            "karma": self.karma,
            "game_time": self.game_time,
            "day_time": self.day_time,
            "inventory": self.inventory,
            "equipment": self.equipment,
            "weather": self.weather,
            "weather_duration": self.weather_duration,
            "env_temp": self.env_temp,
            "wind_level": self.wind_level,
            "triggered_events": list(self.triggered_events),
            "max_altitude": self.max_altitude,
            "lowest_temp": self.lowest_temp,
            "lowest_sanity": self.lowest_sanity,
            "days_survived": self.days_survived
        }
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Save failed: {e}")
            return False

    def load_game(self, filename="savegame.json"):
        if not os.path.exists(filename):
            return False
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key, value in data.items():
                if key == "triggered_events":
                    setattr(self, key, set(value))
                else:
                    setattr(self, key, value)
            return True
        except Exception as e:
            print(f"Load failed: {e}")
            return False

    def save_cart(self, cart, filename="last_cart.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(cart, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_cart(self, filename="last_cart.json"):
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def consume_item(self, item):
        effects = item.get('effects', {})
        used = False
        
        # Items directly modify stats
        # Positive = Restore/Increase
        # Negative = Drain/Decrease
        
        if 'hunger' in effects:
            self.hunger += effects['hunger']
            used = True
            
        if 'thirst' in effects:
            self.thirst += effects['thirst']
            used = True
            
        if 'stamina' in effects:
            self.stamina += effects['stamina']
            used = True
        if 'sanity' in effects:
            self.sanity += effects['sanity']
            used = True
        if 'heal' in effects:
            self.health += effects['heal']
            used = True
            
        self.clamp_stats()
        return used
        return used
