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
import { Sparkles, Download, AlertCircle } from 'lucide-react';
import axios from 'axios';

interface AssignedPlayer {
  id: number;
  player_id: number;
  fid: string;
  game_name: string;
  points: number;
  time_slot?: string;
  avatar_image?: string;
  stove_lv?: number;
  stove_lv_content?: string;
  alliance?: string;
}

interface Assignments {
  [timeSlot: string]: AssignedPlayer[];
}

interface UnassignedPlayer extends AssignedPlayer {
  preferred_times: string[];
}

const DAY_TABS = [
  { key: 'monday', label: 'Monday - Construction' },
  { key: 'tuesday', label: 'Tuesday - Research' },
  { key: 'thursday', label: 'Thursday - Troop Training' },
];

// Generate time slots in 30-minute increments
const generateTimeSlots = () => {
  const slots = [];
  for (let hour = 0; hour < 24; hour++) {
    slots.push(`${hour.toString().padStart(2, '0')}:00`);
    slots.push(`${hour.toString().padStart(2, '0')}:30`);
  }
  return slots;
};

const PLAYER_CARD_CLASS = 'bg-accent/15 border-accent/40 text-accent';

// Draggable player card
function DraggablePlayer({ player, sourceSlot }: { player: AssignedPlayer; sourceSlot: string }) {
  const dragId = `player-${player.player_id}-${sourceSlot}`;
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: dragId,
    data: { player, sourceSlot },
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    opacity: isDragging ? 0.3 : 1,
  } : {
    opacity: isDragging ? 0.3 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`p-3 border-2 rounded-lg cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow ${PLAYER_CARD_CLASS}`}
    >
      <div className="flex items-center gap-2">
        <div className="relative flex-shrink-0">
          {player.avatar_image ? (
            <img
              src={player.avatar_image}
              alt=""
              className="w-8 h-8 rounded-full border border-accent/50"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent">
              {player.game_name.charAt(0).toUpperCase()}
            </div>
          )}
          {player.stove_lv_content && (
            <img
              src={player.stove_lv_content}
              alt={`Lv.${player.stove_lv}`}
              className="absolute -bottom-1 -right-1 w-4 h-4"
            />
          )}
        </div>
        <div className="min-w-0">
          <div className="font-medium truncate">{player.alliance && <span className="text-accent">[{player.alliance}]</span>} {player.game_name}</div>
          <div className="text-xs opacity-75">
            {player.fid} • {(player.points ?? 0).toLocaleString()} pts
          </div>
        </div>
      </div>
    </div>
  );
}

// Static player card (for overlay while dragging)
function PlayerCard({ player }: { player: AssignedPlayer }) {
  return (
    <div
      className={`p-3 border-2 rounded-lg shadow-lg ${PLAYER_CARD_CLASS}`}
    >
      <div className="flex items-center gap-2">
        <div className="relative flex-shrink-0">
          {player.avatar_image ? (
            <img
              src={player.avatar_image}
              alt=""
              className="w-8 h-8 rounded-full border border-accent/50"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent">
              {player.game_name.charAt(0).toUpperCase()}
            </div>
          )}
          {player.stove_lv_content && (
            <img
              src={player.stove_lv_content}
              alt={`Lv.${player.stove_lv}`}
              className="absolute -bottom-1 -right-1 w-4 h-4"
            />
          )}
        </div>
        <div className="min-w-0">
          <div className="font-medium truncate">{player.alliance && <span className="text-accent">[{player.alliance}]</span>} {player.game_name}</div>
          <div className="text-xs opacity-75">
            {player.fid} • {(player.points ?? 0).toLocaleString()} pts
          </div>
        </div>
      </div>
    </div>
  );
}

