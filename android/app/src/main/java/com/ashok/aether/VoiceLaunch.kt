package com.ashok.aether

import android.content.Context
import android.content.Intent

/**
 * Notification "Talk now" action: tapping it opens the app and shows one
 * explicit in-app Live Voice offer. The microphone still starts only from the
 * user's own tap inside the app; the notification never starts audio itself.
 */
internal const val ACTION_START_LIVE_VOICE = "com.ashok.aether.action.START_LIVE_VOICE"

internal fun isLiveVoiceLaunch(action: String?): Boolean = action == ACTION_START_LIVE_VOICE

internal fun liveVoiceLaunchIntent(context: Context): Intent =
    Intent(context, MainActivity::class.java).setAction(ACTION_START_LIVE_VOICE)
