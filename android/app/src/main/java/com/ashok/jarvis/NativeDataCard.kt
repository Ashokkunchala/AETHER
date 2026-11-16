package com.ashok.jarvis

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.location.Location
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.CancellationSignal
import android.os.SystemClock
import android.provider.CalendarContract
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream
import java.time.Instant
import java.time.ZoneId
import kotlin.coroutines.resume

internal data class LocalCalendarRow(val id: Long, val title: String, val begin: Long, val end: Long, val allDay: Boolean)

private fun readCalendar(context: Context): List<LocalCalendarRow> {
    val start = System.currentTimeMillis()
    val builder = CalendarContract.Instances.CONTENT_URI.buildUpon()
    ContentUris.appendId(builder, start)
    ContentUris.appendId(builder, start + 7 * 86_400_000L)
    val rows = mutableListOf<LocalCalendarRow>()
    // Only visible calendars, at most 20 displayed rows plus one truncation sentinel.
    context.contentResolver.query(builder.build(), arrayOf(CalendarContract.Instances.EVENT_ID,
        CalendarContract.Instances.TITLE, CalendarContract.Instances.BEGIN, CalendarContract.Instances.END,
        CalendarContract.Instances.ALL_DAY), "${CalendarContract.Calendars.VISIBLE} = ?", arrayOf("1"),
        "${CalendarContract.Instances.BEGIN} ASC")?.use { cursor ->
        while (rows.size < 21 && cursor.moveToNext()) {
            val id = cursor.getLong(0); val begin = cursor.getLong(2); val end = cursor.getLong(3)
            if (id > 0 && end >= begin) rows += LocalCalendarRow(id, cursor.getString(1)?.take(200).orEmpty(), begin, end, cursor.getInt(4) == 1)
        }
    } ?: error("Calendar provider unavailable")
    return rows
}

private fun inspectImage(context: Context, uri: Uri): String {
    require(uri.scheme == "content")
    require(context.contentResolver.getType(uri) in setOf("image/jpeg", "image/png", "image/webp"))
    // Stream size is bounded even when provider metadata lies or omits SIZE. Never persist grant/bytes.
    val bytes = context.contentResolver.openInputStream(uri)?.use { stream ->
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (output.size() <= 8 * 1024 * 1024) {
            val count = stream.read(buffer, 0, minOf(buffer.size, 8 * 1024 * 1024 + 1 - output.size()))
            if (count == -1) break
            require(count > 0)
            output.write(buffer, 0, count)
        }
        output.toByteArray()
     } ?: error("No stream")
    require(bytes.size in 1..8 * 1024 * 1024)
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    require(bounds.outMimeType in setOf("image/jpeg", "image/png", "image/webp"))
    val sample = imageSampleSize(bounds.outWidth, bounds.outHeight)
    val options = BitmapFactory.Options().apply { inSampleSize = sample; inScaled = false }
    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options) ?: error("No pixels")
    try {
        require(bitmap.width in 1..512 && bitmap.height in 1..512)
        var sum = 0L; var dark = 0L
        for (y in 0 until bitmap.height) for (x in 0 until bitmap.width) {
            val p = bitmap.getPixel(x, y)
            val light = (299 * ((p shr 16) and 255) + 587 * ((p shr 8) and 255) + 114 * (p and 255)) / 1000
            sum += light; if (light < 32) dark++
        }
        val count = bitmap.width.toLong() * bitmap.height
        return "Local pixel analysis: ${bounds.outWidth} x ${bounds.outHeight} encoded pixels; sampled ${bitmap.width} x ${bitmap.height}. Mean RGB luminance ${sum / count}/255; ${dark * 100 / count}% near-dark sampled pixels. No object recognition, OCR, face/identity inference, EXIF/location read or upload. Orientation/alpha/color profiles can affect these simple statistics."
    } finally { bitmap.recycle() }
}

