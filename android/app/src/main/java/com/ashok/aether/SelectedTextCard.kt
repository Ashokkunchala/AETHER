package com.ashok.aether

import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
internal fun SelectedTextCard() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var selected by remember { mutableStateOf<Uri?>(null) }
    var label by remember { mutableStateOf("") }
    var preview by remember { mutableStateOf<LocalTextPreview?>(null) }
    var query by remember { mutableStateOf("") }
    var matches by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("Optional local-only UTF-8 text preview. Selection is not upload approval. A system document provider may itself download remote files and use data.") }
    var busy by remember { mutableStateOf(false) }
    var generation by remember { mutableStateOf(0) }
    var work by remember { mutableStateOf<Job?>(null) }
    fun clearRead() { generation++; work?.cancel(); work = null; busy = false; preview = null; matches = "" }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        clearRead()
        selected = uri?.takeIf { it.scheme == "content" }
        label = if (selected != null) "One selected document" else ""
        status = if (selected == null) "Selection cancelled or unsupported URI; no content read." else "Document selected. Tap Read only if this text is appropriate to display locally. No upload, automatic open, copy or model call."
    }
    DisposableEffect(Unit) { onDispose { work?.cancel() } }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("SELECTED TEXT PREVIEW - no upload")
        Button(onClick = {
            clearRead(); selected = null; label = ""; query = ""
            try { picker.launch(arrayOf("text/plain", "text/markdown")) }
            catch (_: Exception) { status = "Text picker unavailable; no file content read." }
        }) { Text("Select one plain-text document") }
        if (label.isNotEmpty()) Text(label)
        Button(enabled = selected != null && !busy, onClick = {
            val uri = selected ?: return@Button
            clearRead(); busy = true
            val thisGeneration = generation
            status = "Reading selected UTF-8 text locally, at most 65536 bytes. Provider I/O can stall; cancel hides late results but is not a provider-operation cancellation guarantee."
            work = scope.launch {
                try {
                    val value = withContext(Dispatchers.IO) {
                        val resolver = context.contentResolver
                        val mime = resolver.getType(uri)
                        require(mime == "text/plain" || mime == "text/markdown")
                        var name = "One selected document"
                        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                            if (cursor.moveToFirst()) name = cursor.getString(0)?.filter { it.code >= 32 && it.code !in 127..159 && it.code !in 0x202A..0x202E && it.code !in 0x2066..0x2069 }?.take(160) ?: name
                        }
                        val content = resolver.openInputStream(uri)?.use { decodeSelectedText(it) }
                            ?: throw IllegalArgumentException("Unavailable stream")
                        ensureActive()
                        name to content
                    }
                    label = value.first
                    preview = value.second
                    status = "Read ${value.second.bytesRead} bytes locally; ${value.second.controlsReplaced} control/bidi characters replaced. Newlines normalized. Provider metadata is not verified identity/latest-version proof. No content uploaded, executed or copied."
                } catch (_: kotlinx.coroutines.CancellationException) {
                    // Cancelled/changed selection never publishes its eventual result.
                    throw kotlinx.coroutines.CancellationException()
                } catch (_: Exception) {
                    preview = null
                    status = "Unable to read a bounded UTF-8 plain-text document. It may be oversized, malformed, unsupported, unavailable or permission-revoked. Nothing displayed or uploaded."
                } finally { if (generation == thisGeneration) busy = false }
            }
        }) { Text("Read selected text locally (max 64 KiB)") }
        if (busy) TextButton(onClick = { clearRead(); status = "Read cancelled locally; late result will not display. Provider I/O may still finish. Nothing uploaded." }) { Text("Cancel local read") }
        preview?.let { value ->
            Text(value.text.ifEmpty { "[Empty text document]" }, modifier = Modifier.fillMaxWidth().heightIn(max = 240.dp).verticalScroll(rememberScrollState()))
            OutlinedTextField(value = query, onValueChange = { query = it.take(200); matches = "" }, label = { Text("Find literal text in this preview only") }, modifier = Modifier.fillMaxWidth())
            Button(onClick = {
                matches = try {
                    val result = findLocalTextLines(value.text, query)
                    if (result.lineNumbers.isEmpty()) "No matching lines in this captured preview. Not a device-wide search."
                    else "Matching preview lines: ${result.lineNumbers.joinToString()}${if (result.truncated) "; first 100 only" else ""}. Not a device-wide search."
                } catch (_: Exception) { "Enter nonblank literal search text, at most 200 characters." }
            }) { Text("Find in captured text (no regex)") }
        }
        if (matches.isNotEmpty()) Text(matches)
        TextButton(onClick = { clearRead(); selected = null; label = ""; query = ""; status = "Preview and selection cleared locally. This is not secure erasure of process memory, OS/provider logs or backups." }) { Text("Clear text and selection") }
        Text(status)
    }
}
