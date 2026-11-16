package com.ashok.jarvis

import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction

internal const val SELECTED_TEXT_MAX_BYTES = 65536
internal data class LocalTextPreview(val text: String, val bytesRead: Int, val controlsReplaced: Int)
internal data class LocalTextMatches(val lineNumbers: List<Int>, val truncated: Boolean)

internal fun decodeSelectedText(stream: InputStream): LocalTextPreview {
    val bytes = ByteArrayOutputStream()
    val buffer = ByteArray(4096)
    while (true) {
        // Read at most one extra byte to detect an oversized document.
        val remaining = SELECTED_TEXT_MAX_BYTES + 1 - bytes.size()
        if (remaining <= 0) throw IllegalArgumentException("Selected text exceeds 65536 bytes; nothing displayed.")
        val count = stream.read(buffer, 0, minOf(buffer.size, remaining))
        if (count == -1) break
        if (count == 0) throw IllegalArgumentException("Provider returned no progress; nothing displayed.")
        bytes.write(buffer, 0, count)
        if (bytes.size() > SELECTED_TEXT_MAX_BYTES) throw IllegalArgumentException("Selected text exceeds 65536 bytes; nothing displayed.")
    }
    val raw = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes.toByteArray())).toString().removePrefix("\uFEFF")
    var replaced = 0
    val safe = raw.map { char ->
        if ((char.code < 32 && char !in "\n\r\t") || char.code in 127..159 || char.code in 0x202A..0x202E || char.code in 0x2066..0x2069) {
            replaced++
            '\uFFFD'
        } else char
    }.joinToString("")
    return LocalTextPreview(safe.replace("\r\n", "\n").replace('\r', '\n'), bytes.size(), replaced)
}

internal fun findLocalTextLines(text: String, query: String): LocalTextMatches {
    require(query.isNotBlank() && query.length <= 200) { "Enter literal search text, 1-200 characters." }
    require(text.length <= SELECTED_TEXT_MAX_BYTES) { "Text preview exceeds local search bound." }
    val matches = mutableListOf<Int>()
    for ((index, line) in text.lineSequence().withIndex()) {
        if (line.contains(query, ignoreCase = true)) {
            if (matches.size == 100) return LocalTextMatches(matches, true)
            matches.add(index + 1)
        }
    }
    return LocalTextMatches(matches, false)
}
