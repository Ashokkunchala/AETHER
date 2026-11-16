# AETHER saved-data chat preview

The existing text-only chat stays unchanged. To opt in, run the enhanced backend
locally (`python run_enhanced.py`), open the usual browser UI and choose
**AETHER saved-data chat (opt-in)**. The page is also served at
`/static/tool-chat.html`. The minimal backend can serve the page but cannot issue
its tool-chat connection tickets; it explains that the enhanced backend is needed.

Enter an existing API or paired-device token and connect. The token is cleared
from the input after connection and is not stored in local/session storage. This
preview keeps its transcript only in the current page's memory. Disconnect or
cancel ends that assistant session; reconnecting does not resume its context.

The six tools read existing life-manager tasks, notes, expense rows and calendar
drafts, plus backend reminders and unexpired explicit memories. Each listing has
at most 50 records and text fields are clipped at 600 characters. These are not
complete-history or monthly-total tools. Expense currencies remain per row.
Calendar drafts are not confirmed events. Older CLI notes, expenses and commitments
are separate stores and are not silently merged or substituted.

The selected capability profile is bound to the one-use WebSocket ticket, not to
a changeable socket URL or chat instruction. Only the six named reader handlers
are registered for this profile. It cannot send email/WhatsApp, edit calendars,
write records, control devices, access arbitrary files or make purchases. An
unexpected approval request is rejected automatically. Existing legacy socket
clients retain their old policy; this is not a new role system for every API.

The assistant may send requested record contents to the server's configured AI
provider when answering. Nothing is submitted to that provider merely by loading
the page. Mocked regression tests do not use real providers or private data.
Keep this prototype private; no public deployment is approved or configured here.

Automated Python coverage: `pytest tests/test_ws.py tests/test_ws_sessions.py
 tests/test_personal_tool_chat.py` (one command, no newline). Browser interaction
and 390px/desktop layout were checked with a mocked WebSocket/provider, including
wrong-profile refusal, token clearing, no browser storage and blocked action
requests. Physical Android/Windows and real-model acceptance remain separate.
