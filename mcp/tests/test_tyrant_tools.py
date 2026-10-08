"""The generic tools work for event='tyrant' (strict API validation surfaces), plus get_tyrant_summary."""
import pytest

from conftest import call, fid

pytestmark = pytest.mark.anyio

TROOPS = {'infantry': {'furnace_level': 'FC5', 'tier': 10}, 'lancer': None, 'marksman': {'furnace_level': '30', 'tier': 9}}


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
        assert data['created'] and data['profile']['furnace_level'] == 'FC8' and data['profile']['alliance'] == 'FDT'
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
        assert data['applications'][0]['profile']['furnace_level'] == 'FC10'
        err, data = await call(c, 'list_applications', {'event': 'tyrant', 'alliance': 'BBB'})
        assert not err and data['total'] == 1
        err, data = await call(c, 'get_tyrant_summary', {})
        assert not err, data
        assert data['round_id'] == rnd['id'] and data['total'] == 3 and data['opening_rush'] == 2
        assert data['discord_vc'] == 1 and data['roles']['joiner'] == 3
        assert {w['id']: w['count'] for w in data['windows']}['w4'] == 1
        assert data['furnace_levels'] == {'FC10': 3} and data['troop_tiers']['infantry'] == {'T10': 3}
        err, data = await call(c, 'get_tyrant_summary', {'round_id': rnd['id'], 'alliance': 'AAA'})
        assert not err and data['total'] == 2
        ministry = api.start_round('MCP ministry for tyrant check')
        err, data = await call(c, 'get_tyrant_summary', {'round_id': ministry['id']})
        assert err and data['code'] == 'NOT_FOUND'