private suspend fun readApproximateLocation(context: Context): Location? = withTimeout(20_000) {
    require(Build.VERSION.SDK_INT >= 30) { "One-shot location requires Android 11+ in this version" }
    val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    require(manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER))
    suspendCancellableCoroutine { continuation ->
        val signal = CancellationSignal()
        continuation.invokeOnCancellation { signal.cancel() }
        try {
            manager.getCurrentLocation(LocationManager.NETWORK_PROVIDER, signal, context.mainExecutor) { location ->
                if (continuation.isActive) continuation.resume(location)
            }
        } catch (e: Exception) { if (continuation.isActive) continuation.resume(null) }
    }
}

@Composable
fun NativeDataCard() {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var expanded by remember { mutableStateOf(false) }
    var generation by remember { mutableIntStateOf(0) }
    var task by remember { mutableStateOf<Job?>(null) }
    var rows by remember { mutableStateOf(emptyList<LocalCalendarRow>()) }
    var selected by remember { mutableStateOf<Uri?>(null) }
    var targetLat by remember { mutableStateOf("") }
    var targetLon by remember { mutableStateOf("") }
    var radius by remember { mutableStateOf("1000") }
    var note by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("Local only. No background tracking, provider writes or backend/model uploads.") }
    fun invalidate() { generation++; task?.cancel(); task = null; rows = emptyList(); selected = null; status = "Local results cleared. No pending operation success claimed." }
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_STOP) invalidate() }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer); task?.cancel() }
    }
    val calendarPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        status = if (granted) "Calendar permission granted. Tap Read next 7 days separately to read." else "Calendar permission denied. No read or settings fallback."
    }
    val locationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        status = if (granted) "Approximate location permission granted. Tap Check location separately to read." else "Location permission denied. No read or settings fallback."
    }
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (expanded) {
            selected = uri?.takeIf { it.scheme == "content" }
            status = if (selected == null) "Image selection cancelled/unusable. No read." else "One image selected. Tap Analyze locally to read its pixels. No upload."
        }
    }
    fun runLocal(operation: suspend () -> String) {
        task?.cancel(); generation++; val ticket = generation
        status = "Reading locally. Clear or leave this screen to suppress the result."
        task = scope.launch {
            try {
                val result = operation()
                if (ticket == generation && expanded) status = result
            } catch (_: TimeoutCancellationException) { if (ticket == generation && expanded) status = "Local read timed out. No current location or reminder success claimed." }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { if (ticket == generation && expanded) status = "Local read unavailable, denied, too large or invalid. No result or effect success claimed." }
            finally { if (ticket == generation) task = null }
        }
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            TextButton(onClick = { invalidate(); expanded = !expanded }) { Text(if (expanded) "NATIVE CALENDAR / IMAGE / LOCATION - close" else "NATIVE CALENDAR / IMAGE / LOCATION - open") }
            if (expanded) {
                Text("These are separate explicit local reads. Permission approval alone does not start a read. System calendar app owns Save/Delete and attendee notifications.")
                Button(onClick = { calendarPermission.launch(Manifest.permission.READ_CALENDAR) }) { Text("Request read-only calendar permission") }
                Button(enabled = task == null, onClick = {
                    if (context.checkSelfPermission(Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED) status = "Request calendar permission first. Nothing read."
                    else runLocal {
                        val result = withContext(Dispatchers.IO) { readCalendar(context) }
                        currentCoroutineContext().ensureActive()
                        rows = result.take(20)
                        "Read ${rows.size} local calendar occurrences over the next 7 days at ${Instant.now()}. ${if (result.size > 20) "Truncated to first 20." else ""} Refresh before relying on changes."
                    }
                }) { Text("Read next 7 days locally (max 20)") }
                rows.forEach { row ->
                    Text("${row.title.ifBlank { "(untitled)" }} | ${Instant.ofEpochMilli(row.begin).atZone(if (row.allDay) ZoneId.of("UTC") else ZoneId.systemDefault())} to ${Instant.ofEpochMilli(row.end).atZone(if (row.allDay) ZoneId.of("UTC") else ZoneId.systemDefault())}${if (row.allDay) " (all-day, end exclusive)" else ""}")
                    Button(onClick = {
                        try {
                            context.startActivity(Intent(Intent.ACTION_EDIT, ContentUris.withAppendedId(CalendarContract.Events.CONTENT_URI, row.id))
                                .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, row.begin).putExtra(CalendarContract.EXTRA_EVENT_END_TIME, row.end))
                            status = "Opened calendar editor for this occurrence. Review series scope, account and attendees there. No save/delete claimed."
                        } catch (_: Exception) { status = "No calendar editor available. Nothing saved/deleted." }
                    }) { Text("Review edit/cancel in system calendar") }
                }
                Button(onClick = { selected = null; try { imagePicker.launch("image/*") } catch (_: Exception) { status = "Image picker unavailable." } }) { Text("Choose one image (no automatic read)") }
                Button(enabled = selected != null && task == null, onClick = {
                    val uri = selected
                    if (uri != null) runLocal { withContext(Dispatchers.IO) { inspectImage(context, uri) } }
                }) { Text("Analyze selected pixels locally (JPEG/PNG/WebP, max 8 MiB)") }
                Text("Location check: approximate network fix only, Android 11+, 20-second timeout, max age 60 seconds. No stored last-known fallback, geofence service or background reminder.")
                Button(onClick = { locationPermission.launch(Manifest.permission.ACCESS_COARSE_LOCATION) }) { Text("Request approximate foreground location") }
                OutlinedTextField(targetLat, { targetLat = it.take(24) }, label = { Text("Optional reminder target latitude") })
                OutlinedTextField(targetLon, { targetLon = it.take(24) }, label = { Text("Target longitude") })
                OutlinedTextField(radius, { radius = it.take(12) }, label = { Text("Radius in meters (100-50000)") })
                OutlinedTextField(note, { note = it.take(200) }, label = { Text("Local reminder shown only on explicit check") })
                Button(enabled = task == null, onClick = {
                    if (context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) status = "Request location permission first. Nothing read."
                    else {
                        val latText = targetLat; val lonText = targetLon; val radiusText = radius; val reminder = note
                        runLocal {
                            val target = if (latText.isBlank() && lonText.isBlank() && reminder.isBlank()) null else {
                                val lat = latText.toDouble(); val lon = lonText.toDouble(); val r = radiusText.toDouble()
                                require(lat in -90.0..90.0 && lon in -180.0..180.0 && r in 100.0..50000.0 && reminder.isNotBlank())
                                Triple(lat, lon, r)
                            }
                            val fix = readApproximateLocation(context) ?: error("No current fix")
                            val age = SystemClock.elapsedRealtimeNanos() - fix.elapsedRealtimeNanos
                            require(fix.hasAccuracy() && freshLocation(age, fix.latitude, fix.longitude, fix.accuracy))
                            val proximity = target?.let {
                                val distance = distanceMeters(fix.latitude, fix.longitude, it.first, it.second)
                                if (definitelyInside(distance, fix.accuracy, it.third)) " Reminder: $reminder" else " Target not confirmed inside radius with reported accuracy."
                            }.orEmpty()
                            "Approximate location ${fix.latitude}, ${fix.longitude}; accuracy ${fix.accuracy} m; fix time ${Instant.ofEpochMilli(fix.time)}, age ${age / 1_000_000_000}s at check. Snapshot only, not continuously current.$proximity No upload or background watch."
                        }
                    }
                }) { Text("Check location / local reminder once") }
                TextButton(onClick = { invalidate(); targetLat = ""; targetLon = ""; radius = "1000"; note = "" }) { Text("Cancel local read / clear fields and results") }
                Text(status, style = MaterialTheme.typography.bodySmall)
                Text("Clearing suppresses late results and cancels a location request, but cannot undo bytes already read or changes completed in another app. OS-granted permissions remain; revoke them in Android Settings. Picker providers may retrieve selected cloud content themselves.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
