package com.ashok.aether

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.*

@Composable
fun AdvancedCompanionCard() {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var expanded by remember { mutableStateOf(false) }
    var generation by remember { mutableIntStateOf(0) }
    var image by remember { mutableStateOf<Uri?>(null) }
    var camera by remember { mutableStateOf<Bitmap?>(null) }
    var selectionVersion by remember { mutableIntStateOf(0) }
    var pendingPicker by remember { mutableStateOf<Int?>(null) }
    var pendingCamera by remember { mutableStateOf<Int?>(null) }
    var rotation by remember { mutableIntStateOf(0) }
    var job by remember { mutableStateOf<Job?>(null) }
    var lat by remember { mutableStateOf("") }; var lon by remember { mutableStateOf("") }
    var radius by remember { mutableStateOf("2000") }; var hours by remember { mutableStateOf("24") }
    var note by remember { mutableStateOf("") }
    var reviewReminder by remember { mutableStateOf(false) }
    var geminiKey by remember { mutableStateOf(TokenVault.readGeminiKey(context) ?: "") }
    var rememberGeminiKey by remember { mutableStateOf(TokenVault.readGeminiKey(context) != null) }
    var cloudConsentVersion by remember { mutableIntStateOf(-1) }
    var status by remember { mutableStateOf("Bundled on-device image models. Background reminder stays off until separate permission, review and enable.") }
    fun clearImage(invalidateSelection: Boolean = true) { if (invalidateSelection) { selectionVersion++; pendingPicker = null; pendingCamera = null }; generation++; job?.cancel(); job = null; image = null; camera = null; status = "Local image selection/results cleared. Separately enabled background reminders are unchanged." }
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_STOP) { clearImage(false); reviewReminder = false; cloudConsentVersion = -1 } }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer); job?.cancel() }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (expanded && pendingPicker == selectionVersion) { image = uri?.takeIf { it.scheme == "content" }; camera = null; status = "Image selected or cancelled. Analysis requires its separate button." }; pendingPicker = null
    }
    val capture = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap ->
        if (expanded && pendingCamera == selectionVersion) { camera = bitmap; image = null; status = "Camera handler returned a thumbnail or cancelled. AETHER did not request full camera/library access. Analyze separately." }; pendingCamera = null
    }
    val coarse = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { status = "Foreground permission decision returned. No read or reminder enabled. Review Android app permission settings." }
    val notifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { status = "Notification permission decision returned. No reminder enabled." }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            TextButton(onClick = { clearImage(); reviewReminder = false; expanded = !expanded }) { Text(if (expanded) "IMAGE UNDERSTANDING / BACKGROUND REMINDER - close" else "IMAGE UNDERSTANDING / BACKGROUND REMINDER - open") }
            if (expanded) {
                Text("One chosen image or system-camera thumbnail. Bundled labels and Latin OCR run on-device, no AETHER upload. Model/dependency telemetry and selected providers have their own policies. OCR may expose private text locally; do not use for identity, medical or safety decisions.")
                Button(enabled = job == null, onClick = { clearImage(); pendingPicker = selectionVersion; try { picker.launch("image/*") } catch (_: Exception) { status = "No image picker." } }) { Text("Select image for local understanding") }
                Button(enabled = job == null, onClick = { clearImage(); pendingCamera = selectionVersion; try { capture.launch(null) } catch (_: Exception) { status = "No camera handler; nothing captured by AETHER." } }) { Text("Open system camera for one thumbnail") }
                TextButton(onClick = { rotation = (rotation + 90) % 360 }) { Text("Analysis rotation: $rotation degrees (tap +90)") }
                Button(enabled = job == null && (image != null || camera != null), onClick = {
                    val selected = image; val thumbnail = camera; val angle = rotation
                    val ticket = ++generation
                    status = "Running local models. Clear/leave suppresses late results; native model work may finish."
                    job = scope.launch {
                        try {
                            val result = understandSelectedImage(context, selected, thumbnail, angle)
                            currentCoroutineContext().ensureActive()
                            if (ticket == generation && expanded) status = result
                        } catch (e: CancellationException) { throw e }
                        catch (_: Exception) { if (ticket == generation && expanded) status = "Local model/read unavailable or image invalid. No understanding success claimed." }
                        finally { if (ticket == generation) job = null }
                    }
                }) { Text("Understand selected image locally") }
                HorizontalDivider()
                Text("Optional cloud description: sends ONLY this one selected image (downsized to at most 512px JPEG) over HTTPS to Google Gemini under YOUR own API key. Nothing is sent until you confirm for this exact photo. If you save the key it stays encrypted on this device and is sent nowhere except Google's API.")
                OutlinedTextField(geminiKey, { geminiKey = it.take(400); cloudConsentVersion = -1 }, label = { Text("Your Gemini API key") }, visualTransformation = PasswordVisualTransformation())
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = rememberGeminiKey, onCheckedChange = { rememberGeminiKey = it })
                    Text("Save key encrypted on this device (optional)")
                }
                Button(enabled = job == null && (image != null || camera != null) && geminiKey.isNotBlank(), onClick = { cloudConsentVersion = selectionVersion }) { Text("Prepare Gemini cloud description for this photo") }
                if (cloudConsentVersion == selectionVersion && (image != null || camera != null)) {
                    Text("Send THIS selected photo (one downsized JPEG, nothing else) to Google Gemini? Google processes it under your own API account and policies. AETHER keeps no copy and includes no other data.")
                    Button(enabled = job == null, onClick = {
                        val selected = image; val thumbnail = camera; val key = geminiKey
                        val ticket = ++generation
                        cloudConsentVersion = -1
                        status = "Sending this one photo to Google Gemini..."
                        job = scope.launch {
                            try {
                                val checked = GeminiCloudVision.checkedApiKey(key)
                                val description = describeSelectedImageWithGemini(context, selected, thumbnail, checked)
                                if (rememberGeminiKey) TokenVault.storeGeminiKey(context, checked) else TokenVault.clearGeminiKey(context)
                                currentCoroutineContext().ensureActive()
                                if (ticket == generation && expanded) status = description
                            } catch (e: CancellationException) { throw e }
                            catch (e: Exception) { if (ticket == generation && expanded) status = e.message ?: "Cloud description failed. No success claimed." }
                            finally { if (ticket == generation) job = null }
                        }
                    }) { Text("Confirm: send THIS photo to Gemini") }
                    TextButton(onClick = { cloudConsentVersion = -1; status = "Cloud description cancelled. Nothing was sent." }) { Text("Cancel, do not send") }
                }
                TextButton(onClick = { clearImage(); cloudConsentVersion = -1; status = "Local selection/results cleared. No secure-erasure or external camera/gallery deletion claim." }) { Text("Clear image and local result") }
                HorizontalDivider()
                Text("Background proximity reminder: one stored target, approximate network location, best-effort every 15 minutes. Android may delay/miss checks due to power/network/force-stop/permission rules. Not an exact geofence or safety reminder. Use a separate time reminder when missing it matters. Requires Allow all the time plus notifications. No server upload/history. Expires after 1-168 hours, fires at most once; reboot invalidates it.")
                Button(onClick = { coarse.launch(Manifest.permission.ACCESS_COARSE_LOCATION) }) { Text("Request approximate foreground permission first") }
                Button(onClick = {
                    try {
                        require(context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED)
                        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")))
                        status = "In Android permissions, choose Location > Allow all the time if offered. It is optional. Return and review/enable separately. Precise location is not required."
                    } catch (_: Exception) { status = "Grant foreground approximate permission first; background option may be unavailable on this device/policy." }
                }) { Text("Review optional background location in Android Settings") }
                Button(onClick = { if (Build.VERSION.SDK_INT >= 33) notifications.launch(Manifest.permission.POST_NOTIFICATIONS) else status = "Review app notifications in Android Settings." }) { Text("Request notification permission") }
                OutlinedTextField(lat, { lat = it.take(24); reviewReminder = false }, label = { Text("Exact target latitude") })
                OutlinedTextField(lon, { lon = it.take(24); reviewReminder = false }, label = { Text("Exact target longitude") })
                OutlinedTextField(radius, { radius = it.take(12); reviewReminder = false }, label = { Text("Radius meters (100-50000)") })
                OutlinedTextField(hours, { hours = it.take(3); reviewReminder = false }, label = { Text("Expires in hours (1-168)") })
                OutlinedTextField(note, { note = it.take(200); reviewReminder = false }, label = { Text("Exact local notification text") })
                Button(onClick = { reviewReminder = true }) { Text("Review background reminder (does not enable)") }
                if (reviewReminder) {
                    Text("Store one target $lat, $lon, radius $radius m, text '$note', expiry $hours hours. Replaces any previous local proximity reminder. Notifications can be visible to someone using this device. Approximate accuracy may prevent a small-radius trigger. No delivery guarantee.")
                    Button(onClick = {
                        try {
                            LocalLocationReminder.enable(context, lat.toDouble(), lon.toDouble(), radius.toDouble(), note, hours.toInt())
                            status = LocalLocationReminder.status(context)
                        } catch (_: Exception) { status = "Not enabled: invalid scope or missing background/foreground/notification permission, API30+ support or scheduler. Nothing reported scheduled." }
                        reviewReminder = false
                    }) { Text("Enable this exact local background reminder") }
                }
                Button(onClick = { status = LocalLocationReminder.status(context) }) { Text("Read local enabled/expiry status") }
                Button(onClick = {
                    try { LocalLocationReminder.disable(context); status = "Disabled and cleared target/text; outstanding notification cancelled. Cannot undo a notification already seen." }
                    catch (_: Exception) { status = "Disable could not be confirmed. Revoke app location permission in Android Settings." }
                }) { Text("Disable and erase background reminder") }
                Text("Closing/clearing the image panel does NOT disable a separately enabled background reminder. Use Disable above. Revoke OS permissions in Settings.")
                Text(status, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
