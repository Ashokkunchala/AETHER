# Read-only Gmail for AETHER

AETHER reads email with the `gmail.readonly` scope only. It cannot send, delete or change mail.
You sign in yourself, in your own browser, on your own PC. No password or code goes into chat.

One-time setup (about 5 minutes):

1. Open https://console.cloud.google.com/ and create a project (or pick one).
2. APIs and Services > Library > enable **Gmail API**.
3. APIs and Services > OAuth consent screen: choose External, add yourself as a test user.
4. Credentials > Create credentials > OAuth client ID > **Desktop app**. Download the JSON.
5. Save it as `%USERPROFILE%\.aether\google_client.json` (or set `AETHER_GOOGLE_CLIENT_FILE`).
6. In a terminal on the PC run `aether gmail-signin`, sign in, allow read-only access.

Then ask by voice: "read my latest emails". `aether gmail-signout` deletes the local token.
The token is stored only in `%USERPROFILE%\.aether\gmail_token.json`.
