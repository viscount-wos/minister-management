"""v2.2.1 "Add to rally" keys (svs:players.*) and the What's new block v221 for all 9 languages. Re-runnable: it
overwrites these keys only.

    python3 scripts/i18n/v221_add_to_rally.py
"""
import json
from pathlib import Path

LOC = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'
LANGS = ('en', 'es', 'fr', 'de', 'pl', 'ko', 'zh', 'tr', 'ar')

KEYS = [
    'col.plan',
    'place.leader', 'place.joiner', 'place.extra', 'place.group',
    'filter.plan', 'filter.inPlan', 'filter.notInPlan',
    'add.button', 'add.title', 'add.bulkTitle', 'add.now', 'add.loading', 'add.noLeaders', 'add.openPlan',
    'add.chooseLeader', 'add.capacity', 'add.full', 'add.hereNow', 'add.asNamed', 'add.asExtra', 'add.moveNamed',
    'add.moveExtra', 'add.namedHint', 'add.bulkAuto', 'add.bulkExtra', 'add.makeLeader', 'add.moveMakeLeader',
    'add.toGroup', 'add.moveToGroup', 'add.other', 'add.back', 'add.close', 'add.saving',
    'done.one', 'done.moved', 'done.unchanged', 'done.bulk', 'done.bulkGroup', 'done.none', 'done.skipped',
    'done.overflow',
    'err.conflict', 'err.full', 'err.gone',
    'select.row', 'select.all', 'bulk.selected', 'bulk.add', 'bulk.clear',
]

