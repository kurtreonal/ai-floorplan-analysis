"""Shared geometry contracts independent from rendering and persistence."""

from app.geometry.coordinates import (
    CanonicalCoordinateSystem,
    CanonicalPoint,
    WallCoordinateError,
)
from app.geometry.walls import (
    CanonicalWall,
    CanonicalWallCandidate,
    NormalizedWallGeometry,
    RawPixelPoint,
    RawPixelWall,
    normalize_wall_coordinates,
)

__all__ = (
    "CanonicalCoordinateSystem",
    "CanonicalPoint",
    "CanonicalWall",
    "CanonicalWallCandidate",
    "NormalizedWallGeometry",
    "RawPixelPoint",
    "RawPixelWall",
    "WallCoordinateError",
    "normalize_wall_coordinates",
)
