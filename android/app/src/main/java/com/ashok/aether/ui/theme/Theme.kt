package com.ashok.aether.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Cinematic command-centre palette: deep navy space, cyan AETHER core glow.
val DeepSpaceNavy = Color(0xFF050A1F)
val PanelNavy = Color(0xFF0B1533)
val PanelNavyLight = Color(0xFF12204A)
val AETHERCyan = Color(0xFF35E0FF)
val AETHERCyanSoft = Color(0xFF7FEDFF)
val CoreAmber = Color(0xFFFFB347)
val AlertRed = Color(0xFFFF5C5C)
val TextPrimary = Color(0xFFE6F2FF)
val TextMuted = Color(0xFF8EA6C8)
val OutlineNavy = Color(0xFF2A3C63)

private val AETHERColorScheme = darkColorScheme(
    primary = AETHERCyan,
    onPrimary = Color(0xFF00222B),
    secondary = AETHERCyanSoft,
    onSecondary = Color(0xFF00222B),
    tertiary = CoreAmber,
    onTertiary = Color(0xFF2B1800),
    background = DeepSpaceNavy,
    onBackground = TextPrimary,
    surface = PanelNavy,
    onSurface = TextPrimary,
    surfaceVariant = PanelNavyLight,
    onSurfaceVariant = TextMuted,
    outline = OutlineNavy,
    error = AlertRed,
    onError = Color(0xFF2B0000),
)

@Composable
fun AETHERTheme(content: @Composable () -> Unit) {
    // Always the cinematic dark scheme; this app is a night command centre.
    MaterialTheme(colorScheme = AETHERColorScheme, content = content)
}