TR = {
    'en': [
        'Plan',
        'Leader · {{leader}} ({{group}})', 'Joiner {{n}} · {{leader}} ({{group}})', 'Extra · {{leader}} ({{group}})',
        '{{group}}',
        'Battle plan', 'In plan', 'Not in plan',
        'Add {{name}} to a rally', 'Add to rally', 'Add {{n}} selected to a rally', 'Now: {{where}}',
        'Loading the plan…', 'The battle plan has no rally leaders yet.', 'Open the Battle plan',
        'Choose a rally leader', 'Named {{named}}/{{maxNamed}} · Extra {{extra}}/{{maxExtra}}', 'Full', 'here now',
        'As named joiner ({{n}}/{{max}})', 'As extra joiner ({{n}}/{{max}})',
        'Move here as named joiner ({{n}}/{{max}})', 'Move here as extra joiner ({{n}}/{{max}})',
        'The lead hero stays empty: choose it in the Battle plan.',
        'Add them: named places first, then extra ({{free}} places left)', 'All as extra joiners ({{n}}/{{max}})',
        'Make rally leader in {{group}}', 'Move: make rally leader in {{group}}', 'Add to {{group}}',
        'Move to {{group}}', 'Other places', 'Back', 'Close', 'Saving…',
        '{{name}} added: {{where}}.', '{{name}} moved: {{where}}.', '{{name}} is already there: {{where}}.',
        'Added {{n}} to {{to}} ({{named}} named, {{extra}} extra).', 'Added {{n}} to {{to}}.', 'Nobody was added.',
        'Skipped, already in the plan: {{list}}.', 'No room left for: {{list}}.',
        'The plan changed while you were choosing. Check the new numbers and try again.',
        'No room left there.', 'That leader or group is no longer in the plan.',
        'Select {{name}}', 'Select everyone on this page', '{{n}} selected', 'Add {{n}} selected to rally…',
        'Clear selection',
    ],
    'es': [
        'Plan',
        'Líder · {{leader}} ({{group}})', 'Unido {{n}} · {{leader}} ({{group}})', 'Extra · {{leader}} ({{group}})',
        '{{group}}',
        'Plan de batalla', 'En el plan', 'Fuera del plan',
        'Añadir a {{name}} a un rally', 'Añadir a un rally', 'Añadir {{n}} seleccionados a un rally', 'Ahora: {{where}}',
        'Cargando el plan…', 'El plan de batalla aún no tiene líderes de rally.', 'Abrir el plan de batalla',
        'Elige un líder de rally', 'Con nombre {{named}}/{{maxNamed}} · Extra {{extra}}/{{maxExtra}}', 'Lleno', 'aquí ahora',
        'Como unido con nombre ({{n}}/{{max}})', 'Como unido extra ({{n}}/{{max}})',
        'Mover aquí como unido con nombre ({{n}}/{{max}})', 'Mover aquí como unido extra ({{n}}/{{max}})',
        'El héroe principal queda vacío: elígelo en el plan de batalla.',
        'Añadirlos: primero los puestos con nombre, luego extra (quedan {{free}})', 'Todos como unidos extra ({{n}}/{{max}})',
        'Hacer líder de rally en {{group}}', 'Mover: hacer líder de rally en {{group}}', 'Añadir a {{group}}',
        'Mover a {{group}}', 'Otros puestos', 'Atrás', 'Cerrar', 'Guardando…',
        '{{name}} añadido: {{where}}.', '{{name}} movido: {{where}}.', '{{name}} ya está ahí: {{where}}.',
        'Añadidos {{n}} a {{to}} ({{named}} con nombre, {{extra}} extra).', 'Añadidos {{n}} a {{to}}.', 'No se añadió a nadie.',
        'Omitidos, ya están en el plan: {{list}}.', 'No queda sitio para: {{list}}.',
        'El plan cambió mientras elegías. Revisa los nuevos números e inténtalo de nuevo.',
        'No queda sitio ahí.', 'Ese líder o grupo ya no está en el plan.',
        'Seleccionar a {{name}}', 'Seleccionar a todos en esta página', '{{n}} seleccionados',
        'Añadir {{n}} seleccionados al rally…', 'Quitar selección',
    ],
    'fr': [
        'Plan',
        'Chef · {{leader}} ({{group}})', 'Renfort {{n}} · {{leader}} ({{group}})', 'Extra · {{leader}} ({{group}})',
        '{{group}}',
        'Plan de bataille', 'Dans le plan', 'Hors du plan',
        'Ajouter {{name}} à un rallye', 'Ajouter à un rallye', 'Ajouter les {{n}} sélectionnés à un rallye',
        'Actuellement : {{where}}',
        'Chargement du plan…', "Le plan de bataille n'a pas encore de chef de rallye.", 'Ouvrir le plan de bataille',
        'Choisissez un chef de rallye', 'Nommés {{named}}/{{maxNamed}} · Extra {{extra}}/{{maxExtra}}', 'Complet', 'ici',
        'Comme renfort nommé ({{n}}/{{max}})', 'Comme renfort extra ({{n}}/{{max}})',
        'Déplacer ici comme renfort nommé ({{n}}/{{max}})', 'Déplacer ici comme renfort extra ({{n}}/{{max}})',
        'Le héros principal reste vide : choisissez-le dans le plan de bataille.',
        "Les ajouter : places nommées d'abord, puis extra ({{free}} places libres)",
        'Tous comme renforts extra ({{n}}/{{max}})',
        'Nommer chef de rallye dans {{group}}', 'Déplacer : nommer chef de rallye dans {{group}}', 'Ajouter à {{group}}',
        'Déplacer vers {{group}}', 'Autres places', 'Retour', 'Fermer', 'Enregistrement…',
        '{{name}} ajouté : {{where}}.', '{{name}} déplacé : {{where}}.', '{{name}} y est déjà : {{where}}.',
        '{{n}} ajoutés à {{to}} ({{named}} nommés, {{extra}} extra).', '{{n}} ajoutés à {{to}}.', "Personne n'a été ajouté.",
        'Ignorés, déjà dans le plan : {{list}}.', 'Plus de place pour : {{list}}.',
        'Le plan a changé pendant votre choix. Vérifiez les nouveaux chiffres et réessayez.',
        'Plus de place ici.', "Ce chef ou ce groupe n'est plus dans le plan.",
        'Sélectionner {{name}}', 'Tout sélectionner sur cette page', '{{n}} sélectionnés',
        'Ajouter les {{n}} sélectionnés au rallye…', 'Effacer la sélection',
    ],
    'de': [
        'Plan',
        'Anführer · {{leader}} ({{group}})', 'Mitläufer {{n}} · {{leader}} ({{group}})', 'Extra · {{leader}} ({{group}})',
        '{{group}}',
        'Schlachtplan', 'Im Plan', 'Nicht im Plan',
        '{{name}} zu einer Rallye hinzufügen', 'Zur Rallye hinzufügen', '{{n}} Ausgewählte zu einer Rallye hinzufügen',
        'Jetzt: {{where}}',
        'Plan wird geladen…', 'Der Schlachtplan hat noch keine Rallye-Anführer.', 'Schlachtplan öffnen',
        'Rallye-Anführer wählen', 'Benannt {{named}}/{{maxNamed}} · Extra {{extra}}/{{maxExtra}}', 'Voll', 'jetzt hier',
        'Als benannter Mitläufer ({{n}}/{{max}})', 'Als Extra-Mitläufer ({{n}}/{{max}})',
        'Hierher verschieben als benannter Mitläufer ({{n}}/{{max}})',
        'Hierher verschieben als Extra-Mitläufer ({{n}}/{{max}})',
        'Der Hauptheld bleibt leer: im Schlachtplan auswählen.',
        'Hinzufügen: erst benannte Plätze, dann Extra ({{free}} Plätze frei)', 'Alle als Extra-Mitläufer ({{n}}/{{max}})',
        'Zum Rallye-Anführer in {{group}} machen', 'Verschieben: Rallye-Anführer in {{group}}', 'Zu {{group}} hinzufügen',
        'Nach {{group}} verschieben', 'Andere Plätze', 'Zurück', 'Schließen', 'Speichern…',
        '{{name}} hinzugefügt: {{where}}.', '{{name}} verschoben: {{where}}.', '{{name}} ist schon dort: {{where}}.',
        '{{n}} zu {{to}} hinzugefügt ({{named}} benannt, {{extra}} Extra).', '{{n}} zu {{to}} hinzugefügt.',
        'Niemand wurde hinzugefügt.',
        'Übersprungen, schon im Plan: {{list}}.', 'Kein Platz mehr für: {{list}}.',
        'Der Plan hat sich während deiner Auswahl geändert. Prüfe die neuen Zahlen und versuche es erneut.',
        'Dort ist kein Platz mehr.', 'Dieser Anführer oder diese Gruppe ist nicht mehr im Plan.',
        '{{name}} auswählen', 'Alle auf dieser Seite auswählen', '{{n}} ausgewählt', '{{n}} Ausgewählte zur Rallye…',
        'Auswahl aufheben',
    ],
    'pl': [
        'Plan',
        'Lider · {{leader}} ({{group}})', 'Dołączający {{n}} · {{leader}} ({{group}})', 'Dodatkowy · {{leader}} ({{group}})',
        '{{group}}',
        'Plan bitwy', 'W planie', 'Poza planem',
        'Dodaj {{name}} do rajdu', 'Dodaj do rajdu', 'Dodaj {{n}} zaznaczonych do rajdu', 'Teraz: {{where}}',
        'Wczytywanie planu…', 'Plan bitwy nie ma jeszcze liderów rajdów.', 'Otwórz plan bitwy',
        'Wybierz lidera rajdu', 'Imienni {{named}}/{{maxNamed}} · Dodatkowi {{extra}}/{{maxExtra}}', 'Pełny', 'tu teraz',
        'Jako imienny dołączający ({{n}}/{{max}})', 'Jako dodatkowy dołączający ({{n}}/{{max}})',
        'Przenieś tutaj jako imiennego ({{n}}/{{max}})', 'Przenieś tutaj jako dodatkowego ({{n}}/{{max}})',
        'Główny bohater zostaje pusty: wybierz go w planie bitwy.',
        'Dodaj: najpierw miejsca imienne, potem dodatkowe (wolnych: {{free}})', 'Wszyscy jako dodatkowi ({{n}}/{{max}})',
        'Zrób liderem rajdu w {{group}}', 'Przenieś: lider rajdu w {{group}}', 'Dodaj do {{group}}',
        'Przenieś do {{group}}', 'Inne miejsca', 'Wstecz', 'Zamknij', 'Zapisywanie…',
        'Dodano {{name}}: {{where}}.', 'Przeniesiono {{name}}: {{where}}.', '{{name}} już tam jest: {{where}}.',
        'Dodano {{n}} do {{to}} ({{named}} imiennych, {{extra}} dodatkowych).', 'Dodano {{n}} do {{to}}.',
        'Nikogo nie dodano.',
        'Pominięci, już w planie: {{list}}.', 'Brak miejsca dla: {{list}}.',
        'Plan zmienił się w trakcie wyboru. Sprawdź nowe liczby i spróbuj ponownie.',
        'Brak tam miejsca.', 'Tego lidera lub grupy nie ma już w planie.',
        'Zaznacz {{name}}', 'Zaznacz wszystkich na tej stronie', 'Zaznaczono: {{n}}', 'Dodaj zaznaczonych ({{n}}) do rajdu…',
        'Wyczyść zaznaczenie',
    ],
    'ko': [
        '계획',
        '리더 · {{leader}} ({{group}})', '참여자 {{n}} · {{leader}} ({{group}})', '추가 · {{leader}} ({{group}})',
        '{{group}}',
        '전투 계획', '계획에 있음', '계획에 없음',
        '{{name}}님을 집결에 추가', '집결에 추가', '선택한 {{n}}명을 집결에 추가', '현재: {{where}}',
        '계획을 불러오는 중…', '전투 계획에 아직 집결 리더가 없습니다.', '전투 계획 열기',
        '집결 리더 선택', '지정 {{named}}/{{maxNamed}} · 추가 {{extra}}/{{maxExtra}}', '가득 참', '현재 여기',
        '지정 참여자로 ({{n}}/{{max}})', '추가 참여자로 ({{n}}/{{max}})',
        '지정 참여자로 여기로 이동 ({{n}}/{{max}})', '추가 참여자로 여기로 이동 ({{n}}/{{max}})',
        '대표 영웅은 비워 둡니다. 전투 계획에서 선택하세요.',
        '추가: 지정 자리 먼저, 그다음 추가 자리 (남은 자리 {{free}})', '모두 추가 참여자로 ({{n}}/{{max}})',
        '{{group}}의 집결 리더로 지정', '이동: {{group}}의 집결 리더로 지정', '{{group}}에 추가',
        '{{group}}(으)로 이동', '다른 자리', '뒤로', '닫기', '저장 중…',
        '{{name}} 추가됨: {{where}}.', '{{name}} 이동됨: {{where}}.', '{{name}}님은 이미 그곳에 있습니다: {{where}}.',
        '{{to}}에 {{n}}명 추가 (지정 {{named}}, 추가 {{extra}}).', '{{to}}에 {{n}}명 추가.', '추가된 사람이 없습니다.',
        '건너뜀, 이미 계획에 있음: {{list}}.', '자리가 없음: {{list}}.',
        '선택하는 동안 계획이 바뀌었습니다. 새 숫자를 확인하고 다시 시도하세요.',
        '그곳에는 자리가 없습니다.', '그 리더나 그룹은 더 이상 계획에 없습니다.',
        '{{name}} 선택', '이 페이지 모두 선택', '{{n}}명 선택됨', '선택한 {{n}}명을 집결에 추가…', '선택 해제',
    ],
    'zh': [
        '计划',
        '队长 · {{leader}}（{{group}}）', '加入者 {{n}} · {{leader}}（{{group}}）', '额外 · {{leader}}（{{group}}）',
        '{{group}}',
        '作战计划', '已在计划中', '不在计划中',
        '将 {{name}} 加入集结', '加入集结', '将选中的 {{n}} 人加入集结', '当前：{{where}}',
        '正在加载计划…', '作战计划中还没有集结队长。', '打开作战计划',
        '选择集结队长', '指定 {{named}}/{{maxNamed}} · 额外 {{extra}}/{{maxExtra}}', '已满', '当前在此',
        '作为指定加入者（{{n}}/{{max}}）', '作为额外加入者（{{n}}/{{max}}）',
        '移到这里作为指定加入者（{{n}}/{{max}}）', '移到这里作为额外加入者（{{n}}/{{max}}）',
        '主英雄留空：请在作战计划中选择。',
        '加入：先填指定位置，再填额外位置（剩余 {{free}} 个）', '全部作为额外加入者（{{n}}/{{max}}）',
        '设为 {{group}} 的集结队长', '移动：设为 {{group}} 的集结队长', '加入 {{group}}',
        '移到 {{group}}', '其他位置', '返回', '关闭', '正在保存…',
        '已添加 {{name}}：{{where}}。', '已移动 {{name}}：{{where}}。', '{{name}} 已经在那里：{{where}}。',
        '已将 {{n}} 人加入 {{to}}（指定 {{named}}，额外 {{extra}}）。', '已将 {{n}} 人加入 {{to}}。', '没有添加任何人。',
        '已跳过（已在计划中）：{{list}}。', '没有位置：{{list}}。',
        '你选择时计划已更改。请查看新的数字后重试。',
        '那里没有位置了。', '该队长或分组已不在计划中。',
        '选择 {{name}}', '选择本页全部', '已选 {{n}} 人', '将选中的 {{n}} 人加入集结…', '清除选择',
    ],
    'tr': [
        'Plan',
        'Lider · {{leader}} ({{group}})', 'Katılımcı {{n}} · {{leader}} ({{group}})', 'Ek · {{leader}} ({{group}})',
        '{{group}}',
        'Savaş planı', 'Planda', 'Planda değil',
        '{{name}} oyuncusunu bir ralliye ekle', 'Ralliye ekle', 'Seçili {{n}} oyuncuyu bir ralliye ekle', 'Şu an: {{where}}',
        'Plan yükleniyor…', 'Savaş planında henüz ralli lideri yok.', 'Savaş planını aç',
        'Bir ralli lideri seç', 'İsimli {{named}}/{{maxNamed}} · Ek {{extra}}/{{maxExtra}}', 'Dolu', 'şu an burada',
        'İsimli katılımcı olarak ({{n}}/{{max}})', 'Ek katılımcı olarak ({{n}}/{{max}})',
        'Buraya isimli katılımcı olarak taşı ({{n}}/{{max}})', 'Buraya ek katılımcı olarak taşı ({{n}}/{{max}})',
        'Ana kahraman boş kalır: savaş planında seçin.',
        'Ekle: önce isimli yerler, sonra ek ({{free}} yer kaldı)', 'Hepsi ek katılımcı ({{n}}/{{max}})',
        '{{group}} grubunda ralli lideri yap', 'Taşı: {{group}} grubunda ralli lideri yap', '{{group}} grubuna ekle',
        '{{group}} grubuna taşı', 'Diğer yerler', 'Geri', 'Kapat', 'Kaydediliyor…',
        '{{name}} eklendi: {{where}}.', '{{name}} taşındı: {{where}}.', '{{name}} zaten orada: {{where}}.',
        '{{to}} için {{n}} oyuncu eklendi ({{named}} isimli, {{extra}} ek).', '{{to}} için {{n}} oyuncu eklendi.',
        'Kimse eklenmedi.',
        'Atlandı, zaten planda: {{list}}.', 'Yer kalmadı: {{list}}.',
        'Siz seçerken plan değişti. Yeni sayıları kontrol edip tekrar deneyin.',
        'Orada yer kalmadı.', 'Bu lider veya grup artık planda değil.',
        '{{name}} seç', 'Bu sayfadaki herkesi seç', '{{n}} seçildi', 'Seçili {{n}} oyuncuyu ralliye ekle…',
        'Seçimi temizle',
    ],
    'ar': [
        'الخطة',
        'قائد · {{leader}} ({{group}})', 'منضم {{n}} · {{leader}} ({{group}})', 'إضافي · {{leader}} ({{group}})',
        '{{group}}',
        'خطة المعركة', 'في الخطة', 'ليس في الخطة',
        'إضافة {{name}} إلى حشد', 'إضافة إلى حشد', 'إضافة {{n}} محددين إلى حشد', 'الآن: {{where}}',
        'جارٍ تحميل الخطة…', 'لا يوجد قادة حشود في خطة المعركة بعد.', 'فتح خطة المعركة',
        'اختر قائد حشد', 'بالاسم {{named}}/{{maxNamed}} · إضافي {{extra}}/{{maxExtra}}', 'ممتلئ', 'هنا الآن',
        'كمنضم بالاسم ({{n}}/{{max}})', 'كمنضم إضافي ({{n}}/{{max}})',
        'نقل إلى هنا كمنضم بالاسم ({{n}}/{{max}})', 'نقل إلى هنا كمنضم إضافي ({{n}}/{{max}})',
        'يبقى البطل الرئيسي فارغًا: اختره في خطة المعركة.',
        'إضافتهم: الأماكن بالاسم أولًا ثم الإضافية (المتبقي {{free}})', 'الجميع كمنضمين إضافيين ({{n}}/{{max}})',
        'تعيين قائد حشد في {{group}}', 'نقل: تعيين قائد حشد في {{group}}', 'إضافة إلى {{group}}',
        'نقل إلى {{group}}', 'أماكن أخرى', 'رجوع', 'إغلاق', 'جارٍ الحفظ…',
        'تمت إضافة {{name}}: {{where}}.', 'تم نقل {{name}}: {{where}}.', '{{name}} موجود هناك بالفعل: {{where}}.',
        'تمت إضافة {{n}} إلى {{to}} ({{named}} بالاسم، {{extra}} إضافي).', 'تمت إضافة {{n}} إلى {{to}}.',
        'لم تتم إضافة أحد.',
        'تم التخطي، موجودون في الخطة بالفعل: {{list}}.', 'لا مكان متبقٍ لـ: {{list}}.',
        'تغيرت الخطة أثناء اختيارك. تحقق من الأرقام الجديدة وحاول مرة أخرى.',
        'لا مكان متبقٍ هناك.', 'هذا القائد أو المجموعة لم يعد في الخطة.',
        'تحديد {{name}}', 'تحديد الجميع في هذه الصفحة', 'تم تحديد {{n}}', 'إضافة {{n}} محددين إلى حشد…',
        'مسح التحديد',
    ],
}

