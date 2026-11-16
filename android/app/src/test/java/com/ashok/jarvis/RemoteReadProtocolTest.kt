package com.ashok.jarvis

import org.junit.Assert.*
import org.junit.Test

class RemoteReadProtocolTest {
    @Test fun originRequiresReviewedHttpsNoRedirectTargetParameters() {
        assertEquals("https://example.test", remoteReadBase("https://example.test/"))
        assertEquals("https://192.0.2.1:443", remoteReadBase("https://192.0.2.1:443"))
        for (value in listOf("http://example.test", "https://example.test:8443", "https://user@example.test", "https://example.test/path", "https://example.test?x=1", "https://example.test#x", "https://example.test\\evil", " https://example.test")) {
            try { remoteReadBase(value); fail("unsupported origin") } catch (_: IllegalArgumentException) {}
        }
    }
    @Test fun exactIdsTokensAndMemoryLimits() {
        assertEquals("a".repeat(32), remoteReadId("a".repeat(32)))
        for (value in listOf("A".repeat(32), "../x", "x".repeat(32))) {
            try { remoteReadId(value); fail("bad id") } catch (_: IllegalArgumentException) {}
        }
        assertTrue(remoteReadTokenValid("x".repeat(48)))
        assertFalse(remoteReadTokenValid("short")); assertFalse(remoteReadTokenValid("x".repeat(32) + "\n"))
        assertTrue(remoteMemoryValid(1000, 500, 50.0))
        assertFalse(remoteMemoryValid(0, 0, 0.0)); assertFalse(remoteMemoryValid(1000, 1001, 1.0))
        assertFalse(remoteMemoryValid(1000, 1, Double.NaN)); assertFalse(remoteMemoryValid(1000, 1, 101.0))
    }
}
