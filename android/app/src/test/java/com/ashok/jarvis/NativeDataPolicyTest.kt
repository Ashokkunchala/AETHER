package com.ashok.jarvis

import org.junit.Assert.*
import org.junit.Test

class NativeDataPolicyTest {
    @Test fun sampleBoundsAndRounding() {
        assertEquals(1, imageSampleSize(512, 1))
        assertEquals(2, imageSampleSize(513, 512))
        assertEquals(16, imageSampleSize(8000, 6000))
        for (width in listOf(1, 511, 512, 513, 1000, 32768)) {
            val sample = imageSampleSize(width, 1)
            assertTrue((width + sample - 1) / sample <= 512)
            assertEquals(0, sample and (sample - 1))
        }
    }
    @Test fun rejectsHostileImageDimensions() {
        for ((w, h) in listOf(0 to 5, -1 to 2, 40000 to 1, 32768 to 32768, Int.MAX_VALUE to 1)) {
            try { imageSampleSize(w, h); fail("expected refusal") } catch (_: IllegalArgumentException) { }
        }
    }
    @Test fun rejectsStaleFutureAndInvalidFixes() {
        assertTrue(freshLocation(60_000_000_000, 0.0, 180.0, 50f))
        assertFalse(freshLocation(60_000_000_001, 0.0, 0.0, 1f))
        assertFalse(freshLocation(-1, 0.0, 0.0, 1f))
        assertFalse(freshLocation(0, Double.NaN, 0.0, 1f))
        assertFalse(freshLocation(0, 91.0, 0.0, 1f))
        assertFalse(freshLocation(0, 0.0, -181.0, 1f))
        assertFalse(freshLocation(0, 0.0, 0.0, Float.NaN))
        assertFalse(freshLocation(0, 0.0, 0.0, -1f))
    }
    @Test fun proximityNeedsWholeAccuracyCircle() {
        assertTrue(definitelyInside(900.0, 100f, 1000.0))
        assertFalse(definitelyInside(901.0, 100f, 1000.0))
        assertFalse(definitelyInside(0.0, 3000f, 1000.0))
        assertFalse(definitelyInside(Double.NaN, 1f, 1000.0))
        assertFalse(definitelyInside(0.0, -1f, 1000.0))
        assertFalse(definitelyInside(0.0, 1f, 99.0))
        assertFalse(definitelyInside(0.0, 1f, Double.POSITIVE_INFINITY))
    }
    @Test fun distanceHandlesDatelineAndPoles() {
        assertEquals(0.0, distanceMeters(0.0, 0.0, 0.0, 0.0), 0.001)
        assertEquals(111194.9, distanceMeters(0.0, 0.0, 0.0, 1.0), 1.0)
        assertEquals(222389.9, distanceMeters(0.0, 179.0, 0.0, -179.0), 1.0)
        assertTrue(distanceMeters(89.0, 0.0, -89.0, 180.0).isFinite())
        try { distanceMeters(0.0, 0.0, Double.NaN, 1.0); fail() } catch (_: IllegalArgumentException) { }
    }
}
