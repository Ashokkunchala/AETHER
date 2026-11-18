# AETHER reviewed mentor review prompts

This adds one narrow delivery step for deep-mentor spaced review: after the
owner reviews the exact lesson and timestamp, AETHER can place one reminder in
the existing local backend reminder store. It is not automatic learning,
semantic grading or a guaranteed notification.

## Use

The registered tool is:

```text
mentor_deep_schedule_review_prompt(
  lesson_id="python-1",
  due_at="2026-11-18T19:30:00+05:30"
)
```

`lesson_id` must be one exact ID from `mentor_deep_catalog`. `due_at` must be
one ISO timestamp with an explicit UTC offset, in the future and no more than
31 days ahead. The reminder title names the exact lesson and cannot be replaced
with arbitrary text by the caller.

The existing backend database must already be initialized. This tool opens it
read/write, checks the existing `reminders` schema and inserts one uncompleted,
non-recurring row. It does not create or migrate an unrelated database. The
same exact title/timestamp is deduplicated, including concurrent identical
requests. The response includes the reminder ID, lesson title, chosen time,
current deep-progress next-review value when one exists and the lesson source.

## Boundaries

- Creating the local row is not a sent push, Windows toast, Android
  notification, calendar event or email. Existing notification workers need the
  same reachable backend and their separate token/TLS/permission setup; delivery
  is best-effort, not exact.
- The reminder can be reviewed, completed or deleted with the existing reminder
  controls. No recurrence, catch-up, automatic practice session or follow-up
  prompt is created.
- The deep-mentor progress table is read only for context and is not rewritten.
  Scheduling a reminder does not mark review complete, extend a streak, grade
  reasoning or establish mastery.
- The registry requires fresh confirmation for this MEDIUM-risk local write;
  auto/always approval is refused and the emergency stop still blocks it.
- Tests use temporary databases and mocked time-independent future timestamps.
  No real reminder, device notification, provider or user data was touched.

Related guides: [expanded mentor tracks](MENTOR-EXPANDED-TRACKS.md),
[deep-mentor rubric signals](MENTOR-RUBRIC-SIGNALS.md) and
[mentor activity](MENTOR-ACTIVITY.md).
