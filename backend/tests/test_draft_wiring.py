from copy import deepcopy
import math
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.routing.draft_wiring import draft_path, generate_draft_wiring as generate_proposals, _blocked


def generate_draft_wiring(*args, **kwargs):
    """Legacy nearest-anchor benchmark, not the load/save production policy."""
    return generate_proposals(*args, legacy_completion=True, **kwargs)


def test_ordinary_load_and_save_never_infer_attachments_or_join_circuits():
    source = candidate()
    assert generate_proposals(source)[0] == []
    review = {'symbols': [], 'observed_wiring': [], 'generated_wiring': []}
    assert generate_proposals(source, review)[0] == []
from app.routing.graph import RoutingError
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from tests.test_automatic_wiring import example


def candidate():
    _, payload = example()
    values = payload.model_dump(mode="json")
    for item in values["symbols"]["items"]:
        item["observed_label"] = "Duplex outlet"
    return SimpleNamespace(payload=FloorPlanInterpretationPayload.model_validate(values))


def test_astar_is_orthogonal_shortest_on_grid_and_deterministic():
    path = draft_path((20,30),(80,90),(0,0,100,100),[])
    assert path == draft_path((20,30),(80,90),(0,0,100,100),[])
    assert path[0] == (20,30) and path[-1] == (80,90)
    assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(path,path[1:]))
    assert sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(path,path[1:])) == pytest.approx(120)


def test_short_connections_use_bounded_astar_without_building_dense_grid():
    from app.routing import draft_wiring
    with patch.object(draft_wiring,'astar',wraps=draft_wiring.astar) as search:
        path=draft_path((20,30),(80,90),(0,0,100,100),[])
    assert search.call_count==1 and len(search.call_args.args[0])<=4
    assert len(path)==3
    # When the direct Manhattan candidates are blocked, A* must search around
    # the wall rather than treating its small-graph failure as a shortcut.
    wall=((50,20),(50,80),3)
    with patch.object(draft_wiring,'astar',wraps=draft_wiring.astar) as search:
        path=draft_path((20,50),(80,50),(0,0,100,100),[wall])
    assert search.call_count==2 and len(search.call_args.args[0])>4
    assert not any(_blocked(a,b,wall,((20,50),(80,50))) for a,b in zip(path,path[1:]))


def test_astar_avoids_wall_and_never_falls_back_through_blocked_wall():
    wall = ((50,20),(50,80),3)
    path = draft_path((20,50),(80,50),(0,0,100,100),[wall])
    assert len(path)>2
    assert not any(_blocked(a,b,wall,((20,50),(80,50))) for a,b in zip(path,path[1:]))
    with pytest.raises(RoutingError,match="NO_ROUTE"):
        draft_path((20,50),(80,50),(0,0,100,100),[((50,0),(50,100),3)])


def test_mount_exit_is_local_not_a_shortcut_along_entire_wall():
    wall = ((50,0),(50,100),3)
    assert not _blocked((50,20),(55,20),wall,((50,20),(90,20)))
    assert _blocked((50,20),(50,90),wall,((50,20),(90,20)))
    # A drawn device glyph offset from the centerline can attach locally;
    # the rest of that wall remains an obstacle.
    assert not _blocked((40,20),(55,20),wall,((40,20),(90,20)),(12,0))
    assert _blocked((40,20),(60,90),wall,((40,20),(90,20)),(12,0))


def test_unserved_devices_get_separate_generated_paths_not_observations():
    source = candidate()
    before = source.payload.model_dump_json()
    paths, notes = generate_draft_wiring(source)
    assert len(paths)==1 and not notes  # no reverse duplicate
    assert paths[0]["algorithm"]=="astar"
    assert paths[0]["disposition"]=="unresolved"
    assert paths[0]["elevation_meters"] is None
    assert paths[0]["points"][0]=={"x":60,"y":100}
    assert source.payload.model_dump_json()==before
    assert not source.payload.observed_routes.segments


def test_visible_trace_has_priority_and_removed_paths_are_not_regenerated():
    source = candidate()
    review = {"observed_wiring":[{"id":"segment-0001","points":[{"x":260,"y":100},{"x":260,"y":130}]}]}
    paths, _ = generate_draft_wiring(source,review)
    assert len(paths)==1 and paths[0]["target_kind"]=="visible_trace"
    review["generated_wiring"] = [{**paths[0],"disposition":"rejected"}]
    before = deepcopy(review)
    restored, notes = generate_draft_wiring(source,review)
    assert restored == review["generated_wiring"]
    assert "symbol-0001" in notes[0]  # report a removal, never regenerate it
    assert review==before


