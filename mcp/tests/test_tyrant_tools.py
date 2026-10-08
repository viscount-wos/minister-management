"""The generic tools work for event='tyrant' (strict API validation surfaces), plus get_tyrant_summary."""
import pytest

from conftest import call, fid

pytestmark = pytest.mark.anyio

TROOPS = {'infantry': {'furnace_level': 'FC5', 'tier': 10}, 'lancer': None, 'marksman': {'furnace_level': 'FC3', 'tier': 9}}


def answers(**kw):
    a = {'availability': ['w1', 'w2'], 'discord_vc': True, 'gem_spend': 20000, 'roles': ['rally_leader'],
         'language': 'en'}
    a.update(kw)
    return a


async def test_tyrant_submit_get_previous_and_validation(public, admin, api):
    api.start_round('MCP FDT 1', event='tyrant')
    f = fid()
    prof = {'game_name': 'Tyra', 'alliance': 'fdt', 'furnace_level': 'fc8', 'power': 500_000_000,
            'discord_id': 'tyra', 'troops': TROOPS}
    async with public() as c:
        err, data = await call(c, 'get_current_round', {'event': 'tyrant'})
        assert not err and [w['id'] for w in data['settings']['windows']] == ['w1', 'w2', 'w3', 'w4', 'w5']
        err, data = await call(c, 'submit_application', {'event': 'tyrant', 'fid': f, 'answers': answers(),
                                                         'profile': prof})
        assert not err, data
        # Tyrant does not ask the main furnace (owner p2e): an old client's furnace_level is ignored, not stored
        assert data['created'] and data['profile']['furnace_level'] is None and data['profile']['alliance'] == 'FDT'
        assert data['profile']['troops']['lancer'] == {'furnace_level': None, 'tier': None}
        err, data = await call(c, 'get_application', {'event': 'tyrant', 'fid': f})
        assert not err and data['answers']['availability'] == ['w1', 'w2'] and data['answers']['gem_spend'] == 20000

        for bad, field in [({'availability': ['w99']}, 'answers.availability'), ({'roles': ['boss']}, 'answers.roles'),
                           ({'gem_spend': -3}, 'answers.gem_spend')]:
            err, data = await call(c, 'submit_application', {'event': 'tyrant', 'fid': f, 'answers': answers(**bad)})
            assert err and data['code'] == 'VALIDATION_ERROR' and data['field'] == field, data
        err, data = await call(c, 'submit_application', {
            'event': 'tyrant', 'fid': f, 'answers': answers(),
            'profile': {'troops': {'infantry': {'furnace_level': 'FC12'}}}})
        assert err and data['field'] == 'profile.troops.infantry.furnace_level'
        # Tyrant: FC1-FC10 only for every camp (pre-FC -> VALIDATION_ERROR)
        err, data = await call(c, 'submit_application', {'event': 'tyrant', 'fid': f, 'answers': answers(),
                                                         'profile': {'troops': {'lancer': {'furnace_level': '25',
                                                                                           'tier': 10}}}})
        assert err and data['code'] == 'VALIDATION_ERROR' and data['field'] == 'profile.troops.lancer.furnace_level'
        # ... while any main furnace (even an invalid one) is ignored
        err, data = await call(c, 'submit_application', {'event': 'tyrant', 'fid': f, 'answers': answers(),
                                                         'profile': {'furnace_level': '30'}})
        assert not err and data['profile']['furnace_level'] is None, data
        err, data = await call(c, 'submit_application', {'event': 'tyrant', 'fid': fid(), 'answers': answers(),
                                                         'profile': {'game_name': 'NoAlliance'}})
        assert err and data['field'] == 'profile.alliance'

    api.start_round('MCP FDT 2', event='tyrant')
    async with public() as c:
        err, data = await call(c, 'get_application', {'event': 'tyrant', 'fid': f})
        assert err and data['code'] == 'NOT_FOUND'  # new round: new application
        err, data = await call(c, 'get_previous_application', {'event': 'tyrant', 'fid': f})
        assert not err and data['round_name'] == 'MCP FDT 1' and data['answers']['roles'] == ['rally_leader']


