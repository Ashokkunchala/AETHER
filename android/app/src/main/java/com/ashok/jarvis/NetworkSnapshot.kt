package com.ashok.jarvis

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import java.time.Instant

internal enum class NetworkVisibility { CAPABILITIES, NONE_VISIBLE, UNAVAILABLE }

// No identifiers, network handle, backend address, credentials or private payload.
internal data class LocalNetworkSnapshot(
    val sampledAt: String,
    val visibility: NetworkVisibility,
    val transports: List<String> = emptyList(),
    val configuredInternet: Boolean? = null,
    val systemValidated: Boolean? = null,
    val captivePortal: Boolean? = null,
    val systemNotMetered: Boolean? = null,
)

internal fun networkSnapshotText(snapshot: LocalNetworkSnapshot): String {
    val details = when (snapshot.visibility) {
        NetworkVisibility.NONE_VISIBLE -> "No active default network visible to this app (none or blocked for this caller). This does not prove the device is globally offline."
        NetworkVisibility.UNAVAILABLE -> "Network capabilities unavailable; connectivity unknown. The network may have changed or access may be unavailable."
        NetworkVisibility.CAPABILITIES -> {
            fun flag(value: Boolean?) = when (value) { true -> "reported"; false -> "not reported"; null -> "unknown" }
            // Only labels from a fixed internal vocabulary are ever shown.
            val labels = snapshot.transports.filter { it in setOf("Wi-Fi", "cellular", "Ethernet", "VPN", "Bluetooth") }.distinct()
            "Default-network transports: ${labels.joinToString().ifEmpty { "other or unknown" }}. " +
                "Internet configuration capability: ${flag(snapshot.configuredInternet)}. " +
                "Android last-check general-internet validation: ${flag(snapshot.systemValidated)}. " +
                "Captive-portal capability: ${flag(snapshot.captivePortal)}. " +
                "Not-metered capability: ${flag(snapshot.systemNotMetered)} (not a tariff or cost guarantee)."
        }
    }
    return "$details Snapshot ${snapshot.sampledAt}. May change immediately. No AETHER/backend reachability check, network probe, identifier read, radio change, background monitor or upload."
}

internal fun readLocalNetworkSnapshot(context: Context): LocalNetworkSnapshot {
    val capturedAt = Instant.now().toString()
    return try {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return LocalNetworkSnapshot(capturedAt, NetworkVisibility.UNAVAILABLE)
        val network = manager.activeNetwork
            ?: return LocalNetworkSnapshot(capturedAt, NetworkVisibility.NONE_VISIBLE)
        val caps = manager.getNetworkCapabilities(network)
            ?: return LocalNetworkSnapshot(capturedAt, NetworkVisibility.UNAVAILABLE)
        val transports = listOf(
            NetworkCapabilities.TRANSPORT_WIFI to "Wi-Fi",
            NetworkCapabilities.TRANSPORT_CELLULAR to "cellular",
            NetworkCapabilities.TRANSPORT_ETHERNET to "Ethernet",
            NetworkCapabilities.TRANSPORT_VPN to "VPN",
            NetworkCapabilities.TRANSPORT_BLUETOOTH to "Bluetooth",
        ).filter { (transport, _) -> caps.hasTransport(transport) }.map { it.second }
        LocalNetworkSnapshot(
            capturedAt, NetworkVisibility.CAPABILITIES, transports,
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED),
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_CAPTIVE_PORTAL),
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED),
        )
    } catch (_: Exception) {
        // No exception text or identifiers; a permission/race/service failure is not offline.
        LocalNetworkSnapshot(capturedAt, NetworkVisibility.UNAVAILABLE)
    }
}
