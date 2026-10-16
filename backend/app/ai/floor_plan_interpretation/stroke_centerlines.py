"""Bounded raster geometry, not an electrical junction classifier.

Zhang-Suen thinning preserves stroke topology instead of walking its perimeter.
Pixel branches stop at junctions; their shared pixel is NOT electrical approval.
No dilation, gap closing, circuit merging or symbol bridging happens here.
"""
import cv2
import numpy as np


def thin_strokes(mask):
    image = np.pad((mask > 0).astype(np.uint8), 1)
    while True:
        changed = False
        for phase in (0, 1):
            p = [image[:-2, 1:-1], image[:-2, 2:], image[1:-1, 2:], image[2:, 2:],
                 image[2:, 1:-1], image[2:, :-2], image[1:-1, :-2], image[:-2, :-2]]
            count = sum(p)
            transitions = sum((a == 0) & (b == 1) for a, b in zip(p, p[1:] + p[:1]))
            if phase == 0:
                clear = (p[0]*p[2]*p[4] == 0) & (p[2]*p[4]*p[6] == 0)
            else:
                clear = (p[0]*p[2]*p[6] == 0) & (p[0]*p[4]*p[6] == 0)
            remove = (image[1:-1, 1:-1] > 0) & (count >= 2) & (count <= 6) & (transitions == 1) & clear
            if remove.any():
                image[1:-1, 1:-1][remove] = 0
                changed = True
        if not changed:
            return image[1:-1, 1:-1]


def stroke_paths(mask, *, minimum_length=15, maximum_paths=200):
    """Maximal degree-two chains. Stop at branches, retain cycles and curves."""
    skeleton = thin_strokes(mask)
    pixels = {(int(x), int(y)) for y, x in np.argwhere(skeleton)}
    graph = {}
    for x, y in sorted(pixels):
        neighbors = []
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
            other = (x+dx, y+dy)
            # Don't create triangular side branches around raster corners.
            if other in pixels and not (dx and dy and ((x+dx, y) in pixels or (x, y+dy) in pixels)):
                neighbors.append(other)
        graph[(x, y)] = sorted(neighbors)
    visited, paths = set(), []
    # End/branch nodes first, then any closed loops of degree two.
    starts = sorted(graph, key=lambda p: (len(graph[p]) == 2, p))
    for start in starts:
        for next_point in graph[start]:
            edge = tuple(sorted((start, next_point)))
            if edge in visited:
                continue
            visited.add(edge)
            chain = [start, next_point]
            while len(graph[chain[-1]]) == 2 and chain[-1] != start:
                other = next(p for p in graph[chain[-1]] if p != chain[-2])
                edge = tuple(sorted((chain[-1], other)))
                if edge in visited:
                    break
                visited.add(edge)
                chain.append(other)
            array = np.asarray(chain, np.float32).reshape(-1, 1, 2)
            if cv2.arcLength(array, False) < minimum_length:
                continue
            # Subpixel-size simplification, independent of total route length:
            # a long path must not lose a small real bend.
            simplified = cv2.approxPolyDP(array, .75, False).reshape(-1, 2)
            if 2 <= len(simplified) <= 512:
                points = tuple(tuple(map(float, p)) for p in simplified)
                paths.append(min(points, tuple(reversed(points))))
    return sorted(paths, key=lambda p: (-sum(np.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(p, p[1:])), p))[:maximum_paths]
