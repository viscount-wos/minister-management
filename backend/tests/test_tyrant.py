"""Frost Dragon Tyrant: answers, settings (windows), profile split, admin list/summary/exports."""
import csv
import io

import openpyxl

from tests.conftest import start_round

EVENT = 'tyrant'
TROOPS = {'infantry': {'furnace_level': 'FC5', 'tier': 10}, 'lancer': {'furnace_level': '28', 'tier': 9},
          'marksman': {'furnace_level': None, 'tier': 11}}


def put(client, fid, profile=None, answers=None):
    prof = {'game_name': f'P{fid}', 'alliance': 'abc'}
    if profile:
        prof.update(profile)
    return client.put(f'/api/events/{EVENT}/current/application/{fid}', json={'profile': prof, 'answers': answers or {}})


def good_answers(**kw):
    a = {'availability': ['w1', 'w3'], 'discord_vc': True, 'gem_spend': 10000, 'roles': ['joiner', 'rally_leader'],
         'language': 'en'}
    a.update(kw)
    return a


def test_default_windows_and_public_round(client, admin):
    start_round(client, admin, 'FDT 1', event=EVENT)
    r = client.get('/api/events/tyrant/current')
    assert r.status_code == 200
    w = r.json['settings']['windows']
    assert [(x['id'], x['start'], x['end'], x['rush']) for x in w] == [
        ('w1', '11:01', '11:15', True), ('w2', '11:15', '13:00', False), ('w3', '13:00', '15:00', False),
        ('w4', '15:00', '16:30', False), ('w5', '16:30', '18:00', False)]


def test_submit_profile_and_round_split(client, admin):
    start_round(client, admin, 'FDT 1', event=EVENT)
    r = put(client, '1001', profile={'discord_id': 'alice#1234', 'furnace_level': 'fc5', 'power': 410_500_000,
                                     'troops': TROOPS},
            answers=good_answers())
    assert r.status_code == 201, r.json
    prof = r.json['profile']
    assert prof['alliance'] == 'ABC' and prof['discord_id'] == 'alice#1234' and prof['furnace_level'] == 'FC5'
    assert prof['power'] == 410_500_000 and prof['troops']['marksman'] == {'furnace_level': None, 'tier': 11}
    ans = r.json['application']['answers']
    # canonical order (windows order / role list order), not the order sent
    assert ans == {'availability': ['w1', 'w3'], 'discord_vc': True, 'gem_spend': 10000,
                   'roles': ['rally_leader', 'joiner'], 'language': 'en'}
    # profile is shared: visible through the profile endpoint, reusable by other events
    p = client.get('/api/profile/1001').json
    assert p['discord_id'] == 'alice#1234' and p['troops']['infantry'] == {'furnace_level': 'FC5', 'tier': 10}


def test_requires_name_and_alliance(client, admin):
    start_round(client, admin, 'FDT', event=EVENT)
    r = client.put('/api/events/tyrant/current/application/5', json={'profile': {'game_name': 'X'}, 'answers': {}})
    assert r.status_code == 400 and r.json['field'] == 'profile.alliance'
    r = put(client, '5', profile={'alliance': 'ABCD'})
    assert r.status_code == 400 and r.json['field'] == 'profile.alliance'


def test_blank_answers_are_valid(client, admin):
    start_round(client, admin, 'FDT', event=EVENT)
    r = put(client, '6')
    assert r.status_code == 201
    assert r.json['application']['answers'] == {'availability': [], 'discord_vc': False, 'gem_spend': None,
                                                 'roles': [], 'language': None}


def test_strict_answer_validation(client, admin):
    start_round(client, admin, 'FDT', event=EVENT)
    cases = [
        ({'availability': ['w9']}, 'answers.availability'),
        ({'availability': 'w1'}, 'answers.availability'),
        ({'roles': ['king']}, 'answers.roles'),
        ({'discord_vc': 'maybe'}, 'answers.discord_vc'),
        ({'gem_spend': -1}, 'answers.gem_spend'),
        ({'gem_spend': 1.5}, 'answers.gem_spend'),
        ({'gem_spend': 'lots'}, 'answers.gem_spend'),
        ({'gem_spend': 10 ** 10}, 'answers.gem_spend'),
        ({'language': 'xx'}, 'answers.language'),
        ({'surprise': 1}, 'answers.surprise'),
    ]
    for answers, field in cases:
        r = put(client, '7', answers=answers)
        assert r.status_code == 400 and r.json['code'] == 'VALIDATION_ERROR' and r.json['field'] == field, (answers, r.json)
    assert client.get('/api/events/tyrant/current/application/7').status_code == 404  # nothing written


