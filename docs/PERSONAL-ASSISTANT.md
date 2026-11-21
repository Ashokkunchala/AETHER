# AETHER Personal Assistant: Daily Life Management

How each requested ability maps to AETHER's local-first APIs. Everything below
stores data in the local SQLite database (`AETHER_DB_PATH`) behind the device
bearer token. Nothing is sent, booked, cancelled or paid without an explicit
in-app approval; provider actions go through the approval queue and expire
after 5 minutes.

Start here: `GET /api/life/dashboard` returns today's priorities, tasks,
calendar drafts, reminders, unread notifications, month spending and
integration status in one read-only call.

## Ability map

| Ability | Where it lives | Notes |
| --- | --- | --- |
| Daily planning | `POST /api/life/ai-plan`, `GET /api/life/reports/today` | AI plan is a proposal only (`saved: false`); the deterministic report never invents meetings. |
| Reminders | `POST /api/reminders`, `GET /api/reminders`, `POST /api/reminders/{id}/complete` | Recurrence: none/daily/weekly/monthly. Due reminders become cross-device notifications automatically. |
| Calendar | `POST /api/integrations/calendar/proposals`, `POST /api/integrations/approvals/{id}/approve` | Create, update and delete on Google Calendar, each only after explicit approval. Local drafts: `POST /api/life/events`. |
| To-do manager | `POST /api/life/tasks`, `PATCH /api/life/tasks/{id}`, `GET /api/life/tasks` | Priorities 1-5, statuses open/in_progress/done/postponed, timezone-aware due dates. |
| Notes | `POST /api/life/notes`, `GET /api/life/notes` | Kinds: personal, meeting, voice, work. Browser dictation is on the `/life` page. |
| Email | `GET /api/integrations/gmail/messages`, `POST /api/integrations/gmail/summarize`, `POST /api/integrations/gmail/drafts` + approval | Read and summarize need the Google connection (`GET /api/integrations/google/connect`). Sending happens only after approval of the exact draft. |
| WhatsApp | `POST /api/integrations/whatsapp/drafts` + approval | Requires the WhatsApp Cloud API settings. Nothing sends without approval. |
| Contacts | `GET /api/contacts/search` | Explicit read-only Google Contacts opt-in. No edits, merges or sends. |
| Travel | `POST /api/research/travel` | Source shortlists only; never quotes, bookings or payments. |
| Shopping | `POST /api/research/shopping` | Specification/price/warranty source shortlists; never purchases. |
| Document manager | `GET /api/documents/library`, `POST /api/documents/preview`, `POST /api/documents/summary`, `POST /api/documents/download` | Bounded to `DOCUMENT_ALLOWED_ROOTS`; secret-shaped files are excluded. Summaries are local extractive quotes, not AI interpretation. |
| Expense tracker | `POST /api/life/expenses`, `GET /api/life/expenses`, `GET /api/life/reports/expenses`, `GET /api/life/reports/expenses.csv` | Monthly and date-range reports. Currencies are always kept separate. |
| Personal dashboard | `GET /api/life/dashboard` | One read-only aggregation: priorities, tasks, drafts, reminders, alerts, spending, integrations. |
| Notifications | `GET /api/integrations/notifications`, Windows toast agent, Android poll | Laptop delivery via `app/windows_notifications.py`; mobile clients poll the same authenticated inbox. |

## Example conversations and the calls behind them

- "Aether, what are my plans today?" -> `GET /api/life/dashboard`
- "Remind me to pay my electricity bill tomorrow." -> `POST /api/reminders`
- "Summarize my important emails." -> `POST /api/integrations/gmail/summarize`
- "Prepare a weekly expense report." -> `GET /api/life/reports/expenses?start_date=...&end_date=...`
- "Find my latest resume." -> `GET /api/documents/library` then `POST /api/documents/preview`
- "Remind me about my interview at 3 PM." -> `POST /api/reminders` plus a calendar draft via `POST /api/life/events`
- "Prepare a shopping comparison for a new phone." -> `POST /api/research/shopping`

## Safety rules that apply everywhere

1. Sends, calendar changes, deletions of external records and any spending
   require an approval created from the exact fields and approved with the
   same credential within 5 minutes (`/api/integrations/approvals`).
2. Local calendar entries are drafts until approved into Google Calendar.
3. Expense logging records spending; it never pays or orders anything.
4. Research endpoints return unverified source shortlists, not final prices,
   stock, availability or bookings.
5. Credentials live in the server environment and the encrypted integration
   store, never in code, logs or responses.
