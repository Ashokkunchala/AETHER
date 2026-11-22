"""Opt-in local resource alerts and backend-driven daily briefings.

No remote messages, push notifications, cleanup or other remediation actions.
"""
from __future__ import annotations

import math
import os
import re
import sqlite3
import time
from pathlib import Path

_BUILTIN_METRICS = ('cpu', 'memory', 'disk', 'battery')
_CUSTOM_METRIC = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')
_DIRECTIONS = ('above', 'below')


class ProactiveStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get('AETHER_PROACTIVE_DB') or Path.home() / '.aether' / 'proactive.db')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS alert_rules (
                    metric TEXT PRIMARY KEY, threshold REAL NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS resource_alerts (
                    id INTEGER PRIMARY KEY, created REAL NOT NULL, metric TEXT NOT NULL,
                    value REAL NOT NULL, threshold REAL NOT NULL, state TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS proactive_settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
            ''')
        with self.connect() as db:
            cols = {row[1] for row in db.execute('PRAGMA table_info(resource_alerts)')}
            if 'quiet' not in cols:
                db.execute('ALTER TABLE resource_alerts ADD COLUMN quiet INTEGER NOT NULL DEFAULT 0')
            if 'details' not in cols:
                db.execute('ALTER TABLE resource_alerts ADD COLUMN details TEXT')
            rule_cols = {row[1] for row in db.execute('PRAGMA table_info(alert_rules)')}
            if 'kind' not in rule_cols:
                db.execute("ALTER TABLE alert_rules ADD COLUMN kind TEXT NOT NULL DEFAULT 'builtin'")
            if 'direction' not in rule_cols:
                db.execute("ALTER TABLE alert_rules ADD COLUMN direction TEXT NOT NULL DEFAULT ''")
            db.execute(
                'CREATE TABLE IF NOT EXISTS custom_samples ('
                'id INTEGER PRIMARY KEY, created REAL NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL)')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    # -------------------------------------------------- user switches
    def _setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute('SELECT value FROM proactive_settings WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default

    def _set(self, key, value):
        with self.connect() as db:
            db.execute('INSERT INTO proactive_settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))

    def set_paused(self, paused: bool):
        if type(paused) is not bool:
            raise ValueError('paused must be a boolean.')
        self._set('paused', '1' if paused else '0')
        return {'paused': paused,
                'notice': 'While paused, no metric is sampled or recorded and no alert is created. Existing rules, alerts and schedules are unchanged; resume to continue. This does not affect saved briefing schedules or any other feature.'}

    def set_quiet_hours(self, start: str | None = None, end: str | None = None):
        import re
        if start is None and end is None:
            self._set('quiet_start', '')
            self._set('quiet_end', '')
            return {'quiet_hours': None, 'notice': 'Quiet hours cleared.'}
        pattern = re.compile(r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
        if not isinstance(start, str) or not isinstance(end, str) or not pattern.fullmatch(start) or not pattern.fullmatch(end) or start == end:
            raise ValueError('Quiet hours need distinct start and end as HH:MM 24-hour local time, or both null to clear.')
        self._set('quiet_start', start)
        self._set('quiet_end', end)
        return {'quiet_hours': {'start': start, 'end': end},
                'notice': 'Alerts triggered inside quiet hours are recorded and flagged quiet instead of noisy; nothing is hidden or deleted. Local server clock.'}

    def set_throttle(self, seconds: int):
        if type(seconds) is not int or not 0 <= seconds <= 3600:
            raise ValueError('Throttle must be whole seconds from 0 to 3600; 0 disables it.')
        self._set('throttle_seconds', str(seconds))
        return {'throttle_seconds': seconds,
                'notice': 'Repeated trigger events for the same metric inside the window update state without recording another alert. Recovery events always record. Crossings during the window are not shown later.'}

    def switches(self):
        start, end = self._setting('quiet_start', ''), self._setting('quiet_end', '')
        return {'paused': self._setting('paused', '0') == '1',
                'quiet_hours': {'start': start, 'end': end} if start and end else None,
                'throttle_seconds': int(self._setting('throttle_seconds', '0'))}

    def _quiet_now(self, now):
        start, end = self._setting('quiet_start', ''), self._setting('quiet_end', '')
        if not start or not end:
            return False
        current = time.strftime('%H:%M', time.localtime(now))
        if start < end:
            return start <= current < end
        return current >= start or current < end  # overnight window

    def update_alert_details(self, alert_id: int, details: str):
        if type(alert_id) is not int or alert_id < 1 or not isinstance(details, str) or not 1 <= len(details) <= 4000:
            raise ValueError('Valid alert ID and bounded details required.')
        with self.connect() as db:
            db.execute('UPDATE resource_alerts SET details=? WHERE id=?', (details, alert_id))

    def configure(self, metric: str, threshold: float, enabled: bool = False):
        if metric not in _BUILTIN_METRICS:
            raise ValueError('Metric must be cpu, memory, disk or battery.')
        if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 1 <= threshold <= 100:
            raise ValueError('Threshold must be a finite percentage from 1 to 100.')
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean.')
        direction = 'below' if metric == 'battery' else 'above'
        with self.connect() as db:
            db.execute("INSERT INTO alert_rules(metric,threshold,enabled,kind,direction) VALUES (?,?,?,'builtin',?) ON CONFLICT(metric) DO UPDATE SET threshold=excluded.threshold,enabled=excluded.enabled,active=0,kind='builtin',direction=excluded.direction", (metric, threshold, int(enabled), direction))
        return {'metric': metric, 'threshold': threshold, 'enabled': enabled,
                'notice': 'Local alerts while the backend is running, roughly once a minute. Battery alerts below threshold; other metrics at or above. No desktop or phone notification delivery.'}

    def configure_custom(self, metric: str, threshold: float, direction: str = 'above', enabled: bool = False):
        """A user-defined threshold rule over figures the user supplies, e.g. a cost limit."""
        if not isinstance(metric, str) or not _CUSTOM_METRIC.fullmatch(metric) or metric in _BUILTIN_METRICS:
            raise ValueError('Custom metric names must be 1-32 chars of lowercase letters, digits or underscores, start with a letter, and not reuse a built-in metric name.')
        if type(threshold) not in (int, float) or isinstance(threshold, bool) or not math.isfinite(threshold) or not 0 < threshold <= 1e12:
            raise ValueError('Threshold must be a finite positive number up to 1e12.')
        if direction not in _DIRECTIONS:
            raise ValueError("Direction must be 'above' (trigger at or above the threshold) or 'below' (trigger below it).")
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean.')
        with self.connect() as db:
            db.execute("INSERT INTO alert_rules(metric,threshold,enabled,kind,direction) VALUES (?,?,?,'custom',?) ON CONFLICT(metric) DO UPDATE SET threshold=excluded.threshold,enabled=excluded.enabled,active=0,kind='custom',direction=excluded.direction", (metric, threshold, int(enabled), direction))
        return {'metric': metric, 'threshold': threshold, 'direction': direction, 'enabled': enabled,
                'notice': 'Custom metrics are never sampled automatically and nothing is fetched from any provider. Supply a figure with proactive_record_sample whenever you have one (for example a cost total you read from your provider console); the crossing is evaluated at that moment with the same hysteresis, throttle, quiet-hours and pause rules as built-in metrics.'}

    def rules(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM alert_rules ORDER BY metric')]

    def _apply_rule(self, db, rule, value, now, quiet, throttle):
        """Crossing evaluation shared by sampled and user-supplied metrics. Returns the event or None."""
        threshold = rule['threshold']
        direction = rule['direction'] or ('below' if rule['metric'] == 'battery' else 'above')
        # Built-ins keep the original two-point hysteresis; custom metrics use 2% of the threshold.
        hysteresis = 2 if rule['kind'] == 'builtin' else max(abs(threshold) * 0.02, 1e-9)
        if direction == 'below':
            triggered = value < threshold
            recovered = value >= (min(100, threshold + hysteresis) if rule['metric'] == 'battery' else threshold + hysteresis)
        else:
            triggered = value >= threshold
            recovered = value <= max(0, threshold - hysteresis)
        if not rule['active'] and triggered:
            state, active = 'triggered', 1
        elif rule['active'] and recovered:
            state, active = 'recovered', 0
        else:
            return None
        db.execute('UPDATE alert_rules SET active=? WHERE metric=?', (active, rule['metric']))
        if state == 'triggered' and throttle > 0:
            recent = db.execute(
                "SELECT created FROM resource_alerts WHERE metric=? AND state='triggered' AND created>? ORDER BY id DESC LIMIT 1",
                (rule['metric'], now - throttle),
            ).fetchone()
            if recent:
                # State tracked; recording suppressed as spam. Not shown later.
                return None
        cur = db.execute('INSERT INTO resource_alerts(created,metric,value,threshold,state,quiet) VALUES (?,?,?,?,?,?)', (now, rule['metric'], value, threshold, state, int(quiet and state == 'triggered')))
        return {'id': cur.lastrowid, 'metric': rule['metric'], 'value': value, 'threshold': threshold, 'state': state, 'quiet': bool(quiet and state == 'triggered')}

    def evaluate(self, samples: dict[str, float], now: float | None = None):
        """Atomically record crossings, not repeats. Missing metrics stay unknown."""
        now = time.time() if now is None else now
        if self._setting('paused', '0') == '1':
            return []
        quiet = self._quiet_now(now)
        throttle = int(self._setting('throttle_seconds', '0'))
        events = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for rule in db.execute("SELECT * FROM alert_rules WHERE enabled=1 AND kind='builtin'").fetchall():
                value = samples.get(rule['metric'])
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 100:
                    continue
                event = self._apply_rule(db, rule, value, now, quiet, throttle)
                if event:
                    events.append(event)
            db.execute('DELETE FROM resource_alerts WHERE id NOT IN (SELECT id FROM resource_alerts ORDER BY id DESC LIMIT 500)')
        return events

    def record_sample(self, metric: str, value: float, now: float | None = None):
        """Supply the current figure for a user-defined custom metric; evaluate the crossing now."""
        now = time.time() if now is None else now
        if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1e15:
            raise ValueError('Sample value must be a finite number from 0 to 1e15.')
        if self._setting('paused', '0') == '1':
            return {'recorded': False, 'paused': True,
                    'notice': 'Proactive checks are paused, so nothing was recorded. Resume with proactive_set_paused first.'}
        quiet = self._quiet_now(now)
        throttle = int(self._setting('throttle_seconds', '0'))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rule = db.execute("SELECT * FROM alert_rules WHERE metric=? AND kind='custom'", (metric,)).fetchone()
            if rule is None:
                raise ValueError('No custom metric with that name. Create one with proactive_configure_custom first.')
            db.execute('INSERT INTO custom_samples(created,metric,value) VALUES (?,?,?)', (now, metric, value))
            db.execute('DELETE FROM custom_samples WHERE id NOT IN (SELECT id FROM custom_samples ORDER BY id DESC LIMIT 500)')
            event = self._apply_rule(db, rule, value, now, quiet, throttle) if rule['enabled'] else None
            enabled = bool(rule['enabled'])
        result = {'recorded': True, 'metric': metric, 'value': value}
        if event:
            result['alert'] = event
        elif enabled:
            result['notice'] = 'No crossing; the rule state is unchanged.'
        else:
            result['notice'] = 'Sample recorded; the rule is disabled, so no alert is evaluated.'
        return result

    def samples(self, metric: str | None = None):
        with self.connect() as db:
            if metric is None:
                rows = db.execute('SELECT * FROM custom_samples ORDER BY id DESC LIMIT 100').fetchall()
            else:
                rows = db.execute('SELECT * FROM custom_samples WHERE metric=? ORDER BY id DESC LIMIT 100', (metric,)).fetchall()
        return [dict(row) for row in rows]

    def alerts(self, unacknowledged_only: bool = False):
        if type(unacknowledged_only) is not bool:
            raise ValueError('unacknowledged_only must be a boolean.')
        with self.connect() as db:
            query = 'SELECT * FROM resource_alerts'
            if unacknowledged_only:
                query += ' WHERE acknowledged=0'
            return [dict(row) for row in db.execute(query + ' ORDER BY id DESC LIMIT 100')]

    def acknowledge(self, alert_id: int):
        if type(alert_id) is not int or alert_id < 1:
            raise ValueError('Choose an integer alert ID from proactive_alerts.')
        with self.connect() as db:
            changed = db.execute('UPDATE resource_alerts SET acknowledged=1 WHERE id=?', (alert_id,)).rowcount
        if not changed:
            raise ValueError('No alert with that ID.')
        return {'acknowledged': alert_id}


def _sample_metrics(metrics):
    import psutil
    values = {}
    for metric in metrics:
        try:
            if metric == 'cpu':
                values[metric] = psutil.cpu_percent(interval=0.1)
            elif metric == 'memory':
                values[metric] = psutil.virtual_memory().percent
            elif metric == 'disk':
                values[metric] = psutil.disk_usage(Path.home().anchor or '/').percent
            elif metric == 'battery':
                battery = psutil.sensors_battery()
                if battery is not None and not battery.power_plugged:
                    values[metric] = battery.percent
        except (OSError, AttributeError, RuntimeError):
            continue
    return values


class ProactiveRunner:
    """A tick invoked by the existing backend scheduler, at most once a minute."""
    def __init__(self, sample_fn=_sample_metrics, clock=time.monotonic):
        self.sample_fn, self.clock = sample_fn, clock
        self.next_check = 0.0

    def tick(self):
        now = self.clock()
        if now < self.next_check:
            return
        self.next_check = now + 60
        # Do not create a resource database or inspect metrics until configured.
        path = Path(os.environ.get('AETHER_PROACTIVE_DB') or Path.home() / '.aether' / 'proactive.db')
        if path.is_file():
            store = ProactiveStore(path)
            enabled = [row['metric'] for row in store.rules() if row['enabled']]
            if enabled:
                events = store.evaluate(self.sample_fn(enabled))
                for event in events:
                    if event.get('state') == 'triggered' and event.get('metric') == 'cpu':
                        try:
                            from aether.proactive_insights import cpu_offenders
                            import json
                            store.update_alert_details(event['id'], json.dumps(cpu_offenders(limit=5), separators=(',', ':')))
                        except Exception:
                            pass  # Attribution is best-effort; the alert stands without it.
        # Existing saved briefing schedules are explicit opt-in. No job is added.
        from aether.briefing_schedule import BriefingScheduler
        from aether.personal import PersonalStore
        personal_path = Path.home() / '.aether' / 'personal.db'
        if personal_path.is_file():
            BriefingScheduler(store=PersonalStore(personal_path)).run_due()


def register_proactive_tools(registry):
    from aether.tools.registry import Risk, Tool
    def handler_for(method):
        def handler(**kwargs):
            return {'success': True, 'data': getattr(ProactiveStore(), method)(**kwargs)}
        return handler
    definitions = [
        ('proactive_configure', 'Create or update a local resource alert rule. Disabled unless enabled=true. Checks roughly once a minute while backend runs. No message or OS notifications.', 'configure', Risk.LOW,
         {'metric': {'type': 'string', 'enum': ['cpu', 'memory', 'disk', 'battery']}, 'threshold': {'type': 'number'}, 'enabled': {'type': 'boolean'}}, ['metric', 'threshold']),
        ('proactive_rules', 'List saved resource alert rules and whether they are enabled.', 'rules', Risk.SAFE, {}, []),
        ('proactive_alerts', 'Read the local resource alert inbox, including recovery events. No push notification delivery.', 'alerts', Risk.SAFE, {'unacknowledged_only': {'type': 'boolean'}}, []),
        ('proactive_acknowledge', 'Mark a local resource alert reviewed by integer alert ID.', 'acknowledge', Risk.LOW, {'alert_id': {'type': 'integer'}}, ['alert_id']),
        ('proactive_set_paused', 'Turn all proactive resource checks off (or back on). Existing rules and alerts are unchanged; nothing is sampled or recorded while paused.', 'set_paused', Risk.LOW, {'paused': {'type': 'boolean'}}, ['paused']),
        ('proactive_quiet_hours', 'Set or clear quiet hours (HH:MM local). Alerts triggered inside the window are recorded flagged quiet; nothing is hidden or deleted.', 'set_quiet_hours', Risk.LOW, {'start': {'type': 'string', 'description': 'HH:MM 24-hour local, or omit both to clear'}, 'end': {'type': 'string'}}, []),
        ('proactive_set_throttle', 'Set the minimum seconds (0-3600, 0 disables) between recorded trigger alerts for the same metric. Recovery events always record.', 'set_throttle', Risk.LOW, {'seconds': {'type': 'integer'}}, ['seconds']),
        ('proactive_switches', 'Show the pause switch, quiet hours and throttle currently in effect.', 'switches', Risk.SAFE, {}, []),
        ('proactive_configure_custom', 'Create or update a user-defined threshold rule over figures you supply yourself (for example a cost limit). Never sampled automatically; nothing is fetched from any provider. Disabled unless enabled=true.', 'configure_custom', Risk.LOW,
         {'metric': {'type': 'string', 'description': 'Lowercase letters, digits, underscores; not a built-in metric name'}, 'threshold': {'type': 'number'}, 'direction': {'type': 'string', 'enum': ['above', 'below']}, 'enabled': {'type': 'boolean'}}, ['metric', 'threshold']),
        ('proactive_record_sample', 'Supply the current figure for a custom metric you defined. The crossing is evaluated immediately with the same throttle, quiet-hours and pause rules as built-in metrics.', 'record_sample', Risk.LOW,
         {'metric': {'type': 'string'}, 'value': {'type': 'number'}}, ['metric', 'value']),
        ('proactive_samples', 'List recent figures you supplied for custom metrics, newest first.', 'samples', Risk.SAFE, {'metric': {'type': 'string'}}, []),
    ]
    for name, description, method, risk, properties, required in definitions:
        registry.register(Tool(name=name, description=description, parameters={'type': 'object', 'properties': properties, 'required': required}, handler=handler_for(method), risk=risk, category='proactive'))
    from aether.proactive_insights import register_proactive_insights
    register_proactive_insights(registry)
