"""SVS sign-up (v2.2.0): settings (battle start + hours), strict player answers, T10/T11 troops, the shared-profile
troop merge with Frost Dragon Tyrant, admin list/summary/filters/exports."""
import csv
import io

import openpyxl

from tests.conftest import start_round

EVENT = 'svs'


def troops(camp='FC10', tier=11, **override):
    out = {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}
    out.update(override)
    return out


def good(**kw):
    a = {'hours': ['11:00', '13:00'], 'discord_vc': True, 'language': 'en'}
    a.update(kw)
    return a


def put(client, fid, profile=None, answers=None, event=EVENT):
    prof = {'game_name': f'S{fid}', 'alliance': 'svs', 'troops': troops()}
    if profile is not None:
        prof.update(profile)
    return client.put(f'/api/events/{event}/current/application/{fid}',
                      json={'profile': prof, 'answers': good() if answers is None else answers})


def test_default_settings_and_hours(client, admin):
    rnd = start_round(client, admin, 'SVS 1', event=EVENT)
    assert rnd['settings'] == {'battle_start': '11:00', 'battle_hours': 5}
    pub = client.get('/api/events/svs/current').json['settings']
    assert pub == {'battle_start': '11:00', 'battle_hours': 5,
                   'hours': ['11:00', '12:00', '13:00', '14:00', '15:00']}


def test_settings_change_and_validation(client, admin):
    rnd = start_round(client, admin, 'SVS', event=EVENT)
    r = client.put(f'/api/admin/rounds/{rnd["id"]}', json={'settings': {'battle_start': '22:30', 'battle_hours': 4}},
                   headers=admin)
    assert r.status_code == 200, r.json
    assert client.get('/api/events/svs/current').json['settings']['hours'] == ['22:30', '23:30', '00:30', '01:30']
    for bad, field in [({'battle_start': '25:00'}, 'settings.battle_start'), ({'battle_hours': 0}, 'settings.battle_hours'),
                       ({'battle_hours': 25}, 'settings.battle_hours'), ({'battle_hours': True}, 'settings.battle_hours'),
                       ({'windows': []}, 'settings')]:
        r = client.put(f'/api/admin/rounds/{rnd["id"]}', json={'settings': bad}, headers=admin)
        assert r.status_code == 400 and r.json['field'] == field, (bad, r.json)
    # settings carry over to the next round
    nxt = start_round(client, admin, 'SVS 2', event=EVENT)
    assert nxt['settings'] == {'battle_start': '22:30', 'battle_hours': 4}


def test_submit_and_profile(client, admin):
    start_round(client, admin, 'SVS', event=EVENT)
    r = put(client, '501', answers=good(hours=['13:00', '11:00']))
    assert r.status_code == 201, r.json
    assert r.json['application']['answers'] == {'hours': ['11:00', '13:00'], 'discord_vc': True, 'language': 'en'}
    p = r.json['profile']
    assert p['alliance'] == 'SVS' and p['troops']['lancer'] == {'furnace_level': 'FC10', 'tier': 11}
    # edit by FID: same application
    r = put(client, '501', answers=good(discord_vc=False, hours=['15:00']))
    assert r.status_code == 200 and r.json['created'] is False
    assert client.get('/api/events/svs/current/application/501').json['answers']['discord_vc'] is False


def test_role_no_longer_asked(client, admin):
    """Owner: SVS sign-up does not ask the role (the planner assigns leaders). An old client that still sends one is
    not refused and the value is not stored."""
    start_round(client, admin, 'SVS', event=EVENT)
    for i, role in enumerate(('call', 'join', 'lead', None)):
        r = put(client, f'52{i}', answers=good(role=role))
        assert r.status_code == 201, r.json
        assert 'role' not in r.json['application']['answers']


def test_strict_player_answers(client, admin):
    start_round(client, admin, 'SVS', event=EVENT)
    cases = [
        ({'hours': []}, 'answers.hours'),
        ({'hours': ['10:00']}, 'answers.hours'),
        ({'hours': '11:00'}, 'answers.hours'),
        ({'discord_vc': None}, 'answers.discord_vc'),
        ({'discord_vc': 'maybe'}, 'answers.discord_vc'),
        ({'language': 'xx'}, 'answers.language'),
        ({'gem_spend': 5}, 'answers.gem_spend'),
    ]
    for patch, field in cases:
        r = put(client, '502', answers=good(**patch))
        assert r.status_code == 400 and r.json['field'] == field, (patch, r.json)


