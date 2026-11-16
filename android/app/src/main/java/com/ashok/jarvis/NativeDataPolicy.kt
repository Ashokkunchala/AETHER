package com.ashok.jarvis

import kotlin.math.*

internal fun imageSampleSize(width: Int, height: Int): Int {
    require(width in 1..32768 && height in 1..32768 && width.toLong() * height <= 100_000_000)
    var sample = 1
    while ((width + sample - 1) / sample > 512 || (height + sample - 1) / sample > 512) sample *= 2
    return sample
}

internal fun freshLocation(ageNanos: Long, latitude: Double, longitude: Double, accuracy: Float): Boolean =
    ageNanos in 0..60_000_000_000L && latitude.isFinite() && latitude in -90.0..90.0 &&
        longitude.isFinite() && longitude in -180.0..180.0 && accuracy.isFinite() && accuracy >= 0

internal fun distanceMeters(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    require(listOf(lat1, lon1, lat2, lon2).all { it.isFinite() })
    require(lat1 in -90.0..90.0 && lat2 in -90.0..90.0 && lon1 in -180.0..180.0 && lon2 in -180.0..180.0)
    val a = sin(Math.toRadians(lat2 - lat1) / 2).pow(2) + cos(Math.toRadians(lat1)) *
        cos(Math.toRadians(lat2)) * sin(Math.toRadians(lon2 - lon1) / 2).pow(2)
    return 6_371_000.0 * 2 * asin(sqrt(a.coerceIn(0.0, 1.0)))
}

// Require the accuracy circle to fit inside the target, not merely its centre.
internal fun definitelyInside(distance: Double, accuracy: Float, radius: Double): Boolean =
    distance.isFinite() && distance >= 0 && accuracy.isFinite() && accuracy >= 0 &&
        radius.isFinite() && radius in 100.0..50000.0 && distance + accuracy <= radius
