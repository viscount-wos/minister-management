"""SVS battle planner e2e (v2.2.0, phase 2): build a main + counter plan in the browser (leaders from sign-ups and by
quick add, heroes by drag and by click-to-place, ratios, split rally/garrison, pet buffs, PFP + alias, 4 named joiners
with lead heroes, extra joiners), move a leader to the other group, double booking blocked, the state hero
generation limit, the stale-revision conflict banner (two pages), the share link lifecycle, and the shared plan view
on an iPhone in English and Arabic with Find me. Every context fails on a CSP violation (conftest).

Own SVS round for the module; sign-ups seeded through the public API (no role: SVS doesn't ask it).
"""
from __future__ import annotations

import re
import secrets
import time

import pytest
from playwright.sync_api import Browser, Page, Playwright, expect

import ui

RUN = time.strftime('%H%M%S')
BASE = 61_000_000 + secrets.randbelow(900_000)
NAMES = ['Aster', 'Birch', 'Cedar', 'Dune', 'Ember', 'Fjord', 'Grove', 'Heath', 'Iris', 'Juniper', 'Kestrel', 'Larch']
FIDS = {n: str(BASE + i) for i, n in enumerate(NAMES)}
QUICK_FID = str(BASE + 99)


def tr(key: str, lang: str = 'en', **v) -> str:
    return ui.tr(lang, key, **v)


def troops(camp, tier):
    return {k: {'furnace_level': camp, 'tier': tier} for k in ('infantry', 'lancer', 'marksman')}


@pytest.fixture(scope='module', autouse=True)
def plan_round(api):
    _, res = api.call('POST', '/api/admin/events/svs/start-new-round',
                      {'name': f'SVS plan e2e {RUN}', 'settings': {'battle_start': '11:00', 'battle_hours': 5}},
                      admin=True)
    for i, (name, fid) in enumerate(FIDS.items()):
        camp, tier = ('FC10', 11) if i < 4 else ('FC6', 10) if name == 'Iris' else ('FC9', 11)
        api.call('PUT', f'/api/events/svs/current/application/{fid}',
                 {'profile': {'game_name': f'{name}{RUN}', 'alliance': 'PLN' if i % 2 else 'ICE',
                              'troops': troops(camp, tier)},
                  'answers': {'hours': ['11:00', '12:00', '13:00'], 'discord_vc': i % 3 != 0}})
    yield res['round']
    api.call('PUT', '/api/admin/settings', {'state_generation': 17}, admin=True)


def nm(name: str) -> str:
    return f'{name}{RUN}'


def open_planner(page: Page, base_url: str, api: ui.Api) -> None:
    ui.use_admin_token(page, base_url, api.token(), ui.admin_dashboard_url('svs'))
    page.get_by_test_id('tab-plan').click()
    expect(page.get_by_test_id('svs-planner')).to_be_visible()
    page.wait_for_load_state('networkidle')


def wait_saved(page: Page) -> None:
    expect(page.get_by_test_id('save-status')).to_have_attribute('data-status', 'saved', timeout=10_000)


def get_plan(api: ui.Api) -> dict:
    return api.call('GET', '/api/admin/svs/rounds/current/plan', admin=True)[1]


def leader(page: Page, name: str):
    return page.locator(f'[data-testid=leader-card][data-name="{name}"]')


def drag(page: Page, src, dst) -> None:
    """dnd-kit needs real pointer moves: press, nudge past the 5px threshold, glide onto the target, release."""
    dst.scroll_into_view_if_needed()
    s, d = src.bounding_box(), dst.bounding_box()
    page.mouse.move(s['x'] + s['width'] / 2, s['y'] + s['height'] / 2)
    page.mouse.down()
    page.mouse.move(s['x'] + s['width'] / 2 + 12, s['y'] + s['height'] / 2 + 12, steps=4)
    page.mouse.move(d['x'] + d['width'] / 2, d['y'] + d['height'] / 2, steps=15)
    page.mouse.move(d['x'] + d['width'] / 2 + 1, d['y'] + d['height'] / 2 + 1, steps=2)
    page.mouse.up()


