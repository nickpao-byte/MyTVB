package com.mytvb.network.ua

import android.content.Context
import com.mytvb.core.common.settings.AppSettingsDataStore
import org.koin.mp.KoinPlatform
import java.util.Locale
import kotlin.random.Random

class DesktopUserAgentStore(
    private val defaultUserAgent: String,
    private val preferenceKey: String
) {

    private val appSettings: AppSettingsDataStore get() = KoinPlatform.getKoin().get()

    private var currentUserAgent: String = defaultUserAgent

    fun init(context: Context): String {
        currentUserAgent = loadOrCreateCurrentUserAgent(context.applicationContext)
        return currentUserAgent
    }

    fun getCurrentUserAgent(): String {
        return currentUserAgent
    }

    fun getAcceptLanguage(locale: Locale = Locale.getDefault()): String {
        val languageTag = locale.toLanguageTag().ifBlank { "en-US" }
        val language = locale.language.ifBlank { "en" }
        return "$languageTag,$language;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    fun refreshUserAgent(context: Context?): String {
        val newUserAgent = generateDesktopUserAgent()
        currentUserAgent = newUserAgent
        appSettings.putStringAsync(preferenceKey, newUserAgent)
        return newUserAgent
    }

    private fun loadOrCreateCurrentUserAgent(context: Context): String {
        val stored = appSettings.getCachedString(preferenceKey).orEmpty().trim()
        if (stored.isNotBlank()) {
            return stored
        }
        val generated = generateDesktopUserAgent()
        appSettings.putStringAsync(preferenceKey, generated)
        return generated
    }

    private fun generateDesktopUserAgent(): String {
        // Keep the emulated desktop browser generation close to current Chrome stable/extended-stable.
        // Chrome 153 is stable in Sep 2026; 152 remains a normal extended-stable generation.
        val chromeMajor = Random.nextInt(152, 154)
        val chromeBuild = Random.nextInt(7900, 8050)
        val chromePatch = Random.nextInt(20, 220)
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/$chromeMajor.0.$chromeBuild.$chromePatch Safari/537.36"
    }
}
