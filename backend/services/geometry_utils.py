"""
Geometry utility functions for PCB design rule checking
Provides accurate distance calculations for clearance and creepage
"""
import math
from typing import List, Tuple, Optional
from models.canonical import Point, BoundingBox, Polygon


def bbox_distance(bbox1: BoundingBox, bbox2: BoundingBox) -> float:
    """
    Calculate minimum distance between two bounding boxes
    
    Returns 0 if boxes overlap, otherwise the minimum clearance
    """
    # Calculate horizontal separation
    dx = max(0, max(bbox2.min_x - bbox1.max_x, bbox1.min_x - bbox2.max_x))
    
    # Calculate vertical separation
    dy = max(0, max(bbox2.min_y - bbox1.max_y, bbox1.min_y - bbox2.max_y))
    
    # Return Euclidean distance
    return math.sqrt(dx**2 + dy**2)


def point_distance(p1: Point, p2: Point) -> float:
    """Calculate Euclidean distance between two points"""
    return math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)


def point_to_bbox_distance(point: Point, bbox: BoundingBox) -> float:
    """Calculate minimum distance from point to bounding box"""
    # Find closest point on bbox to the given point
    closest_x = max(bbox.min_x, min(point.x, bbox.max_x))
    closest_y = max(bbox.min_y, min(point.y, bbox.max_y))
    
    # Calculate distance to closest point
    return math.sqrt((point.x - closest_x)**2 + (point.y - closest_y)**2)


def line_distance(p1: Point, p2: Point, p3: Point, p4: Point) -> float:
    """
    Calculate minimum distance between two line segments
    (p1, p2) and (p3, p4)
    """
    # Check all point-to-segment distances
    distances = [
        point_to_line_segment_distance(p1, p3, p4),
        point_to_line_segment_distance(p2, p3, p4),
        point_to_line_segment_distance(p3, p1, p2),
        point_to_line_segment_distance(p4, p1, p2),
    ]
    
    # Also check if lines intersect
    if lines_intersect(p1, p2, p3, p4):
        return 0.0
    
    return min(distances)


def point_to_line_segment_distance(point: Point, line_start: Point, line_end: Point) -> float:
    """Calculate minimum distance from point to line segment"""
    # Line segment vector
    dx = line_end.x - line_start.x
    dy = line_end.y - line_start.y
    
    # If line segment is a point
    if dx == 0 and dy == 0:
        return point_distance(point, line_start)
    
    # Parameter t of projection onto line
    t = ((point.x - line_start.x) * dx + (point.y - line_start.y) * dy) / (dx**2 + dy**2)
    
    # Clamp t to [0, 1] to stay on segment
    t = max(0, min(1, t))
    
    # Find closest point on segment
    closest_x = line_start.x + t * dx
    closest_y = line_start.y + t * dy
    
    # Return distance to closest point
    return math.sqrt((point.x - closest_x)**2 + (point.y - closest_y)**2)


def lines_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """Check if two line segments intersect"""
    def ccw(a: Point, b: Point, c: Point) -> bool:
        """Check if three points are in counter-clockwise order"""
        return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)
    
    # Two segments intersect if endpoints are on opposite sides
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4) and
            ccw(p1, p2, p3) != ccw(p1, p2, p4))


def point_to_polygon_distance(point: Point, polygon: Polygon) -> float:
    """
    Calculate minimum distance from point to polygon boundary
    
    Uses point-to-line-segment for each edge of the polygon
    """
    if not polygon.points or len(polygon.points) < 3:
        return float('inf')
    
    min_dist = float('inf')
    
    # Check distance to each edge
    for i in range(len(polygon.points)):
        p1 = polygon.points[i]
        p2 = polygon.points[(i + 1) % len(polygon.points)]
        
        dist = point_to_line_segment_distance(point, p1, p2)
        min_dist = min(min_dist, dist)
    
    return min_dist


def polygon_to_polygon_distance(poly1: Polygon, poly2: Polygon) -> float:
    """
    Calculate minimum distance between two polygons
    
    Checks edge-to-edge distances
    """
    if not poly1.points or not poly2.points:
        return float('inf')
    
    min_dist = float('inf')
    
    # Check each edge of poly1 against each edge of poly2
    for i in range(len(poly1.points)):
        p1 = poly1.points[i]
        p2 = poly1.points[(i + 1) % len(poly1.points)]
        
        for j in range(len(poly2.points)):
            p3 = poly2.points[j]
            p4 = poly2.points[(j + 1) % len(poly2.points)]
            
            dist = line_distance(p1, p2, p3, p4)
            min_dist = min(min_dist, dist)
    
    return min_dist


