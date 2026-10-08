"""v2.2.1 admin Edit / Remove in the SVS and Frost Dragon Tyrant player lists: admin:playerEdit.*,
svs:players.deletePlan.* and the What's new item changelog:v221edit, for all 9 languages. Re-runnable: it overwrites
these keys only (v221edit goes after the existing v221 items).

    python3 scripts/i18n/v221_admin_edit.py
"""
import json
from pathlib import Path

LOC = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'
LANGS = ('en', 'es', 'fr', 'de', 'pl', 'ko', 'zh', 'tr', 'ar')

ADMIN_KEYS = ['desc', 'shared', 'sharedTyrant', 'troopsHint', 'fidFixed', 'editLabel', 'deleteLabel', 'closed', 'old',
              'oldHour', 'oldWindow', 'deleteTitle', 'deleteBody', 'deleteConfirm', 'saved', 'removed', 'removedPlan']
PLAN_KEYS = ['leader', 'joiner', 'extra', 'group']

ADMIN = {
    'en': [
        "Change this player's sign-up for this round.",
        'Name, alliance and troops are shared with other events: a change here shows everywhere.',
        'Name, alliance, troops, power and Discord ID are shared with other events: a change here shows everywhere.',
        'A blank level keeps what is already stored.',
        "The player ID can't be changed.",
        'Edit {{name}}', 'Remove {{name}}',
        "This round is closed: players can't be edited or removed.",
        'old',
        'No longer in this battle; kept from their sign-up.',
        'No longer in this round; kept from their sign-up.',
        'Remove {{name}}?',
        'This removes their sign-up from this round. Their profile (name, alliance, troops) is kept for other events.',
        'Remove',
        'Saved {{name}}.', 'Removed {{name}} from this round.',
        'Removed {{name}} from this round and from the battle plan.',
    ],
    'es': [
        'Cambia la inscripción de este jugador en esta ronda.',
        'El nombre, la alianza y las tropas se comparten con otros eventos: un cambio aquí se ve en todas partes.',
        'El nombre, la alianza, las tropas, el poder y el ID de Discord se comparten con otros eventos: un cambio aquí '
        'se ve en todas partes.',
        'Un nivel en blanco conserva lo que ya está guardado.',
        'El ID de jugador no se puede cambiar.',
        'Editar a {{name}}', 'Quitar a {{name}}',
        'Esta ronda está cerrada: no se pueden editar ni quitar jugadores.',
        'antigua',
        'Ya no está en esta batalla; se conserva de su inscripción.',
        'Ya no está en esta ronda; se conserva de su inscripción.',
        '¿Quitar a {{name}}?',
        'Esto elimina su inscripción de esta ronda. Su perfil (nombre, alianza, tropas) se conserva para otros eventos.',
        'Quitar',
        '{{name}} guardado.', '{{name}} se quitó de esta ronda.',
        '{{name}} se quitó de esta ronda y del plan de batalla.',
    ],
    'fr': [
        "Modifiez l'inscription de ce joueur pour cette manche.",
        "Le nom, l'alliance et les troupes sont partagés avec les autres événements : une modification ici s'applique "
        'partout.',
        "Le nom, l'alliance, les troupes, la puissance et l'ID Discord sont partagés avec les autres événements : une "
        "modification ici s'applique partout.",
        'Un niveau laissé vide conserve la valeur déjà enregistrée.',
        "L'ID du joueur ne peut pas être modifié.",
        'Modifier {{name}}', 'Retirer {{name}}',
        'Cette manche est fermée : les joueurs ne peuvent être ni modifiés ni retirés.',
        'ancienne',
        "Ne fait plus partie de cette bataille ; conservée depuis son inscription.",
        "Ne fait plus partie de cette manche ; conservée depuis son inscription.",
        'Retirer {{name}} ?',
        "Cela supprime son inscription de cette manche. Son profil (nom, alliance, troupes) est conservé pour les autres "
        'événements.',
        'Retirer',
        '{{name}} enregistré.', '{{name}} a été retiré de cette manche.',
        '{{name}} a été retiré de cette manche et du plan de bataille.',
    ],
    'de': [
        'Ändere die Anmeldung dieses Spielers für diese Runde.',
        'Name, Allianz und Truppen werden mit anderen Events geteilt: Eine Änderung hier gilt überall.',
        'Name, Allianz, Truppen, Macht und Discord-ID werden mit anderen Events geteilt: Eine Änderung hier gilt '
        'überall.',
        'Ein leeres Level behält den gespeicherten Wert.',
        'Die Spieler-ID kann nicht geändert werden.',
        '{{name}} bearbeiten', '{{name}} entfernen',
        'Diese Runde ist geschlossen: Spieler können nicht bearbeitet oder entfernt werden.',
        'alt',
        'Nicht mehr Teil dieser Schlacht; aus der Anmeldung übernommen.',
        'Nicht mehr Teil dieser Runde; aus der Anmeldung übernommen.',
        '{{name}} entfernen?',
        'Damit wird die Anmeldung aus dieser Runde entfernt. Das Profil (Name, Allianz, Truppen) bleibt für andere '
        'Events erhalten.',
        'Entfernen',
        '{{name}} gespeichert.', '{{name}} wurde aus dieser Runde entfernt.',
        '{{name}} wurde aus dieser Runde und aus dem Schlachtplan entfernt.',
    ],
    'pl': [
        'Zmień zgłoszenie tego gracza w tej rundzie.',
        'Nazwa, sojusz i wojska są wspólne z innymi wydarzeniami: zmiana tutaj będzie widoczna wszędzie.',
        'Nazwa, sojusz, wojska, moc i ID Discord są wspólne z innymi wydarzeniami: zmiana tutaj będzie widoczna '
        'wszędzie.',
        'Puste pole poziomu zachowuje zapisaną wartość.',
        'Nie można zmienić ID gracza.',
        'Edytuj: {{name}}', 'Usuń: {{name}}',
        'Ta runda jest zamknięta: graczy nie można edytować ani usuwać.',
        'stara',
        'Już nie w tej bitwie; zachowana z jego zgłoszenia.',
        'Już nie w tej rundzie; zachowana z jego zgłoszenia.',
        'Usunąć gracza {{name}}?',
        'To usuwa jego zgłoszenie z tej rundy. Profil (nazwa, sojusz, wojska) zostaje zachowany dla innych wydarzeń.',
        'Usuń',
        'Zapisano: {{name}}.', 'Usunięto gracza {{name}} z tej rundy.',
        'Usunięto gracza {{name}} z tej rundy i z planu bitwy.',
    ],
    'ko': [
        '이번 라운드에서 이 플레이어의 신청 내용을 변경합니다.',
        '이름, 연맹, 병력은 다른 이벤트와 공유됩니다. 여기서 바꾸면 모든 곳에 반영됩니다.',
        '이름, 연맹, 병력, 전투력, 디스코드 ID는 다른 이벤트와 공유됩니다. 여기서 바꾸면 모든 곳에 반영됩니다.',
        '레벨을 비워 두면 이미 저장된 값이 유지됩니다.',
        '플레이어 ID는 변경할 수 없습니다.',
        '{{name}} 편집', '{{name}} 제거',
        '종료된 라운드입니다. 플레이어를 편집하거나 제거할 수 없습니다.',
        '이전',
        '더 이상 이번 전투에 없는 시간입니다. 신청 내용에서 유지됩니다.',
        '더 이상 이번 라운드에 없는 시간대입니다. 신청 내용에서 유지됩니다.',
        '{{name}}을(를) 제거할까요?',
        '이번 라운드에서 이 플레이어의 신청이 삭제됩니다. 프로필(이름, 연맹, 병력)은 다른 이벤트를 위해 유지됩니다.',
        '제거',
        '{{name}} 저장됨.', '{{name}}을(를) 이번 라운드에서 제거했습니다.',
        '{{name}}을(를) 이번 라운드와 전투 계획에서 제거했습니다.',
    ],
    'zh': [
        '修改该玩家在本轮的报名。',
        '名字、联盟和部队与其他活动共享：在这里修改，所有地方都会同步。',
        '名字、联盟、部队、战力和 Discord ID 与其他活动共享：在这里修改，所有地方都会同步。',
        '等级留空会保留已保存的数值。',
        '玩家 ID 无法修改。',
        '编辑 {{name}}', '移除 {{name}}',
        '本轮已关闭：无法编辑或移除玩家。',
        '旧',
        '已不在本场战斗中；保留自其报名。',
        '已不在本轮中；保留自其报名。',
        '移除 {{name}}？',
        '这会删除其在本轮的报名。其资料（名字、联盟、部队）会保留给其他活动。',
        '移除',
        '已保存 {{name}}。', '已将 {{name}} 移出本轮。',
        '已将 {{name}} 移出本轮和作战计划。',
    ],
    'tr': [
        'Bu oyuncunun bu turdaki kaydını değiştirin.',
        'Ad, ittifak ve birlikler diğer etkinliklerle paylaşılır: burada yapılan değişiklik her yerde görünür.',
        'Ad, ittifak, birlikler, güç ve Discord ID diğer etkinliklerle paylaşılır: burada yapılan değişiklik her yerde '
        'görünür.',
        'Boş bırakılan seviye kayıtlı değeri korur.',
        'Oyuncu ID değiştirilemez.',
        '{{name}} düzenle', '{{name}} kaldır',
        'Bu tur kapalı: oyuncular düzenlenemez veya kaldırılamaz.',
        'eski',
        'Artık bu savaşta yok; kaydından korunuyor.',
        'Artık bu turda yok; kaydından korunuyor.',
        '{{name}} kaldırılsın mı?',
        'Bu, oyuncunun bu turdaki kaydını siler. Profili (ad, ittifak, birlikler) diğer etkinlikler için korunur.',
        'Kaldır',
        '{{name}} kaydedildi.', '{{name}} bu turdan kaldırıldı.',
        '{{name}} bu turdan ve savaş planından kaldırıldı.',
    ],
    'ar': [
        'غيّر تسجيل هذا اللاعب في هذه الجولة.',
        'الاسم والتحالف والقوات مشتركة مع الفعاليات الأخرى: أي تغيير هنا يظهر في كل مكان.',
        'الاسم والتحالف والقوات والقوة ومعرّف ديسكورد مشتركة مع الفعاليات الأخرى: أي تغيير هنا يظهر في كل مكان.',
        'المستوى الفارغ يحتفظ بالقيمة المحفوظة.',
        'لا يمكن تغيير معرّف اللاعب.',
        'تحرير {{name}}', 'إزالة {{name}}',
        'هذه الجولة مغلقة: لا يمكن تحرير اللاعبين أو إزالتهم.',
        'قديم',
        'لم تعد ضمن هذه المعركة؛ محفوظة من تسجيله.',
        'لم تعد ضمن هذه الجولة؛ محفوظة من تسجيله.',
        'إزالة {{name}}؟',
        'سيؤدي هذا إلى حذف تسجيله من هذه الجولة. يبقى ملفه الشخصي (الاسم، التحالف، القوات) محفوظًا للفعاليات الأخرى.',
        'إزالة',
        'تم حفظ {{name}}.', 'تمت إزالة {{name}} من هذه الجولة.',
        'تمت إزالة {{name}} من هذه الجولة ومن خطة المعركة.',
    ],
}

