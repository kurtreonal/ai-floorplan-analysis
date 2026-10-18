"""Bounded quarter-turn recognition; pixels/geometry stay in the source plane.

Choose one coherent inference view, not the union of incompatible class guesses.
Agreement ranks views; it is neither calibrated confidence nor human approval.
"""
import numpy as np

from app.ai.floor_plan_interpretation.experimental_symbol_detector import _iou

CONFIGURATION = dict(version='quarter-turn-cross-view-agreement-v1', turns=(0, 1, 2, 3),
                     minimum_agreement_iou=.5, minimum_agreed_symbols=2,
                     minimum_selected_agreement_fraction=.5)


def restore_box(box, width, height, turn):
    """Inverse rotation of continuous xyxy image-edge bounds (not pixel indices)."""
    x1, y1, x2, y2 = box
    if turn == 0:
        return tuple(box)
    if turn == 1:
        return width-y2, x1, width-y1, x2
    if turn == 2:
        return width-x2, height-y2, width-x1, height-y1
    if turn == 3:
        return y1, height-x2, y2, height-x1
    raise ValueError('Only bounded quarter turns are supported.')


def restore_prediction(row, width, height, turn):
    result = {**row, 'bbox': restore_box(row['bbox'], width, height, turn)}
    size = row.get('tile_size', 256)
    if 'tile_origin' in row:
        x, y = row['tile_origin']
        tile = restore_box((x, y, x+size, y+size), width, height, turn)
        # Edge tiles are padded for inference. The recorded source origin is
        # the clipped visible tile, never a negative padding coordinate.
        result['tile_origin'] = (max(0, tile[0]), max(0, tile[1]))
    # These are retained diagnostic observations, not coordinates in a second
    # hidden model. Invert every nested box as well as the winning box.
    for key in ('localization_observations', 'equivalent_observations'):
        if row.get(key):
            result[key] = tuple(restore_prediction(p, width, height, turn) for p in row[key])
    if turn:
        result['inference_rotation_ccw'] = turn*90
        result.pop('clipped_tile_edges', None)  # Seam fusion already ran in that view.
    return result


def locate_orientation_consensus(rgb, infer, class_groups, *, diagnostics=None):
    height, width = rgb.shape[:2]
    views = []
    for turn in CONFIGURATION['turns']:
        rows, truncated = infer(np.ascontiguousarray(np.rot90(rgb, turn)))
        views.append((tuple(restore_prediction(p, width, height, turn) for p in rows), truncated))
    ranks = []; agreed_counts = []
    for turn, (rows, _) in enumerate(views):
        agreed = [p for p in rows if any(
            class_groups.get(p['class_id'], ('id', p['class_id']))
                == class_groups.get(q['class_id'], ('id', q['class_id']))
            and _iou(p['bbox'], q['bbox']) >= CONFIGURATION['minimum_agreement_iou']
            for other, (observations, _) in enumerate(views) if other != turn for q in observations)]
        # Score a corroborated set, never the raw detection count. More guesses
        # from text/columns cannot win unless another orientation supports them.
        ranks.append(sum(p['score'] for p in agreed)
                     if len(agreed) >= CONFIGURATION['minimum_agreed_symbols'] else 0.)
        agreed_counts.append(len(agreed))
    selected = max(range(len(views)), key=lambda k: ranks[k])
    # A few repeatable guesses cannot justify normalizing a page containing
    # mostly unsupported marks. Keep the native proposals reviewable rather
    # than choosing a high-count view of text/furniture; orientation is unknown.
    resolved = (agreed_counts[selected] >= CONFIGURATION['minimum_agreed_symbols']
                and agreed_counts[selected] >= len(views[selected][0])
                    * CONFIGURATION['minimum_selected_agreement_fraction'])
    if not resolved:
        selected = 0
    if diagnostics is not None:
        diagnostics.update(selected_turn=selected, agreement_ranks=ranks,
                           agreed_counts=agreed_counts, orientation_resolved=resolved,
                           retained_counts=[len(v[0]) for v in views],
                           truncated_views=[v[1] for v in views])
    rows, truncated = views[selected]
    # A capped alternative makes the orientation assessment incomplete too.
    return rows, truncated or any(v[1] for v in views)
