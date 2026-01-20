# AI Coding Agent Instructions for Alarm System

## Project Overview
A desktop alarm application built with Python supporting both GUI (Tkinter) and CUI (command-line) modes. The system manages recurring alarms with complex scheduling rules, sound playback, and state persistence.

## Architecture: Data Flow & Service Boundaries

### Core Data Model (alarm_model.py)
Three parallel dataclass hierarchies handle data at different stages:

1. **AlarmJson / AlarmStateJson** - JSON-serializable format for persistence
   - `AlarmJson`: alarm settings (id, name, date, time, repeat rules, sound, snooze config)
   - `AlarmStateJson`: transient state (snooze_until, snooze_count, triggered, last_fired_at)
   - Properties use underscore prefix (`_snoozed_until`) with @property getters for immutability

2. **AlarmInternal / AlarmStateInternal** - In-memory runtime format
   - Uses `datetime` objects instead of strings
   - State properties include `last_fired_at` to prevent duplicate triggers within 5 seconds
   - All state changes pass through manager before persistence

3. **AlarmInternal** - Combined settings + state in single class
   - Stores both alarm configuration AND runtime state
   - Managed exclusively by `AlarmManager` (never directly modified by UI/CUI)

### Service Boundaries

**AlarmStorage** (alarm_storage.py)
- **Single responsibility**: JSON file I/O only
- Loads/saves AlarmJson[], AlarmStateJson[] from `alarms.json` and `standby.json`
- Never converts data types—passes raw dicts to AlarmLoader
- Handles backup creation (max 3 backups in `backup/` directory)

**AlarmLoader** (alarm_loader.py)
- **Single responsibility**: Dataclass conversion between JSON ↔ Internal formats
- `alarm_json_to_internal()`: Merges AlarmJson + AlarmStateJson into AlarmInternal
- `alarm_internal_to_json()`: Splits AlarmInternal back to separate AlarmJson + AlarmStateJson
- Datetime conversions: `"YYYY-MM-DD HH:MM"` or ISO8601 (both supported via `.replace(" ", "T")`)

**AlarmScheduler** (alarm_scheduler.py)
- Computes next trigger time based on repeat rules
- Methods: `get_next_time(alarm, now)` → delegates to `_next_daily()`, `_next_weekly()`, `_next_monthly()`, `_next_custom()`
- Single-occurrence alarms return base time if future, else None

**AlarmManager** (alarm_manager.py)
- **Central coordinator**: orchestrates all state changes
- Loads via `Storage → Loader → internal list`
- Methods: `add_alarm()`, `update_alarm()`, `delete_alarm()`, `trigger()`, `snooze()`, `reset()`
- Listeners (observer pattern): GUI/CUI register callbacks via `register_listener()` for state change notifications
- **PyInstaller-aware**: uses `get_base_dir()` for path resolution (EXE vs Python)

**AlarmRepeatRules** (alarm_repeat_rules.py)
- Rule checking functions: `check_daily_rule()`, `check_weekly_rule()`, `check_monthly_rule()`, `check_custom_rule()`
- Validates repeat conditions + time matching + duplicate-fire prevention (5-second window on `_last_fired_at`)

## Key Patterns & Conventions

### 1. Enum-like Constants in constants.py
Use nested dicts for bidirectional mapping:
```python
REPEAT_INTERNAL = {"単発": "none", "毎日": "daily", "毎週": "weekly_1"}
REPEAT_DISPLAY = {v: k for k, v in REPEAT_INTERNAL.items()}
WEEKDAY_LABELS = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAY_TO_INDEX = {label: i for i, label in enumerate(WEEKDAY_LABELS)}
```
When converting UI display ↔ internal representation, always use these dicts.

### 2. Datetime Handling
- JSON storage: `date` (YYYY-MM-DD) + `time` (HH:MM) as separate fields
- Internal: combined `datetime_` object
- Conversion in AlarmLoader: handles both `"2025-01-15 10:30"` and ISO8601 `"2025-01-15T10:30"` via `.replace(" ", "T")`

