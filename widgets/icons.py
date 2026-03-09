# widgets/icons.py
import math

PALETTE = {
    0: (0,0,0),         # Black
    1: (255, 200, 0),   # Sun Yellow
    2: (255, 140, 0),   # Sun Orange
    3: (255, 255, 255), # White (Used for Plane)
    4: (100, 100, 100), # Grey (Used for Plane shading)
    5: (180, 80, 255),  # Purple
}

def create_sun_21x32(expanded_rays=False):
    grid = [0] * 672
    center_x, center_y = 10, 15 
    radius = 6
    
    # Draw Core
    for y in range(32):
        for x in range(21):
            dist = ((x-center_x)**2 + (y-center_y)**2)**0.5
            if dist < radius:
                grid[y*21 + x] = 1 if x < center_x + 1 else 2
                
    # Draw Rays
    ray_len = 9 if expanded_rays else 7
    for i in range(0, 360, 45):
        rad = math.radians(i)
        for d in range(radius, ray_len + radius):
            rx = int(center_x + math.cos(rad) * d)
            ry = int(center_y + math.sin(rad) * d)
            if 0 <= rx < 21 and 0 <= ry < 32:
                grid[ry*21 + rx] = 1
    return grid

def create_rain_21x32(frame_offset=0):
    grid = [0] * 672
    # Narrower cloud for 21px
    for y in range(8, 18):
        for x in range(2, 19):
            dist_left = ((x-7)**2 + (y-13)**2)**0.5
            dist_mid = ((x-10)**2 + (y-11)**2)**0.5
            dist_right = ((x-14)**2 + (y-13)**2)**0.5
            if dist_left < 4 or dist_mid < 5 or dist_right < 4:
                grid[y*21 + x] = 3 if y < 14 else 4
                
    # Rain Drops
    drops = [(6, 20), (10, 22), (14, 20), (8, 24), (12, 24)]
    for dx, dy in drops:
        y_pos = (dy + frame_offset) % 32
        if 18 < y_pos < 31:
            grid[int(y_pos)*21 + dx] = 5
    return grid

def create_side_view_plane():
    # 14x6 side-profile airliner silhouette (Pointing RIGHT)
    # 0=Black, 3=White, 4=Grey shading
    grid = [
        0,3,0,0,0,0,0,0,0,0,0,0,0,0, # Tail top (now on left)
        0,3,3,0,0,0,0,0,0,0,0,0,0,0, # Tail fin
        0,3,3,3,3,3,3,3,3,3,3,3,3,0, # Fuselage top
        3,3,3,3,3,4,4,4,4,3,3,3,3,3, # Main body + wing area
        0,0,3,3,3,3,3,3,3,3,3,3,0,0, # Fuselage bottom
        0,0,0,0,0,4,4,4,4,0,0,0,0,0, # Lower wing/engine
    ]
    return grid

SIDE_PLANE = create_side_view_plane()

SUN_1 = create_sun_21x32(False)
SUN_2 = create_sun_21x32(True)
RAIN_1 = create_rain_21x32(0)
RAIN_2 = create_rain_21x32(2)

ANIMATIONS = {
    "Clear": [[0]*672],
    "Clouds": [RAIN_1, RAIN_2],
    "Rain": [RAIN_1, RAIN_2],
    "Drizzle": [RAIN_1, RAIN_2],
    "Thunderstorm": [RAIN_1, RAIN_2],
    "SidePlane": [SIDE_PLANE]
}


def get_frame(condition, frame_index):
    frames = ANIMATIONS.get(condition, ANIMATIONS["Clear"])
    current_frame = frames[frame_index % len(frames)]
    return current_frame, PALETTE