def test_troops_t10_t11_only_and_required(client, admin):
    start_round(client, admin, 'SVS', event=EVENT)
    for tr, field in [
        (troops(tier=9), 'profile.troops.infantry.tier'),
        (troops(tier=8), 'profile.troops.infantry.tier'),
        (troops(camp='25'), 'profile.troops.infantry.furnace_level'),
        (troops(marksman={'furnace_level': 'FC9', 'tier': None}), 'profile.troops.marksman.tier'),
        (troops(lancer={'tier': 10}), 'profile.troops.lancer.furnace_level'),
        ({'infantry': {'furnace_level': 'FC1', 'tier': 10}}, 'profile.troops.lancer.furnace_level'),
        (None, 'profile.troops.infantry.furnace_level'),
    ]:
        r = put(client, '503', profile={'troops': tr})
        assert r.status_code == 400 and r.json['field'] == field, (tr, r.json)
    r = put(client, '503', profile={'troops': troops(camp='fc4', tier='T10')})
    assert r.status_code == 201 and r.json['profile']['troops']['infantry'] == {'furnace_level': 'FC4', 'tier': 10}


def test_returning_player_need_not_resend_valid_troops(client, admin):
    start_round(client, admin, 'SVS', event=EVENT)
    assert put(client, '510').status_code == 201
    r = client.put('/api/events/svs/current/application/510', json={'profile': {}, 'answers': good()})
    assert r.status_code == 200, r.json
    # ... but a stored T9 (e.g. from Frost Dragon Tyrant) must be replaced by T10/T11
    client.put('/api/profile/511', json={'game_name': 'T9', 'alliance': 'NIN', 'troops': {
        'infantry': {'furnace_level': 'FC6', 'tier': 9}, 'lancer': {'furnace_level': 'FC6', 'tier': 10},
        'marksman': {'furnace_level': 'FC6', 'tier': 10}}})
    r = client.put('/api/events/svs/current/application/511', json={'profile': {}, 'answers': good()})
    assert r.status_code == 400 and r.json['field'] == 'profile.troops.infantry.tier'
    r = client.put('/api/events/svs/current/application/511', json={
        'profile': {'troops': {'infantry': {'tier': 10}}}, 'answers': good()})
    assert r.status_code == 201 and r.json['profile']['troops']['infantry'] == {'furnace_level': 'FC6', 'tier': 10}


def test_alliance_only_needed_for_new_players(client, admin):
    start_round(client, admin, 'SVS', event=EVENT)
    r = client.put('/api/events/svs/current/application/504',
                   json={'profile': {'game_name': 'New', 'troops': troops()}, 'answers': good()})
    assert r.status_code == 400 and r.json['field'] == 'profile.alliance'
    # a known player (alliance on the shared profile) is not asked again
    client.put('/api/profile/505', json={'game_name': 'Known', 'alliance': 'KNO'})
    r = client.put('/api/events/svs/current/application/505',
                   json={'profile': {'game_name': 'Known', 'troops': troops()}, 'answers': good()})
    assert r.status_code == 201 and r.json['profile']['alliance'] == 'KNO'


def test_ignored_profile_fields(client, admin):
    start_round(client, admin, 'SVS', event=EVENT)
    client.put('/api/profile/506', json={'game_name': 'P', 'alliance': 'PPP', 'furnace_level': 'FC8', 'power': 9})
    r = put(client, '506', profile={'furnace_level': '30', 'power': 1, 'discord_id': 'x'})
    assert r.status_code == 201
    p = client.get('/api/profile/506').json
    assert p['furnace_level'] == 'FC8' and p['power'] == 9 and p['discord_id'] is None


def test_closing_time_blocks_new_but_not_edit(client, admin):
    rnd = start_round(client, admin, 'SVS', event=EVENT)
    assert put(client, '507').status_code == 201
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'closing_time': '2020-01-01T00:00:00Z'}, headers=admin)
    r = put(client, '508')
    assert r.status_code == 403 and r.json['code'] == 'APPLICATIONS_CLOSED'
    assert put(client, '507', answers=good(hours=['12:00'])).status_code == 200


