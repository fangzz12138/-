import pygame
import math
import random
from .config import *

class EnvironmentVisualizer:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)
        self.animation_timer = 0
        
        # Persistent State
        self.clouds = []
        self.terrain_elements = []
        self.weather_particles = []
        self.current_terrain_type = None
        self.current_weather_type = None
        
        # Initialize Clouds
        for i in range(5):
            self.clouds.append({
                'x': random.randint(0, w),
                'y': random.randint(0, h // 3),
                'speed': random.uniform(0.2, 0.8), # Slower clouds
                'size': random.randint(40, 80)
            })

    def update_terrain_elements(self, terrain_type, ground_y):
        if self.current_terrain_type == terrain_type:
            return
            
        self.current_terrain_type = terrain_type
        self.terrain_elements = []
        
        if terrain_type == 'forest':
            # Generate static trees
            count = 12
            for i in range(count):
                # Randomize x slightly but keep order
                x = self.rect.x + (i * (self.rect.width / count)) + random.randint(-10, 10)
                y = ground_y + random.randint(-5, 10)
                # Tree properties: type (0=pine, 1=round), height, color var
                self.terrain_elements.append({
                    'type': 'tree',
                    'x': x,
                    'y': y,
                    'variant': random.choice(['pine', 'round']),
                    'scale': random.uniform(0.8, 1.2),
                    'color_offset': random.randint(-20, 20)
                })
        elif terrain_type == 'rocky':
            # Generate static rocks
            count = 60 # Increased for denser look
            for i in range(count):
                x = self.rect.x + random.randint(0, self.rect.width)
                y = ground_y + random.randint(-20, 60) # Spread vertically
                self.terrain_elements.append({
                    'type': 'rock',
                    'x': x,
                    'y': y,
                    'size': random.randint(8, 25),
                    'shape': [random.randint(-4, 4) for _ in range(6)] # Random vertices offsets
                })
        # Add more terrain types as needed

    def update_weather_particles(self, weather, wind_level):
        # Adjust particle count based on weather
        target_count = 0
        if weather == 'rain': target_count = 100
        elif weather == 'storm': target_count = 200
        elif weather == 'snow': target_count = 150
        
        # Add or remove particles
        while len(self.weather_particles) < target_count:
            self.weather_particles.append({
                'x': random.randint(self.rect.x, self.rect.x + self.rect.width),
                'y': random.randint(self.rect.y, self.rect.y + self.rect.height),
                'speed': random.uniform(2, 5) if weather != 'snow' else random.uniform(1, 3),
                'size': random.randint(1, 3)
            })
        
        if len(self.weather_particles) > target_count:
            self.weather_particles = self.weather_particles[:target_count]

        # Update positions
        for p in self.weather_particles:
            # Fall down
            p['y'] += p['speed']
            # Wind effect (Reversed: Blows Left)
            p['x'] -= wind_level * 0.5
            
            # Reset if out of bounds
            if p['y'] > self.rect.bottom:
                p['y'] = self.rect.top - 10
                p['x'] = random.randint(self.rect.x, self.rect.x + self.rect.width + 100)
            if p['x'] < self.rect.left:
                p['x'] = self.rect.right + 10

    def draw(self, screen, game_state, map_system):
        self.animation_timer += 1
        
        # Clip drawing to the rect
        clip_rect = self.rect
        prev_clip = screen.get_clip()
        screen.set_clip(clip_rect)
        
        # 1. Draw Background (Sky & Terrain)
        self.draw_background(screen, game_state, map_system)
        
        # 2. Draw Character
        self.draw_character(screen, game_state)
        
        # 3. Draw Weather/Wind Effects
        self.draw_effects(screen, game_state)
        
        # 4. Fog Overlay
        if game_state.weather == 'fog':
            self.draw_fog_overlay(screen)
        
        # Restore clip
        screen.set_clip(prev_clip)
        
        # Draw Border
        pygame.draw.rect(screen, GRAY, self.rect, 4)

    def draw_background(self, screen, game_state, map_system):
        node = map_system.get_node(game_state.current_node_id)
        terrain = node.get('terrain', 'normal')
        weather = game_state.weather
        altitude = node.get('altitude', 0)
        
        # Base Sky Color
        if weather in ['sunny']:
            sky_color = (100, 180, 255) # Brighter Blue
        elif weather in ['cloudy', 'fog']:
            sky_color = (180, 190, 200)
        elif weather in ['rain', 'storm']:
            sky_color = (80, 90, 100)
        elif weather in ['snow']:
            sky_color = (200, 210, 220)
        else:
            sky_color = (100, 180, 255)
            
        # Time of Day Tint & Sun Position
        hour = game_state.day_time
        
        # Calculate Sun/Moon Position (Arc)
        # 6:00 (Rise) -> 12:30 (Zenith) -> 19:00 (Set)
        # Map hour to angle: 6 -> PI, 12.5 -> PI/2, 19 -> 0
        # Actually, standard math: 0 is right, PI is left.
        # So 6am (Left) = PI, 19pm (Right) = 0.
        
        sun_visible = False
        moon_visible = False
        celestial_x = 0
        celestial_y = 0
        
        if 5 <= hour <= 20:
            sun_visible = True
            # Normalize time to 0.0 - 1.0 range for day (5 to 20 = 15 hours)
            t = (hour - 5) / 15.0
            # Arc: x goes from left to right, y goes up then down
            celestial_x = self.rect.x + int(t * self.rect.width)
            # Y: Peak at 0.5. Use sine wave.
            # sin(0) = 0, sin(PI) = 0. Peak at PI/2.
            # t * PI
            celestial_y = self.rect.bottom - 50 - int(math.sin(t * math.pi) * (self.rect.height * 0.8))
        else:
            moon_visible = True
            # Night time logic (20 to 5 = 9 hours)
            if hour >= 20:
                t = (hour - 20) / 9.0
            else:
                t = (hour + 4) / 9.0 # 0-4am is late night
            
            celestial_x = self.rect.x + int(t * self.rect.width)
            celestial_y = self.rect.bottom - 50 - int(math.sin(t * math.pi) * (self.rect.height * 0.6))

        # Sky Color Interpolation
        # Define key colors for times
        colors = {
            0: (10, 10, 30),    # Midnight
            5: (20, 20, 60),    # Pre-dawn
            6: (255, 100, 50),  # Sunrise (Orange/Red)
            8: (135, 206, 235), # Morning (Sky Blue)
            12: (100, 180, 255),# Noon (Bright Blue)
            17: (135, 206, 235),# Late Afternoon
            19: (255, 140, 0),  # Sunset (Orange)
            20: (50, 50, 100),  # Dusk
            24: (10, 10, 30)    # Midnight loop
        }
        
        # Find current interval
        h1, h2 = 0, 24
        c1, c2 = colors[0], colors[24]
        
        sorted_hours = sorted(colors.keys())
        for i in range(len(sorted_hours)-1):
            if sorted_hours[i] <= hour < sorted_hours[i+1]:
                h1 = sorted_hours[i]
                h2 = sorted_hours[i+1]
                c1 = colors[h1]
                c2 = colors[h2]
                break
                
        # Interpolate
        if h2 == h1: factor = 0
        else: factor = (hour - h1) / (h2 - h1)
        
        current_sky = (
            int(c1[0] + (c2[0] - c1[0]) * factor),
            int(c1[1] + (c2[1] - c1[1]) * factor),
            int(c1[2] + (c2[2] - c1[2]) * factor)
        )
        
        # Weather Overrides
        if weather in ['rain', 'storm']:
            # Darken sky
            current_sky = (
                int(current_sky[0] * 0.4),
                int(current_sky[1] * 0.5),
                int(current_sky[2] * 0.6)
            )
        elif weather == 'cloudy':
             current_sky = (
                int(current_sky[0] * 0.7),
                int(current_sky[1] * 0.75),
                int(current_sky[2] * 0.8)
            )
        elif weather == 'snow':
             current_sky = (220, 225, 230) # White/Grey sky
            
        pygame.draw.rect(screen, current_sky, self.rect)
        
        # Draw Celestial Body
        if sun_visible and weather in ['sunny', 'cloudy', 'snow']: # Sun hidden in rain/storm
            # Sun
            pygame.draw.circle(screen, (255, 220, 0), (celestial_x, celestial_y), 25)
            pygame.draw.circle(screen, (255, 255, 100), (celestial_x, celestial_y), 20)
        elif moon_visible:
            # Moon
            pygame.draw.circle(screen, (240, 240, 255), (celestial_x, celestial_y), 20)
            pygame.draw.circle(screen, current_sky, (celestial_x - 10, celestial_y), 15) # Crescent shape

        # Clouds (Slower, fluffier)
        for cloud in self.clouds:
            cloud['x'] += cloud['speed'] * (1 + game_state.wind_level * 0.05)
            if cloud['x'] > self.rect.width + 100:
                cloud['x'] = -100
                cloud['y'] = random.randint(0, self.rect.height // 3)
            
            cx = self.rect.x + int(cloud['x'])
            cy = self.rect.y + int(cloud['y'])
            # Draw cloud as multiple circles
            c_color = (255, 255, 255, 200)
            if weather in ['rain', 'storm']: c_color = (150, 150, 160, 200)
            
            pygame.draw.circle(screen, c_color, (cx, cy), 20)
            pygame.draw.circle(screen, c_color, (cx+25, cy-10), 25)
            pygame.draw.circle(screen, c_color, (cx+50, cy), 20)

        # Mountains (Background Layer)
        if altitude > 2500:
            mx = self.rect.x
            my = self.rect.bottom - 40
            # Draw jagged peaks
            points = [
                (mx, my), 
                (mx + 100, my - 120), 
                (mx + 200, my - 40), 
                (mx + 350, my - 180), 
                (mx + 500, my - 60), 
                (mx + 640, my - 100), 
                (mx + 640, my)
            ]
            pygame.draw.polygon(screen, (60, 70, 80), points)
            # Snow caps
            pygame.draw.polygon(screen, (240, 240, 255), [(mx+85, my-100), (mx+100, my-120), (mx+115, my-100)])
            pygame.draw.polygon(screen, (240, 240, 255), [(mx+330, my-150), (mx+350, my-180), (mx+370, my-150)])

        # Ground
        ground_y = self.rect.y + self.rect.height * 0.65
        ground_h = self.rect.height * 0.35
        ground_rect = pygame.Rect(self.rect.x, ground_y, self.rect.width, ground_h)
        
        # Ground Colors
        top_color = (34, 139, 34)
        side_color = (101, 67, 33)
        
        if terrain == 'rocky' or terrain == 'ridge':
            top_color = (100, 100, 100)
            side_color = (60, 60, 60)
        elif terrain == 'snow' or altitude > 3500 or weather == 'snow':
            top_color = (240, 250, 255)
            side_color = (200, 210, 220)
        elif terrain == 'meadow':
            top_color = (100, 200, 50)
            side_color = (80, 160, 40)
            
        # Draw Ground Block
        pygame.draw.rect(screen, side_color, ground_rect)
        pygame.draw.rect(screen, top_color, (self.rect.x, ground_y, self.rect.width, 15)) # Top layer
        
        # Update and Draw Static Elements
        self.update_terrain_elements(terrain, ground_y)
        
        wind = getattr(game_state, 'wind_level', 1)
        
        for el in self.terrain_elements:
            if el['type'] == 'tree':
                self.draw_pixel_tree(screen, el['x'], el['y'], el['variant'], el['scale'], el['color_offset'], wind, weather)
            elif el['type'] == 'rock':
                self.draw_pixel_rock(screen, el['x'], el['y'], el['size'], el['shape'], weather)

    def draw_pixel_tree(self, screen, x, y, variant, scale, color_offset, wind_level, weather):
        # Calculate sway
        sway = math.sin(self.animation_timer * 0.1 + x * 0.05) * (wind_level * 1.0)
        
        # Trunk
        tw = 12 * scale
        th = 30 * scale
        pygame.draw.rect(screen, (80, 50, 20), (x - tw/2, y - th, tw, th))
        
        # Leaves
        base_color = (34, 139, 34)
        if weather == 'snow':
             base_color = (200, 220, 200) # Snow covered
             
        c = (max(0, min(255, base_color[0] + color_offset)),
             max(0, min(255, base_color[1] + color_offset)),
             max(0, min(255, base_color[2] + color_offset)))
             
        if variant == 'pine':
            # Triangle layers with sway
            # Top moves most, bottom moves least
            s1 = sway * 0.5
            s2 = sway * 0.8
            s3 = sway * 1.0
            
            pygame.draw.polygon(screen, c, [(x + s1, y-th-40*scale), (x-20*scale, y-th), (x+20*scale, y-th)])
            pygame.draw.polygon(screen, c, [(x + s2, y-th-60*scale), (x-15*scale + s1, y-th-20*scale), (x+15*scale + s1, y-th-20*scale)])
            
            # Snow on top
            if weather == 'snow':
                pygame.draw.polygon(screen, (240, 240, 250), [(x + s2, y-th-60*scale), (x-5*scale + s1, y-th-45*scale), (x+5*scale + s1, y-th-45*scale)])
                
        else:
            # Round top (Circles) with sway
            pygame.draw.circle(screen, c, (x + sway, y-th-15*scale), 20*scale)
            pygame.draw.circle(screen, c, (x-10*scale + sway*0.8, y-th-5*scale), 15*scale)
            pygame.draw.circle(screen, c, (x+10*scale + sway*0.8, y-th-5*scale), 15*scale)
            
            # Snow on top
            if weather == 'snow':
                 pygame.draw.circle(screen, (240, 240, 250), (x + sway, y-th-25*scale), 10*scale)

    def draw_pixel_rock(self, screen, x, y, size, shape, weather):
        # Draw a polygon rock
        points = [
            (x, y),
            (x + size + shape[0], y),
            (x + size + shape[1], y - size + shape[2]),
            (x + size/2 + shape[3], y - size*1.2 + shape[4]),
            (x + shape[5], y - size + shape[0])
        ]
        pygame.draw.polygon(screen, (100, 100, 100), points)
        pygame.draw.lines(screen, (60, 60, 60), True, points, 2)
        
        # Snow on rock
        if weather == 'snow':
             snow_points = [
                (x + size + shape[1], y - size + shape[2]),
                (x + size/2 + shape[3], y - size*1.2 + shape[4]),
                (x + shape[5], y - size + shape[0])
             ]
             pygame.draw.polygon(screen, (240, 240, 250), snow_points)

    def draw_character(self, screen, game_state):
        # Pixel Art Style Character
        cx = self.rect.x + self.rect.width // 2
        cy = self.rect.y + self.rect.height * 0.65
        
        scale = 2
        
        # Bobbing
        bob = int(math.sin(self.animation_timer * 0.15) * 2)
        
        # Colors
        skin = (255, 200, 180)
        shirt = (200, 50, 50) # Red jacket
        pants = (50, 50, 150) # Blue pants
        pack = (160, 82, 45) # Brown pack
        
        # Backpack
        pygame.draw.rect(screen, pack, (cx - 8*scale, cy - 22*scale + bob, 6*scale, 14*scale))
        
        # Legs (Walking)
        leg_anim = math.sin(self.animation_timer * 0.2)
        # Left Leg
        l_off = int(leg_anim * 5 * scale)
        pygame.draw.rect(screen, pants, (cx - 2*scale + l_off, cy - 8*scale, 3*scale, 8*scale))
        # Right Leg
        r_off = int(-leg_anim * 5 * scale)
        pygame.draw.rect(screen, pants, (cx + 2*scale + r_off, cy - 8*scale, 3*scale, 8*scale))
        
        # Body
        pygame.draw.rect(screen, shirt, (cx - 4*scale, cy - 20*scale + bob, 8*scale, 12*scale))
        
        # Head
        pygame.draw.rect(screen, skin, (cx - 3*scale, cy - 26*scale + bob, 6*scale, 6*scale))
        
        # Arms
        arm_off = int(-leg_anim * 4 * scale)
        pygame.draw.rect(screen, shirt, (cx + 4*scale, cy - 18*scale + bob + arm_off, 3*scale, 8*scale))


    def draw_effects(self, screen, game_state):
        weather = game_state.weather
        wind = getattr(game_state, 'wind_level', 1)
        
        self.update_weather_particles(weather, wind)
        
        # Wind Lines (Horizontal streaks)
        if wind >= 3:
            count = int(wind * 2)
            for i in range(count):
                # Random positions that move fast (Reversed: Right to Left)
                # Use negative offset for movement
                offset = (self.animation_timer * (wind * 3) + i * 150)
                wx = self.rect.right + 100 - (offset % (self.rect.width + 200))
                
                wy = self.rect.y + random.randint(20, self.rect.height - 50)
                # Only draw if inside rect
                if self.rect.left < wx < self.rect.right:
                    pygame.draw.line(screen, (255, 255, 255, 100), (wx, wy), (wx - 40 - wind*5, wy), 1)

        # Draw Particles
        for p in self.weather_particles:
            if weather == 'snow':
                pygame.draw.circle(screen, (255, 255, 255), (int(p['x']), int(p['y'])), p['size'])
            else:
                # Rain - Angle based on wind
                angle_x = wind * 2
                end_x = p['x'] - angle_x
                end_y = p['y'] + 10
                pygame.draw.line(screen, (150, 150, 255), (p['x'], p['y']), (end_x, end_y), 1)

    def draw_mini_character(self, screen, x, y):
        # Mini version for progress bar
        # Scale down to fit ~20px height
        scale = 0.5
        cx, cy = x, y
        
        # Colors
        skin = (255, 200, 180)
        shirt = (200, 50, 50)
        pants = (50, 50, 150)
        pack = (160, 82, 45)
        
        # Backpack
        pygame.draw.rect(screen, pack, (cx - 8*scale, cy - 22*scale, 6*scale, 14*scale))
        
        # Legs
        pygame.draw.rect(screen, pants, (cx - 2*scale, cy - 8*scale, 3*scale, 8*scale))
        pygame.draw.rect(screen, pants, (cx + 2*scale, cy - 8*scale, 3*scale, 8*scale))
        
        # Body
        pygame.draw.rect(screen, shirt, (cx - 4*scale, cy - 20*scale, 8*scale, 12*scale))
        
        # Head
        pygame.draw.rect(screen, skin, (cx - 3*scale, cy - 26*scale, 6*scale, 6*scale))

    def draw_fog_overlay(self, screen):
        # Draw a semi-transparent gray rect
        s = pygame.Surface((self.rect.width, self.rect.height))
        s.set_alpha(180) # High opacity for dense fog
        s.fill((200, 200, 210))
        screen.blit(s, (self.rect.x, self.rect.y))
        
        # Draw some "fog clouds" near bottom
        for i in range(5):
            fx = (self.animation_timer * 0.5 + i * 150) % (self.rect.width + 200) - 100
            fy = self.rect.bottom - 40 + math.sin(self.animation_timer * 0.05 + i) * 10
            pygame.draw.ellipse(screen, (220, 220, 230), (fx, fy, 120, 60))
