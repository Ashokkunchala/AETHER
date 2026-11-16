package com.ashok.jarvis

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.URL
import javax.net.ssl.HttpsURLConnection

private fun remoteReadHttp(base: String, token: String, requestId: String?, cancel: Boolean = false): JSONObject {
    require(!cancel || requestId != null)
    val path = (if (requestId == null) "/v1/remote-read/requests" else "/v1/remote-read/requests/${remoteReadId(requestId)}") + if (cancel) "/cancel" else ""
    val connection = URL(remoteReadBase(base) + path).openConnection() as HttpsURLConnection
    try {
        connection.instanceFollowRedirects = false
        connection.connectTimeout = 8000
        connection.readTimeout = 8000
        connection.requestMethod = if (requestId == null || cancel) "POST" else "GET"
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("Accept", "application/json")
        if (requestId == null || cancel) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.outputStream.use { it.write((if (cancel) "{}" else "{\"action\":\"memory_snapshot\"}").toByteArray(Charsets.UTF_8)) }
        }
        require(connection.responseCode == if (requestId == null) 201 else 200)
        val bytes = connection.inputStream.use { stream ->
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(1024)
            while (true) {
                val n = stream.read(buffer, 0, minOf(buffer.size, 8193 - output.size()))
                if (n == -1) break
                require(n > 0)
                output.write(buffer, 0, n)
                require(output.size() <= 8192)
            }
            output.toByteArray()
        }
        return JSONObject(String(bytes, Charsets.UTF_8))
    } finally { connection.disconnect() }
}

