# AETHER integrations and daily automation

This guide describes the current integration implementation on `jarvis-cinematic-local-voice`. Keep the server bound to localhost or a private HTTPS endpoint. Never commit OAuth client secrets, Meta tokens, or device tokens.

## Google Calendar and Gmail

AETHER uses Google's OAuth 2.0 authorization-code flow. It requests Calendar Events, Gmail readonly, and Gmail send scopes. The refresh token is encrypted at rest in SQLite using a key derived from `SECRET_KEY`; keep that secret stable and back it up securely. Rotating it without reconnecting Google makes stored provider tokens unreadable.

1. Create or select a project in Google Cloud Console.
2. Enable **Google Calendar API** and **Gmail API**.
3. Configure the OAuth consent screen. During testing, add the Google account as a test user.
4. Create an OAuth client suitable for a web application and add this exact redirect URI:
   `http://127.0.0.1:8000/api/integrations/google/callback`
5. Put the client ID and secret in the local `.env` as `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. Keep `GOOGLE_OAUTH_REDIRECT_URI` identical to the registered URI.
6. Ensure `SECRET_KEY` is a random value of at least 32 characters. Restart AETHER and open **Life Manager → Email & WhatsApp → Connect Google**.

Google Calendar can be read. Create, update and delete operations are stored as approval requests and only run after the user selects **Approve & execute**. Gmail search reads message metadata and snippets; the AI summary endpoint retrieves message bodies and sends the selected content to the configured AI provider. Gmail send is an approval request, not an immediate send.

The requested OAuth scopes may require Google verification for public distribution. For personal development, keep the OAuth app in testing and use an explicitly listed test account. Do not publish this OAuth client as a multi-user public service without completing Google's verification and security requirements.

## WhatsApp

AETHER uses the official Meta WhatsApp Business Cloud API. It does not automate WhatsApp Web or scrape private sessions.

1. Create a Meta developer app and add the WhatsApp product.
2. Configure a WhatsApp Business Account and phone number.
3. Add the access token to `WHATSAPP_ACCESS_TOKEN` and the sender's phone-number ID to `WHATSAPP_PHONE_NUMBER_ID`.
4. Use a production system-user token and secure secret storage for a long-running deployment; temporary developer tokens expire.
5. Follow WhatsApp opt-in, template approval and customer-service-window policies.

AETHER saves message drafts as pending approvals. A message is sent only when a user explicitly approves it. Recipient numbers must be in international format. Never send unsolicited messages.

## Android and Windows notifications

- Android WorkManager polls the authenticated AETHER notification inbox while notifications are enabled and Android notification permission is granted. It also retains the existing due-reminder polling path.
- Windows browser notifications are delivered while the AETHER Life Manager page is open, the user has granted browser notification permission, and the authenticated backend is reachable. A native Windows toast agent is also available with `python -m app.windows_notifications`; install it to run at sign-in with `powershell -ExecutionPolicy Bypass -File .\\scripts\\install-aether-notifications.ps1` (remove with `-Remove`). The agent uses the local master API token from `.env` and stores only a notification cursor locally.
- The backend scheduler creates one-shot notifications up to 15 minutes before a reminder becomes due.

This is authenticated polling, not Firebase Cloud Messaging. Android WorkManager timing is OS-controlled and is not an exact alarm. The Windows native agent is a local polling process, not a remote push service. A future remote deployment should add FCM and device-scoped credentials.

## Authorized document search

Set `DOCUMENT_ALLOWED_ROOTS` to one or more absolute directories separated by semicolons. For example:

```dotenv
DOCUMENT_ALLOWED_ROOTS=C:\\Users\\YourUser\\Documents;D:\\Work\\Notes
```

AETHER never silently scans the entire home directory. Search currently extracts text from TXT, Markdown, LOG, PDF and DOCX files, limits each file to 10 MB, and bounds the directory walk. Scanned PDFs without an embedded text layer need OCR, which is not enabled. Spreadsheet and PowerPoint parsing are not enabled yet.

Use folders containing only the documents you want AETHER to access. A future release should add an explicit folder-picker UI and per-device root permissions before multi-user or public deployment.

## AI daily planning and proactive reminders

The AI daily planner uses the configured Gemini, OpenRouter or Groq provider to propose a schedule from open tasks, saved calendar drafts, working hours, timezone and commitments supplied by the user. It returns a proposal and does not automatically change task state or write calendar events. The user reviews the proposal and separately approves external calendar changes.

The scheduler checks due reminders and queues a notification once per reminder. Android and Windows clients read the same authenticated notification inbox. This local scheduler is single-process; do not run multiple public workers against the same SQLite file.

## Approval and security model

- Reading external data requires the user to connect the relevant provider and grant OAuth/API scopes.
- Calendar create/update/delete, Gmail send and WhatsApp send are queued as pending approval records.
- Approval execution uses a single-claim state transition to reduce duplicate actions.
- API tokens and provider secrets are never returned to browser clients.
- Keep the backend on localhost or private HTTPS. Do not expose it through a public tunnel.
- Review OAuth scopes and revoke unused provider grants from the provider's security settings.

## Read-only Google Contacts opt-in

The Email/WhatsApp/Contacts section has a separate **Connect Google with read-only
Contacts** button. Ordinary Google connect keeps its existing scope set. Contacts
opt-in appends `https://www.googleapis.com/auth/contacts.readonly`; Google still
asks for consent. Enable the Google People API in the same OAuth project. This
uses the same Google credential slot as Gmail/calendar, not another account:
check the selected Google account when reconnecting because it can replace the
existing integration account. No live connection is made by installing this code.

`GET /api/contacts/status` checks the stored scope; it is not proof of current
provider availability. Authenticated `GET /api/contacts/search?q=prefix&limit=20`
checks the grant, warms Google's lazy contacts search cache, waits five seconds,
then performs a read-only prefix search. Names, email addresses, phone numbers
and organizations only, at most 30 contacts. It never requests contact-write scope,
merges duplicates, chooses a recipient or sends a message. Similar names remain
separate; a matching address-book record is not verified identity. No contact data
is written to AETHER's database or sent to an AI provider by this endpoint.
Provider failures are redacted; missing consent/API enablement gives an actionable
error. Search is not a complete address-book export. Local automated tests mock
all Google calls and do not verify a real OAuth deployment/account.

Official API grounding:
- https://developers.google.com/people/api/rest/v1/people/searchContacts
- https://developers.google.com/people/v1/contacts