def test_old_hours_kept_when_resent_after_settings_change(client, admin):
    rnd = start_round(client, admin, 'SVS', event=EVENT)
    assert put(client, '509', answers=good(hours=['11:00', '15:00'])).status_code == 201
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'settings': {'battle_start': '12:00'}}, headers=admin)
    # re-sent unchanged: kept; a new unknown hour is refused
    assert put(client, '509', answers=good(hours=['11:00', '15:00'])).status_code == 200
    r = put(client, '509', answers=good(hours=['11:00', '10:00']))
    assert r.status_code == 400 and r.json['field'] == 'answers.hours'


# ------------------------------------------------------------------ shared profile with Frost Dragon Tyrant

def test_prefill_flows_both_ways_and_merge_rule(client, admin):
    start_round(client, admin, 'FDT', event='tyrant')
    start_round(client, admin, 'SVS', event=EVENT)
    tyr = {'infantry': {'furnace_level': 'FC8', 'tier': 9}, 'lancer': {'furnace_level': 'FC9', 'tier': 11},
           'marksman': {'furnace_level': 'FC7', 'tier': 10}}
    r = client.put('/api/events/tyrant/current/application/600', json={
        'profile': {'game_name': 'Tyra', 'alliance': 'TYR', 'power': 5, 'discord_id': 'tyra', 'troops': tyr},
        'answers': {}})
    assert r.status_code == 201
    # SVS sees Tyrant's data on the shared profile (the wizard pre-fills from it)
    assert client.get('/api/profile/600').json['troops'] == tyr
    # SVS: T10/T11 only; the player re-picks infantry (stored T9) as T10 and raises marksman's camp
    svs = troops(infantry={'furnace_level': 'FC8', 'tier': 10}, lancer={'furnace_level': 'FC9', 'tier': 11},
                 marksman={'furnace_level': 'FC8', 'tier': 10})
    assert put(client, '600', profile={'troops': svs}).status_code == 201
    p = client.get('/api/profile/600').json
    assert p['troops']['infantry'] == {'furnace_level': 'FC8', 'tier': 10}
    assert p['troops']['marksman'] == {'furnace_level': 'FC8', 'tier': 10}
    assert p['power'] == 5 and p['discord_id'] == 'tyra'  # SVS never touches what it doesn't ask
    # ... and Tyrant pre-fills from SVS (same profile)
    r = client.put('/api/events/tyrant/current/application/600', json={'profile': {}, 'answers': {}})
    assert r.status_code == 200 and r.json['profile']['troops']['marksman'] == {'furnace_level': 'FC8', 'tier': 10}
    # merge: a Tyrant submit with a blank troop value never wipes what SVS stored
    r = client.put('/api/events/tyrant/current/application/600', json={'profile': {'troops': {
        'infantry': {'furnace_level': 'FC9', 'tier': None}, 'lancer': None}}, 'answers': {}})
    assert r.status_code == 200
    t = r.json['profile']['troops']
    assert t['infantry'] == {'furnace_level': 'FC9', 'tier': 10} and t['lancer'] == {'furnace_level': 'FC9', 'tier': 11}


def test_merge_keeps_extra_keys():
    from core.troops import merge_troops
    stored = {'infantry': {'furnace_level': 'FC5', 'tier': 9, 'note': 'x'}, 'other': 1}
    out = merge_troops(stored, {'infantry': {'tier': 10}})
    assert out['infantry'] == {'furnace_level': 'FC5', 'tier': 10, 'note': 'x'} and out['other'] == 1
    assert out['lancer'] == {'furnace_level': None, 'tier': None}
    assert merge_troops(None, {}) == {k: {'furnace_level': None, 'tier': None} for k in ('infantry', 'lancer', 'marksman')}


# ------------------------------------------------------------------ admin

def _seed(client, admin):
    rnd = start_round(client, admin, 'SVS admin', event=EVENT)
    put(client, '701', profile={'alliance': 'AAA', 'troops': troops('FC10', 11)},
        answers=good(hours=['11:00', '12:00'], discord_vc=True))
    put(client, '702', profile={'alliance': 'AAA', 'troops': troops('FC9', 10)},
        answers=good(hours=['12:00'], discord_vc=False))
    put(client, '703', profile={'alliance': 'BBB', 'troops': troops('FC10', 10, marksman={'furnace_level': 'FC8',
                                                                                            'tier': 11})},
        answers=good(hours=['12:00', '15:00'], discord_vc=True))
    return rnd