def calculate_creepage_distance(poly1: Polygon, poly2: Polygon) -> float:
    """
    Calculate creepage distance (surface path) between two polygons
    
    For now, same as polygon-to-polygon distance (Euclidean).
    In reality, creepage follows board surface and must avoid holes/cutouts.
    
    TODO: Implement true surface path calculation considering:
    - Board edge path
    - Cutouts and holes
    - Via keepouts
    """
    return polygon_to_polygon_distance(poly1, poly2)


def component_bounding_box(component: 'Component', pad_expansion: float = 0.5) -> Optional[BoundingBox]:
    """
    Calculate component bounding box from its pads
    
    Args:
        component: Component object with pads list
        pad_expansion: Extra margin to add (in mm)
    
    Returns:
        BoundingBox or None if component has no position/pads
    """
    if not component.position:
        return None
    
    # If component has explicit bbox, use it
    if component.bbox:
        return component.bbox
    
    # If component has pads, calculate from pads
    if component.pads:
        xs = [pad.position.x for pad in component.pads if pad.position]
        ys = [pad.position.y for pad in component.pads if pad.position]
        
        if xs and ys:
            return BoundingBox(
                min_x=min(xs) - pad_expansion,
                min_y=min(ys) - pad_expansion,
                max_x=max(xs) + pad_expansion,
                max_y=max(ys) + pad_expansion
            )
    
    # Fallback: estimate from footprint name
    # Common packages: 0805, 1206, SOT23, QFN, etc.
    footprint = component.footprint or ""
    
    # Simple heuristics (very approximate)
    if "0603" in footprint:
        size = 1.6  # 1.6mm x 0.8mm
    elif "0805" in footprint:
        size = 2.0  # 2.0mm x 1.25mm
    elif "1206" in footprint:
        size = 3.2  # 3.2mm x 1.6mm
    elif "SOT23" in footprint or "SOT-23" in footprint:
        size = 3.0
    elif "SOIC" in footprint:
        size = 6.0
    elif "QFN" in footprint or "DFN" in footprint:
        size = 5.0
    elif "BGA" in footprint:
        size = 10.0
    else:
        size = 5.0  # Default
    
    # Create square bbox around component position
    return BoundingBox(
        min_x=component.position.x - size/2,
        min_y=component.position.y - size/2,
        max_x=component.position.x + size/2,
        max_y=component.position.y + size/2
    )


def track_to_zone_clearance(track: 'Track', zone: 'Zone') -> float:
    """
    Calculate clearance between a track and a zone
    
    Args:
        track: Track object with start/end points
        zone: Zone object with polygon
    
    Returns:
        Minimum clearance in mm (0 if track is in same net as zone)
    """
    # If same net, no clearance needed
    if track.net == zone.net:
        return float('inf')
    
    if not track.start or not track.end or not zone.polygon:
        return float('inf')
    
    # Calculate distance from track segment to zone polygon
    min_dist = float('inf')
    
    # Check both track endpoints to polygon
    min_dist = min(min_dist, point_to_polygon_distance(track.start, zone.polygon))
    min_dist = min(min_dist, point_to_polygon_distance(track.end, zone.polygon))
    
    # For more accuracy, sample points along track
    # (tracks can be long and curve around zones)
    num_samples = 5
    for i in range(1, num_samples):
        t = i / num_samples
        sample_x = track.start.x + t * (track.end.x - track.start.x)
        sample_y = track.start.y + t * (track.end.y - track.start.y)
        sample_point = Point(sample_x, sample_y)
        
        dist = point_to_polygon_distance(sample_point, zone.polygon)
        min_dist = min(min_dist, dist)
    
    # Account for track width (half-width on each side)
    return max(0, min_dist - track.width / 2)


def via_to_component_clearance(via: 'Via', component: 'Component', pad_expansion: float = 0.5) -> float:
    """
    Calculate clearance between via and component
    
    Args:
        via: Via object with position
        component: Component object
        pad_expansion: Extra margin for component bbox
    
    Returns:
        Minimum clearance in mm
    """
    if not via.position:
        return float('inf')
    
    comp_bbox = component_bounding_box(component, pad_expansion)
    if not comp_bbox:
        return float('inf')
    
    # Distance from via center to component bbox
    clearance = point_to_bbox_distance(via.position, comp_bbox)
    
    # Account for via diameter
    return max(0, clearance - via.size / 2)