def test_unknowns_outside_region_and_budget_are_not_silently_wired():
    source = candidate()
    paths, notes = generate_draft_wiring(source,budget_seconds=0)
    assert not paths and "symbol-0001" in notes[0]
    _, unknown = example()
    paths,notes=generate_draft_wiring(SimpleNamespace(payload=unknown))
    assert not paths and "Device type needed" in notes[0] and "symbol-0002" in notes[0]
    paths, notes = generate_draft_wiring(source,maximum_devices=0)
    assert not paths and "symbol-0002" in notes[0]


def test_unreachable_traces_do_not_starve_reachable_device_fallback():
    source = candidate()
    values = source.payload.model_dump(mode="json")
    third = deepcopy(values["symbols"]["items"][0])
    third.update(id="symbol-0003",center={"x":100,"y":100},bounds={"x":92,"y":88,"width":16,"height":24})
    values["symbols"]["items"].append(third)
    source.payload = FloorPlanInterpretationPayload.model_validate(values)
    review = {"walls":[{"id":"wall-0001","start":{"x":150,"y":0},"end":{"x":150,"y":200}}],
              "observed_wiring":[{"id":f"segment-{i:04d}","points":[{"x":260,"y":y},{"x":260,"y":y+5}]} for i,y in enumerate((90,100,110,120),1)]}
    paths,notes=generate_draft_wiring(source,review)
    assert paths[0]["target_id"]=="symbol-0003"
    assert paths[0]["target_kind"]=="device"
    assert not any("Unwired draft devices" in note for note in notes)
    assert any("Disconnected draft wiring" in note for note in notes)


def test_moved_devices_are_reported_if_saved_wiring_no_longer_touches_them():
    source = candidate()
    paths, _ = generate_draft_wiring(source)
    review = {"generated_wiring":paths,"symbols":[{"id":"symbol-0001","center":{"x":60,"y":30}}]}
    existing, notes = generate_draft_wiring(source,review)
    assert existing==paths  # preserve explicit wire edits; never reroute silently
    assert "symbol-0001" in notes[0]


def test_manual_device_is_wired_after_save_without_replacing_existing_edits():
    source = candidate()
    paths, _ = generate_draft_wiring(source)
    paths[0]["id"] = "manual-route-0007"
    review = {"generated_wiring":paths,"symbols":[
        {"id":s.id,"center":s.center.model_dump(),"class_name":"Duplex outlet"}
        for s in source.payload.symbols.items
    ] + [{"id":"manual-symbol-0001","center":{"x":120,"y":60},"class_name":"Wall switch"}]}
    before = deepcopy(review)
    result, notes = generate_draft_wiring(source,review)
    assert result[:1] == paths
    assert len(result)==2 and result[1]["id"]=="manual-route-0008"
    assert result[1]["source_device_id"]=="manual-symbol-0001"
    assert not notes and review==before


def test_reclassified_devices_with_empty_saved_routes_receive_automatic_paths():
    _, payload = example()
    source = SimpleNamespace(payload=payload)
    review={"generated_wiring":[],"symbols":[
        {"id":s.id,"center":s.center.model_dump(),"class_name":"1x40 watts fluorescent lamp"}
        for s in payload.symbols.items
    ]}
    paths, notes=generate_draft_wiring(source,review)
    assert len(paths)==1 and not notes


def test_rejected_wire_is_not_recreated_but_new_devices_can_still_get_paths():
    source=candidate()
    paths,_=generate_draft_wiring(source)
    review={"generated_wiring":[{**paths[0],"disposition":"rejected"}],"symbols":[
        {"id":s.id,"center":s.center.model_dump(),"class_name":"Duplex outlet"}
        for s in source.payload.symbols.items
    ] + [{"id":"manual-symbol-0001","center":{"x":120,"y":60},"class_name":"Wall switch"}]}
    result,notes=generate_draft_wiring(source,review)
    assert result[0]==review["generated_wiring"][0]
    assert len(result)==2 and result[1]["source_device_id"]=="manual-symbol-0001"
    assert all(p["id"] != "manual-route-0001" for p in result[1:])
    assert notes  # deliberately removed original path remains a user choice


def test_omitted_and_rejected_devices_cannot_become_automatic_path_anchors():
    source=candidate()
    review={"symbols":[{"id":"manual-symbol-0001","center":{"x":120,"y":60},"class_name":"Wall switch"},
                       {"id":"symbol-0001","center":{"x":60,"y":100},"disposition":"rejected"}]}
    paths,notes=generate_draft_wiring(source,review)
    assert not paths and "manual-symbol-0001" in notes[0]
    assert "symbol-0002" not in notes[0]


