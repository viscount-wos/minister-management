"""Owner change (v2.2.0): SVS sign-up no longer asks the role (call / join rallies); the battle planner assigns
leaders. Rewrites the affected strings and removes the unused keys in all 9 languages. Re-runnable."""
import json
from pathlib import Path

LOC = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'

T = {
    'en': dict(s4='Voice chat', s4d='Can you talk with us during the battle?',
               signup3='No role question: you choose the rally leaders yourself in the Battle plan.',
               stats='The cards show total players, average battle hours per player, players with T11 in all three troop types and Discord VC. Underneath: players per hour and alliances, then camp levels and tiers per troop type. Tap any bar or count to filter by it; tap it again to remove the filter.',
               f1='Search by name or player ID; filter by alliance, hours (players online in ALL the chosen hours), troop type, camp level and tier.',
               add="For players who didn't sign up: Add player creates their sign-up with just the player ID and in-game name; hours, voice chat and troops are optional. If they already have a sign-up in the round, edit that one instead.",
               v220a="Sign up for SVS: pick the battle hours you will be online, each troop camp's level with T10 or T11, and whether you can join Discord voice chat.",
               avg='Avg hours per player', t11='T11 in all three'),
    'es': dict(s4='Chat de voz', s4d='¿Puedes hablar con nosotros durante la batalla?',
               signup3='Sin pregunta de papel: tú eliges a los líderes de rally en el Plan de batalla.',
               stats='Las tarjetas muestran el total de jugadores, la media de horas de batalla por jugador, los jugadores con T11 en los tres tipos de tropa y el VC de Discord. Debajo: jugadores por hora y alianzas, y luego niveles de campamento y de tropa por tipo. Toca una barra o un número para filtrar; tócalo de nuevo para quitar el filtro.',
               f1='Busca por nombre o ID; filtra por alianza, horas (jugadores conectados en TODAS las horas elegidas), tipo de tropa, nivel de campamento y nivel de tropa.',
               add='Para quienes no se inscribieron: Añadir jugador crea su inscripción solo con el ID y el nombre en el juego; horas, chat de voz y tropas son opcionales. Si ya tiene una inscripción en la ronda, edita esa.',
               v220a='Inscríbete en SVS: elige las horas de batalla en que estarás conectado, el nivel de cada campamento con T10 o T11 y si puedes unirte al chat de voz de Discord.',
               avg='Media de horas por jugador', t11='T11 en los tres'),
    'fr': dict(s4='Vocal', s4d='Pouvez-vous nous parler pendant la bataille ?',
               signup3='Pas de question de rôle : vous choisissez vous-même les chefs de rassemblement dans le Plan de bataille.',
               stats="Les cartes montrent le total des joueurs, la moyenne d'heures de bataille par joueur, les joueurs en T11 dans les trois types de troupes et le vocal Discord. En dessous : joueurs par heure et alliances, puis niveaux de camp et paliers par type de troupe. Touchez une barre ou un nombre pour filtrer ; touchez-le à nouveau pour retirer le filtre.",
               f1='Recherchez par nom ou ID ; filtrez par alliance, heures (joueurs en ligne à TOUTES les heures choisies), type de troupe, niveau de camp et palier.',
               add="Pour ceux qui ne se sont pas inscrits : Ajouter un joueur crée leur inscription avec seulement l'ID et le nom en jeu ; heures, vocal et troupes sont facultatifs. S'il a déjà une inscription dans la manche, modifiez-la plutôt.",
               v220a='Inscrivez-vous au SVS : choisissez les heures de bataille où vous serez en ligne, le niveau de chaque camp avec T10 ou T11, et si vous pouvez rejoindre le vocal Discord.',
               avg='Heures moyennes par joueur', t11='T11 partout'),
    'de': dict(s4='Sprachchat', s4d='Kannst du während der Schlacht mit uns reden?',
               signup3='Keine Rollenfrage: Die Rally-Leiter wählst du selbst im Schlachtplan.',
               stats='Die Karten zeigen Spieler gesamt, durchschnittliche Kampfstunden pro Spieler, Spieler mit T11 in allen drei Truppenarten und Discord-VC. Darunter: Spieler pro Stunde und Allianzen, dann Lager- und Truppenstufen pro Truppenart. Tippe auf einen Balken oder eine Zahl, um danach zu filtern; noch einmal tippen entfernt den Filter.',
               f1='Suche nach Name oder ID; filtere nach Allianz, Stunden (Spieler, die in ALLEN gewählten Stunden online sind), Truppenart, Lagerstufe und Truppenstufe.',
               add='Für Spieler ohne Anmeldung: Spieler hinzufügen legt ihre Anmeldung nur mit ID und Spielname an; Stunden, Sprachchat und Truppen sind optional. Hat er in der Runde schon eine Anmeldung, bearbeite diese.',
               v220a='Melde dich für SVS an: Wähle die Kampfstunden, in denen du online bist, die Stufe jedes Truppenlagers mit T10 oder T11 und ob du in den Discord-Sprachchat kannst.',
               avg='Ø Stunden pro Spieler', t11='T11 in allen drei'),
    'pl': dict(s4='Czat głosowy', s4d='Czy możesz z nami rozmawiać podczas bitwy?',
               signup3='Bez pytania o rolę: liderów rajdów wybierasz sam w Planie bitwy.',
               stats='Karty pokazują liczbę graczy, średnią liczbę godzin bitwy na gracza, graczy z T11 we wszystkich trzech typach wojsk i VC Discord. Niżej: gracze na godzinę i sojusze, potem poziomy obozów i wojsk według typu. Dotknij paska lub liczby, aby filtrować; dotknij ponownie, aby usunąć filtr.',
               f1='Szukaj po nazwie lub ID; filtruj po sojuszu, godzinach (gracze online we WSZYSTKICH wybranych godzinach), typie wojsk, poziomie obozu i poziomie wojsk.',
               add='Dla graczy bez zapisu: Dodaj gracza tworzy zapis tylko z ID i nazwą w grze; godziny, czat głosowy i wojska są opcjonalne. Jeśli gracz ma już zapis w rundzie, edytuj tamten.',
               v220a='Zapisz się na SVS: wybierz godziny bitwy, w których będziesz online, poziom każdego obozu z T10 lub T11 oraz czy możesz dołączyć do czatu głosowego Discord.',
               avg='Śr. godzin na gracza', t11='T11 we wszystkich trzech'),
    'ko': dict(s4='음성 채팅', s4d='전투 중에 함께 이야기할 수 있나요?',
               signup3='역할 질문 없음: 집결 리더는 전투 계획에서 직접 고릅니다.',
               stats='카드에는 전체 플레이어, 플레이어당 평균 전투 시간, 세 병종 모두 T11인 플레이어, Discord VC가 표시됩니다. 그 아래에 시간별 플레이어와 연맹, 병종별 병영 레벨과 티어가 있습니다. 막대나 숫자를 누르면 그것으로 필터링되고, 다시 누르면 필터가 해제됩니다.',
               f1='이름이나 ID로 검색하고, 연맹, 시간(선택한 모든 시간에 접속하는 플레이어), 병종, 병영 레벨, 티어로 필터링하세요.',
               add='신청하지 않은 플레이어: 플레이어 추가는 ID와 게임 닉네임만으로 신청을 만듭니다. 시간, 음성 채팅, 병력은 선택입니다. 라운드에 이미 신청이 있으면 그것을 수정하세요.',
               v220a='SVS에 신청하세요: 접속할 전투 시간, T10 또는 T11과 함께 각 병영의 레벨, Discord 음성 채팅 참여 여부를 고르세요.',
               avg='플레이어당 평균 시간', t11='세 병종 모두 T11'),
    'zh': dict(s4='语音', s4d='战斗期间你能和我们语音吗？',
               signup3='不再询问角色：集结队长由你在“作战计划”中亲自指定。',
               stats='卡片显示总人数、人均战斗小时数、三个兵种都是 T11 的人数和 Discord 语音人数。下方是每小时人数和联盟，然后是各兵种的兵营等级和阶级。点击任意条或数字即可按其筛选，再点一次取消筛选。',
               f1='按名称或 ID 搜索；按联盟、时段（在所选全部小时都在线的玩家）、兵种、兵营等级和阶级筛选。',
               add='针对未报名的玩家：“添加玩家”只用 ID 和游戏名称即可创建报名；时段、语音和部队都是可选的。如果该玩家本轮已有报名，请编辑那一条。',
               v220a='报名 SVS：选择你会在线的战斗小时、每个兵营的等级和 T10 或 T11，以及能否加入 Discord 语音。',
               avg='人均小时数', t11='三兵种均 T11'),
    'tr': dict(s4='Sesli sohbet', s4d='Savaş sırasında bizimle konuşabilir misin?',
               signup3='Rol sorusu yok: ralli liderlerini Savaş planında kendin seçersin.',
               stats="Kartlar toplam oyuncuyu, oyuncu başına ortalama savaş saatini, üç birlik türünde de T11 olan oyuncuları ve Discord VC'yi gösterir. Altında: saat başına oyuncular ve ittifaklar, ardından birlik türüne göre kamp seviyeleri ve kademeler. Filtrelemek için bir çubuğa veya sayıya dokun; kaldırmak için tekrar dokun.",
               f1='İsim veya kimlikle ara; ittifaka, saatlere (seçilen TÜM saatlerde çevrimiçi olanlar), birlik türüne, kamp seviyesine ve kademeye göre filtrele.',
               add='Kaydolmayan oyuncular için: Oyuncu ekle, yalnızca kimlik ve oyun içi isimle kayıt oluşturur; saatler, sesli sohbet ve birlikler isteğe bağlıdır. Turda zaten kaydı varsa onu düzenle.',
               v220a="SVS'ye kaydol: çevrimiçi olacağın savaş saatlerini, T10 veya T11 ile her birlik kampının seviyesini ve Discord sesli sohbete katılıp katılamayacağını seç.",
               avg='Oyuncu başına ort. saat', t11='Üçünde de T11'),
    'ar': dict(s4='الدردشة الصوتية', s4d='هل يمكنك التحدث معنا أثناء المعركة؟',
               signup3='لا سؤال عن الدور: أنت من يختار قادة الحشود في خطة المعركة.',
               stats='تعرض البطاقات إجمالي اللاعبين ومتوسط ساعات المعركة لكل لاعب واللاعبين الذين لديهم T11 في أنواع القوات الثلاثة وصوت Discord. وتحتها: اللاعبون في كل ساعة والتحالفات، ثم مستويات المعسكرات والقوات لكل نوع. اضغط على أي شريط أو رقم للتصفية به، واضغط مرة أخرى لإزالة التصفية.',
               f1='ابحث بالاسم أو المعرف؛ صفِّ حسب التحالف والساعات (اللاعبون المتصلون في كل الساعات المختارة) ونوع القوات ومستوى المعسكر والمستوى.',
               add='للاعبين الذين لم يسجّلوا: «إضافة لاعب» ينشئ تسجيلهم بالمعرف والاسم في اللعبة فقط؛ الساعات والدردشة الصوتية والقوات اختيارية. إن كان له تسجيل في الجولة فعدّله بدلًا من ذلك.',
               v220a='سجّل في SVS: اختر ساعات المعركة التي ستكون فيها متصلًا، ومستوى كل معسكر مع T10 أو T11، وهل يمكنك الانضمام إلى الدردشة الصوتية في Discord.',
               avg='متوسط الساعات لكل لاعب', t11='T11 في الثلاثة'),
}


def rw(path, fn):
    data = json.loads(path.read_text(encoding='utf-8'))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


for lang, v in T.items():
    def svs(d, v=v):
        d['step4']['title'] = v['s4']
        d['step4']['desc'] = v['s4d']
        d['step4'].pop('roleTitle', None)
        d.pop('roles', None)
        d['errors'].pop('roleRequired', None)
        stats = d['admin']['stats']
        stats.pop('callers', None)
        stats.pop('joiners', None)
        stats['avgHours'] = v['avg']
        stats['allT11'] = v['t11']
        d['admin']['col'].pop('role', None)
        d['admin']['pill'].pop('role', None)

    def guide(d, v=v):
        g = d['svsAdmin']
        g['signup3'], g['statsBody'], g['filters1'], g['addBody'] = v['signup3'], v['stats'], v['f1'], v['add']

    def changelog(d, v=v):
        d['v220a'] = v['v220a']

    rw(LOC / lang / 'svs.json', svs)
    rw(LOC / lang / 'guide.json', guide)
    rw(LOC / lang / 'changelog.json', changelog)
print('ok')