def palette_hero(page: Page, slug: str, search: str):
    page.get_by_test_id('sidebar-tab-heroes').click()
    page.get_by_test_id('palette-search').fill(search)
    hero = page.locator(f'[data-palette-hero="{slug}"]')
    expect(hero).to_be_visible()
    return hero


def click_place(page: Page, slot, slug: str, search: str) -> None:
    """Click-to-place: click the slot (it lights up), then the hero in the palette."""
    slot.scroll_into_view_if_needed()
    slot.locator('button').first.click()
    expect(page.get_by_test_id('armed-slot-banner')).to_be_visible()
    palette_hero(page, slug, search).click()
    expect(slot).to_have_attribute('data-hero', slug)


def pick_player(page: Page, search, text: str, fid: str | None = None, keyboard: bool = False) -> None:
    box = search.get_by_role('combobox')
    box.fill(text)
    if keyboard:
        box.press('ArrowDown')
        box.press('ArrowUp')
        box.press('Enter')
    else:
        search.locator(f'[data-testid=option-{fid}]').click()


def test_build_plan(page: Page, base_url, api, shot):
    page.on('dialog', lambda d: d.accept())
    open_planner(page, base_url, api)
    expect(page.get_by_test_id('strategy-main_counter')).to_have_attribute('aria-checked', 'true')
    expect(page.get_by_test_id('group-main')).to_be_visible()
    expect(page.get_by_test_id('group-counter')).to_be_visible()
    expect(page.get_by_test_id('unplaced-count')).to_have_count(0)  # heroes tab first
    shot('empty')

    main = page.get_by_test_id('group-main')
    counter = page.get_by_test_id('group-counter')
    main.get_by_test_id('group-name').fill('Main rallies')
    main.get_by_test_id('group-tag').fill('ICE')
    main.get_by_test_id('min-infantry-camp').select_option('FC8')
    main.get_by_test_id('min-infantry-tier').select_option('11')

    # ---- leader 1 (main) from the sign-ups, keyboard pick
    main.get_by_test_id('add-leader').click()
    l1_search = main.get_by_test_id('leader-search')
    pick_player(page, l1_search, nm('Aster'), keyboard=True)
    l1 = leader(page, nm('Aster'))
    expect(l1).to_be_visible()
    # hover shows the sign-up (troops, hours, VC)
    l1.get_by_test_id('leader-name').locator('span').first.hover()
    expect(page.get_by_test_id('player-hover')).to_contain_text('FC10 T11')
    page.mouse.move(5, 5)

    # disguise: PFP by click-to-place + alias
    l1.get_by_test_id('disguise-open').click()
    click_place(page, l1.get_by_test_id('slot-pfp'), 'flint', 'Flint')
    l1.get_by_test_id('alias-input').fill('Rally Caller 01')
    expect(l1).to_have_attribute('data-alias', 'Rally Caller 01')

    # rally heroes: one dragged from the palette, two by click-to-place (the slot advances by itself)
    drag(page, palette_hero(page, 'jeronimo', 'Jeron'), l1.get_by_test_id('slot-march-rally-0'))
    expect(l1.get_by_test_id('slot-march-rally-0')).to_have_attribute('data-hero', 'jeronimo')
    click_place(page, l1.get_by_test_id('slot-march-rally-1'), 'molly', 'Molly')
    expect(l1.get_by_test_id('slot-march-rally-2')).to_have_attribute('data-armed', 'true')
    palette_hero(page, 'zinman', 'Zinman').click()
    expect(l1.get_by_test_id('slot-march-rally-2')).to_have_attribute('data-hero', 'zinman')

    # ratio: must total 100 (not saved until it does)
    l1.get_by_test_id('ratio-rally-inf').fill('50')
    l1.get_by_test_id('ratio-rally-lan').fill('20')
    expect(l1.get_by_test_id('ratio-rally-total')).to_have_text(tr('svs:plan.ratioTotal', n=70))
    l1.get_by_test_id('ratio-rally-mks').fill('30')
    expect(l1.get_by_test_id('ratio-rally-total')).to_have_text('= 100%')

    # split: separate garrison heroes and ratio
    l1.get_by_test_id('split-toggle').click()
    g = l1.get_by_test_id('march-garrison')
    expect(g).to_be_visible()
    click_place(page, g.get_by_test_id('slot-march-garrison-0'), 'natalia', 'Natalia')
    page.keyboard.press('Escape')
    g.get_by_test_id('ratio-garrison-inf').fill('70')
    g.get_by_test_id('ratio-garrison-lan').fill('15')
    g.get_by_test_id('ratio-garrison-mks').fill('15')

    # pet buff with its time
    pet = l1.get_by_test_id('pet-buff-two_hours')
    expect(pet).to_have_text(tr('svs:plan.petAt', moment=tr('svs:plan.pet.two_hours'), time='13:00'))
    pet.click()
    expect(pet).to_have_attribute('aria-pressed', 'true')

    # 4 named joiners (search; one by quick add WITH an FID = a new sign-up), each with a lead hero
    joiners = [('Birch', FIDS['Birch']), ('Cedar', FIDS['Cedar']), ('Iris', FIDS['Iris'])]
    for i, (name, fid) in enumerate(joiners):
        pick_player(page, l1.get_by_test_id(f'joiner-{i}').get_by_test_id('joiner-search'), name + RUN[:2], fid)
        expect(l1.get_by_test_id(f'joiner-{i}')).to_have_attribute('data-name', nm(name))
    # Iris is FC6 T10: below the main group's FC8/T11 infantry minimum -> warning badge (not blocked)
    expect(l1.get_by_test_id('joiner-2').get_by_test_id('below-minimum')).to_be_visible()
    j3 = l1.get_by_test_id('joiner-3')
    j3.get_by_role('combobox').fill(f'Newbie{RUN}')
    j3.get_by_test_id('option-quick-add').click()
    j3.get_by_test_id('quick-add-fid').fill(QUICK_FID)
    j3.get_by_test_id('quick-add-submit').click()
    expect(j3).to_have_attribute('data-name', f'Newbie{RUN}')
    _, app = api.call('GET', f'/api/events/svs/current/application/{QUICK_FID}')
    assert app['fid'] == QUICK_FID  # quick add with an FID created the SVS sign-up
    for i, (slug, search) in enumerate([('jessie', 'Jessie'), ('jessie', 'Jessie'), ('sergey', 'Sergey'), ('patrick', 'Patrick')]):
        click_place(page, l1.get_by_test_id(f'slot-joiner-rally-{i}'), slug, search)
    click_place(page, l1.get_by_test_id('slot-joiner-garrison-0'), 'sergey', 'Sergey')
    # one joiner with an own (override) ratio
    l1.get_by_test_id('joiner-ratio-toggle-1').click()
    l1.get_by_test_id('joiner-1-ratio-rally-inf').fill('40')
    l1.get_by_test_id('joiner-1-ratio-rally-lan').fill('40')
    l1.get_by_test_id('joiner-1-ratio-rally-mks').fill('20')
    # everyone else may use
    click_place(page, l1.get_by_test_id('slot-other-rally-0'), 'jessie', 'Jessie')
    # 2 extra joiners: one from the sign-ups (dragged from the unplaced list), one name-only quick add
    page.get_by_test_id('sidebar-tab-players').click()
    drag(page, page.get_by_test_id(f'unplaced-{FIDS["Dune"]}'), l1.get_by_test_id('extra-search'))
    expect(l1.get_by_test_id('extra-chip')).to_have_count(1)
    ex = l1.get_by_test_id('extra-search')
    ex.get_by_role('combobox').fill(f'Walkin{RUN}')
    ex.get_by_test_id('option-quick-add').click()
    expect(page.get_by_test_id('quick-add-name')).to_have_value(f'Walkin{RUN}')
    page.get_by_test_id('quick-add-submit').click()
    expect(l1.get_by_test_id('extra-chip')).to_have_count(2)
    expect(l1.get_by_test_id('extra-chip').nth(1).get_by_test_id('not-signed-up')).to_be_visible()
    wait_saved(page)
    shot('half')

    # ---- leader 2 (main), then leader 3 (counter) by quick add (name only)
    main.get_by_test_id('add-leader').click()
    pick_player(page, main.get_by_test_id('leader-search'), nm('Ember'), FIDS['Ember'])
    l2 = leader(page, nm('Ember'))
    click_place(page, l2.get_by_test_id('slot-march-rally-0'), 'natalia', 'Natalia')
    counter.get_by_test_id('add-leader').click()
    cs = counter.get_by_test_id('leader-search')
    cs.get_by_role('combobox').fill(f'Ghost{RUN}')
    cs.get_by_test_id('option-quick-add').click()
    page.get_by_test_id('quick-add-submit').click()
    expect(leader(page, f'Ghost{RUN}')).to_be_visible()
    wait_saved(page)

    # ---- double booking: Birch is with Rally Caller 01 -> badge in the search, the pick is refused
    js = l2.get_by_test_id('joiner-0').get_by_test_id('joiner-search')
    js.get_by_role('combobox').fill(nm('Birch'))
    opt = js.locator(f'[data-testid=option-{FIDS["Birch"]}]')
    expect(opt.get_by_test_id('already-placed')).to_have_text(tr('svs:plan.placed.with', leader='Rally Caller 01'))
    opt.click(force=True)  # aria-disabled: Playwright would wait for it to become enabled
    expect(js.get_by_test_id('joiner-search-msg')).to_contain_text('Rally Caller 01')
    expect(l2.get_by_test_id('joiner-0')).to_have_attribute('data-name', '')
    # ... and the server refuses one too (422 + where they already are)
    plan = get_plan(api)
    bad = plan['plan']
    bad['leaders'][1]['named_joiners'][0]['player'] = {'fid': FIDS['Birch']}
    status, err = api.call('PUT', '/api/admin/svs/rounds/current/plan', {'revision': plan['revision'], 'plan': bad},
                           admin=True, ok=None)
    assert status == 422 and err['code'] == 'DOUBLE_BOOKED' and err['details']['leader_label'] == 'Rally Caller 01'
    # an explicit move is allowed: "Move here" takes Birch from leader 1 to leader 2
    js.get_by_role('combobox').fill(nm('Birch'))
    js.get_by_test_id(f'move-here-{FIDS["Birch"]}').click()
    expect(l2.get_by_test_id('joiner-0')).to_have_attribute('data-name', nm('Birch'))
    expect(l1.get_by_test_id('joiner-0')).to_have_attribute('data-name', '')
    pick_player(page, l1.get_by_test_id('joiner-0').get_by_test_id('joiner-search'), nm('Fjord'), FIDS['Fjord'])

    # ---- drag leader 2 to the counter group (and the menu moves it back and forth too)
    drag(page, l2.get_by_test_id('leader-drag'), counter.get_by_test_id('new-leader-drop'))
    expect(counter.locator(f'[data-testid=leader-card][data-name="{nm("Ember")}"]')).to_be_visible()
    expect(main.get_by_test_id('leader-card')).to_have_count(1)
    wait_saved(page)
    shot('full')

    plan = get_plan(api)
    p, view = plan['plan'], plan['view']
    assert p['strategy'] == 'main_counter'
    by_group = {g['kind']: g for g in view['groups']}
    assert [l['player']['name'] for l in by_group['main']['leaders']] == [nm('Aster')]
    assert {l['player']['name'] for l in by_group['counter']['leaders']} == {f'Ghost{RUN}', nm('Ember')}
    l1v = by_group['main']['leaders'][0]
    assert l1v['alias'] == 'Rally Caller 01' and l1v['pfp_hero']['slug'] == 'flint'
    assert [h['slug'] for h in l1v['rally']['heroes']] == ['jeronimo', 'molly', 'zinman']
    assert l1v['rally']['ratio'] == {'inf': 50, 'lan': 20, 'mks': 30}
    assert l1v['split'] and l1v['garrison']['heroes'][0]['slug'] == 'natalia'
    assert l1v['garrison']['ratio'] == {'inf': 70, 'lan': 15, 'mks': 15}
    assert l1v['pet_buff'] == 'two_hours' and l1v['pet_buff_time'] == '13:00'
    names = [j['player']['name'] for j in l1v['named_joiners']]
    assert names == [nm('Fjord'), nm('Cedar'), nm('Iris'), f'Newbie{RUN}']
    assert [j['rally']['lead_hero']['slug'] for j in l1v['named_joiners']] == ['jessie', 'jessie', 'sergey', 'patrick']
    assert l1v['named_joiners'][1]['rally']['ratio'] == {'inf': 40, 'lan': 40, 'mks': 20}
    assert l1v['named_joiners'][1]['rally']['ratio_overridden']
    assert l1v['named_joiners'][0]['garrison']['ratio'] == {'inf': 70, 'lan': 15, 'mks': 15}  # inherits
    assert [e['name'] for e in l1v['extra_joiners']] == [nm('Dune'), f'Walkin{RUN}']
    assert [h['slug'] for h in l1v['rally']['other_joiner_heroes']] == ['jessie']
    assert by_group['main']['min_requirements']['infantry'] == {'min_camp': 'FC8', 'min_tier': 11}
    # the plan reloads exactly as saved
    page.reload()
    page.get_by_test_id('tab-plan').click()
    expect(leader(page, nm('Aster')).get_by_test_id('alias-input')).to_have_value('Rally Caller 01')
    expect(leader(page, nm('Aster')).get_by_test_id('ratio-garrison-inf')).to_have_value('70')