CHANGELOG = {
    'en': ('Rallies from the players list', 'October 2026',
           'Leaders can add players to a rally straight from the SVS players list.'),
    'es': ('Rallies desde la lista de jugadores', 'Octubre 2026',
           'Los líderes pueden añadir jugadores a un rally directamente desde la lista de jugadores de SVS.'),
    'fr': ('Rallyes depuis la liste des joueurs', 'Octobre 2026',
           'Les chefs peuvent ajouter des joueurs à un rallye directement depuis la liste des joueurs SVS.'),
    'de': ('Rallyes aus der Spielerliste', 'Oktober 2026',
           'Anführer können Spieler direkt aus der SVS-Spielerliste zu einer Rallye hinzufügen.'),
    'pl': ('Rajdy z listy graczy', 'Październik 2026',
           'Liderzy mogą dodawać graczy do rajdu prosto z listy graczy SVS.'),
    'ko': ('플레이어 목록에서 집결 편성', '2026년 10월',
           '리더가 SVS 플레이어 목록에서 바로 플레이어를 집결에 추가할 수 있습니다.'),
    'zh': ('从玩家列表安排集结', '2026年10月',
           '队长可以直接从 SVS 玩家列表把玩家加入集结。'),
    'tr': ('Oyuncu listesinden ralliler', 'Ekim 2026',
           'Liderler oyuncuları doğrudan SVS oyuncu listesinden bir ralliye ekleyebilir.'),
    'ar': ('الحشود من قائمة اللاعبين', 'أكتوبر 2026',
           'يمكن للقادة إضافة اللاعبين إلى حشد مباشرة من قائمة لاعبي SVS.'),
}


def put(tree, dotted, value):
    parts = dotted.split('.')
    node = tree
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


def main():
    for lang in LANGS:
        vals = TR[lang]
        assert len(vals) == len(KEYS), (lang, len(vals), len(KEYS))
        path = LOC / lang / 'svs.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data.pop('players', None)
        for k, v in zip(KEYS, vals):
            put(data, 'players.' + k, v)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        cpath = LOC / lang / 'changelog.json'
        c = json.loads(cpath.read_text(encoding='utf-8'))
        title, date, line = CHANGELOG[lang]
        out = {}
        for k, v in c.items():
            if k.startswith('v221'):
                continue
            if k == 'v220Title':
                out.update({'v221Title': title, 'v221Date': date, 'v221a': line})
            out[k] = v
        cpath.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('ok', len(KEYS), 'keys')


if __name__ == '__main__':
    main()
