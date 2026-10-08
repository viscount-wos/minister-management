"""SVS through the MCP (v2.2.0): submit (strict), list_applications svs filters, get_svs_summary, add_player for every
event, get_heroes and set_state_generation."""
import pytest

from conftest import call, fid

pytestmark = pytest.mark.anyio


def troops(camp='FC10', tier=11, **kw):
    out = {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}
    out.update(kw)
    return out


def answers(**kw):
    a = {'hours': ['11:00', '12:00'], 'discord_vc': True, 'language': 'en'}
    a.update(kw)
    return a


async def test_svs_submit_list_and_summary(public, admin, api):
    rnd = api.start_round('MCP SVS 1', event='svs')
    caller, joiner, weak = fid(), fid(), fid()
    async with public() as c:
        err, data = await call(c, 'get_current_round', {'event': 'svs'})
        assert not err and data['settings']['hours'] == ['11:00', '12:00', '13:00', '14:00', '15:00']
        for f, a, tr, ally in ((caller, answers(role='call'), troops(), 'AAA'),  # an old client's role is ignored
                               (joiner, answers(hours=['12:00'], discord_vc=False), troops('FC9', 10), 'AAA'),
                               (weak, answers(hours=['15:00']), troops('FC5', 10), 'BBB')):
            err, data = await call(c, 'submit_application', {'event': 'svs', 'fid': f, 'answers': a,
                                                             'profile': {'game_name': f'S{f}', 'alliance': ally,
                                                                         'troops': tr}})
            assert not err, data
        # strict player rules surface as structured errors
        for bad, field in (({'hours': []}, 'answers.hours'), ({'discord_vc': None}, 'answers.discord_vc')):
            err, data = await call(c, 'submit_application', {'event': 'svs', 'fid': caller, 'answers': answers(**bad)})
            assert err and data['field'] == field, data
        err, data = await call(c, 'submit_application', {'event': 'svs', 'fid': caller, 'answers': answers(),
                                                         'profile': {'troops': troops(tier=9)}})
        assert err and data['field'] == 'profile.troops.infantry.tier'
    async with admin() as c:
        err, data = await call(c, 'list_applications', {'event': 'svs'})
        assert not err and data['round_id'] == rnd['id'] and data['total'] == 3
        assert all('role' not in a['answers'] for a in data['applications'])
        err, data = await call(c, 'list_applications', {'event': 'svs', 'role': 'call'})
        assert not err and data['total'] == 3  # no role filter any more: the argument is ignored
        err, data = await call(c, 'list_applications', {'event': 'svs', 'hours': ['12:00'], 'vc': True})
        assert not err and [a['fid'] for a in data['applications']] == [caller]
        err, data = await call(c, 'list_applications', {'event': 'svs', 'alliance': 'AAA', 'min_camp': 'FC9',
                                                        'min_tier': 10})
        assert not err and sorted(a['fid'] for a in data['applications']) == sorted([caller, joiner])
        err, data = await call(c, 'list_applications', {'event': 'svs', 'svs_filters': {'camp': {'lancer': 'FC5'}}})
        assert not err and [a['fid'] for a in data['applications']] == [weak]
        err, data = await call(c, 'list_applications', {'event': 'svs', 'sort': 'strength', 'direction': 'desc'})
        assert not err and data['applications'][0]['fid'] == caller and data['applications'][0]['joiner_strength'] == 63
        err, data = await call(c, 'list_applications', {'event': 'svs', 'hours': ['09:00']})
        assert err and data['code'] == 'VALIDATION_ERROR' and data['field'] == 'hours'
        err, data = await call(c, 'get_svs_summary', {})
        assert not err, data
        assert (data['total'], data['avg_hours'], data['all_t11'], data['discord_vc']) == (3, 1.3, 1, 2)
        assert {h['hour']: h['count'] for h in data['hours']}['12:00'] == 2
        err, data = await call(c, 'get_svs_summary', {'vc': False, 'alliance': 'AAA'})
        assert not err and data['total'] == 1 and data['round_total'] == 3
        tyr = api.start_round('MCP FDT for svs check', event='tyrant')
        err, data = await call(c, 'get_svs_summary', {'round_id': tyr['id']})
        assert err and data['code'] == 'NOT_FOUND'


@pytest.mark.parametrize('event', ['ministry', 'tyrant', 'svs'])
async def test_add_player_every_event(admin, api, event):
    rnd = api.start_round(f'MCP add {event}', event=event)
    f = fid()
    async with admin() as c:
        err, data = await call(c, 'add_player', {'event': event, 'fid': f, 'profile': {'game_name': 'Added'}})
        assert not err, data
        assert data['round_id'] == rnd['id'] and data['fid'] == f and data['profile_created'] is True
        err, data = await call(c, 'add_player', {'event': event, 'fid': f, 'profile': {'game_name': 'Again'}})
        assert err and data['code'] == 'APPLICATION_EXISTS' and data['http_status'] == 409
        err, data = await call(c, 'add_player', {'event': event, 'fid': fid()})
        assert err and data['field'] == 'profile.game_name'
        if event == 'svs':
            err, data = await call(c, 'add_player', {'event': 'svs', 'fid': fid(), 'round_id': rnd['id'],
                                                     'profile': {'game_name': 'Lean'},
                                                     'answers': {'hours': ['13:00']}})
            assert not err and data['answers']['discord_vc'] is None and 'role' not in data['answers']


async def test_add_player_needs_admin_endpoint(public):
    async with public() as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert 'add_player' not in names and 'set_state_generation' not in names and 'get_heroes' in names


async def test_heroes_and_state_generation(public, admin):
    async with public() as c:
        err, data = await call(c, 'get_heroes', {})
        assert not err and data['total'] == 65 and 'Century Games' in data['attribution']
        err, data = await call(c, 'get_heroes', {'max_gen': 1, 'troop': 'infantry'})
        assert not err and {h['slug'] for h in data['heroes'] if h['has_generation']} == {'natalia', 'jeronimo'}
    async with admin() as c:
        err, data = await call(c, 'set_state_generation', {'generation': 6})
        assert not err and data['state_generation'] == 6
        err, data = await call(c, 'get_heroes', {})
        assert not err and data['max_gen'] == 6 and max(h['generation'] or 0 for h in data['heroes']) == 6
        err, data = await call(c, 'set_state_generation', {'generation': 30})
        assert err and data['field'] == 'state_generation'
        err, data = await call(c, 'set_state_generation', {'generation': 17})
        assert not err and data['state_generation'] == 17