def test_admin_summary(client, admin):
    rnd = _seed(client, admin)
    s = client.get('/api/admin/svs/rounds/current/summary', headers=admin).json
    assert s['round_id'] == rnd['id'] and s['total'] == 3 and s['round_total'] == 3
    assert (s['avg_hours'], s['all_t11'], s['discord_vc']) == (1.7, 1, 2)
    assert 'roles' not in s and 'rally_callers' not in s
    assert {h['hour']: h['count'] for h in s['hours']} == {'11:00': 1, '12:00': 3, '13:00': 0, '14:00': 0, '15:00': 1}
    assert s['alliances'][0] == {'alliance': 'AAA', 'count': 2} and s['alliance_options'] == ['AAA', 'BBB']
    assert s['camp_levels']['infantry'] == {'FC10': 2, 'FC9': 1}
    assert s['troop_tiers']['marksman'] == {'T11': 2, 'T10': 1}
    f = client.get('/api/admin/svs/rounds/current/summary?vc=no&alliance=aaa', headers=admin).json
    assert f['total'] == 1 and f['round_total'] == 3 and f['filters']['vc'] == 'no'


def test_admin_list_filters_and_sort(client, admin):
    _seed(client, admin)

    def fids(qs):
        r = client.get(f'/api/admin/svs/rounds/current/applications?{qs}', headers=admin)
        assert r.status_code == 200, r.json
        return [a['fid'] for a in r.json['applications']]

    assert sorted(fids('hours=12:00')) == ['701', '702', '703']
    assert fids('hours=11:00,12:00') == ['701']
    assert sorted(fids('role=call')) == ['701', '702', '703']  # an old link's role filter is ignored
    assert sorted(fids('vc=yes')) == ['701', '703']
    assert sorted(fids('min_tier=11&troop=marksman')) == ['701', '703']
    assert fids('min_camp=FC10&min_tier=11') == ['701']
    assert fids('infantry_camp=FC9') == ['702']
    assert fids('marksman_tier=11&alliance=BBB') == ['703']
    assert fids('q=703') == ['703']
    assert fids('sort=strength&dir=desc') == ['701', '703', '702']
    rows = client.get('/api/admin/svs/rounds/current/applications', headers=admin).json['applications']
    assert 'furnace_level' not in rows[0]['profile'] and rows[0]['joiner_strength'] is not None
    for qs, field in [('hours=10:00', 'hours'), ('vc=maybe', 'vc'), ('min_camp=25', 'min_camp'),
                      ('sort=power', 'sort')]:
        r = client.get(f'/api/admin/svs/rounds/current/applications?{qs}', headers=admin)
        assert r.status_code == 400 and r.json['field'] == field, (qs, r.json)
    # a tyrant round is not an svs round
    t = start_round(client, admin, 'FDT', event='tyrant')
    assert client.get(f'/api/admin/svs/rounds/{t["id"]}/summary', headers=admin).status_code == 404
    assert client.get('/api/admin/svs/rounds/current/summary').status_code == 401


def test_exports_follow_filters(client, admin):
    _seed(client, admin)
    r = client.get('/api/admin/svs/rounds/current/export.csv?hours=15:00', headers=admin)
    assert r.status_code == 200 and 'svs_' in r.headers['Content-Disposition']
    rows = list(csv.reader(io.StringIO(r.data.decode('utf-8-sig'))))
    assert rows[0][:4] == ['FID', 'In-Game Name', 'Alliance', '11:00 UTC'] and 'Role' not in rows[0]
    assert [r[0] for r in rows[1:]] == ['703']
    assert 'Infantry Camp Level' in rows[0] and 'Joiner Strength' in rows[0]
    r = client.get('/api/admin/svs/rounds/current/export?vc=yes', headers=admin)
    wb = openpyxl.load_workbook(io.BytesIO(r.data))
    ws = wb['SVS Sign-ups']
    assert ws.max_row == 3 and wb['Summary']['A1'].value == 'Round'


def test_admin_edit_is_lenient(client, admin):
    _seed(client, admin)
    app = client.get('/api/admin/svs/rounds/current/applications?q=701', headers=admin).json['applications'][0]
    r = client.put(f'/api/admin/applications/{app["id"]}', json={'answers': {'hours': [], 'discord_vc': None}},
                   headers=admin)
    assert r.status_code == 200 and r.json['answers']['hours'] == [] and r.json['answers']['discord_vc'] is None
    assert client.get('/api/admin/svs/rounds/current/applications?vc=none', headers=admin).json['total'] == 1
