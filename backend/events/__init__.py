"""Event registry. The set of event keys is fixed: ministry, tyrant, svs, tal.

Each event provides an ``EventSpec``. Core modules (rounds, applications) call
these hooks so they stay event-agnostic. Ministry, tyrant and svs override the hooks;
tal has no rounds yet ("coming soon").
"""
from core.errors import ApiError, not_found, validation_error

EVENT_KEYS = ('ministry', 'tyrant', 'svs', 'tal')


class EventSpec:
    key = None
    has_rounds = True
    # Profile fields that must be non-empty (after merging) when applying.
    required_profile_fields = ('game_name',)
    # Profile fields this event does not ask: dropped from an application's profile BEFORE validation, so an old
    # client that still sends one is neither rejected nor allowed to change the shared profile through this event.
    ignored_profile_fields = ()

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

    def strip_ignored_profile_fields(self, profile):
        """The application's raw ``profile`` object without ``ignored_profile_fields`` (other shapes unchanged:
        core validation reports them)."""
        if isinstance(profile, dict) and self.ignored_profile_fields:
            return {k: v for k, v in profile.items() if k not in self.ignored_profile_fields}
        return profile

    # Profile fields an ADMIN must give when creating a sign-up for a player with no profile yet ("add player").
    admin_required_profile_fields = ('game_name',)

    def validate_profile(self, fields, existing=None, admin=False):
        """Event-specific checks on the (already core-validated) profile fields sent with an
        application, e.g. tyrant's troop-level structure. Returns the fields to store.
        ``admin``: an admin create/edit, which may leave optional values blank."""
        return fields

    def validate_answers(self, answers, round_, existing=None, admin=False):
        """Validate/normalise answers. ``existing``: the answers currently stored for this
        application (None when new), so legacy values can be accepted when re-sent unchanged.
        ``admin``: an admin create/edit ("add player"), which may leave answers a player must give blank."""
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
    from events.svs.logic import SvsEvent
    register(SvsEvent())
    register(GenericEvent('tal', has_rounds=False))
