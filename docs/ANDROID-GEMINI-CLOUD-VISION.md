# Optional Gemini cloud image description (Android)

The on-device image understanding (bundled labels + Latin OCR) never uploads
anything. This adds a separate, optional cloud path for a richer description.

## What it does

- In the IMAGE UNDERSTANDING panel, after selecting one image or camera
  thumbnail, the owner can paste their own Google Gemini API key, tap
  "Prepare Gemini cloud description for this photo", read exactly what will
  be sent, and tap "Confirm: send THIS photo to Gemini".
- AETHER then sends only that one image - downsized to at most 512px and
  JPEG-encoded - to Google's Generative Language API
  (`gemini-2.0-flash:generateContent`) over HTTPS and shows the returned
  description, labelled as unverified model output.

## Limits and guarantees

- Per-photo consent only. Every send requires a fresh confirmation tied to the
  current selection; changing or clearing the image, editing the key, or
  leaving the screen cancels a pending confirmation. There is no "always send"
  switch.
- Only the image bytes are sent. No location, metadata, other photos,
  conversation history or device data is included in the request.
- The API key is the owner's own. It is sent only to
  `generativelanguage.googleapis.com`. Saving it is optional; when saved it is
  stored encrypted with the same Android Keystore AES protection as the device
  token (`TokenVault`), and can be forgotten by unticking the save option and
  running one description, or by clearing app data.
- The Gemini prompt forbids identifying people, medical/safety advice and
  following instructions embedded in the image, but model output is still
  unverified content, not facts.
- Google processes the photo under the owner's own API account and Google's
  terms; that processing is outside AETHER's control.
- HTTP errors are mapped to honest messages (bad key, quota, server problem)
  and never echo the API key.

## Setup for the owner

1. Create a Gemini API key at https://aistudio.google.com/apikey (Google
   account required; free tier exists, paid usage is billed by Google to the
   owner).
2. Paste it into the Gemini section of the IMAGE UNDERSTANDING panel.
3. Optionally tick "Save key encrypted on this device".

## Development honesty

No real Gemini API call, API key, or photo upload was used while developing
this feature. JVM tests cover request building, response parsing, bounds and
error mapping with fake data only. Real upload, quota and on-device behavior
remain unverified until the owner runs it on their phone.
