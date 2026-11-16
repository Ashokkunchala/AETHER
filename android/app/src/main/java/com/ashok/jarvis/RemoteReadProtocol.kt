package com.ashok.jarvis

import java.net.URI

internal const val REMOTE_READ_ACTION = "memory_snapshot"
internal val REMOTE_READ_STATES = setOf("pending_local_review", "running_local_read", "completed", "denied", "failed", "expired", "result_expired", "stopped", "revoked")

internal fun remoteReadBase(value: String): String {
    require(value.length in 9..2048 && value.none { it.code <= 32 || it.code == 127 } && '\\' !in value)
    val uri = URI(value)
    require(uri.scheme == "https" && uri.host != null && uri.rawUserInfo == null && uri.rawQuery == null && uri.rawFragment == null)
    require(uri.port == -1 || uri.port == 443)
    require(uri.rawPath.isNullOrEmpty() || uri.rawPath == "/")
    return value.removeSuffix("/")
}

internal fun remoteReadId(value: String): String {
    require(Regex("[0-9a-f]{32}").matches(value))
    return value
}

internal fun remoteReadTokenValid(value: String): Boolean = value.length in 32..256 && value.all { it.code in 33..126 }

internal fun remoteMemoryValid(total: Long, available: Long, usedPercent: Double): Boolean =
    total in 1..(1L shl 60) && available in 0..total && usedPercent.isFinite() && usedPercent in 0.0..100.0
