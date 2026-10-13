from copy import deepcopy
from types import SimpleNamespace

from app.services.wiring_legend_service import annotate_wiring
from tests.test_draft_wiring import candidate


def catalog():
    rows=[SimpleNamespace(id=10,name='Raceway conduit concealed under floor [pdf-test:p1:L10]'),
          SimpleNamespace(id=11,name='Raceway conduit concealed in ceiling [pdf-test:p1:L09]'),
          SimpleNamespace(id=12,name='Raceway conduit concealed in ceiling [pdf-drawing:p2:L09]')]
    return SimpleNamespace(scalars=lambda statement:iter(rows))


def test_reuses_approved_patterns_and_explicit_drawing_legend_wins_without_mutation():
    review={'observed_wiring':[{'id':'manual-wiring-0001','line_style':'dashed','points':[]},
        {'id':'manual-wiring-0002','line_style':'solid','points':[]},
        {'id':'manual-wiring-0003','line_style':'dashed','wiring_legend_id':12,'points':[]}]}
    before=deepcopy(review)
    wires=annotate_wiring(catalog(),candidate(),review)['observed_wiring']
    assert wires[0]['installation_method']=='concealed_under_floor' and wires[0]['wiring_legend_id']==10
    assert wires[1]['installation_method']=='concealed_in_ceiling' and wires[1]['wiring_legend_id']==11
    assert wires[2]['installation_method']=='concealed_in_ceiling' and wires[2]['wiring_legend_id']==12
    assert review==before
    assert all('elevation_meters' not in w and 'price' not in w for w in wires)


def test_missing_explicit_legend_and_unknown_pattern_do_not_guess_a_replacement():
    review={'observed_wiring':[{'id':'manual-wiring-0001','line_style':'dashed','wiring_legend_id':99,'points':[]},
                              {'id':'manual-wiring-0002','line_style':'unknown','points':[]}]}
    wires=annotate_wiring(catalog(),candidate(),review)['observed_wiring']
    assert all(w['installation_method']=='unknown' and w['wiring_legend_id'] is None for w in wires)


def test_lighting_intent_defaults_automatic_dashes_and_untyped_generated_paths_to_ceiling():
    review={'observed_wiring':[{'id':'segment-0001','disposition':'unresolved','line_style':'dashed','points':[]}],
            'generated_wiring':[{'id':'manual-route-0001','disposition':'unresolved','points':[]}]}
    before=deepcopy(review)
    result=annotate_wiring(catalog(),candidate(),review,drawing_name='Another school LIGHTING layout.jpeg')
    assert all(w['installation_method']=='concealed_in_ceiling' and w['wiring_legend_id']==11
               for w in result['observed_wiring']+result['generated_wiring'])
    assert result['observed_wiring'][0]['line_style']=='dashed'
    assert review==before


def test_lighting_default_never_replaces_explicit_underground_or_manual_unknown():
    review={'observed_wiring':[{'id':'manual-wiring-0001','disposition':'added','line_style':'dashed',
                               'wiring_legend_id':10,'points':[]},
                              {'id':'manual-wiring-0002','disposition':'added','line_style':'unknown','points':[]}]}
    result=annotate_wiring(catalog(),candidate(),review,drawing_name='lightinglayout.jpg')
    assert result['observed_wiring'][0]['installation_method']=='concealed_under_floor'
    assert result['observed_wiring'][1]['installation_method']=='unknown'
