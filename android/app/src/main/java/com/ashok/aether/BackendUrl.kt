package com.ashok.aether

import java.net.URI

/** Only an HTTPS origin, optionally with a LAN port. Never credentials or URL parameters. */
internal fun backendOrigin(value: String): String {
    require(value.length in 9..2048 && value.none { it.code <= 32 || it.code == 127 } && '\\' !in value) {
        "Enter an HTTPS backend origin without spaces."
    }
    val uri = URI(value)
    require(uri.scheme == "https" && uri.host != null && uri.rawUserInfo == null &&
        uri.rawQuery == null && uri.rawFragment == null &&
        (uri.rawPath.isNullOrEmpty() || uri.rawPath == "/") &&
        (uri.port == -1 || uri.port in 1..65535)) {
        "Use https://hostname:port only, without a path, login or query."
    }
    return value.removeSuffix("/")
}
