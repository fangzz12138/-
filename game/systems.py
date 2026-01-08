import json
import os
import random
from .config import *

class DataLoader:
    @staticmethod
    def load_json(filename):
        path = os.path.join("data", filename)
        if not os.path.exists(path):
            print(f"Error: {path} not found.")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

class ItemSystem:
    def __init__(self):
        self.items = {item['id']: item for item in DataLoader.load_json("items.json")}

    def get_item(self, item_id):
        return self.items.get(item_id)

    def calculate_weight(self, inventory):
        total_weight = 0
        for item_id, count in inventory.items():
            item = self.get_item(item_id)
            if item:
                total_weight += item['weight'] * count
        return total_weight

class MapSystem:
    def __init__(self):
        self.node_list = DataLoader.load_json("map_nodes.json")
        self.nodes = {node['node_id']: node for node in self.node_list}

    def get_node(self, node_id):
        return self.nodes.get(node_id)

    def get_connections(self, node_id):
        node = self.get_node(node_id)
        if node:
            return [self.get_node(conn_id) for conn_id in node['connections']]
        return []

class WeatherSystem:
    def __init__(self):
        self.weather_types = ["sunny", "cloudy", "fog", "rain", "snow", "storm"]
        self.transitions = {
            "sunny": {"sunny": 0.5, "cloudy": 0.3, "fog": 0.1, "rain": 0.1},
            "cloudy": {"sunny": 0.3, "cloudy": 0.4, "fog": 0.1, "rain": 0.2},
            "fog": {"sunny": 0.2, "cloudy": 0.3, "fog": 0.4, "rain": 0.1},
            "rain": {"cloudy": 0.4, "rain": 0.4, "storm": 0.1, "sunny": 0.1},
            "snow": {"cloudy": 0.3, "snow": 0.5, "storm": 0.2},
            "storm": {"snow": 0.5, "cloudy": 0.5}
        }

    def next_weather(self, current_weather, season="spring"):
        # Adjust probabilities based on season
        probs = self.transitions.get(current_weather, {}).copy()
        
        # Season Modifiers
        if season == "summer":
            # More rain/storm, less snow
            if "rain" in probs: probs["rain"] *= 1.5
            if "storm" in probs: probs["storm"] *= 1.5
            if "snow" in probs: probs["snow"] *= 0.1
        elif season == "winter":
            # More snow/storm, less rain
            if "snow" in probs: probs["snow"] *= 2.0
            if "storm" in probs: probs["storm"] *= 1.5
            if "rain" in probs: probs["rain"] *= 0.1
        elif season == "autumn":
            # More sunny/cloudy
            if "sunny" in probs: probs["sunny"] *= 1.5
            
        # Normalize
        total = sum(probs.values())
        if total > 0:
            for k in probs:
                probs[k] /= total
        else:
            return "sunny" # Fallback
            
        rand = random.random()
        cumulative = 0
        for weather, prob in probs.items():
            cumulative += prob
            if rand <= cumulative:
                return weather
        return "sunny"

    def get_weather_effects(self, weather):
        effects = {
            "sunny": {"temp": 2, "stamina_cost": 1.0},
            "cloudy": {"temp": 0, "stamina_cost": 1.0},
            "fog": {"temp": -1, "stamina_cost": 1.1},
            "rain": {"temp": -3, "stamina_cost": 1.3},
            "snow": {"temp": -5, "stamina_cost": 1.5},
            "storm": {"temp": -10, "stamina_cost": 2.0}
        }
        return effects.get(weather, {"temp": 0, "stamina_cost": 1.0})

class EventSystem:
    def __init__(self):
        self.events = DataLoader.load_json("events.json")

    def check_event(self, game_state, map_system, context=None):
        # Simple random event trigger
        if random.random() < 0.3: # 30% chance per check
            valid_events = []
            current_node = map_system.get_node(game_state.current_node_id)
            
            for event in self.events:
                # Check if unique and already triggered
                if event.get("unique", False) and event['event_id'] in game_state.triggered_events:
                    continue

                conditions = event.get("trigger_conditions", {})
                
                # Check terrain condition
                if "terrain" in conditions:
                    if current_node['terrain'] != conditions['terrain']:
                        continue
                
                # Check weather condition (Support list or single string)
                if "weather" in conditions:
                    cond_weather = conditions['weather']
                    if isinstance(cond_weather, list):
                        if game_state.weather not in cond_weather:
                            continue
                    elif game_state.weather != cond_weather:
                        continue

                # Check time condition (day/night)
                if "time" in conditions:
                    is_night = game_state.day_time < 6 or game_state.day_time > 19
                    if conditions['time'] == "night" and not is_night:
                        continue
                    if conditions['time'] == "day" and is_night:
                        continue
                        
                # Check time range
                if "time_range" in conditions:
                    start, end = conditions['time_range']
                    if not (start <= game_state.day_time <= end):
                        continue

                # Check phase condition (e.g. camp, rest, hike)
                if "phase" in conditions and context:
                    if context.get('phase') != conditions['phase']:
                        continue
                
                valid_events.append(event)
            
            if valid_events:
                return random.choice(valid_events)
        return None