def test_strict_troop_validation(client, admin):
    start_round(client, admin, 'FDT', event=EVENT)
    cases = [
        ({'troops': {'archer': {}}}, 'profile.troops'),
        ({'troops': {'infantry': {'furnace_level': 'FC11'}}}, 'profile.troops.infantry.furnace_level'),
        ({'troops': {'infantry': {'furnace_level': 31}}}, 'profile.troops.infantry.furnace_level'),
        ({'troops': {'infantry': {'tier': 12}}}, 'profile.troops.infantry.tier'),
        ({'troops': {'infantry': {'tier': 'T10'}}}, 'profile.troops.infantry.tier'),
        ({'troops': {'infantry': {'level': 3}}}, 'profile.troops.infantry'),
        ({'troops': [1, 2]}, 'profile.troops'),
        ({'furnace_level': 'FC11'}, 'profile.furnace_level'),
        ({'furnace_level': '31'}, 'profile.furnace_level'),
        ({'furnace_level': 0}, 'profile.furnace_level'),
        ({'power': -5}, 'profile.power'),
        ({'discord_id': 'x' * 65}, 'profile.discord_id'),
    ]
    for prof, field in cases:
        r = put(client, '8', profile=prof)
        assert r.status_code == 400 and r.json['field'] == field, (prof, r.json)
    r = put(client, '8', profile={'troops': {'infantry': {'furnace_level': 'FC2'}}})
    assert r.status_code == 201
    blank = {'furnace_level': None, 'tier': None}
    assert r.json['profile']['troops'] == {'infantry': {'furnace_level': 'FC2', 'tier': None}, 'lancer': blank,
                                           'marksman': blank}


def test_windows_settings_validation_and_carry_over(client, admin):
    rnd = start_round(client, admin, 'FDT', event=EVENT)
    url = f'/api/admin/rounds/{rnd["id"]}'
    bad = [
        ({'windows': []}, 'settings.windows'),
        ({'windows': [{'id': 'a', 'start': '12:00', 'end': '11:00'}]}, 'settings.windows.0.end'),
        ({'windows': [{'id': 'a', 'start': '1200', 'end': '13:00'}]}, 'settings.windows.0.start'),
        ({'windows': [{'id': 'A B', 'start': '10:00', 'end': '11:00'}]}, 'settings.windows.0.id'),
        ({'windows': [{'id': 'a', 'start': '10:00', 'end': '11:00'}, {'id': 'a', 'start': '12:00', 'end': '13:00'}]},
         'settings.windows.1.id'),
        ({'windows': [{'id': 'a', 'start': '10:00', 'end': '11:00', 'colour': 'red'}]}, 'settings.windows.0'),
        ({'research_day': 'friday'}, 'settings'),
    ]
    for settings, field in bad:
        r = client.put(url, json={'settings': settings}, headers=admin)
        assert r.status_code == 400 and r.json['field'] == field, (settings, r.json)
    new = [{'id': 'late', 'start': '19:00', 'end': '20:00'}, {'id': 'rush', 'start': '10:00', 'end': '10:15', 'rush': True}]
    r = client.put(url, json={'settings': {'windows': new}, 'closing_time': '2099-01-01T00:00:00Z'}, headers=admin)
    assert r.status_code == 200
    assert [w['id'] for w in r.json['settings']['windows']] == ['rush', 'late']  # sorted by start
    assert r.json['closing_time'] == '2099-01-01T00:00:00Z'
    assert client.get('/api/events/tyrant/current').json['settings']['windows'][0] == \
        {'id': 'rush', 'start': '10:00', 'end': '10:15', 'rush': True}
    r2 = start_round(client, admin, 'FDT 2', event=EVENT)
    assert [w['id'] for w in r2['settings']['windows']] == ['rush', 'late']  # carried over


def test_removed_window_kept_on_resubmit(client, admin):
    rnd = start_round(client, admin, 'FDT', event=EVENT)
    assert put(client, '9', answers=good_answers(availability=['w2', 'w5'])).status_code == 201
    client.put(f'/api/admin/rounds/{rnd["id"]}', headers=admin,
               json={'settings': {'windows': [{'id': 'w2', 'start': '11:15', 'end': '13:00'}]}})
    r = put(client, '9', answers=good_answers(availability=['w2', 'w5']))
    assert r.status_code == 200 and r.json['application']['answers']['availability'] == ['w2', 'w5']
    r = put(client, '10', answers=good_answers(availability=['w5']))
    assert r.status_code == 400 and r.json['field'] == 'answers.availability'