// Droppable time slot container
function DroppableSlot({ slotId, children, isOver, hasPlayer }: {
  slotId: string;
  children: React.ReactNode;
  isOver: boolean;
  hasPlayer: boolean;
}) {
  const { setNodeRef } = useDroppable({ id: `slot-${slotId}` });

  return (
    <div
      ref={setNodeRef}
      className={`border-2 border-dashed rounded-lg p-3 min-h-[100px] transition-colors ${
        isOver && !hasPlayer
          ? 'border-accent bg-accent/10'
          : isOver && hasPlayer
          ? 'border-danger bg-danger/10'
          : 'border-theme-border bg-dark-bg'
      }`}
    >
      <div className="font-semibold text-theme-dim mb-2">{slotId}</div>
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

export default function AssignmentManagement() {
  const { t } = useTranslation();
  const [selectedDay, setSelectedDay] = useState('monday');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [assignments, setAssignments] = useState<Assignments>({});
  const [unassignedPlayers, setUnassignedPlayers] = useState<UnassignedPlayer[]>([]);
  const [activePlayer, setActivePlayer] = useState<AssignedPlayer | null>(null);
  const [overSlotId, setOverSlotId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const timeSlots = generateTimeSlots();

  useEffect(() => {
    fetchAssignments();
  }, [selectedDay]);

  const fetchAssignments = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('adminToken');
      const response = await axios.get(`/api/admin/assignments/${selectedDay}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      // Enforce 1 player per slot on load
      const cleaned: Assignments = {};
      for (const [slot, players] of Object.entries(response.data as Assignments)) {
        cleaned[slot] = (players || []).slice(0, 1);
      }
      setAssignments(cleaned);
      setUnassignedPlayers([]);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to fetch assignments');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoAssign = async () => {
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('adminToken');
      const response = await axios.post(
        '/api/admin/assignments/auto-assign',
        { day: selectedDay },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setAssignments(response.data.assignments);
      setUnassignedPlayers(response.data.unassigned);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to auto-assign');
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
          // Move existing player to unassigned
          newUnassigned.push({ ...existingPlayer, time_slot: undefined, preferred_times: [] } as UnassignedPlayer);
          // Remove moved player from unassigned
          const idx = newUnassigned.findIndex((p) => p.player_id === movedPlayer.player_id);
          if (idx !== -1) newUnassigned.splice(idx, 1);
        } else {
          // Swap: put existing player in source slot
          newAssignments[sourceSlot] = [{ ...existingPlayer, time_slot: sourceSlot }];
        }

        // Put moved player in target slot
        newAssignments[targetSlot] = [{ ...movedPlayer, time_slot: targetSlot }];

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
      newUnassigned.push({ ...movedPlayer, time_slot: undefined, preferred_times: [] } as UnassignedPlayer);
    } else {
      newAssignments[targetSlot] = [{ ...movedPlayer, time_slot: targetSlot }];
    }

    setAssignments(newAssignments);
    setUnassignedPlayers(newUnassigned);
    saveAssignments(newAssignments);
  };

  const saveAssignments = async (assignmentsToSave: Assignments) => {
    try {
      const token = localStorage.getItem('adminToken');
      await axios.post(
        '/api/admin/assignments/update',
        {
          day: selectedDay,
          assignments: assignmentsToSave,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save assignments');
    }
  };

  const handleExport = async () => {
    try {
      const token = localStorage.getItem('adminToken');
      const response = await axios.get('/api/admin/export', {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'ministry_assignments.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      setError('Failed to export assignments');
    }
  };

  return (
    <div className="bg-dark-card rounded-xl border border-theme-border p-6">
      {/* Day Tabs */}
      <div className="flex gap-4 mb-6 border-b border-theme-border pb-2">
        {DAY_TABS.map((day) => (
          <button
            key={day.key}
            onClick={() => setSelectedDay(day.key)}
            className={`px-4 py-2 font-medium rounded-lg transition-colors ${
              selectedDay === day.key
                ? 'bg-accent text-dark-bg'
                : 'text-theme-dim hover:text-theme-text'
            }`}
          >
            {t(`admin.${day.key}`)}
          </button>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={handleAutoAssign}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
        >
          <Sparkles className="w-5 h-5" />
          {t('admin.autoAssign')}
        </button>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-6 py-3 bg-success text-dark-bg rounded-lg hover:bg-success-dark font-medium transition-colors"
        >
          <Download className="w-5 h-5" />
          {t('admin.exportExcel')}
        </button>
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
          <p className="text-theme-dim">{t('form.loading')}</p>
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
              <h3 className="text-lg font-semibold mb-4 text-accent">{t('admin.assigned')}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 max-h-[600px] overflow-y-auto">
                {timeSlots.map((slot) => {
                  const slotPlayers = assignments[slot] || [];
                  const hasPlayer = slotPlayers.length > 0;
                  return (
                    <DroppableSlot
                      key={slot}
                      slotId={slot}
                      isOver={overSlotId === slot}
                      hasPlayer={hasPlayer && activePlayer?.player_id !== slotPlayers[0]?.player_id}
                    >
                      <div className="space-y-2">
                        {slotPlayers.slice(0, 1).map((player) => (
                          <DraggablePlayer
                            key={`player-${player.player_id}-${slot}`}
                            player={player}
                            sourceSlot={slot}
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
                {t('admin.unassigned')} ({unassignedPlayers.length})
              </h3>
              <DroppableUnassigned isOver={overSlotId === 'unassigned'}>
                <div className="space-y-2">
                  {[...unassignedPlayers].sort((a, b) => (b.points ?? 0) - (a.points ?? 0)).map((player) => (
                    <div key={`player-${player.player_id}-unassigned`}>
                      <DraggablePlayer
                        player={player}
                        sourceSlot="unassigned"
                      />
                      {player.preferred_times && player.preferred_times.length > 0 && (
                        <div className="text-xs text-theme-dim mt-1 pl-2">
                          Wants: {player.preferred_times.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {unassignedPlayers.length === 0 && !activePlayer && (
                  <p className="text-theme-dim text-sm text-center mt-8">
                    {t('admin.allAssigned', 'All players assigned!')}
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
          <strong>Tip:</strong> {t('admin.dragToAssign')}. Drag players from time slots to the unassigned area to remove them from the schedule.
        </p>
      </div>
    </div>
  );
}
