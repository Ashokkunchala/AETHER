package com.ashok.jarvis

import android.content.Context
import android.net.Uri
import android.provider.ContactsContract

// Remove visual ASCII separators only. Never infer a country, add a prefix,
// translate letters, accept dial codes/extensions, or choose among multiple rows.
internal fun selectedInternationalNumber(raw: String?): String? {
    if (raw == null || raw.length !in 1..80) return null
    if (raw.any { it !in "+0123456789 -()." }) return null
    val candidate = raw.filter { it == '+' || it in '0'..'9' }
    return candidate.takeIf { validPhoneTarget(it) }
}

internal fun selectedPhoneRouteAllowed(authority: String?, segments: List<String>, query: String?, fragment: String?): Boolean {
    if (authority != "com.android.contacts" || query != null || fragment != null) return false
    val prefix = segments.dropLast(1)
    if (prefix != listOf("data") && prefix != listOf("data", "phones")) return false
    return segments.lastOrNull()?.matches(Regex("[1-9][0-9]{0,18}")) == true
}

internal fun readSelectedPhoneNumber(context: Context, uri: Uri): String? {
    // Accept only the selected temporary content grant. Never query a base
    // directory URI, infer another URI, persist a grant or fall back to contacts.
    if (uri.scheme != "content" || !selectedPhoneRouteAllowed(uri.authority, uri.pathSegments, uri.query, uri.fragment)) return null
    return try {
        context.contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.Data.MIMETYPE), null, null, null)?.use { cursor ->
            if (!cursor.moveToFirst()) return@use null
            val column = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            if (column < 0) return@use null
            val kind = cursor.getColumnIndex(ContactsContract.Data.MIMETYPE)
            if (kind < 0 || cursor.getString(kind) != ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE) return@use null
            val number = selectedInternationalNumber(cursor.getString(column))
            if (cursor.moveToNext()) null else number
        }
    } catch (_: Exception) {
        // Missing/revoked grant, handler or provider error is not an empty directory.
        null
    }
}
