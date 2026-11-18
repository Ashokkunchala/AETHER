package com.ashok.aether

import android.app.Activity
import android.app.KeyguardManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.BatteryManager
import android.os.StatFs
import android.provider.CalendarContract
import android.provider.ContactsContract
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import java.time.OffsetDateTime

// Only user-entered exact international numbers; no USSD, pause/wait or dial codes.
internal fun validPhoneTarget(value: String): Boolean = Regex("\\+[1-9][0-9]{6,14}").matches(value)

internal fun calendarTimes(start: String, end: String): Pair<Long, Long> {
    val first = OffsetDateTime.parse(start).toInstant().toEpochMilli()
    val last = OffsetDateTime.parse(end).toInstant().toEpochMilli()
    require(last > first) { "End must be after start. Include timezone offset in both dates." }
    return first to last
}

private fun launchPhoneIntent(context: Context, intent: Intent, report: (String) -> Unit) {
    try {
        context.startActivity(intent)
        report("Opened system composer/handler. Nothing is reported sent, called or saved. Review and finish there.")
    } catch (_: Exception) {
        report("No usable handler or permission. Nothing is reported sent, called or saved.")
    }
}

@Composable
fun PhoneActionsCard() {
    val context = LocalContext.current
    // No rememberSaveable or backend/client call: selection/clipboard/composer data stays transient.
    var expanded by remember { mutableStateOf(false) }
    var number by remember { mutableStateOf("") }
    var selectedPhoneCandidate by remember { mutableStateOf<String?>(null) }
    var selectedTextReset by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var begin by remember { mutableStateOf("") }
    var end by remember { mutableStateOf("") }
    var clipboard by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("Local controls only. No data here is uploaded to chat or a model.") }
    val report: (String) -> Unit = { status = it }
    val contact = rememberLauncherForActivityResult(ActivityResultContracts.PickContact()) { uri ->
        // PickContact selects a contact, not necessarily a specific phone number. Do not infer a recipient.
        selectedPhoneCandidate = null
        if (uri == null) status = "Contact selection cancelled. Number field unchanged."
        else {
            number = ""
            status = "Contact selected in system UI. Previous number field cleared to avoid using another contact's number. Open Contacts to review its numbers; enter the exact number below. No contact directory was read or recipient inferred."
        }
    }
    val phoneNumber = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        selectedPhoneCandidate = null
        if (result.resultCode != Activity.RESULT_OK) {
            status = "Phone-number selection cancelled or unavailable. Existing number field unchanged."
        } else {
            val uri = result.data?.data
            val candidate = if (uri == null) null else readSelectedPhoneNumber(context, uri)
            selectedPhoneCandidate = candidate
            status = if (candidate == null) "No single usable international +number returned. The grant/row may be missing, revoked, ambiguous or locally formatted. Existing field unchanged; no country inferred. Enter the exact number manually."
                else "One specific phone-number row selected. ASCII visual separators removed only. Review the candidate and intended person, then explicitly copy it into the number field. No recipient identity verified, call, draft or send."
        }
    }
    val document = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        status = if (uri == null) "File selection cancelled." else try {
            var name = "selected document"
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) name = cursor.getString(0)?.take(200) ?: name
            }
            "Selected: $name. Content not read, copied, organized or uploaded. Selection grant is not upload approval."
        } catch (_: Exception) { "Document selected; display metadata unavailable. No content read or upload." }
    }
    val photo = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        status = if (uri == null) "Image selection cancelled." else "One image selected. No pixels read, analysis or upload. Image analysis needs a separate reviewed destination and permission."
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "LOCAL PHONE ACTIONS - close" else "LOCAL PHONE ACTIONS - open") }
            if (expanded) {
                Text("System composers, selected items and local device status. Call/Send/Save stay in the destination app. Missing handlers are normal.", style = MaterialTheme.typography.bodySmall)
                Button(onClick = { selectedPhoneCandidate = null; try { contact.launch(null) } catch (_: Exception) { status = "Contact picker unavailable; no contacts read." } }) { Text("Choose contact (system picker)") }
                Button(onClick = {
                    selectedPhoneCandidate = null
                    try { phoneNumber.launch(Intent(Intent.ACTION_PICK).setType(ContactsContract.CommonDataKinds.Phone.CONTENT_TYPE)) }
                    catch (_: Exception) { status = "Specific-number picker unavailable; no directory fallback or number-field change." }
                }) { Text("Choose one phone number (system picker)") }
                selectedPhoneCandidate?.let { candidate ->
                    Text("Selected candidate: $candidate. Check the intended person; not verified identity.", style = MaterialTheme.typography.bodySmall)
                    Button(onClick = {
                        number = candidate
                        selectedPhoneCandidate = null
                        status = "Copied only the reviewed candidate into the local number field. Dial/SMS still require their separate buttons and system review."
                    }) { Text("Use this candidate in number field") }
                    TextButton(onClick = { selectedPhoneCandidate = null }) { Text("Discard selected candidate") }
                }
                OutlinedTextField(value = number, onValueChange = { number = it.take(16) }, label = { Text("Exact international number, e.g. +919876543210") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(enabled = selectedPhoneCandidate == null, onClick = {
                    if (!validPhoneTarget(number)) status = "Enter one exact international +number (7-15 digits), no codes or separators."
                    else launchPhoneIntent(context, Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", number, null)), report)
                }) { Text("Review number in dialer (does not call)") }
                OutlinedTextField(value = message, onValueChange = { message = it.take(2000) }, label = { Text("Exact SMS draft (max 2000 characters)") }, modifier = Modifier.fillMaxWidth())
                Button(enabled = selectedPhoneCandidate == null, onClick = {
                    if (!validPhoneTarget(number) || message.isBlank()) status = "Enter exact international number and a nonempty draft."
                    else launchPhoneIntent(context, Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", number, null)).putExtra("sms_body", message), report)
                }) { Text("Review SMS draft (does not send)") }
                OutlinedTextField(value = title, onValueChange = { title = it.take(200) }, label = { Text("Calendar event title") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = begin, onValueChange = { begin = it.take(50) }, label = { Text("Start: 2026-12-01T10:00:00+05:30") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = end, onValueChange = { end = it.take(50) }, label = { Text("End with timezone offset") }, modifier = Modifier.fillMaxWidth())
                Button(onClick = {
                    try {
                        require(title.isNotBlank())
                        val (first, last) = calendarTimes(begin, end)
                        launchPhoneIntent(context, Intent(Intent.ACTION_INSERT, CalendarContract.Events.CONTENT_URI)
                            .putExtra(CalendarContract.Events.TITLE, title)
                            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, first)
                            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, last), report)
                    } catch (_: Exception) { status = "Enter a title and valid ISO start/end with timezone offsets; end must be later. Nothing saved." }
                }) { Text("Review event in calendar (does not save)") }
                Button(onClick = { try { document.launch(arrayOf("*/*")) } catch (_: Exception) { status = "Document picker unavailable; no file read." } }) { Text("Select one accessible document") }
                Button(onClick = { try { photo.launch("image/*") } catch (_: Exception) { status = "Image picker unavailable; no image read." } }) { Text("Select one image (no upload)") }
                OutlinedTextField(value = clipboard, onValueChange = { clipboard = it.take(8000) }, label = { Text("Local clipboard text (may be private)") }, modifier = Modifier.fillMaxWidth())
                Button(onClick = {
                    try {
                        val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        // Explicit foreground interaction only; do not coerce content URIs into file contents.
                        clipboard = manager.primaryClip?.getItemAt(0)?.text?.toString()?.take(8000) ?: ""
                        status = "Read plain clipboard text into this local field only. No upload, secret classification or background read."
                    } catch (_: Exception) { status = "Clipboard unavailable; nothing uploaded." }
                }) { Text("Paste plain clipboard text locally") }
                Button(onClick = {
                    try {
                        (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("AETHER local text", clipboard))
                        status = "Copied this field to the system clipboard. Other permitted apps may read it; nothing sent by AETHER."
                    } catch (_: Exception) { status = "Clipboard copy unavailable." }
                }) { Text("Copy this field to clipboard") }
                Button(onClick = {
                    number = ""; selectedPhoneCandidate = null; selectedTextReset++; message = ""; title = ""; begin = ""; end = ""; clipboard = ""
                    status = "Local fields cleared. This does not erase system clipboard, destination-app drafts, logs or backups."
                }) { Text("Clear local fields") }
                Button(onClick = { status = localDeviceStatus(context) }) { Text("Read battery, volume and lock status now") }
                Button(onClick = { status = networkSnapshotText(readLocalNetworkSnapshot(context)) }) { Text("Read local network capabilities now") }
                key(selectedTextReset) { SelectedTextCard() }
                Text(status, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private fun localDeviceStatus(context: Context): String {
    val battery = try {
        val data = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = data?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = data?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val percent = if (scale > 0 && level in 0..scale) "${(level.toLong() * 100 / scale)}%" else "unknown"
        val charging = when (data?.getIntExtra(BatteryManager.EXTRA_STATUS, -1)) {
            BatteryManager.BATTERY_STATUS_CHARGING -> "charging"
            BatteryManager.BATTERY_STATUS_FULL -> "full"
            BatteryManager.BATTERY_STATUS_DISCHARGING -> "discharging"
            BatteryManager.BATTERY_STATUS_NOT_CHARGING -> "not charging"
            else -> "unknown"
        }
        val rawTemperature = data?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE) ?: Int.MIN_VALUE
        val temperature = if (rawTemperature in -1000..2000) "${rawTemperature / 10.0} C (battery sensor only, not CPU temperature or a health diagnosis)" else "unknown"
        "Battery $percent; state $charging; temperature $temperature."
    } catch (_: Exception) { "Battery unknown." }
    val volume = try {
        val fs = StatFs(context.filesDir.path)
        "App-data volume capacity ${fs.totalBytes} bytes; available ${fs.availableBytes} bytes. Not all-files inventory or app storage usage."
    } catch (_: Exception) { "App-data volume unknown." }
    val lock = try {
        val manager = context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        "Device credential configured: ${manager.isDeviceSecure}; currently locked: ${manager.isDeviceLocked}. Not a security/malware audit."
    } catch (_: Exception) { "Lock state unknown." }
    val permissions = listOf(android.Manifest.permission.RECORD_AUDIO, android.Manifest.permission.POST_NOTIFICATIONS).joinToString { permission ->
        val granted = if (permission == android.Manifest.permission.POST_NOTIFICATIONS && android.os.Build.VERSION.SDK_INT < 33) "not applicable before API33" else if (context.checkSelfPermission(permission) == android.content.pm.PackageManager.PERMISSION_GRANTED) "granted" else "not granted"
        "${permission.substringAfterLast('.')}: $granted"
    }
    return "$battery $volume $lock Own app permissions: $permissions. Snapshot ${java.time.Instant.now()}; no monitor or upload."
}
