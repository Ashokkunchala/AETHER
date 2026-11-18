package com.ashok.aether

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/** Pure matcher for the "Hey Aether" wake phrase; unit-tested on the JVM. */
internal object WakePhraseMatcher {
    /** Lowercases, splits on non-alphanumerics, drops empties; bounded at 40 tokens. */
    fun tokens(raw: String): List<String> =
        raw.lowercase().take(2000).split(Regex("[^a-z0-9]+")).filter { it.isNotEmpty() }.take(40)

    /** True for "hey aether", "hey ether" (common mishearing), or a standalone "aether" token. */
    fun matches(transcript: String): Boolean {
        val words = tokens(transcript)
        for (i in words.indices) {
            if (words[i] == "aether") return true
            if (words[i] == "hey" && i + 1 < words.size &&
                (words[i + 1] == "aether" || words[i + 1] == "ether")
            ) {
                return true
            }
        }
        return false
    }
}

/**
 * Foreground-only "Hey Aether" listener. Runs Android's on-device SpeechRecognizer
 * only while the app screen is visible and the owner has explicitly enabled the
 * toggle; the activity stops it on ON_STOP. It never records, stores or uploads
 * audio: when the phrase is heard it simply opens the app's normal voice capture,
 * whose transcript the owner still reviews before anything is sent.
 */
class WakePhraseController(
    private val context: Context,
    private val language: () -> String,
    private val onWake: () -> Unit,
    private val onStatus: (String) -> Unit,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    @Volatile private var active = false
    private var restartCount = 0

    val isActive: Boolean get() = active

    fun start() {
        check(!active) { "Wake phrase listener is already on." }
        require(SpeechRecognizer.isRecognitionAvailable(context)) {
            "On-device speech recognition is not available on this device."
        }
        active = true
        restartCount = 0
        onStatus(
            "Listening for \"Hey Aether\" while this screen is open. " +
                "Microphone is on; nothing is recorded or sent."
        )
        listen()
    }

    fun stop() {
        if (!active) return
        active = false
        release()
        onStatus("Wake phrase listener off. Microphone released.")
    }

    private fun release() {
        handler.removeCallbacksAndMessages(null)
        recognizer?.let {
            runCatching { it.stopListening() }
            runCatching { it.destroy() }
        }
        recognizer = null
    }

    private fun listen() {
        if (!active) return
        val rec = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = rec
        rec.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(eventType: Int, params: Bundle?) {}

            override fun onPartialResults(partialResults: Bundle?) {
                checkResults(partialResults)
            }

            override fun onResults(results: Bundle?) {
                if (!checkResults(results)) restart()
            }

            override fun onError(error: Int) {
                when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH,
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT,
                    -> restart()
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS ->
                        fail("Microphone permission missing; wake phrase listener stopped.")
                    SpeechRecognizer.ERROR_CLIENT,
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY,
                    SpeechRecognizer.ERROR_SERVER,
                    ->
                        if (restartCount < 5) {
                            restart(delayMs = 1500)
                        } else {
                            fail("Speech recognizer keeps failing; wake phrase listener stopped.")
                        }
                    else -> restart(delayMs = 1000)
                }
            }
        })
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, if (language() == "te") "te-IN" else "en-IN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
        }
        runCatching { rec.startListening(intent) }
            .onFailure { fail("Could not start speech recognition: ${it.message}") }
    }

    private fun checkResults(bundle: Bundle?): Boolean {
        if (!active) return true
        val heard = bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
        if (heard.any { WakePhraseMatcher.matches(it) }) {
            active = false
            release()
            onWake()
            return true
        }
        return false
    }

    private fun restart(delayMs: Long = 600) {
        if (!active) return
        restartCount++
        release()
        handler.postDelayed({ listen() }, delayMs)
    }

    private fun fail(message: String) {
        active = false
        release()
        onStatus(message)
    }
}