def test_manual_unclassified_type_is_reported_without_guessing_a_path_or_class():
    source=candidate()
    review={"symbols":[{"id":"manual-symbol-0001","center":{"x":120,"y":60},"class_name":None}]}
    before=deepcopy(review)
    paths,notes=generate_draft_wiring(source,review)
    assert not paths and notes==["Device type needed for automatic wiring: manual-symbol-0001"]
    assert review==before


@pytest.mark.parametrize("label",["CCTV camera","Magnetic contact","Keypad","Electric service meter",
                                  "Service entrance","Circuit breaker","Push button","Pull box","Utility box"])
def test_other_approved_device_names_are_not_silently_excluded(label):
    source=candidate()
    review={"symbols":[{"id":s.id,"center":s.center.model_dump(),"class_name":label}
                        for s in source.payload.symbols.items]}
    paths,notes=generate_draft_wiring(source,review)
    assert len(paths)==1 and not notes


def test_explicit_catalog_mapping_can_route_without_guessing_from_name():
    source=candidate()
    review={"symbols":[{"id":s.id,"center":s.center.model_dump(),"class_name":"VED approved device",
                        "class_id":1234} for s in source.payload.symbols.items]}
    paths,notes=generate_draft_wiring(source,review)
    assert len(paths)==1 and not notes


def branch_review():
    return {"walls":[],"observed_wiring":[],"symbols":[
        {"id":f"manual-symbol-{i:04d}","center":{"x":x,"y":y},"class_name":"Duplex outlet"}
        for i,(x,y) in enumerate(((40,40),(70,40),(240,140),(270,140)),1)
    ]}


def test_separate_device_pairs_are_joined_into_one_continuous_draft():
    source, review = candidate(), branch_review()
    before = deepcopy(review)
    paths, notes = generate_draft_wiring(source,review)
    assert len(paths)==3  # two local branches plus one network join
    from app.routing.draft_wiring import _wire_components
    assert len(_wire_components(paths))==1
    assert not notes and review==before
    reloaded, notes = generate_draft_wiring(source,{**review,"generated_wiring":paths})
    assert reloaded==paths and not notes  # no duplicate joins on save/reload


def test_orphan_observation_is_reported_separately_from_connected_devices():
    source=candidate()
    paths,_=generate_draft_wiring(source)
    review={'generated_wiring':paths,'observed_wiring':[
        {'id':'segment-0001','points':[{'x':20,'y':20},{'x':100,'y':20}]}]}
    before=deepcopy(review)
    result,notes=generate_draft_wiring(source,review)
    assert result==paths and review==before
    assert not any('Disconnected draft wiring' in n for n in notes)
    assert any('Unattached drawing traces: 1' in n for n in notes)


def test_saved_branches_stay_unchanged_and_join_cannot_cross_a_blocking_wall():
    source, review = candidate(), branch_review()
    paths, _ = generate_draft_wiring(source,review,maximum_devices=2)
    second={**paths[0],"id":"manual-route-0002","source_device_id":"manual-symbol-0003",
            "target_id":"manual-symbol-0004","points":[{"x":240,"y":140},{"x":270,"y":140}]}
    existing=[paths[0],second]
    review["generated_wiring"]=existing
    joined, notes = generate_draft_wiring(source,review)
    assert joined[:2]==existing and len(joined)==3 and not notes
    review["walls"]=[{"start":{"x":160,"y":0},"end":{"x":160,"y":200}}]
    blocked, notes = generate_draft_wiring(source,review)
    assert blocked==existing
    assert any("Disconnected draft wiring" in note for note in notes)


def test_deleted_join_is_not_recreated_and_different_heights_are_not_joined():
    source, review = candidate(), branch_review()
    paths, _ = generate_draft_wiring(source,review)
    review["generated_wiring"]=[*paths[:2],{**paths[2],"disposition":"rejected"}]
    saved=deepcopy(review["generated_wiring"])
    restored, notes=generate_draft_wiring(source,review)
    assert restored==saved and notes
    review["generated_wiring"]=[{**paths[0],"elevation_meters":2.7},
                                {**paths[1],"elevation_meters":0.3}]
    restored, _=generate_draft_wiring(source,review)
    assert restored==review["generated_wiring"]


def test_wire_components_require_literal_contact_not_nearby_pixels():
    from app.routing.draft_wiring import _wire_components
    wires=[{"points":[{"x":0,"y":0},{"x":100,"y":0}]},
           {"points":[{"x":50,"y":0},{"x":50,"y":40}]},
           {"points":[{"x":0,"y":6},{"x":40,"y":6}]}]
    assert sorted(map(len,_wire_components(wires)))==[1,2]
    wires[1]["elevation_meters"]=2.7
    assert len(_wire_components(wires))==3


