"""Build the hero library from the scraped hero-test data (one-off; re-run when heroes are added).

    python3 scripts/heroes/build_heroes.py ~/ai/fun/wos/hero-test

Reads <src>/heroes.json + <src>/img/*, writes:
  backend/gamedata/heroes.json            versioned library: slug, name, troop, generation, rarity, image
  frontend/public/heroes/<slug>.webp  256x256 WebP (stable names; served as /heroes/<slug>.webp)

Needs Pillow (any venv). Hero art (c) Century Games; see README "Credits".
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
OUT_JSON = REPO / 'backend' / 'gamedata' / 'heroes.json'
OUT_IMG = REPO / 'frontend' / 'public' / 'heroes'
SIZE = 256
VERSION = 1
TROOPS = {'Infantry': 'infantry', 'Lancer': 'lancer', 'Marksman': 'marksman'}
RARITIES = {'Rare': 'rare', 'Epic': 'epic', 'Mythic': 'mythic'}


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def main(src):
    src = Path(src).expanduser()
    raw = json.loads((src / 'heroes.json').read_text(encoding='utf-8'))
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    heroes, seen = [], set()
    for h in raw:
        slug = slugify(h['name'])
        assert slug not in seen, slug
        seen.add(slug)
        img = Image.open(src / h['img']).convert('RGBA')
        img.thumbnail((SIZE, SIZE), Image.LANCZOS)
        img.save(OUT_IMG / f'{slug}.webp', 'WEBP', quality=82, method=6)
        gen = h.get('generation')
        heroes.append({
            'slug': slug,
            'name': h['name'],
            'troop': TROOPS[h['troop']],
            'generation': int(gen) if gen is not None else None,
            'rarity': RARITIES[h['rarity']],
            'image': f'/heroes/{slug}.webp',
        })
    heroes.sort(key=lambda x: (x['generation'] is not None, x['generation'] or 0,
                               ['rare', 'epic', 'mythic'].index(x['rarity']),
                               list(TROOPS.values()).index(x['troop']), x['name']))
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        'version': VERSION,
        'source': 'whiteoutsurvival.wiki (scraped 2026-10-08, hero-test/build.py)',
        'attribution': 'Hero names and artwork (c) Century Games. Whiteout Survival is a trademark of Century Games.',
        'max_generation': max(x['generation'] or 0 for x in heroes),
        'heroes': heroes,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(heroes)} heroes -> {OUT_JSON.relative_to(REPO)}, images -> {OUT_IMG.relative_to(REPO)}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '~/ai/fun/wos/hero-test')
