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
from app.geometry.canonical import (
    CanonicalDocumentWall,
    CanonicalFloor,
    CanonicalGeometryDocument,
    CanonicalGeometryError,
    CanonicalRoom,
    CanonicalRoute,
    CanonicalRoutePoint,
    CanonicalSymbol,
    build_canonical_geometry,
    canonical_geometry_from_dict,
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
    "CanonicalDocumentWall",
    "CanonicalFloor",
    "CanonicalGeometryDocument",
    "CanonicalGeometryError",
    "CanonicalRoom",
    "CanonicalRoute",
    "CanonicalRoutePoint",
    "CanonicalSymbol",
    "build_canonical_geometry",
    "canonical_geometry_from_dict",
)