def test_different_drawings_and_traces_without_device_anchors_are_not_blindly_joined():
    source, review = candidate(), branch_review()
    paths,_=generate_draft_wiring(source,review)
    review["generated_wiring"]=paths[:2]
    values=source.payload.model_dump(mode="json")
    region=next(r for r in values["regions"] if r["kind"]=="plan_region")
    region["bounds"]={"x":0,"y":0,"width":150,"height":200}
    values["regions"].append({**deepcopy(region),"id":"region-0002",
                             "bounds":{"x":170,"y":0,"width":150,"height":200}})
    source.payload=FloorPlanInterpretationPayload.model_validate(values)
    result,notes=generate_draft_wiring(source,review)
    assert result==paths[:2] and any("Disconnected" in n for n in notes)
    source=candidate()
    review["observed_wiring"]=[{"id":"segment-0001","points":[{"x":10,"y":190},{"x":20,"y":190}]}]
    result,notes=generate_draft_wiring(source,review)
    assert len(result)==3 and any("Unattached drawing traces" in n for n in notes)


def test_redundant_automatic_shortcut_is_removed_but_edits_and_topology_are_preserved():
    from app.routing.draft_wiring import _prune_redundant, _wire_components
    observed=[{"id":"segment-0001","points":[{"x":40,"y":40},{"x":70,"y":40},{"x":70,"y":140}]}]
    shortcut={"id":"manual-route-0001","disposition":"unresolved","elevation_meters":None,
        "points":[{"x":40,"y":40},{"x":40,"y":140},{"x":70,"y":140}]}
    before=deepcopy([observed,shortcut])
    result=_prune_redundant([shortcut],observed)
    assert result[0]["disposition"]=="rejected"
    assert result[0]["suppression_reason"]=="redundant_observed_connection"
    assert result[0]["points"]==shortcut["points"]
    assert len(_wire_components(observed))==1
    assert [observed,shortcut]==before
    for disposition in ("corrected","added","accepted","rejected"):
        edited={**shortcut,"disposition":disposition}
        assert _prune_redundant([edited],observed)==[edited]
    unrelated={**shortcut,"points":[{"x":40,"y":40},{"x":80,"y":140}]}
    assert _prune_redundant([unrelated],observed)==[unrelated]
    raised={**shortcut,"elevation_meters":2.7}
    assert _prune_redundant([raised],observed)==[raised]


def test_literal_glyph_gap_gets_a_short_attachment_and_inherits_underfloor_type():
    source=candidate()
    review={"walls":[],"observed_wiring":[{"id":"segment-0001","points":[{"x":66,"y":100},{"x":254,"y":100}],
        "installation_method":"concealed_under_floor","line_style":"dashed","wiring_legend_id":1790,
        "wiring_legend_name":"Raceway conduit concealed under floor [pdf-test:p1:L10]"}]}
    paths,notes=generate_draft_wiring(source,review)
    assert len(paths)==2 and not notes  # six-pixel stubs, no duplicate full-span route
    assert all(sum(math.dist(a,b) for a,b in zip([(p['x'],p['y']) for p in w['points']],
        [(p['x'],p['y']) for p in w['points']][1:]))==6 for w in paths)
    assert all(w["installation_method"]=="concealed_under_floor" for w in paths)
    assert all(w["elevation_meters"] is None for w in paths)


def test_one_panel_roots_the_existing_network_without_star_routes_to_each_device():
    from app.routing.draft_wiring import _wire_components
    source,review=candidate(),branch_review()
    review['symbols'][0]['class_name']='Panelboard'
    review['observed_wiring']=[{'id':'segment-0001','points':[{'x':40,'y':40},{'x':70,'y':40}]},
                             {'id':'segment-0002','points':[{'x':240,'y':140},{'x':270,'y':140}]}]
    paths,notes=generate_draft_wiring(source,review)
    assert len(paths)==1 and not notes
    assert len(_wire_components(review['observed_wiring']+paths))==1
    assert paths[0]['source_device_id'] in {'manual-symbol-0001','manual-symbol-0002'} or paths[0]['target_id'] in {'manual-symbol-0001','manual-symbol-0002'}
    review['symbols'][2]['class_name']='Panelboard'
    paths,notes=generate_draft_wiring(source,review)
    assert not paths and any('Multiple panelboards' in note for note in notes)


def test_unknown_crossing_cannot_merge_conflicting_floor_and_ceiling_networks():
    from app.routing.draft_wiring import _wire_components
    wires=[{'installation_method':'concealed_under_floor','points':[{'x':0,'y':0},{'x':100,'y':0}]},
           {'installation_method':'unknown','points':[{'x':50,'y':0},{'x':50,'y':100}]},
           {'installation_method':'concealed_in_ceiling','points':[{'x':0,'y':100},{'x':100,'y':100}]}]
    assert len(_wire_components(wires))==2
