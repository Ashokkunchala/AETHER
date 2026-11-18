package com.ashok.aether

import org.junit.Assert.*
import org.junit.Test

class NetworkSnapshotTest {
    private val time = "2026-11-16T18:00:00Z"

    @Test fun noneVisibleDoesNotMeanGlobalOffline() {
        val text = networkSnapshotText(LocalNetworkSnapshot(time, NetworkVisibility.NONE_VISIBLE))
        assertTrue(text.contains("none or blocked for this caller"))
        assertTrue(text.contains("does not prove the device is globally offline"))
        assertFalse(text.contains("transports:"))
        assertTrue(text.contains(time))
    }

    @Test fun unavailableIsUnknownNotHealthy() {
        val text = networkSnapshotText(LocalNetworkSnapshot(time, NetworkVisibility.UNAVAILABLE))
        assertTrue(text.contains("connectivity unknown"))
        assertTrue(text.contains("No AETHER/backend reachability check"))
        assertFalse(text.contains("Internet configuration capability:"))
    }

    @Test fun osCapabilitiesStaySeparateAndNotReportedIsNotFalseProof() {
        val text = networkSnapshotText(LocalNetworkSnapshot(time, NetworkVisibility.CAPABILITIES,
            listOf("Wi-Fi", "VPN"), true, false, true, false))
        assertTrue(text.contains("Wi-Fi, VPN"))
        assertTrue(text.contains("Internet configuration capability: reported"))
        assertTrue(text.contains("Android last-check general-internet validation: not reported"))
        assertTrue(text.contains("Captive-portal capability: reported"))
        assertTrue(text.contains("Not-metered capability: not reported"))
        assertTrue(text.contains("not a tariff or cost guarantee"))
        assertTrue(text.contains("May change immediately"))
    }

    @Test fun missingFlagsAndTransportsRemainUnknown() {
        val text = networkSnapshotText(LocalNetworkSnapshot(time, NetworkVisibility.CAPABILITIES))
        assertTrue(text.contains("other or unknown"))
        assertTrue(text.contains("Internet configuration capability: unknown"))
        assertTrue(text.contains("validation: unknown"))
    }

    @Test fun vocabularyIsBoundedAndDoesNotEchoUnknownLabels() {
        val text = networkSnapshotText(LocalNetworkSnapshot(time, NetworkVisibility.CAPABILITIES,
            listOf("private network name", "Wi-Fi", "Wi-Fi", "Ethernet", "cellular", "Bluetooth")))
        assertFalse(text.contains("private network name"))
        assertEquals(1, Regex("Wi-Fi").findAll(text).count())
        assertTrue(text.contains("Ethernet, cellular, Bluetooth"))
    }

    @Test fun validatedDoesNotClaimBackendOrCurrentGuarantee() {
        val text = networkSnapshotText(LocalNetworkSnapshot(time, NetworkVisibility.CAPABILITIES,
            listOf("Wi-Fi"), true, true, false, true))
        assertTrue(text.contains("last-check general-internet validation: reported"))
        assertTrue(text.contains("No AETHER/backend reachability check"))
        assertTrue(text.contains("no", ignoreCase = true))
        assertTrue(text.contains("background monitor or upload"))
    }
}