def test_new_vs_edit_and_previous_round(client, admin):
    start_round(client, admin, 'FDT 1', event=EVENT)
    assert put(client, '11', answers=good_answers()).status_code == 201
    assert put(client, '11', answers=good_answers(gem_spend=5)).status_code == 200
    r2 = start_round(client, admin, 'FDT 2', event=EVENT)
    assert client.get('/api/events/tyrant/current/application/11').status_code == 404  # new round: new application
    prev = client.get('/api/events/tyrant/previous-application/11')
    assert prev.status_code == 200 and prev.json['round_name'] == 'FDT 1' and prev.json['answers']['gem_spend'] == 5
    assert client.get('/api/events/ministry/previous-application/11').status_code == 404
    assert client.get('/api/profile/11').json['alliance'] == 'ABC'  # profile pre-fills
    assert r2['status'] == 'open'


def test_closing_time_blocks_new_only(client, admin):
    rnd = start_round(client, admin, 'FDT', event=EVENT)
    assert put(client, '12').status_code == 201
    client.put(f'/api/admin/rounds/{rnd["id"]}', json={'closing_time': '2000-01-01T00:00:00Z'}, headers=admin)
    r = put(client, '13')
    assert r.status_code == 403 and r.json['code'] == 'APPLICATIONS_CLOSED'
    assert put(client, '12', answers={'discord_vc': True}).status_code == 200


def _seed(client, admin):
    rnd = start_round(client, admin, 'FDT', event=EVENT)
    put(client, '21', profile={'game_name': 'Zed', 'alliance': 'AAA', 'furnace_level': 'FC10', 'power': 900_000_000,
                               'troops': TROOPS, 'discord_id': 'zed'},
        answers=good_answers(availability=['w1', 'w2'], roles=['rally_leader'], gem_spend=50000))
    put(client, '22', profile={'game_name': 'amy', 'alliance': 'BBB', 'furnace_level': '30', 'power': 100_000_000,
                               'troops': {'infantry': {'furnace_level': 'FC1', 'tier': 8}}},
        answers=good_answers(availability=['w3'], discord_vc=False, roles=['joiner', 'gathering'], gem_spend=None))
    put(client, '23', profile={'game_name': '=HYPERLINK("x")', 'alliance': 'aaa'},
        answers=good_answers(availability=['w1'], roles=[], gem_spend=0))
    return rnd


def test_admin_list_filter_search_sort_paging(client, admin):
    rnd = _seed(client, admin)
    base = f'/api/admin/tyrant/rounds/{rnd["id"]}/applications'
    assert client.get(base).status_code == 401
    r = client.get(base, headers=admin)
    assert r.status_code == 200 and r.json['total'] == 3
    assert [a['fid'] for a in r.json['applications']] == ['23', '22', '21']  # newest first
    assert r.json['applications'][0]['profile']['game_name'] == '=HYPERLINK("x")'
    r = client.get(base + '?alliance=aaa', headers=admin)
    assert sorted(a['fid'] for a in r.json['applications']) == ['21', '23']
    r = client.get(base + '?q=AM', headers=admin)
    assert [a['fid'] for a in r.json['applications']] == ['22']
    r = client.get(base + '?q=zed', headers=admin)  # discord id / name
    assert [a['fid'] for a in r.json['applications']] == ['21']
    r = client.get(base + '?sort=power&dir=desc', headers=admin)
    assert [a['fid'] for a in r.json['applications']] == ['21', '22', '23']  # blank power last
    r = client.get(base + '?sort=furnace&dir=desc', headers=admin)
    assert [a['fid'] for a in r.json['applications']] == ['21', '22', '23']  # FC10 > 30 > blank
    r = client.get(base + '?sort=furnace&dir=asc', headers=admin)
    assert [a['fid'] for a in r.json['applications']] == ['22', '21', '23']
    r = client.get(base + '?sort=name&dir=asc', headers=admin)
    assert [a['fid'] for a in r.json['applications']] == ['23', '22', '21']
    r = client.get(base + '?sort=gems&dir=asc&limit=1&offset=1', headers=admin)
    assert r.json['total'] == 3 and r.json['limit'] == 1 and [a['fid'] for a in r.json['applications']] == ['21']
    assert client.get(base + '?sort=bogus', headers=admin).json['field'] == 'sort'
    assert client.get(base + '?limit=0', headers=admin).json['field'] == 'limit'
    r = client.get('/api/admin/tyrant/rounds/current/applications', headers=admin)
    assert r.json['round_id'] == rnd['id']
    m = start_round(client, admin, 'Ministry', event='ministry')
    assert client.get(f'/api/admin/tyrant/rounds/{m["id"]}/applications', headers=admin).status_code == 404
    # generic list also works for tyrant (MCP list_applications)
    g = client.get(f'/api/admin/rounds/{rnd["id"]}/applications', headers=admin)
    assert g.status_code == 200 and g.json['total'] == 3


