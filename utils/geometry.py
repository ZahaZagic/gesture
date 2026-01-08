import numpy as np
import math

def calculate_distance(p1, p2):
    """Euclidean distance between two 2D points."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def calculate_distance_normalized(p1, p2):
    """Distance for normalized landmarks (0.0-1.0)."""
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

def get_midpoint(p1, p2):
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

def map_range(value, in_min, in_max, out_min, out_max):
    """Maps a value from one range to another."""
    return out_min + (((value - in_min) / (in_max - in_min)) * (out_max - out_min))