async def test_tyrant_admin_list_and_summary(public, admin, api):
    rnd = api.start_round('MCP FDT summary', event='tyrant')
    fids = [fid() for _ in range(3)]
    async with public() as c:
        for i, f in enumerate(fids):
            err, data = await call(c, 'submit_application', {
                'event': 'tyrant', 'fid': f,
                'answers': answers(availability=['w1'] if i < 2 else ['w4'], discord_vc=i == 0, roles=['joiner']),
                'profile': {'game_name': f'T{i}', 'alliance': 'AAA' if i < 2 else 'BBB', 'furnace_level': 'FC10',
                            'troops': TROOPS}})
            assert not err, data
    async with admin() as c:
        err, data = await call(c, 'list_applications', {'event': 'tyrant'})
        assert not err and data['round_id'] == rnd['id'] and data['total'] == 3
        assert 'furnace_level' not in data['applications'][0]['profile']  # tyrant rows: no main furnace (p2e)
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'alliance': 'BBB'})
        assert not err and data['total'] == 1
        err, data = await call(c, 'get_tyrant_summary', {})
        assert not err, data
        assert data['round_id'] == rnd['id'] and data['total'] == 3 and data['opening_rush'] == 2
        assert data['discord_vc'] == 1 and data['roles']['joiner'] == 3 and 'gem_spend_total' not in data
        assert data['camp_levels']['infantry'] == {'FC5': 3} and data['camp_levels']['lancer'] == {'none': 3}
        assert {w['id']: w['count'] for w in data['windows']}['w4'] == 1
        assert 'furnace_levels' not in data and data['troop_tiers']['infantry'] == {'T10': 3}
        err, data = await call(c, 'get_tyrant_summary', {'round_id': rnd['id'], 'alliance': 'AAA'})
        assert not err and data['total'] == 2
        ministry = api.start_round('MCP ministry for tyrant check')
        err, data = await call(c, 'get_tyrant_summary', {'round_id': ministry['id']})
        assert err and data['code'] == 'NOT_FOUND'


def _full(camp, tier):
    return {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}


async def test_tyrant_troop_filters_one_call(public, admin, api):
    """'who has T11' and 'FC10 camps with T11' are ONE list_applications call; the summary takes the same filters."""
    rnd = api.start_round('MCP FDT camps', event='tyrant')
    best, t11_fc9, t10 = fid(), fid(), fid()
    lancer9 = _full('FC10', 11)
    lancer9['lancer'] = {'furnace_level': 'FC9', 'tier': 11}
    async with public() as c:
        for f, troops, vc in ((best, _full('FC10', 11), True), (t11_fc9, lancer9, False), (t10, _full('FC10', 10), True)):
            err, data = await call(c, 'submit_application', {
                'event': 'tyrant', 'fid': f, 'answers': answers(discord_vc=vc),
                'profile': {'game_name': f'J{f}', 'alliance': 'JJJ', 'furnace_level': 'FC10', 'troops': troops}})
            assert not err, data
    async with admin() as c:
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'min_tier': 11})
        assert not err, data
        assert data['round_id'] == rnd['id'] and sorted(a['fid'] for a in data['applications']) == sorted([best, t11_fc9])
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'min_camp': 'FC10', 'min_tier': 'T11'})
        assert not err and [a['fid'] for a in data['applications']] == [best] and data['total'] == 1
        assert data['applications'][0]['joiner_strength'] == 63
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'min_camp': 'FC10', 'troop': 'infantry'})
        assert not err and data['total'] == 3
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'sort': 'strength', 'direction': 'desc'})
        assert not err and data['applications'][0]['fid'] == best and data['applications'][-1]['fid'] == t10
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'filters': {
            'camp': {'lancer': 'FC9'}, 'vc': False}})
        assert not err and [a['fid'] for a in data['applications']] == [t11_fc9]
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'min_camp': '30'})
        assert err and data['code'] == 'VALIDATION_ERROR' and data['field'] == 'min_camp'
        err, data = await call(c, 'get_tyrant_summary', {'min_camp': 'FC10', 'min_tier': 11})
        assert not err and data['total'] == 1 and data['round_total'] == 3
        assert data['camp_levels']['lancer'] == {'FC10': 1} and data['troop_tiers']['marksman'] == {'T11': 1}
        err, data = await call(c, 'get_tyrant_summary', {'filters': {'tier': {'marksman': 10}}})
        assert not err and data['total'] == 1 and data['filters'] == {'marksman_tier': 10}
        # no furnace filter any more (p2e): the tool refuses it rather than silently returning everyone
        for tool in ('list_applications', 'get_tyrant_summary'):
            err, data = await call(c, tool, {'event': 'tyrant', 'filters': {'min_furnace': 'FC10'}}
                                   if tool == 'list_applications' else {'filters': {'min_furnace': 'FC10'}})
            assert err, (tool, data)
