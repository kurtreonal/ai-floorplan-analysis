---
name: electrical-routing-estimator
description: >-
  Comprehensive guide and runbook for 3D electrical pathfinding (A*), branch circuit routing,
  conduit fill calculations, material takeoff (BOM), and dynamic cost estimation in VED Electrical Services.
  Use when implementing automated routing algorithms, ceiling/wall drop geometry, circuit assignment,
  material quantity calculation, and unit price capture logic.
---

# Electrical Routing & Automated Cost Estimator

This skill defines the technical algorithms, electrical code rules, and data integrity standards for automated electrical routing and cost estimation in VED Electrical Services.

---

## 1. Core Principles & Engineering Constraints

1. **No Direct Diagonal Shortcuts**: Automated routing must follow real structural paths (ceiling/service corridors, wall rises, and wall drops). Never draw direct diagonal air-wires between panel and device.
2. **Ceiling & Wall Movement Architecture**:
   - **Horizontal Movement**: Traverses at ceiling level (`y = ceilingHeight - 0.1m`).
   - **Vertical Drops**: Drops down vertically along the inside or surface of the relevant wall to reach receptacle height (`0.30m`) or switch height (`1.20m`).
   - **Vertical Rises**: Rises vertically from device up to ceiling raceway.
   - **Inter-Floor Risers**: Multi-floor routing must strictly pass through verified vertical risers/chases.
3. **Database-Authoritative Material Prices**: Material prices must come directly from the database (`materials` and `material_prices` tables). Never hardcode prices in frontend components or Python calculations.
4. **Unit Price Capture**: When generating an estimate, capture the exact unit price at that timestamp into `estimate_items`. Subsequent admin price adjustments must never retroactively alter historical estimates.

---

## 2. 3D Spatial Pathfinding Algorithm (A*)

Automated routing generates waypoints on a 3D orthogonal grid:

```python
"""
Conceptual A* routing algorithm for electrical branch circuits.
"""
from heapq import heappop, heappush
import math

def heuristic(a, b):
    # Manhattan distance preferred for orthogonal electrical conduits
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

def route_branch_circuit(start_panel_pos, end_device_pos, obstacles, ceiling_y=2.7, grid_step=0.2):
    """
    Routes from start_panel_pos to end_device_pos via ceiling level:
    1. Rise from panel elevation to ceiling_y.
    2. Traverse orthogonally at ceiling_y avoiding obstacles.
    3. Drop down wall from ceiling_y to end_device_pos elevation.
    """
    panel_rise = (start_panel_pos[0], ceiling_y, start_panel_pos[2])
    device_drop_top = (end_device_pos[0], ceiling_y, end_device_pos[2])

    # A* pathfinding on ceiling 2D/3D slice
    open_set = []
    heappush(open_set, (0, panel_rise))
    came_from = {}
    g_score = {panel_rise: 0}

    while open_set:
        _, current = heappop(open_set)

        if math.dist((current[0], current[2]), (device_drop_top[0], device_drop_top[2])) <= grid_step:
            # Reconstruct ceiling path
            path = [device_drop_top]
            curr = current
            while curr in came_from:
                path.append(curr)
                curr = came_from[curr]
            path.reverse()

            # Prepend panel rise and append device drop
            full_route = [start_panel_pos] + path + [end_device_pos]
            return full_route

        # Explore orthogonal neighbors (North, South, East, West)
        for dx, dz in [(grid_step, 0), (-grid_step, 0), (0, grid_step), (0, -grid_step)]:
            neighbor = (round(current[0] + dx, 2), ceiling_y, round(current[2] + dz, 2))
            if (neighbor[0], neighbor[2]) in obstacles:
                continue

            tentative_g = g_score[current] + grid_step
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, device_drop_top)
                heappush(open_set, (f_score, neighbor))

    # Fallback to direct orthogonal riser-drop if pathfinding finds no free corridor
    return [start_panel_pos, panel_rise, device_drop_top, end_device_pos]
```

---

## 3. Material Takeoff (BOM) & Measurement Rules

From the verified canonical geometry and routes, compute:

1. **Conduit Length**: Sum of Euclidean segment lengths for each conduit run:
   $$\text{Conduit Length} = \sum_{i=0}^{n-1} \sqrt{(x_{i+1}-x_i)^2 + (y_{i+1}-y_i)^2 + (z_{i+1}-z_i)^2} \times 1.10\ (\text{10\% waste factor})$$
2. **Wire Length**: Each conduit carries multiple conductors depending on circuit type:
   - 1-Phase 120V/230V 2-Wire + Ground: $\text{Conduit Length} \times 3$ conductors.
   - Extra conductor slack for termination: $+0.30\text{ m}$ per junction box / outlet box.
3. **Boxes & Fittings**:
   - 1 device box per wall receptacle / switch.
   - 1 conduit connector per termination into box or panel.
   - 1 conduit coupling per 3.0 meters (standard EMT stick length).

---

## 4. Cost Calculation Integrity

Core formula:
$$\text{Line Total} = \text{Quantity} \times \text{Captured Unit Price}$$
$$\text{Total Estimate} = \sum \text{Line Totals} + \text{Labor Cost} + \text{Contingency}$$

Ensure all calculations happen in backend services, with frontend components purely displaying authoritative backend results.
