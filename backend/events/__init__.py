"""Event registry. The set of event keys is fixed: ministry, tyrant, svs, tal.

Each event provides an ``EventSpec``. Core modules (rounds, applications) call
these hooks so they stay event-agnostic. Ministry and tyrant override the hooks;
svs uses the generic spec until its phase lands (free-form JSON answers);
tal has no rounds yet ("coming soon").
"""
from core.errors import ApiError, not_found, validation_error

EVENT_KEYS = ('ministry', 'tyrant', 'svs', 'tal')


class EventSpec:
    key = None
    has_rounds = True
    # Profile fields that must be non-empty (after merging) when applying.
    required_profile_fields = ('game_name',)

    def default_settings(self):
        return {}

    def validate_settings(self, incoming, current):
        """Merge partial ``incoming`` settings into ``current`` and return the validated result."""
        if not isinstance(incoming, dict):
            raise validation_error('settings must be an object', 'settings')
        merged = dict(current)
        merged.update(incoming)
        return merged

    def carry_over_settings(self, previous):
        """Settings a new round inherits from the previous one (start-new-round)."""
        return dict(previous)

    def public_settings(self, settings):
        return dict(settings)

    def validate_profile(self, fields, existing=None):
        """Event-specific checks on the (already core-validated) profile fields sent with an
        application, e.g. tyrant's troop-level structure. Returns the fields to store."""
        return fields

    def validate_answers(self, answers, round_, existing=None):
        """Validate/normalise answers. ``existing``: the answers currently stored for this
        application (None when new), so legacy values can be accepted when re-sent unchanged."""
        if answers is None:
            answers = {}
        if not isinstance(answers, dict):
            raise validation_error('answers must be an object', 'answers')
        import json
        if len(json.dumps(answers)) > 50000:
            raise validation_error('answers is too large', 'answers')
        return answers

    def decorate_application(self, app, round_):
        """Add event-specific computed fields (e.g. points) to an admin application dict."""
        return app

    def on_settings_changed(self, db, round_, old, new):
        """Hook after an admin changes round settings. Return extra response fields."""
        return {}

    def on_application_deleted(self, db, round_id, player_id):
        pass

    def export_round(self, round_):
        raise ApiError(400, 'EXPORT_NOT_SUPPORTED', f'Export is not available for {self.key}')


class GenericEvent(EventSpec):
    def __init__(self, key, has_rounds=True):
        self.key = key
        self.has_rounds = has_rounds


_REGISTRY = {}


def register(spec):
    assert spec.key in EVENT_KEYS, spec.key
    _REGISTRY[spec.key] = spec


def get_event(key, need_rounds=True):
    spec = _REGISTRY.get(key)
    if spec is None:
        raise not_found(f'Unknown event: {key}', code='UNKNOWN_EVENT')
    if need_rounds and not spec.has_rounds:
        raise ApiError(400, 'EVENT_HAS_NO_ROUNDS', f'Event {key} has no rounds yet')
    return spec


def all_events():
    return [_REGISTRY[k] for k in EVENT_KEYS if k in _REGISTRY]


def register_defaults():
    from events.ministry.logic import MinistryEvent
    register(MinistryEvent())
    from events.tyrant.logic import TyrantEvent
    register(TyrantEvent())
    register(GenericEvent('svs'))
    register(GenericEvent('tal', has_rounds=False))
