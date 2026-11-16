# AETHER selected phone-number review

LOCAL PHONE ACTIONS now offers a separate "Choose one phone number" system picker.
It uses ACTION_PICK with CommonDataKinds.Phone.CONTENT_TYPE, not a background
contacts query. The user can search within the system handler and select a
specific number row. The existing generic contact picker remains available and
still does not extract a recipient. No READ_CONTACTS permission, directory export,
contact write, provider/model upload or automatic call/draft/send is added.

Only a content URI for com.android.contacts with a positive numeric data row
under /data/{id} or /data/phones/{id}, no query/fragment, is accepted. Unrecognized
providers, work-profile URI variants and base directory routes fail closed rather
than widening access. This intentionally limits handler compatibility. The
returned temporary content URI is queried only for NUMBER and MIMETYPE. The
row must report the phone-number MIME kind. Missing,
revoked, inaccessible, empty or multi-row results fail without changing the number
field. No directory fallback, inferred URI, persistent URI grant, display-name
read or selection of a default number is performed. The selected URI/provider
must actually grant access; a returned URI alone does not prove a usable grant.

The local helper accepts only a single explicit international +number with 7-15
digits. It removes ASCII space, hyphen, dot and parentheses from the selected
number. No country code or prefix is inferred, no letters are translated, and
extensions, dial/USSD codes, separators for multiple numbers, URI schemes,
control characters and Unicode digits are refused. Local-format numbers must be
entered manually after the user confirms the correct international number. This
is format validation, not carrier allocation, number ownership, person identity,
current reachability or proof the selected row's content is trustworthy.

A valid candidate is shown locally with "not verified identity" and requires
explicit review plus "Use this candidate in number field" before it replaces the
existing field. Discard leaves that field alone. Selection errors/cancellation
also leave it unchanged. The dialer/SMS buttons remain separate, and Call/Send
remain in the destination application. Selecting or copying a number never
confirms a communication, its words or its recipient identity.

Candidate state is transient Compose memory, not saved settings or chat. Clear
local fields also discards it, but OS handlers/input methods/providers may retain
their own records. No secure-erasure promise is made. No emulator or phone was run
or pixel-inspected for this addition. JVM tests cover formatting/refusal and
source tests check narrow query/wiring; these are not provider grants, real search,
system picker, missing-handler, rotation or layout acceptance. This is selected
phone-number access through system UI, not general native contacts search/export.

Official source checked November 16, 2026:
- https://developer.android.com/guide/components/intents-common
- https://developer.android.com/reference/android/provider/ContactsContract.CommonDataKinds.Phone
- https://developer.android.com/reference/android/provider/ContactsContract.Data
- Historical Android CTS examples of supported row routes (not a runtime guarantee): https://android.googlesource.com/platform/cts/+/16d0fbf21756263d8bcd2da20e560ba9c56ffc23/tests/tests/contactsprovider/src/android/provider/cts/contacts/ContactsContract_AllUriTest.java
