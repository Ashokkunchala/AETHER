package com.ashok.aether

import java.io.ByteArrayInputStream
import org.junit.Assert.*
import org.junit.Test

class SelectedTextTest {
    @Test fun utf8BomAndNewlinesAreExplicitlyNormalized() {
        val result = decodeSelectedText(ByteArrayInputStream("\uFEFFTelugu తెలుగు\r\nnext\rfinal".toByteArray()))
        assertEquals("Telugu తెలుగు\nnext\nfinal", result.text)
        assertEquals(0, result.controlsReplaced)
    }
    @Test fun emptyAndExactBoundAcceptedButOneExtraByteRefused() {
        assertEquals("", decodeSelectedText(ByteArrayInputStream(byteArrayOf())).text)
        assertEquals(65536, decodeSelectedText(ByteArrayInputStream(ByteArray(65536) { 65 })).bytesRead)
        try { decodeSelectedText(ByteArrayInputStream(ByteArray(65537) { 65 })); fail("oversized") } catch (_: IllegalArgumentException) {}
    }
    @Test fun malformedUtf8RefusedInsteadOfClaimingAccurateText() {
        try { decodeSelectedText(ByteArrayInputStream(byteArrayOf(0xC3.toByte(), 0x28))); fail("malformed") } catch (_: java.nio.charset.CharacterCodingException) {}
    }
    @Test fun controlsAndBidiReplacedNotInterpreted() {
        val value = decodeSelectedText(ByteArrayInputStream("hello\u0000\u001B\u202E\u2066\tworld".toByteArray()))
        assertEquals(4, value.controlsReplaced)
        assertEquals("hello\uFFFD\uFFFD\uFFFD\uFFFD\tworld", value.text)
    }
    @Test fun searchLiteralCaseInsensitiveOneBasedLines() {
        assertEquals(listOf(1,3), findLocalTextLines("A.*b\nnone\na.*B", ".*b").lineNumbers)
        assertTrue(findLocalTextLines("hello", "absent").lineNumbers.isEmpty())
        assertEquals(listOf(2), findLocalTextLines("one\nతెలుగు", "తెలుగు").lineNumbers)
    }
    @Test fun searchBoundedAndBlankRefused() {
        val value = findLocalTextLines(List(101) { "match" }.joinToString("\n"), "match")
        assertEquals(100, value.lineNumbers.size); assertTrue(value.truncated)
        assertFalse(findLocalTextLines(List(100) { "match" }.joinToString("\n"), "match").truncated)
        for (query in listOf("", " ", "x".repeat(201))) {
            try { findLocalTextLines("text", query); fail("invalid") } catch (_: IllegalArgumentException) {}
        }
    }
}