PLAN = {
    'en': [
        'They lead the rally {{leader}} ({{group}}); they will be removed from the battle plan too. The rally card '
        'stays, without a leader.',
        'They are Joiner {{n}} with {{leader}} ({{group}}); they will be removed from the battle plan too.',
        'They are an extra joiner with {{leader}} ({{group}}); they will be removed from the battle plan too.',
        'They are in {{group}}; they will be removed from the battle plan too.',
    ],
    'es': [
        'Lidera el rally {{leader}} ({{group}}); también se quitará del plan de batalla. La tarjeta del rally se '
        'queda, sin líder.',
        'Es el unido {{n}} con {{leader}} ({{group}}); también se quitará del plan de batalla.',
        'Es un unido extra con {{leader}} ({{group}}); también se quitará del plan de batalla.',
        'Está en {{group}}; también se quitará del plan de batalla.',
    ],
    'fr': [
        "Il mène le rallye {{leader}} ({{group}}) ; il sera aussi retiré du plan de bataille. La carte du rallye reste, "
        'sans chef.',
        'Il est le renfort {{n}} avec {{leader}} ({{group}}) ; il sera aussi retiré du plan de bataille.',
        'Il est renfort extra avec {{leader}} ({{group}}) ; il sera aussi retiré du plan de bataille.',
        'Il est dans {{group}} ; il sera aussi retiré du plan de bataille.',
    ],
    'de': [
        'Er führt die Rallye {{leader}} ({{group}}); er wird auch aus dem Schlachtplan entfernt. Die Rallye-Karte '
        'bleibt ohne Anführer bestehen.',
        'Er ist Mitläufer {{n}} bei {{leader}} ({{group}}); er wird auch aus dem Schlachtplan entfernt.',
        'Er ist zusätzlicher Mitläufer bei {{leader}} ({{group}}); er wird auch aus dem Schlachtplan entfernt.',
        'Er ist in {{group}}; er wird auch aus dem Schlachtplan entfernt.',
    ],
    'pl': [
        'Prowadzi rajd {{leader}} ({{group}}); zostanie też usunięty z planu bitwy. Karta rajdu zostaje, bez lidera.',
        'Jest dołączającym {{n}} u {{leader}} ({{group}}); zostanie też usunięty z planu bitwy.',
        'Jest dodatkowym dołączającym u {{leader}} ({{group}}); zostanie też usunięty z planu bitwy.',
        'Jest w {{group}}; zostanie też usunięty z planu bitwy.',
    ],
    'ko': [
        '{{leader}} ({{group}}) 집결을 이끌고 있습니다. 전투 계획에서도 제거됩니다. 집결 카드는 리더 없이 남습니다.',
        '{{leader}} ({{group}})의 참여자 {{n}}입니다. 전투 계획에서도 제거됩니다.',
        '{{leader}} ({{group}})의 추가 참여자입니다. 전투 계획에서도 제거됩니다.',
        '{{group}}에 있습니다. 전투 계획에서도 제거됩니다.',
    ],
    'zh': [
        '其担任集结 {{leader}}（{{group}}）的队长；也会从作战计划中移除。集结卡片会保留，但没有队长。',
        '其是 {{leader}}（{{group}}）的加入者 {{n}}；也会从作战计划中移除。',
        '其是 {{leader}}（{{group}}）的额外加入者；也会从作战计划中移除。',
        '其在 {{group}} 中；也会从作战计划中移除。',
    ],
    'tr': [
        '{{leader}} ({{group}}) rallisini yönetiyor; savaş planından da kaldırılacak. Ralli kartı lidersiz olarak kalır.',
        '{{leader}} ({{group}}) ile Katılımcı {{n}}; savaş planından da kaldırılacak.',
        '{{leader}} ({{group}}) ile ek katılımcı; savaş planından da kaldırılacak.',
        '{{group}} içinde; savaş planından da kaldırılacak.',
    ],
    'ar': [
        'يقود الحشد {{leader}} ({{group}})؛ ستتم إزالته من خطة المعركة أيضًا. تبقى بطاقة الحشد بدون قائد.',
        'هو المنضم {{n}} مع {{leader}} ({{group}})؛ ستتم إزالته من خطة المعركة أيضًا.',
        'هو منضم إضافي مع {{leader}} ({{group}})؛ ستتم إزالته من خطة المعركة أيضًا.',
        'هو ضمن {{group}}؛ ستتم إزالته من خطة المعركة أيضًا.',
    ],
}

