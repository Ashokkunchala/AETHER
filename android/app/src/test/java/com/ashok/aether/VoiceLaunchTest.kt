package com.ashok.aether

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceLaunchTest {

    @Test
    fun `exact live voice action matches`() {
        assertTrue(isLiveVoiceLaunch(ACTION_START_LIVE_VOICE))
    }

    @Test
    fun `null blank and other actions never match`() {
        assertFalse(isLiveVoiceLaunch(null))
        assertFalse(isLiveVoiceLaunch(""))
        assertFalse(isLiveVoiceLaunch("com.ashok.aether.action.START_LIVE_VOICE2"))
        assertFalse(isLiveVoiceLaunch("com.ashok.aether.action.START_LIVE_VOICE "))
        assertFalse(isLiveVoiceLaunch(ACTION_START_LIVE_VOICE.lowercase()))
        assertFalse(isLiveVoiceLaunch("android.intent.action.MAIN"))
    }

    @Test
    fun `action constant is namespaced and stable`() {
        assertEquals("com.ashok.aether.action.START_LIVE_VOICE", ACTION_START_LIVE_VOICE)
    }
}