def test_generation_limit(page: Page, base_url, api):
    api.call('PUT', '/api/admin/settings', {'state_generation': 3}, admin=True)
    try:
        open_planner(page, base_url, api)
        page.get_by_test_id('sidebar-tab-heroes').click()
        grid = page.get_by_test_id('palette-grid')
        expect(grid.locator('[data-palette-hero="jeronimo"]')).to_be_visible()     # gen 1
        expect(grid.locator('[data-palette-hero="greg"]')).to_be_visible()         # gen 3
        expect(grid.locator('[data-palette-hero="sergey"]')).to_be_visible()       # epic, no generation
        expect(grid.locator('[data-palette-hero="ahmose"]')).to_have_count(0)      # gen 4
        expect(grid.locator('[data-palette-hero="aiden"]')).to_have_count(0)       # gen 17
        gens = [int(g) for g in grid.locator('[data-generation]').evaluate_all(
            'els => els.map(e => e.dataset.generation).filter(Boolean)')]
        assert gens and max(gens) <= 3
        # rare/epic (no generation) are listed after the generation heroes
        order = grid.locator('[data-palette-hero]').evaluate_all('els => els.map(e => e.dataset.generation)')
        first_blank = order.index('')
        assert all(g == '' for g in order[first_blank:])
        # a hero saved earlier above the new limit stays, flagged
        _, plan = api.call('GET', '/api/admin/svs/rounds/current/plan', admin=True)
        assert plan['state_generation'] == 3
        # the server refuses a NEW hero above the limit
        p = plan['plan']
        p['leaders'][0]['other_joiner_heroes']['rally'].append('ahmose')
        status, err = api.call('PUT', '/api/admin/svs/rounds/current/plan', {'revision': plan['revision'], 'plan': p},
                               admin=True, ok=None)
        assert status == 400 and err['details']['hero'] == 'ahmose'
    finally:
        api.call('PUT', '/api/admin/settings', {'state_generation': 17}, admin=True)


