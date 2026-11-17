package com.ashok.jarvis

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import androidx.work.*
import kotlinx.coroutines.CancellationException
import java.util.UUID
import java.util.concurrent.TimeUnit

internal object LocalLocationReminder {
    private const val STORE = "aether_local_location_reminder"
    private const val WORK = "aether_local_proximity"
    private const val CHANNEL = "aether_local_proximity"
    private const val NOTIFICATION = 58031
    private val lock = Any()
    private fun prefs(context: Context) = context.getSharedPreferences(STORE, Context.MODE_PRIVATE)
    private fun boot(context: Context) = Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
    fun allowed(context: Context): Boolean = Build.VERSION.SDK_INT >= 30 &&
        context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED &&
        context.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED &&
        (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) &&
        context.getSystemService(NotificationManager::class.java).areNotificationsEnabled()
    fun status(context: Context): String = synchronized(lock) {
        val p = prefs(context)
        if (target(context) != null) "One local reminder enabled until ${java.time.Instant.ofEpochMilli(p.getLong("expires", 0))}; background delivery is best-effort."
        else "No background location reminder enabled."
    }
    fun enable(context: Context, latitude: Double, longitude: Double, radius: Double, note: String, hours: Int) = synchronized(lock) {
        require(allowed(context) && boot(context) >= 0)
        require(latitude.isFinite() && latitude in -90.0..90.0 && longitude.isFinite() && longitude in -180.0..180.0)
        require(radius.isFinite() && radius in 100.0..50000.0 && note.isNotBlank() && note.length <= 200 && hours in 1..168)
        val token = UUID.randomUUID().toString()
        val expiry = System.currentTimeMillis() + hours * 3_600_000L
        val expiresElapsed = SystemClock.elapsedRealtime() + hours * 3_600_000L
        require(prefs(context).edit().clear().putString("id", token).putString("lat", latitude.toString()).putString("lon", longitude.toString())
            .putString("radius", radius.toString()).putString("note", note).putLong("expires", expiry)
            .putLong("expires_elapsed", expiresElapsed).putLong("created_elapsed", SystemClock.elapsedRealtime()).putInt("boot", boot(context)).putBoolean("enabled", true).commit())
        try {
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.CANCEL_AND_REENQUEUE,
                PeriodicWorkRequestBuilder<LocationReminderWorker>(15, TimeUnit.MINUTES).build())
        } catch (e: Exception) { prefs(context).edit().clear().commit(); throw e }
    }
    fun disable(context: Context) = synchronized(lock) {
        require(prefs(context).edit().clear().commit())
        WorkManager.getInstance(context).cancelUniqueWork(WORK)
        context.getSystemService(NotificationManager::class.java).cancel(NOTIFICATION)
    }
    data class Target(val id: String, val lat: Double, val lon: Double, val radius: Double)
    fun target(context: Context): Target? = synchronized(lock) {
        val p = prefs(context)
        val now = SystemClock.elapsedRealtime()
        if (!p.getBoolean("enabled", false)) return@synchronized null
        // Reboot/clock-reset fails closed; user re-enables. Wall clock cannot prolong monotonic lifetime.
        if (!reminderWindowValid(p.getLong("created_elapsed", -1), p.getLong("expires_elapsed", 0), now,
                p.getLong("expires", 0), System.currentTimeMillis(), p.getInt("boot", -2), boot(context))) {
            disable(context); return@synchronized null
        }
        if (!allowed(context)) { disable(context); return@synchronized null }
        try { Target(p.getString("id", null) ?: return@synchronized null, p.getString("lat", null)!!.toDouble(), p.getString("lon", null)!!.toDouble(), p.getString("radius", null)!!.toDouble()) }
        catch (_: Exception) { disable(context); null }
    }
    fun notifyIfCurrent(context: Context, target: Target, distance: Double, accuracy: Float) = synchronized(lock) {
        val current = LocalLocationReminder.target(context)
        if (current != target || !definitelyInside(distance, accuracy, target.radius)) return@synchronized
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "AETHER local proximity reminders", NotificationManager.IMPORTANCE_DEFAULT))
        if (manager.getNotificationChannel(CHANNEL)?.importance == NotificationManager.IMPORTANCE_NONE) return@synchronized
        val message = prefs(context).getString("note", "Local reminder").orEmpty().take(200)
        // Consume before notification, no duplicate retry after process loss. A crash can lose delivery.
        require(prefs(context).edit().clear().commit())
        val open = PendingIntent.getActivity(context, NOTIFICATION, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        manager.notify(NOTIFICATION, Notification.Builder(context, CHANNEL).setSmallIcon(android.R.drawable.ic_popup_reminder)
            .setContentTitle("AETHER local proximity reminder").setContentText(message).setVisibility(Notification.VISIBILITY_PRIVATE)
            .setContentIntent(open).setAutoCancel(true).build())
        WorkManager.getInstance(context).cancelUniqueWork(WORK)
    }
}

class LocationReminderWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        try {
            val target = LocalLocationReminder.target(applicationContext) ?: return Result.success()
            val fix = readApproximateLocation(applicationContext) ?: return Result.success()
            val age = SystemClock.elapsedRealtimeNanos() - fix.elapsedRealtimeNanos
            if (!fix.hasAccuracy() || !freshLocation(age, fix.latitude, fix.longitude, fix.accuracy)) return Result.success()
            if (!isStopped) LocalLocationReminder.notifyIfCurrent(applicationContext, target,
                distanceMeters(fix.latitude, fix.longitude, target.lat, target.lon), fix.accuracy)
            return Result.success()
        } catch (e: CancellationException) { throw e }
        catch (_: Exception) { return Result.success() } // No stale fallback or aggressive retry.
    }
}
