"""Add the SVS admin guide's 'Add to rally' entries (svsAdmin.table4..6) in all 9 languages."""
import json, os

BASE = os.path.expanduser('~/ai/fun/wos/wos-events/frontend/src/i18n/locales')
T = {
 'en': [
  'Plan column: shows where each player is in this round\'s battle plan, e.g. "Joiner 2 · Rally Caller 01 (Main alliance)". A dash means they are not in the plan yet. The "In plan" and "Not in plan" counts above the table filter the list.',
  'Add to rally: the person-plus button on a row lists your rally leaders with their free places (named n/4, extra n/14). Pick a leader, then "As named joiner" (pick the lead hero later in Battle plan) or "As extra joiner". You can also make the player a rally leader or add them to a group such as Turrets. If they are already placed, the menu says where and offers "Move here".',
  'Bulk add: tick several players, then use "Add N selected to rally…" in the bar at the bottom. Named places fill first, then extra. Anyone already in the plan, or who did not fit, is named in the message. If another leader changed the plan at the same time, it is retried once and nothing is overwritten.',
 ],
 'es': [
  'Columna Plan: muestra dónde está cada jugador en el plan de batalla de esta ronda, p. ej. «Acompañante 2 · Rally Caller 01 (Alianza principal)». Un guion significa que aún no está en el plan. Los contadores «En el plan» y «Fuera del plan» encima de la tabla filtran la lista.',
  'Añadir a un rally: el botón de persona con «+» de cada fila muestra tus líderes de rally con sus plazas libres (con nombre n/4, extra n/14). Elige un líder y luego «Como unido con nombre» (el héroe principal se elige después en Plan de batalla) o «Como unido extra». También puedes hacerlo líder de rally o añadirlo a un grupo como Torretas. Si ya está colocado, el menú indica dónde y ofrece «Mover aquí».',
  'Añadir varios: marca varios jugadores y usa «Añadir N seleccionados al rally…» en la barra inferior. Primero se llenan las plazas con nombre y luego las extra. Quien ya esté en el plan o no quepa aparece nombrado en el mensaje. Si otro líder cambió el plan a la vez, se reintenta una vez y no se sobrescribe nada.',
 ],
 'fr': [
  'Colonne Plan : indique la place de chaque joueur dans le plan de bataille de ce tour, par ex. « Participant 2 · Rally Caller 01 (Alliance principale) ». Un tiret signifie qu’il n’est pas encore dans le plan. Les compteurs « Dans le plan » et « Hors du plan » au-dessus du tableau filtrent la liste.',
  'Ajouter à un rally : le bouton personne « + » d’une ligne liste vos chefs de rally avec leurs places libres (nommés n/4, extra n/14). Choisissez un chef, puis « Comme renfort nommé » (le héros principal se choisit ensuite dans Plan de bataille) ou « Comme renfort extra ». Vous pouvez aussi en faire un chef de rally ou l’ajouter à un groupe comme Tourelles. S’il est déjà placé, le menu indique où et propose « Déplacer ici ».',
  'Ajout groupé : cochez plusieurs joueurs puis utilisez « Ajouter les N sélectionnés au rallye… » dans la barre du bas. Les places nommées se remplissent d’abord, puis les extra. Les joueurs déjà dans le plan, ou qui n’ont pas trouvé de place, sont cités dans le message. Si un autre chef a modifié le plan en même temps, l’action est relancée une fois et rien n’est écrasé.',
 ],
 'de': [
  'Spalte Plan: zeigt, wo jeder Spieler im Schlachtplan dieser Runde steht, z. B. „Mitläufer 2 · Rally Caller 01 (Hauptallianz)“. Ein Strich heißt: noch nicht im Plan. Die Zähler „Im Plan“ und „Nicht im Plan“ über der Tabelle filtern die Liste.',
  'Zur Rallye hinzufügen: Die Person-Plus-Schaltfläche in einer Zeile zeigt deine Rallye-Leiter mit freien Plätzen (benannt n/4, extra n/14). Wähle einen Leiter, dann „Als benannter Mitläufer“ (den Haupthelden wählst du später im Schlachtplan) oder „Als Extra-Mitläufer“. Du kannst den Spieler auch zum Rallye-Leiter machen oder einer Gruppe wie Türme hinzufügen. Ist er schon eingeplant, zeigt das Menü wo und bietet „Hierher verschieben“.',
  'Mehrere hinzufügen: Hake mehrere Spieler an und nutze „N Ausgewählte zur Rallye…“ in der Leiste unten. Zuerst werden benannte Plätze gefüllt, dann zusätzliche. Wer schon im Plan ist oder nicht mehr passt, wird in der Meldung genannt. Hat ein anderer Leiter den Plan gleichzeitig geändert, wird es einmal wiederholt und nichts überschrieben.',
 ],
 'pl': [
  'Kolumna Plan: pokazuje, gdzie gracz jest w planie bitwy tej rundy, np. „Dołączający 2 · Rally Caller 01 (Główny sojusz)”. Myślnik oznacza, że nie ma go jeszcze w planie. Liczniki „W planie” i „Poza planem” nad tabelą filtrują listę.',
  'Dodaj do rajdu: przycisk osoby z plusem w wierszu pokazuje liderów rajdów i wolne miejsca (imienne n/4, dodatkowe n/14). Wybierz lidera, potem „Jako imienny dołączający” (głównego bohatera wybierzesz później w Planie bitwy) albo „Jako dodatkowy dołączający”. Możesz też zrobić z gracza lidera rajdu lub dodać go do grupy, np. Wieżyczki. Jeśli już jest w planie, menu pokaże gdzie i zaproponuje „Przenieś tutaj”.',
  'Dodawanie wielu: zaznacz kilku graczy i użyj „Dodaj zaznaczonych (N) do rajdu…” na pasku na dole. Najpierw zapełniane są miejsca imienne, potem dodatkowe. Gracze już w planie lub ci, którzy się nie zmieścili, są wymienieni w komunikacie. Jeśli inny lider zmienił plan w tym samym czasie, operacja jest ponawiana raz i nic nie zostaje nadpisane.',
 ],
 'ko': [
  '계획 열: 각 플레이어가 이번 라운드 전투 계획의 어디에 있는지 보여 줍니다(예: "참여자 2 · Rally Caller 01 (메인 연맹)"). "—"는 아직 계획에 없다는 뜻입니다. 표 위의 "계획에 있음"과 "계획에 없음" 숫자를 누르면 목록이 필터됩니다.',
  '집결에 추가: 행의 사람+ 버튼을 누르면 집결 리더 목록과 남은 자리(지정 n/4, 추가 n/14)가 나옵니다. 리더를 고른 뒤 "지정 참여자로"(대표 영웅은 나중에 전투 계획에서 선택) 또는 "추가 참여자로"를 선택하세요. 집결 리더로 지정하거나 포탑 같은 그룹에 넣을 수도 있습니다. 이미 배치된 플레이어는 위치가 표시되고 "여기로 이동"을 고를 수 있습니다.',
  '여러 명 추가: 여러 플레이어를 체크한 뒤 아래 막대의 "선택한 N명을 집결에 추가…"를 사용하세요. 지정 자리부터 채우고 그다음 추가 자리를 채웁니다. 이미 계획에 있거나 자리가 없는 플레이어는 메시지에 이름이 나옵니다. 다른 리더가 동시에 계획을 바꿨다면 한 번 다시 시도하며, 아무것도 덮어쓰지 않습니다.',
 ],
 'zh': [
  '计划列：显示每位玩家在本轮作战计划中的位置，例如“随从 2 · Rally Caller 01（主联盟）”。“—”表示还未加入计划。表格上方的“已在计划中”和“不在计划中”计数可筛选列表。',
  '加入集结：点击行上的“人+”按钮，会列出集结队长及其空位（指定 n/4，额外 n/14）。选择队长后，再选“作为指定加入者”（主将英雄稍后在作战计划中选择）或“作为额外加入者”。也可以把玩家设为集结队长，或加入“炮台”等分组。若玩家已在计划中，菜单会显示位置并提供“移到这里”。',
  '批量加入：勾选多名玩家，然后使用底部栏的“将选中的 N 人加入集结…”。先填满指定位置，再填额外位置。已在计划中或放不下的玩家会在提示中列出。如果其他队长同时修改了计划，会自动重试一次，不会覆盖任何内容。',
 ],
 'tr': [
  'Plan sütunu: her oyuncunun bu turun savaş planında nerede olduğunu gösterir, ör. "Katılımcı 2 · Rally Caller 01 (Ana ittifak)". Tire, henüz planda olmadığı anlamına gelir. Tablonun üstündeki "Planda" ve "Planda değil" sayıları listeyi filtreler.',
  'Ralliye ekle: bir satırdaki kişi-artı düğmesi ralli liderlerini ve boş yerlerini (isimli n/4, ek n/14) listeler. Bir lider seç, sonra "İsimli katılımcı olarak" (ana kahraman sonra Savaş planında seçilir) veya "Ek katılımcı olarak". Oyuncuyu ralli lideri yapabilir ya da Taretler gibi bir gruba da ekleyebilirsin. Zaten yerleştirilmişse menü nerede olduğunu gösterir ve "Buraya taşı" seçeneğini sunar.',
  'Toplu ekleme: birkaç oyuncuyu işaretle ve alttaki çubukta "Seçili N oyuncuyu ralliye ekle…" seçeneğini kullan. Önce isimli yerler, sonra ek yerler dolar. Zaten planda olanlar veya sığmayanlar mesajda adlarıyla belirtilir. Başka bir lider planı aynı anda değiştirdiyse işlem bir kez yeniden denenir ve hiçbir şeyin üzerine yazılmaz.',
 ],
 'ar': [
  'عمود الخطة: يُظهر مكان كل لاعب في خطة المعركة لهذه الجولة، مثل «منضم 2 · Rally Caller 01 (التحالف الرئيسي)». الشرطة تعني أنه ليس في الخطة بعد. عدّادا «في الخطة» و«ليس في الخطة» فوق الجدول يصفّيان القائمة.',
  'إضافة إلى حشد: زر الشخص مع «+» في الصف يعرض قادة الحشود وأماكنهم الفارغة (بالاسم n/4، إضافي n/14). اختر قائدًا، ثم «كمنضم بالاسم» (يُختار البطل الرئيسي لاحقًا في خطة المعركة) أو «كمنضم إضافي». يمكنك أيضًا جعل اللاعب قائد حشد أو إضافته إلى مجموعة مثل الأبراج. إذا كان موضوعًا في الخطة من قبل، تُظهر القائمة مكانه وتعرض «نقل إلى هنا».',
  'إضافة جماعية: حدّد عدة لاعبين ثم استخدم «إضافة N محددين إلى حشد…» في الشريط السفلي. تُملأ الأماكن بالاسم أولًا ثم الإضافية. من كان في الخطة مسبقًا أو لم يجد مكانًا يُذكر اسمه في الرسالة. إذا غيّر قائد آخر الخطة في الوقت نفسه، تُعاد المحاولة مرة واحدة ولا يُستبدل أي شيء.',
 ],
}
for lang, items in T.items():
    p = f'{BASE}/{lang}/guide.json'
    d = json.load(open(p, encoding='utf-8'))
    for i, txt in enumerate(items, start=4):
        d['svsAdmin'][f'table{i}'] = txt
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(p, 'a', encoding='utf-8').write('\n')
p = os.path.expanduser('~/ai/fun/wos/wos-events/frontend/src/events/svs/admin/SvsAdminGuide.tsx')
s = open(p).read()
s = s.replace("keys={['table1', 'table2', 'table3']}", "keys={['table1', 'table2', 'table3', 'table4', 'table5', 'table6']}")
open(p, 'w').write(s)
print('ok')
