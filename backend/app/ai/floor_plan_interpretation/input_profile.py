"""Descriptive raster capabilities, never a deskew or source-coordinate change."""
import cv2
import numpy as np


def inspect_input_pixels(image, payload):
    height,width=image.shape[:2]
    # Sampling is for orientation/quality metadata ONLY. Recovery uses native
    # pixels and exact integer crop translations, not this thumbnail.
    ratio=min(1,512/max(width,height))
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    small=cv2.resize(gray,(max(1,round(width*ratio)),max(1,round(height*ratio))))
    edges=cv2.Canny(small,60,180)
    lines=cv2.HoughLinesP(edges,1,np.pi/180,20,minLineLength=max(8,round(min(small.shape)*.08)),maxLineGap=2)
    angles=[]
    if lines is not None:
        for a,b,c,d in lines[:512,0]:
            angles.append(float(np.degrees(np.arctan2(d-b,c-a))%90))
    sizes=[min(s.bounds.width,s.bounds.height) for s in payload.symbols.items if s.bounds]
    return dict(width_pixels=width,height_pixels=height,aspect_ratio=width/height,
        grayscale_range=[int(np.percentile(small,5)),int(np.percentile(small,95))],
        dominant_axis_degrees=round(float(np.median([a if a<=45 else a-90 for a in angles])),2) if angles else None,
        orientation_action='preserve_source_plane',
        symbol_short_side_pixels=dict(minimum=min(sizes),median=float(np.median(sizes)),maximum=max(sizes)) if sizes else None,
        resolution_basis='registered_normalized_artifact',physical_dpi=None)