### 3. State Management: Snooze + Trigger Logic
- `_snooze_count`: increments each snooze; resets when alarm fires
- `_snoozed_until`: blocks triggers until this datetime passes
- `_triggered`: one-time flag per scheduled occurrence
- `_last_fired_at`: Unix-like check for duplicate prevention (if current_time - last_fired < 5s, skip)
- Snooze limit enforced via `snooze_limit` field

### 4. Listener Pattern (Observer)
```python
# Manager registers listeners:
manager.register_listener(gui_callback)
manager.register_listener(cui_callback)

# When state changes:
manager.notify_listeners(alarm_dict, "trigger")  # UI updates display
```

### 5. PyInstaller Compatibility
- Always use `AlarmManager.get_base_dir()` for file paths, not hardcoded paths
- Detects frozen state via `getattr(sys, 'frozen', False)`

## Common Workflows

### Adding/Updating Alarms
1. UI/CUI creates dict from form inputs
2. Convert display values → internal (e.g., "毎日" → "daily")
3. Call `manager.add_alarm(name, datetime_, repeat, **kwargs)` or `manager.update_alarm(id, ...)`
4. Manager converts to AlarmInternal → Storage → disk
5. Manager notifies listeners; UI/CUI refresh display

### Triggering Alarms
1. Scheduler background thread calls `manager.should_fire()` for each alarm
2. `should_fire()` checks: enabled? repeat rule matches? snooze expired?
3. If true: `manager.trigger(alarm_id)` → sets `_triggered=True`, plays sound
4. Listeners notified → UI shows notification

### Snoozing
1. User clicks snooze button → `manager.snooze(alarm_id, snooze_minutes)`
2. Sets `_snoozed_until = now + timedelta(minutes=snooze_minutes)` and increments `_snooze_count`
3. Sound stops immediately (via `AlarmPlayer.stop()`)
4. Next `should_fire()` check will skip until `_snoozed_until` passes

### Testing
- `alarm_test.py`: unit tests for manager, loader, scheduler
- Run: `python alarm_test.py` from workspace root
- Test files use in-memory dicts; no file I/O by default

## External Dependencies
- **pygame**: audio playback (fallback silent on init failure)
- **Tkinter**: GUI framework (stdlib)
- **dataclasses**: alarm data models (stdlib, Python 3.7+)

## File Locations & Configuration
- Alarms data: `alarms.json` (list of AlarmJson dicts under `{"alarms": [...]}`)
- Standby state: `standby.json` (list of AlarmStateJson under `{"standby": [...]}`)
- User config: `config.json` (GUI/CUI preferences, window positions)
- Backups: `backup/alarms_YYYYMMDDHHMMSS.json` (auto-created on save)
- Sounds: `sound/` directory (e.g., `Alarm01.wav` in DEFAULT_SOUND)

## When Extending

### Adding a New Repeat Rule
1. Define rule in constants.py (e.g., `"bi-monthly": "bimonthly"`)
2. Implement `check_bimonthly_rule()` in alarm_repeat_rules.py
3. Add `_next_bimonthly()` method to AlarmScheduler
4. Register in `AlarmScheduler.get_next_time()` dispatch

### Modifying AlarmInternal/AlarmJson
1. Update dataclass definition in alarm_model.py
2. Add conversion logic in AlarmLoader (`alarm_json_to_internal()` + `alarm_internal_to_json()`)
3. If new state field: also update AlarmStateJson + AlarmStateInternal
4. Test round-trip: `json → internal → json` preserves data

### Adding UI/CUI Features
1. Always call manager methods (never mutate alarms directly)
2. Register listener callback with manager BEFORE loading
3. Update display in callback, not in direct method call
4. Use constants.py mappings for label/value conversions

---
**Last updated**: 2025-01-13 | **Python**: 3.10+ | **Author**: F.Kurokawa