@Composable
internal fun RemoteReadCard() {
    var expanded by remember { mutableStateOf(false) }
    var base by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var requestId by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("Optional Windows read-only memory request. Separate laptop pairing and reviewed HTTPS reachability are required; backend pairing is not companion access.") }
    var memory by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var generation by remember { mutableStateOf(0) }
    var work by remember { mutableStateOf<Job?>(null) }
    val scope = rememberCoroutineScope()
    fun invalidate() { generation++; work?.cancel(); work = null; busy = false; requestId = ""; memory = "" }
    DisposableEffect(Unit) { onDispose { work?.cancel() } }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { expanded = !expanded; if (!expanded) { invalidate(); token = ""; base = ""; status = "Local fields cleared. This does not cancel a queued laptop request or erase OS/network history." } }) { Text(if (expanded) "Close Windows read-only panel" else "Windows read-only request") }
            if (expanded) {
                Text("This sends only a fixed memory_snapshot request. Phone actions never approve laptop execution. No shell, generic tool, files, apps or fallback.")
                OutlinedTextField(value = base, onValueChange = { invalidate(); base = it.take(2048) }, label = { Text("Reviewed companion HTTPS origin (443 only)") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = token, onValueChange = { invalidate(); token = it.take(256) }, label = { Text("Dedicated laptop-issued per-device token, not backend/master token") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
                Button(enabled = !busy && remoteReadTokenValid(token), onClick = {
                    val exactBase = try { remoteReadBase(base) } catch (_: Exception) { status = "Use the exact reviewed HTTPS origin on port 443, no path/query/user info. No HTTP or certificate bypass."; return@Button }
                    invalidate(); busy = true
                    val activeGeneration = generation
                    val activeToken = token
                    status = "Queueing one fixed memory request. A timeout can leave a request pending; do not retry blindly. Nothing executes until reviewed on the laptop."
                    work = scope.launch {
                        try {
                            val value = withContext(Dispatchers.IO) { remoteReadHttp(exactBase, activeToken, null) }
                            require(value.getString("action") == REMOTE_READ_ACTION && value.getString("state") == "pending_local_review" && value.getBoolean("executed") == false)
                            val id = remoteReadId(value.getString("request_id"))
                            if (generation == activeGeneration) { requestId = id; status = "Pending laptop-local review, expires 120 seconds after queueing. Review the exact request and requesting device ID in the trusted laptop terminal. Then tap Check once. No polling or approval from this phone." }
                        } catch (_: Exception) { if (generation == activeGeneration) status = "Queue response unavailable or unsupported. No success claimed; the request may still exist. Check locally before retrying. Raw server errors are hidden." }
                        finally { if (generation == activeGeneration) busy = false }
                    }
                }) { Text("Request one laptop memory snapshot") }
                if (requestId.isNotEmpty()) {
                    Text("Exact request ID: $requestId")
                    Button(enabled = !busy, onClick = {
                        val activeId = requestId
                        val activeBase = base
                        val activeToken = token
                        val activeGeneration = generation
                        busy = true; memory = ""
                        work = scope.launch {
                            try {
                                val value = withContext(Dispatchers.IO) { remoteReadHttp(activeBase, activeToken, activeId) }
                                require(value.getString("request_id") == activeId && value.getString("action") == REMOTE_READ_ACTION)
                                val state = value.getString("state"); require(state in REMOTE_READ_STATES)
                                var display = ""
                                if (state == "completed") {
                                    val result = value.getJSONObject("result")
                                    require(result.length() == 3)
                                    val totalValue = result.get("total_bytes"); val availableValue = result.get("available_bytes"); val percentValue = result.get("used_percent_reported")
                                    require(totalValue is Long || totalValue is Int); require(availableValue is Long || availableValue is Int); require(percentValue is Number)
                                    val total = (totalValue as Number).toLong(); val available = (availableValue as Number).toLong(); val percent = percentValue.toDouble()
                                    require(remoteMemoryValid(total, available, percent))
                                    display = "Reported laptop memory: total $total bytes, available $available bytes, used $percent%. Captured after local review, not current health or a complete system report. Server result expires 120 seconds after collection; this displayed copy can be stale."
                                } else require(value.isNull("result"))
                                if (generation == activeGeneration) { memory = display; status = "Request state: $state. No automatic retry or background monitoring." }
                            } catch (_: Exception) { if (generation == activeGeneration) { memory = ""; status = "Request/result unavailable, expired, revoked, stopped or unsupported. No memory/health claim. No retry performed." } }
                            finally { if (generation == activeGeneration) busy = false }
                        }
                    }) { Text("Check this request once") }
                }
                if (requestId.isNotEmpty()) {
                    Button(enabled = !busy, onClick = {
                        val activeId = requestId
                        val activeBase = base
                        val activeToken = token
                        val activeGeneration = generation
                        busy = true; memory = ""
                        status = "Requesting owner-bound cancellation/result clearing. This does not terminate or undo a running read."
                        work = scope.launch {
                            try {
                                val value = withContext(Dispatchers.IO) { remoteReadHttp(activeBase, activeToken, activeId, true) }
                                require(value.getString("request_id") == activeId && value.getString("action") == REMOTE_READ_ACTION && value.getBoolean("cancel_acknowledged"))
                                require(value.isNull("result") && value.getBoolean("running_operation_termination_verified") == false)
                                val state = value.getString("state"); require(state in REMOTE_READ_STATES)
                                if (generation == activeGeneration) status = "Cancellation/result-clear acknowledged: $state. Pending requests cannot start. If already dispatched, the read may have happened; result access is suppressed, not OS cancellation or recall of previous copies."
                            } catch (_: Exception) { if (generation == activeGeneration) status = "Cancellation response unavailable or unsupported. No cancellation success claimed. The server request/read may remain; check this exact request or review on the laptop. No automatic retry." }
                            finally { if (generation == activeGeneration) busy = false }
                        }
                    }) { Text("Cancel this request / clear server result") }
                }
                Text(status)
                if (memory.isNotEmpty()) Text(memory)
                TextButton(onClick = { invalidate(); token = ""; status = "Local request/result/token fields cleared. Not server cancellation, secure erasure, token revocation or deletion of logs." }) { Text("Clear local fields (not cancel)") }
            }
        }
    }
}