CHANGELOG = {
    'en': 'Leaders can edit and remove players in the Frost Dragon Tyrant and SVS lists.',
    'es': 'Los líderes pueden editar y quitar jugadores en las listas de Tirano Dragón de Escarcha y SVS.',
    'fr': 'Les chefs peuvent modifier et retirer des joueurs dans les listes Tyran Dragon de Givre et SVS.',
    'de': 'Anführer können Spieler in den Listen von Frostdrachen-Tyrann und SVS bearbeiten und entfernen.',
    'pl': 'Liderzy mogą edytować i usuwać graczy na listach Tyrana Mroźnego Smoka i SVS.',
    'ko': '리더가 서리 용 폭군과 SVS 목록에서 플레이어를 편집하고 제거할 수 있습니다.',
    'zh': '队长可以在霜龙暴君和 SVS 名单中编辑和移除玩家。',
    'tr': 'Liderler Ayaz Ejderhası Tiranı ve SVS listelerinde oyuncuları düzenleyip kaldırabilir.',
    'ar': 'يمكن للقادة تحرير اللاعبين وإزالتهم في قوائم طاغية تنين الصقيع وSVS.',
}


def load(lang, ns):
    return json.loads((LOC / lang / f'{ns}.json').read_text(encoding='utf-8'))


def save(lang, ns, data):
    (LOC / lang / f'{ns}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    for lang in LANGS:
        assert len(ADMIN[lang]) == len(ADMIN_KEYS), (lang, len(ADMIN[lang]))
        assert len(PLAN[lang]) == len(PLAN_KEYS), lang
        admin = load(lang, 'admin')
        admin['playerEdit'] = dict(zip(ADMIN_KEYS, ADMIN[lang]))
        save(lang, 'admin', admin)
        svs = load(lang, 'svs')
        svs['players']['deletePlan'] = dict(zip(PLAN_KEYS, PLAN[lang]))
        save(lang, 'svs', svs)
        cl = load(lang, 'changelog')
        out = {}
        for k, v in cl.items():
            if k == 'v221edit':
                continue
            out[k] = v
            if k == 'v221a':
                out['v221edit'] = CHANGELOG[lang]
        save(lang, 'changelog', out)
    print('ok', len(ADMIN_KEYS) + len(PLAN_KEYS) + 1, 'keys x', len(LANGS), 'languages')


if __name__ == '__main__':
    main()
