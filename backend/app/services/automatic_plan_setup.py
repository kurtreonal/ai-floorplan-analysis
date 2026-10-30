"""Snapshotted planning assumptions; never detected or professionally verified heights."""


def automatic_settings(values, defaults, revision):
    result=dict(values)
    reference=values.get('reference')
    complete=values.get('measurement_method')=='full_sheet' and values.get('full_sheet_confirmed')
    result.update(height_mode='automatic',allow_estimated_scale=True,applied_defaults_revision=revision,
        floor_to_ceiling_height_meters=defaults['ceiling_height_meters'],
        service_height_above_floor_meters=None,fixture_center_height_meters=None,fixture_connection_height_meters=None,service_elevation_meters=None,
        outlet_center_height_meters=defaults['outlet_center_height_meters'],
        switch_center_height_meters=defaults['switch_center_height_meters'],
        measurement_method='reference' if reference else 'full_sheet' if complete else 'auto')
    if not complete:
        result.update(source_paper_size=defaults['paper_size'],source_orientation=None,
            source_width_mm=None,source_height_mm=None,image_size_percent=100)
    if not values.get('drawing_scale_confirmed'):
        result['scale_denominator']=defaults['scale_denominator']
    return result


def height_context(settings):
    automatic=settings.get('height_mode')=='automatic'
    ceiling=settings.get('floor_to_ceiling_height_meters')
    mounts={family:settings[key] for family,key in (
        ('outlet','outlet_center_height_meters'),('switch','switch_center_height_meters'),
        ('fixture','fixture_center_height_meters')) if settings.get(key) is not None}
    if settings.get('fixture_connection_height_meters') is not None:
        mounts.pop('fixture',None)
        mounts['fixture_connection']=settings['fixture_connection_height_meters']
    elif automatic:
        mounts.pop('fixture',None)
        mounts['fixture_connection']=ceiling
    return dict(height_mode='automatic' if automatic else 'custom',ceiling_height_meters=ceiling,
        height_basis='assumed' if automatic else 'custom',applied_defaults_revision=settings.get('applied_defaults_revision'),
        service_height_above_floor_meters=settings.get('service_height_above_floor_meters') if settings.get('service_height_above_floor_meters') is not None else ceiling if automatic else None,
        mounting_defaults=mounts)
