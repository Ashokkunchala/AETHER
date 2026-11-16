package com.ashok.jarvis

import org.junit.Assert.*
import org.junit.Test

class PhoneActionsValidationTest {
    @Test fun exactInternationalNumbersOnly() {
        assertTrue(validPhoneTarget("+919876543210"))
        for (value in listOf("9876543210", "+0", "+919876543210;123", "tel:+919876543210", "*123#", "+919876543210\n", "+91 9876543210")) assertFalse(value, validPhoneTarget(value))
    }
    @Test fun timezoneOffsetsPreserveExactInstants() {
        val times = calendarTimes("2026-12-01T10:00:00+05:30", "2026-12-01T11:00:00+05:30")
        assertEquals(3600000L, times.second - times.first)
        assertEquals(times, calendarTimes("2026-12-01T04:30:00Z", "2026-12-01T05:30:00Z"))
    }
    @Test fun malformedOrReversedTimesRefused() {
        for (pair in listOf("bad" to "bad", "2026-12-01T10:00:00" to "2026-12-01T11:00:00", "2026-12-01T10:00:00Z" to "2026-12-01T09:00:00Z")) {
            try { calendarTimes(pair.first, pair.second); fail("Expected invalid time") } catch (_: IllegalArgumentException) {} catch (_: java.time.DateTimeException) {}
        }
    }
}
