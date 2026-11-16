# Provider approval boundary

Google Calendar proposals, Gmail drafts and WhatsApp drafts remain review-only
until an authenticated client explicitly approves the saved request ID. This
boundary is separate from browser-chat/WebSocket approvals.

- A request is bound to its creating bearer credential's hash and device identity
  (or the shared master credential), never the bearer secret itself. Other device
  credentials cannot list, approve or reject it. Using the same master token on
  two devices does not make them separate principals.
- Requests expire five minutes after creation. Listing shows only the current
  credential's unexpired requests for the same provider connection. Recreate old
  unbound requests after upgrading. Database upgrades add columns only; they do
  not delete or automatically approve old rows.
- Google OAuth completion creates a fresh connection generation. Reconnect or
  disconnect invalidates earlier requests. Normal access-token refresh preserves
  the generation. A stale token refresh cannot overwrite credentials after
  a concurrent reconnect/disconnect. Changes to configured WhatsApp token/phone ID also invalidate
  earlier requests. These checks do not add multi-account support.
- The pending-to-executing claim is serialized. Parallel approve calls cannot
  dispatch the same request twice. Revocation/rotation, expiry, account binding
  and the existing local emergency stop are checked at claim and again before
  entering the provider adapter. A request-local check runs again at the Google
  or Meta network-write entry, after any asynchronous token refresh/client setup.
  An unavailable safety store fails closed.
- Reject is allowed for the creating credential even when a request expired or
  emergency stop is active. Reject never contacts a provider.

The boundary does not revoke an HTTP request already handed to a provider or undo
completed actions. There is still a small check-to-network race; this is not a
transaction with Google or Meta. A provider timeout may leave the external result
unknown. Failed/executing requests are not automatically retried: inspect the
provider account before recreating one, to avoid duplicate mail/events/messages.
A process crash after claim may leave a request executing. No automatic recovery
or provider-wide idempotency is claimed.

Older local/API paths and device permissions keep their own policies. No live
account acceptance is implied by mocked tests. Never expose this prototype to the
public internet. No provider send, OAuth connection or account action is needed
to run the regression tests in `tests/test_provider_approvals.py`.
