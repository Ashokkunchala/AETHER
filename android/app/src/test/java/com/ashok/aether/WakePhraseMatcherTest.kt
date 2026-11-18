package com.ashok.aether

import org.junit.Assert.*
import org.junit.Test

class WakePhraseMatcherTest {

    @Test fun matchesWakePhraseVariants() {
        assertTrue(WakePhraseMatcher.matches("Hey Aether"))
        assertTrue(WakePhraseMatcher.matches("hey, aether!"))
        assertTrue(WakePhraseMatcher.matches("AETHER"))
        assertTrue(WakePhraseMatcher.matches("aether"))
        assertTrue(WakePhraseMatcher.matches("okay hey ether"))
        assertTrue(WakePhraseMatcher.matches("Hey Aether, what's the time"))
        assertTrue(WakePhraseMatcher.matches("um hey aether please"))
    }

    @Test fun rejectsLookalikesAndNoise() {
        assertFalse(WakePhraseMatcher.matches(""))
        assertFalse(WakePhraseMatcher.matches("   "))
        assertFalse(WakePhraseMatcher.matches("either way"))
        assertFalse(WakePhraseMatcher.matches("ethernet cable"))
        assertFalse(WakePhraseMatcher.matches("hey there"))
        assertFalse(WakePhraseMatcher.matches("the ether is vast"))
        assertFalse(WakePhraseMatcher.matches("aethernet"))
        assertFalse(WakePhraseMatcher.matches("hey"))
        assertFalse(WakePhraseMatcher.matches("what time is it"))
    }

    @Test fun tokenizationIsBoundedAndNormalized() {
        assertEquals(listOf("hey", "aether"), WakePhraseMatcher.tokens("Hey, AETHER!!"))
        assertEquals(40, WakePhraseMatcher.tokens("word ".repeat(200)).size)
    }
}