def test_conflict_banner(browser: Browser, base_url, api):
    pages = []
    for _ in range(2):
        ctx = browser.new_context(base_url=base_url, viewport={'width': 1400, 'height': 900}, locale='en-US',
                                  timezone_id='UTC')
        pg = ctx.new_page()
        open_planner(pg, base_url, api)
        pages.append(pg)
    a, b = pages
    # B saves a change (a newer revision) ...
    b.get_by_test_id('group-counter').get_by_test_id('group-name').fill('Counter B')
    wait_saved(b)
    # ... A, still on the old revision, edits: 409 -> clear banner, nothing overwritten
    a.get_by_test_id('group-main').get_by_test_id('group-name').fill('Main from A')
    banner = a.get_by_test_id('conflict-banner')
    expect(banner).to_be_visible()
    expect(banner).to_contain_text(tr('svs:plan.conflictTitle'))
    assert get_plan(api)['plan']['groups'][0]['name'] != 'Main from A'
    assert get_plan(api)['plan']['groups'][1]['name'] == 'Counter B'
    a.get_by_test_id('conflict-reload').click()
    expect(banner).to_have_count(0)
    expect(a.get_by_test_id('group-counter').get_by_test_id('group-name')).to_have_value('Counter B')
    for pg in pages:
        pg.context.close()