def test_admin_summary(client, admin):
    rnd = _seed(client, admin)
    s = client.get(f'/api/admin/tyrant/rounds/{rnd["id"]}/summary', headers=admin).json
    assert s['total'] == 3 and s['opening_rush'] == 2 and s['discord_vc'] == 2 and s['gem_spend_total'] == 50000
    assert {w['id']: w['count'] for w in s['windows']} == {'w1': 2, 'w2': 1, 'w3': 1, 'w4': 0, 'w5': 0}
    assert s['alliances'] == [{'alliance': 'AAA', 'count': 2}, {'alliance': 'BBB', 'count': 1}]
    assert s['roles'] == {'rally_leader': 1, 'joiner': 1, 'gathering': 1, 'battle_mgmt': 0, 'event_prep': 0}
    assert s['troop_tiers']['infantry'] == {'T10': 1, 'T8': 1, 'none': 1}
    assert s['troop_tiers']['marksman'] == {'T11': 1, 'none': 2}
    assert s['furnace_levels'] == {'FC10': 1, '30': 1, 'none': 1}  # FC above pre-FC, blanks last
    s = client.get(f'/api/admin/tyrant/rounds/{rnd["id"]}/summary?alliance=BBB', headers=admin).json
    assert s['total'] == 1 and s['opening_rush'] == 0


def test_exports_are_formula_safe(client, admin):
    rnd = _seed(client, admin)
    r = client.get(f'/api/admin/tyrant/rounds/{rnd["id"]}/export.csv', headers=admin)
    assert r.status_code == 200 and r.mimetype == 'text/csv' and 'attachment' in r.headers['Content-Disposition']
    rows = list(csv.reader(io.StringIO(r.data.decode('utf-8-sig'))))
    head = rows[0]
    assert head[:4] == ['FID', 'In-Game Name', 'Alliance', 'Discord ID'] and '11:01-11:15 Opening Rush' in head
    by = {row[0]: dict(zip(head, row)) for row in rows[1:]}
    assert by['23']['In-Game Name'] == '\'=HYPERLINK("x")'
    assert by['21']['Furnace Level'] == 'FC10' and by['22']['Furnace Level'] == '30' and by['21']['Power (M)'] == '900.0'
    assert by['21']['Infantry Furnace Level'] == 'FC5' and by['21']['Infantry T-Level'] == 'T10'
    assert by['21']['Rally Leader'] == 'Yes' and by['22']['Rally Leader'] == 'No'
    for url in (f'/api/admin/tyrant/rounds/{rnd["id"]}/export', f'/api/admin/rounds/{rnd["id"]}/export'):
        r = client.get(url, headers=admin)
        assert r.status_code == 200 and r.mimetype.endswith('spreadsheetml.sheet')
        wb = openpyxl.load_workbook(io.BytesIO(r.data))
        ws = wb['Tyrant Poll Results']
        cells = {c.value: c for c in ws['B']}
        cell = cells['=HYPERLINK("x")']
        assert cell.data_type == 's' and cell.quotePrefix
        assert ws.freeze_panes == 'A2' and 'Summary' in wb.sheetnames
    assert client.get(f'/api/admin/tyrant/rounds/{rnd["id"]}/export.csv').status_code == 401


def test_delete_and_admin_edit(client, admin):
    rnd = _seed(client, admin)
    apps = client.get(f'/api/admin/tyrant/rounds/{rnd["id"]}/applications', headers=admin).json['applications']
    aid = next(a['id'] for a in apps if a['fid'] == '22')
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'roles': ['event_prep']}}, headers=admin)
    assert r.status_code == 200 and r.json['answers']['roles'] == ['event_prep']
    r = client.put(f'/api/admin/applications/{aid}', json={'answers': {'roles': ['nope']}}, headers=admin)
    assert r.status_code == 400 and r.json['field'] == 'answers.roles'
    assert client.delete(f'/api/admin/applications/{aid}', headers=admin).json['deleted'] is True
    assert client.get(f'/api/admin/tyrant/rounds/{rnd["id"]}/summary', headers=admin).json['total'] == 2
    assert client.get('/api/profile/22').status_code == 200  # profile kept


def test_ministry_ignores_tyrant_profile_fields(client, admin):
    """Ministry keeps its free-form troops; the tyrant troop structure is only enforced on tyrant submits."""
    start_round(client, admin, 'M', event='ministry')
    r = client.put('/api/events/ministry/current/application/31',
                   json={'profile': {'game_name': 'M', 'alliance': 'MMM', 'troops': {'infantry': 5}}, 'answers': {}})
    assert r.status_code == 201 and r.json['profile']['troops'] == {'infantry': 5}
