import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  DragEndEvent,
  DragStartEvent,
} from '@dnd-kit/core';
import { Sparkles, Download, AlertCircle, Globe, EyeOff, Lock, Unlock, Link2 } from 'lucide-react';
import api, { Round, downloadBlob } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import TimezoneSelector from '../../../shared/TimezoneSelector';
import { useTimezone } from '../../../shared/TimezoneContext';
import { generateAssignmentSlots, getSlotDisplayTime, TimeSlotScheme } from '../../../shared/timezone';
import { activeDaysInOrder } from '../../../shared/days';

interface AssignedPlayer {
  id: number;
  player_id: number;
  fid: string;
  game_name: string;
  points: number;
  time_slot?: string;
  alliance?: string;
  /** profile furnace code, e.g. 'FC8' */
  furnace_level?: string | null;
  is_sticky?: boolean;
}

interface Assignments {
  [timeSlot: string]: AssignedPlayer[];
}

interface UnassignedPlayer extends AssignedPlayer {
  preferred_times: string[];
}

// Use the shared slot generator (23:50 through 23:50+)
const generateTimeSlots = generateAssignmentSlots;

const PLAYER_CARD_CLASS = 'bg-accent/15 border-accent/40 text-accent';

// Draggable player card
function DraggablePlayer({ player, sourceSlot, onToggleLock, timezone, disabled }: { player: AssignedPlayer; sourceSlot: string; onToggleLock?: (player: AssignedPlayer, slot: string) => void; timezone?: string; disabled?: boolean }) {
  const { t } = useTranslation();
  const [showTooltip, setShowTooltip] = useState(false);
  const dragId = `player-${player.player_id}-${sourceSlot}`;
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: dragId,
    data: { player, sourceSlot },
    disabled,
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    opacity: isDragging ? 0.3 : 1,
  } : {
    opacity: isDragging ? 0.3 : 1,
  };

  const preferredTimes = (player as any).preferred_times as string[] | undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-testid={`card-${player.fid}`}
      className={`p-3 border-2 rounded-lg ${disabled ? 'cursor-default' : 'cursor-grab active:cursor-grabbing'} hover:shadow-md transition-shadow relative ${
        player.is_sticky ? 'bg-warning/15 border-warning/50 text-accent' : PLAYER_CARD_CLASS
      }`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Tooltip */}
      {showTooltip && !isDragging && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-3 bg-dark-bg border border-accent/40 rounded-lg shadow-xl text-sm pointer-events-none">
          <div className="font-semibold text-accent truncate">
            {player.alliance && <span>[{player.alliance}] </span>}{player.game_name}
          </div>
          <div className="text-xs text-theme-dim mt-1">{t('admin:fid')}: {player.fid} • {t('admin:pointsShort', { n: (player.points ?? 0).toLocaleString() })}</div>
          {preferredTimes && preferredTimes.length > 0 ? (
            <div className="mt-2 border-t border-theme-border pt-2">
              <div className="text-xs font-medium text-theme-dim mb-1">{t('admin:requestedTimes')}:</div>
              <div className="flex flex-wrap gap-1">
                {preferredTimes.map((time) => (
                  <span key={time} className="text-xs px-1.5 py-0.5 bg-accent/15 text-accent rounded">
                    {timezone ? getSlotDisplayTime(time, timezone) : time}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-2 border-t border-theme-border pt-2 text-xs text-theme-dim italic">
              {t('admin:noTimePref')}
            </div>
          )}
          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-accent/40" />
        </div>
      )}
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-medium truncate">{player.alliance && <span className="text-accent">[{player.alliance}]</span>} {player.game_name}
              {player.furnace_level && (
                <span className="ms-1 px-1.5 py-0.5 rounded bg-accent/20 text-accent text-[10px] font-semibold align-middle" data-testid="furnace-badge">
                  {player.furnace_level}
                </span>
              )}
          </div>
          <div className="text-xs opacity-75">
            {player.fid} • {t('admin:pointsShort', { n: (player.points ?? 0).toLocaleString() })}
          </div>
        </div>
        {sourceSlot !== 'unassigned' && onToggleLock && (
          <button
            onPointerDown={(e) => {
              e.stopPropagation();
              onToggleLock(player, sourceSlot);
            }}
            className={`flex-shrink-0 p-1 rounded transition-colors ${
              player.is_sticky ? 'text-warning hover:text-accent-light' : 'text-theme-dim hover:text-accent opacity-40 hover:opacity-100'
            }`}
            title={player.is_sticky ? t('admin:clickToUnlock') : t('admin:clickToLock')}
            aria-label={player.is_sticky ? t('admin:clickToUnlock') : t('admin:clickToLock')}
          >
            {player.is_sticky ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  );
}

// Static player card (for overlay while dragging)
function PlayerCard({ player }: { player: AssignedPlayer }) {
  const { t } = useTranslation();
  return (
    <div
      className={`p-3 border-2 rounded-lg shadow-lg ${PLAYER_CARD_CLASS}`}
    >
      <div className="flex items-center gap-2">
        <div className="min-w-0">
          <div className="font-medium truncate">{player.alliance && <span className="text-accent">[{player.alliance}]</span>} {player.game_name}
              {player.furnace_level && (
                <span className="ms-1 px-1.5 py-0.5 rounded bg-accent/20 text-accent text-[10px] font-semibold align-middle" data-testid="furnace-badge">
                  {player.furnace_level}
                </span>
              )}
          </div>
          <div className="text-xs opacity-75">
            {player.fid} • {t('admin:pointsShort', { n: (player.points ?? 0).toLocaleString() })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Droppable time slot container
function DroppableSlot({ slotId, displayTime, children, isOver, hasPlayer, sharedNote }: {
  slotId: string;
  displayTime: string;
  children: React.ReactNode;
  isOver: boolean;
  hasPlayer: boolean;
  sharedNote?: string | null;
}) {
  const { setNodeRef } = useDroppable({ id: `slot-${slotId}` });

  return (
    <div
      ref={setNodeRef}
      className={`border-2 border-dashed rounded-lg p-3 min-h-[100px] transition-colors ${
        sharedNote
          ? 'border-warning/50 bg-warning/10'
          : isOver && !hasPlayer
          ? 'border-accent bg-accent/10'
          : isOver && hasPlayer
          ? 'border-danger bg-danger/10'
          : 'border-theme-border bg-dark-bg'
      }`}
    >
      <div className="font-semibold text-theme-dim mb-2">
        {displayTime}
        {slotId === '23:50+' && <span className="text-xs opacity-60 ml-1">(+1d)</span>}
      </div>
      {sharedNote && (
        <div className="flex items-start gap-1 text-[11px] leading-tight text-warning mb-2">
          <Link2 className="w-3 h-3 mt-0.5 shrink-0" />
          <span>{sharedNote}</span>
        </div>
      )}
      {children}
    </div>
  );
}

// Droppable unassigned area
function DroppableUnassigned({ children, isOver }: { children: React.ReactNode; isOver: boolean }) {
  const { setNodeRef } = useDroppable({ id: 'slot-unassigned' });

  return (
    <div
      ref={setNodeRef}
      className={`border-2 border-dashed rounded-lg p-4 min-h-[400px] transition-colors ${
        isOver
          ? 'border-accent bg-accent/10'
          : 'border-theme-border bg-dark-bg'
      }`}
    >
      {children}
    </div>
  );
}

interface AssignmentManagementProps {
  round: Round;
  readOnly: boolean;
  onRoundUpdated: (r: Round) => void;
}

export default function AssignmentManagement({ round, readOnly, onRoundUpdated }: AssignmentManagementProps) {
  const { t } = useTranslation();
  const [selectedDay, setSelectedDay] = useState('monday');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [assignments, setAssignments] = useState<Assignments>({});
  const [unassignedPlayers, setUnassignedPlayers] = useState<UnassignedPlayer[]>([]);
  const [activePlayer, setActivePlayer] = useState<AssignedPlayer | null>(null);
  const [overSlotId, setOverSlotId] = useState<string | null>(null);
  const { timezone, setTimezone } = useTimezone();
  // Per-round settings come from the selected round (the dashboard keeps it fresh).
  const researchDay = round.settings.research_day;
  const publishedDays = round.settings.published_days;
  const timeSlotScheme: TimeSlotScheme = round.settings.time_slot_scheme;

  const DAY_TABS = activeDaysInOrder(researchDay);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const timeSlots = generateTimeSlots(timeSlotScheme);

  // Shared 23:50 boundary: in max_slots mode, adjacent active days share the
  // same real-time slot (Mon 23:50+ == Tue 23:50; Thu 23:50+ == Fri 23:50).
  const sharedBoundary = (() => {
    if (timeSlotScheme !== 'max_slots') return null;
    const dayName = (k: string) => t(`admin:${k}`).split(' - ')[0];
    if (selectedDay === 'monday' && researchDay === 'tuesday')
      return { slot: '23:50+', note: t('admin:sharedSlotNote', { day: dayName('tuesday') }) };
    if (selectedDay === 'tuesday' && researchDay === 'tuesday')
      return { slot: '23:50', note: t('admin:sharedSlotNote', { day: dayName('monday') }) };
    if (selectedDay === 'thursday' && researchDay === 'friday')
      return { slot: '23:50+', note: t('admin:sharedSlotNote', { day: dayName('friday') }) };
    if (selectedDay === 'friday' && researchDay === 'friday')
      return { slot: '23:50', note: t('admin:sharedSlotNote', { day: dayName('thursday') }) };
    return null;
  })();

  // Research day may have changed in Settings: keep the day tab valid.
  useEffect(() => {
    if (!DAY_TABS.includes(selectedDay)) setSelectedDay(researchDay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [researchDay]);

  useEffect(() => {
    if (DAY_TABS.includes(selectedDay)) fetchAssignments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDay, round.id, timeSlotScheme]);

  const setPublished = async (publish: boolean) => {
    setError('');
    try {
      const res = publish
        ? await api.admin.ministry.publish(round.id, selectedDay)
        : await api.admin.ministry.unpublish(round.id, selectedDay);
      onRoundUpdated({ ...round, settings: { ...round.settings, published_days: res.published_days } });
    } catch (err) {
      setError(errorText(t, err, publish ? 'admin:publishError' : 'admin:unpublishError'));
    }
  };

  const fetchAssignments = async () => {
    setLoading(true);
    try {
      const res = await api.admin.ministry.assignments(round.id, selectedDay);
      // Enforce 1 player per slot on load
      const cleaned: Assignments = {};
      for (const [slot, players] of Object.entries(res.assignments || {})) {
        cleaned[slot] = (players || []).slice(0, 1) as AssignedPlayer[];
      }
      setAssignments(cleaned);
      setUnassignedPlayers((res.unassigned || []) as UnassignedPlayer[]);
      setError('');
    } catch (err) {
      setError(errorText(t, err, 'admin:fetchAssignmentsError'));
    } finally {
      setLoading(false);
    }
  };

  const handleAutoAssign = async () => {
    if (readOnly) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.admin.ministry.autoAssign(round.id, selectedDay);
      setAssignments(res.assignments as Assignments);
      setUnassignedPlayers(res.unassigned as UnassignedPlayer[]);
    } catch (err) {
      setError(errorText(t, err, 'admin:autoAssignError'));
    } finally {
      setLoading(false);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    const { player } = event.active.data.current as { player: AssignedPlayer; sourceSlot: string };
    setActivePlayer(player);
  };

  const handleDragOver = (event: any) => {
    const { over } = event;
    if (over) {
      const overId = over.id as string;
      setOverSlotId(overId.startsWith('slot-') ? overId.replace('slot-', '') : null);
    } else {
      setOverSlotId(null);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActivePlayer(null);
    setOverSlotId(null);

    const { active, over } = event;
    if (!over) return;

    const { player: movedPlayer, sourceSlot } = active.data.current as {
      player: AssignedPlayer;
      sourceSlot: string;
    };

    const overId = over.id as string;

    // Determine target slot
    let targetSlot: string;
    if (overId.startsWith('slot-')) {
      targetSlot = overId.replace('slot-', '');
    } else if (overId.startsWith('player-')) {
      // Dropped on another player - get that player's slot
      const parts = overId.split('-');
      targetSlot = parts.slice(2).join('-');
    } else {
      return;
    }

    // No-op if same slot
    if (sourceSlot === targetSlot) return;

    // If target is a time slot (not unassigned), check if it already has a player
    if (targetSlot !== 'unassigned') {
      const existingPlayers = assignments[targetSlot] || [];
      if (existingPlayers.length > 0) {
        // Slot occupied - swap the players
        const existingPlayer = existingPlayers[0];

        const newAssignments = { ...assignments };
        const newUnassigned = [...unassignedPlayers];

        // Put existing player where the moved player came from
        if (sourceSlot === 'unassigned') {
          // Move existing player to unassigned (clear sticky)
          newUnassigned.push({ ...existingPlayer, time_slot: undefined, preferred_times: [], is_sticky: false } as UnassignedPlayer);
          // Remove moved player from unassigned
          const idx = newUnassigned.findIndex((p) => p.player_id === movedPlayer.player_id);
          if (idx !== -1) newUnassigned.splice(idx, 1);
        } else {
          // Swap: put existing player in source slot (keep its sticky status)
          newAssignments[sourceSlot] = [{ ...existingPlayer, time_slot: sourceSlot }];
        }

        // Put moved player in target slot - mark as sticky (manual move)
        newAssignments[targetSlot] = [{ ...movedPlayer, time_slot: targetSlot, is_sticky: true }];

        setAssignments(newAssignments);
        setUnassignedPlayers(newUnassigned);
        saveAssignments(newAssignments);
        return;
      }
    }

    // Normal move (target is empty or unassigned)
    const newAssignments = { ...assignments };
    const newUnassigned = [...unassignedPlayers];

    // Remove from old location
    if (sourceSlot === 'unassigned') {
      const index = newUnassigned.findIndex((p) => p.player_id === movedPlayer.player_id);
      if (index !== -1) newUnassigned.splice(index, 1);
    } else {
      newAssignments[sourceSlot] = (newAssignments[sourceSlot] || []).filter(
        (p) => p.player_id !== movedPlayer.player_id
      );
    }

    // Add to new location
    if (targetSlot === 'unassigned') {
      // Moving to unassigned clears sticky
      newUnassigned.push({ ...movedPlayer, time_slot: undefined, preferred_times: [], is_sticky: false } as UnassignedPlayer);
    } else {
      // Manual move to a slot = sticky
      newAssignments[targetSlot] = [{ ...movedPlayer, time_slot: targetSlot, is_sticky: true }];
    }

    setAssignments(newAssignments);
    setUnassignedPlayers(newUnassigned);
    saveAssignments(newAssignments);
  };

  const handleToggleLock = (player: AssignedPlayer, slot: string) => {
    const newAssignments = { ...assignments };
    const slotPlayers = newAssignments[slot] || [];
    if (slotPlayers.length > 0 && slotPlayers[0].player_id === player.player_id) {
      newAssignments[slot] = [{ ...slotPlayers[0], is_sticky: !slotPlayers[0].is_sticky }];
      setAssignments(newAssignments);
      saveAssignments(newAssignments);
    }
  };

  const saveAssignments = async (assignmentsToSave: Assignments) => {
    if (readOnly) return;
    // The API takes the first player per slot: {slot: [{player_id, is_sticky}]}.
    const body: Record<string, { player_id: number; is_sticky: boolean }[]> = {};
    for (const [slot, players] of Object.entries(assignmentsToSave)) {
      if (players && players.length > 0) {
        body[slot] = [{ player_id: players[0].player_id, is_sticky: !!players[0].is_sticky }];
      }
    }
    try {
      await api.admin.ministry.saveAssignments(round.id, selectedDay, body);
    } catch (err) {
      setError(errorText(t, err, 'admin:saveError'));
      fetchAssignments();
    }
  };

  const handleExport = async () => {
    try {
      const blob = await api.admin.exportRound(round.id);
      downloadBlob(blob, `ministry_round_${round.id}_assignments.xlsx`);
    } catch (err) {
      setError(errorText(t, err, 'admin:exportError'));
    }
  };

  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-6">
      {/* Day Tabs */}
      <div className="flex gap-4 mb-6 border-b border-theme-border pb-2">
        {DAY_TABS.map((day) => (
          <button
            key={day}
            data-testid={`assign-day-${day}`}
            onClick={() => setSelectedDay(day)}
            className={`px-4 py-2 font-medium rounded-lg transition-colors ${
              selectedDay === day
                ? 'bg-accent text-dark-bg'
                : 'text-theme-dim hover:text-theme-text'
            }`}
          >
            {t(`admin:${day}`)}
          </button>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        {!readOnly && (
        <button
          onClick={handleAutoAssign}
          data-testid="auto-assign"
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
        >
          <Sparkles className="w-5 h-5" />
          {t('admin:autoAssign')}
        </button>
        )}
        <button
          onClick={handleExport}
          data-testid="export-excel"
          className="flex items-center gap-2 px-6 py-3 bg-success text-dark-bg rounded-lg hover:bg-success-dark font-medium transition-colors"
        >
          <Download className="w-5 h-5" />
          {t('admin:exportExcel')}
        </button>

        {/* Publish / Unpublish Button */}
        {readOnly ? null : publishedDays.includes(selectedDay) ? (
          <button
            onClick={() => setPublished(false)}
            data-testid="unpublish"
            className="flex items-center gap-2 px-6 py-3 bg-danger/80 text-white rounded-lg hover:bg-danger font-medium transition-colors"
          >
            <EyeOff className="w-5 h-5" />
            {t('admin:unpublish')}
          </button>
        ) : (
          <button
            onClick={() => setPublished(true)}
            data-testid="publish"
            className="flex items-center gap-2 px-6 py-3 bg-accent/80 text-dark-bg rounded-lg hover:bg-accent font-medium transition-colors"
          >
            <Globe className="w-5 h-5" />
            {t('admin:publish')}
          </button>
        )}

        {/* Timezone Selector */}
        <TimezoneSelector value={timezone} onChange={setTimezone} />
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-danger" />
          <p className="text-danger">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-theme-dim">{t('ministry:form.loading')}</p>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Time Slots */}
            <div className="lg:col-span-3">
              <h3 className="text-lg font-semibold mb-4 text-accent">{t('admin:assigned')}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 max-h-[600px] overflow-y-auto">
                {timeSlots.map((slot) => {
                  const slotPlayers = assignments[slot] || [];
                  const hasPlayer = slotPlayers.length > 0;
                  return (
                    <DroppableSlot
                      key={slot}
                      slotId={slot}
                      displayTime={getSlotDisplayTime(slot, timezone)}
                      isOver={overSlotId === slot}
                      hasPlayer={hasPlayer && activePlayer?.player_id !== slotPlayers[0]?.player_id}
                      sharedNote={sharedBoundary?.slot === slot ? sharedBoundary.note : null}
                    >
                      <div className="space-y-2">
                        {slotPlayers.slice(0, 1).map((player) => (
                          <DraggablePlayer
                            key={`player-${player.player_id}-${slot}`}
                            player={player}
                            sourceSlot={slot}
                            onToggleLock={readOnly ? undefined : handleToggleLock}
                            timezone={timezone}
                            disabled={readOnly}
                          />
                        ))}
                      </div>
                    </DroppableSlot>
                  );
                })}
              </div>
            </div>

            {/* Unassigned Players */}
            <div className="lg:col-span-1">
              <h3 className="text-lg font-semibold mb-4 text-accent">
                {t('admin:unassigned')} ({unassignedPlayers.length})
              </h3>
              <DroppableUnassigned isOver={overSlotId === 'unassigned'}>
                <div className="space-y-2">
                  {[...unassignedPlayers].sort((a, b) => (b.points ?? 0) - (a.points ?? 0)).map((player) => (
                    <div key={`player-${player.player_id}-unassigned`}>
                      <DraggablePlayer
                        player={player}
                        sourceSlot="unassigned"
                        timezone={timezone}
                        disabled={readOnly}
                      />
                      {player.preferred_times && player.preferred_times.length > 0 && (
                        <div className="text-xs text-theme-dim mt-1 pl-2">
                          {t('admin:wants')}: {player.preferred_times.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {unassignedPlayers.length === 0 && !activePlayer && (
                  <p className="text-theme-dim text-sm text-center mt-8">
                    {t('admin:allAssigned')}
                  </p>
                )}
              </DroppableUnassigned>
            </div>
          </div>

          {/* Drag overlay - shows a floating copy of the card while dragging */}
          <DragOverlay>
            {activePlayer ? (
              <PlayerCard player={activePlayer} />
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      <div className="mt-6 p-4 bg-accent/10 border border-accent/30 rounded-lg">
        <p className="text-sm text-accent">
          <strong>{t('admin:tip')}:</strong> {t('admin:dragToAssign')}. {t('admin:dragTip')}
        </p>
      </div>
    </div>
  );
}