def test_share_link_and_phone_view(page: Page, base_url, api, browser: Browser, playwright: Playwright, shot):
    page.on('dialog', lambda d: d.accept())
    open_planner(page, base_url, api)
    page.get_by_test_id('share-button').click()
    panel = page.get_by_test_id('share-panel')
    expect(panel).to_have_attribute('data-enabled', 'false')
    panel.get_by_test_id('share-create').click()
    expect(panel).to_have_attribute('data-enabled', 'true')
    url1 = panel.get_by_test_id('share-url').input_value()
    assert re.fullmatch(re.escape(base_url) + r'/svs/plan/[A-Za-z0-9_-]{22}', url1), url1
    path1 = url1[len(base_url):]

    # the shared plan on an iPhone: English, then Arabic (RTL), with Find me
    dev = dict(playwright.devices['iPhone 13'])
    dev.pop('default_browser_type', None)
    for lang, locale in (('en', 'en-US'), ('ar', 'ar-SA')):
        ctx = browser.new_context(**dev, base_url=base_url, locale=locale, timezone_id='Europe/London')
        ph = ctx.new_page()
        resp = ph.goto(base_url + path1)
        assert resp.headers.get('referrer-policy') == 'no-referrer' and 'noindex' in resp.headers.get('x-robots-tag', '')
        expect(ph.get_by_test_id('svs-plan-view')).to_be_visible()
        assert ph.evaluate('document.documentElement.dir') == ('rtl' if lang == 'ar' else 'ltr')
        assert ph.locator('meta[name=robots]').get_attribute('content').startswith('noindex')
        expect(ph.get_by_test_id('view-alias').first).to_have_text('Rally Caller 01')
        expect(ph.get_by_test_id('view-pet').first).to_contain_text('13:00')
        width = ph.viewport_size['width']
        assert ph.evaluate('document.documentElement.scrollWidth') <= width
        assert not ui.raw_i18n_keys(ui.visible_text(ph))
        ph.screenshot(path=str(ui_artifact(f'view-{lang}.png')), full_page=True)
        # Find me: a named joiner by name, then a leader by FID
        ph.get_by_test_id('find-me-input').fill(nm('Cedar'))
        ph.get_by_test_id('find-me-go').click()
        expect(ph.get_by_test_id('find-me-result')).to_have_text(
            tr('svs:view.youJoin', lang, n=2, leader='Rally Caller 01', group='Main rallies'))
        found = ph.locator('[data-found=true]')
        expect(found).to_have_count(1)
        expect(found).to_contain_text(nm('Cedar'))
        expect(found).to_be_in_viewport()
        ph.get_by_test_id('find-me-input').fill(FIDS['Aster'])
        ph.get_by_test_id('find-me-go').click()
        expect(ph.get_by_test_id('find-me-result')).to_contain_text('Rally Caller 01')
        ph.screenshot(path=str(ui_artifact(f'view-{lang}-findme.png')))
        ctx.close()

    # rotate: the old link dies at once, the new one works
    panel.get_by_test_id('share-rotate').click()
    expect(panel.get_by_test_id('share-url')).not_to_have_value(url1)
    path2 = panel.get_by_test_id('share-url').input_value()[len(base_url):]
    other = page.context.new_page()
    other.goto(base_url + path1)
    expect(other.get_by_test_id('plan-not-found')).to_be_visible()
    other.goto(base_url + path2)
    expect(other.get_by_test_id('svs-plan-view')).to_be_visible()
    # turn off sharing
    panel.get_by_test_id('share-disable').click()
    expect(panel).to_have_attribute('data-enabled', 'false')
    other.goto(base_url + path2)
    expect(other.get_by_test_id('plan-not-found')).to_be_visible()
    other.close()


def ui_artifact(name: str):
    from conftest import ARTIFACTS, RUN_ID
    out = ARTIFACTS / RUN_ID / 'planner'
    out.mkdir(parents=True, exist_ok=True)
    return out / name
