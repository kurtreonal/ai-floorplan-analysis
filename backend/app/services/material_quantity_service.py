"""Reproducible quantities from saved canonical geometry, never raw detections."""
from dataclasses import dataclass

from app.geometry.canonical import CanonicalGeometryDocument, canonical_geometry_from_dict
from app.services.layout_service import retrieve_accessible_current_layout


@dataclass(frozen=True)
class ComponentQuantity:
    class_id: int
    class_name: str
    quantity: int
    symbol_ids: tuple[str, ...]


@dataclass(frozen=True)
class LayoutQuantities:
    layout_version_id: int
    version_number: int
    project_id: int
    project_floor_id: int
    components: tuple[ComponentQuantity, ...]


def component_quantities(document: CanonicalGeometryDocument) -> tuple[ComponentQuantity, ...]:
    # Revalidate even typed objects: callers can construct dataclasses directly.
    document = canonical_geometry_from_dict(document.to_dict())
    groups, names, seen = {}, {}, set()
    for symbol in document.symbols:
        if symbol.id in seen:
            raise ValueError("Duplicate canonical symbol identity.")
        seen.add(symbol.id)
        if symbol.class_id in names and names[symbol.class_id] != symbol.class_name:
            raise ValueError("Conflicting canonical class names.")
        names[symbol.class_id] = symbol.class_name
        groups.setdefault(symbol.class_id, []).append(symbol.id)
    return tuple(ComponentQuantity(key, names[key], len(groups[key]), tuple(sorted(groups[key])))
                 for key in sorted(groups))


def retrieve_component_quantities(session, *, current_user, project_id, project_floor_id):
    layout = retrieve_accessible_current_layout(session, current_user=current_user,
        project_id=project_id, project_floor_id=project_floor_id)
    return LayoutQuantities(layout.id, layout.version_number, project_id, project_floor_id,
                            component_quantities(layout.geometry))
