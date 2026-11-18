package com.ashok.aether

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class GeminiCloudVisionTest {

    @Test fun apiKeyValidation() {
        val good = "AIzaSyD4iE-example-key-1234567890"
        assertEquals(good, GeminiCloudVision.checkedApiKey("  $good  "))
        for (bad in listOf("", "   ", "short", "has space inside the key value", "a".repeat(301))) {
            try {
                GeminiCloudVision.checkedApiKey(bad)
                fail("expected refusal for invalid key")
            } catch (_: IllegalArgumentException) {
            }
        }
    }

    @Test fun requestJsonIsValidAndBounded() {
        val b64 = "QUJDREVGRw=="
        val json = JSONObject(GeminiCloudVision.buildRequestJson(b64))
        val parts = json.getJSONArray("contents").getJSONObject(0).getJSONArray("parts")
        assertTrue(parts.getJSONObject(0).getString("text").contains("Describe this image"))
        val inline = parts.getJSONObject(1).getJSONObject("inline_data")
        assertEquals("image/jpeg", inline.getString("mime_type"))
        assertEquals(b64, inline.getString("data"))
        assertEquals(512, json.getJSONObject("generationConfig").getInt("maxOutputTokens"))
    }

    @Test fun requestJsonRejectsBadPayload() {
        for (bad in listOf("", "not base64 !!", "QUJD\nREVGRw==", "A".repeat(6 * 1024 * 1024))) {
            try {
                GeminiCloudVision.buildRequestJson(bad)
                fail("expected refusal for payload")
            } catch (_: IllegalArgumentException) {
            }
        }
    }

    @Test fun promptIsEscapedSafely() {
        val tricky = "say \"hi\"\nnow\\done"
        val json = JSONObject(GeminiCloudVision.buildRequestJson("QUJD", tricky))
        val text = json.getJSONArray("contents").getJSONObject(0)
            .getJSONArray("parts").getJSONObject(0).getString("text")
        assertEquals(tricky, text)
    }

    @Test fun parsesDescriptionParts() {
        val body = """{"candidates":[{"content":{"parts":[{"text":"A dog on a beach."},{"text":" Sunny day."}]}}]}"""
        assertEquals("A dog on a beach. Sunny day.", GeminiCloudVision.parseResponse(body))
    }

    @Test fun parseRejectsEmptyShapes() {
        for (bad in listOf(
            "{}",
            """{"candidates":[]}""",
            """{"candidates":[{"content":{}}]}""",
            """{"candidates":[{"content":{"parts":[{"text":"   "}]}}]}""",
        )) {
            try {
                GeminiCloudVision.parseResponse(bad)
                fail("expected refusal for: $bad")
            } catch (_: Exception) {
            }
        }
    }

    @Test fun parseTruncatesLongOutput() {
        val body = """{"candidates":[{"content":{"parts":[{"text":"""" + "x".repeat(5000) + """"}]}}]}"""
        assertEquals(4000, GeminiCloudVision.parseResponse(body).length)
    }

    @Test fun httpErrorsAreHonestAndKeyless() {
        assertTrue(GeminiCloudVision.httpErrorMessage(401, "{}").contains("API key"))
        assertTrue(GeminiCloudVision.httpErrorMessage(403, "{}").contains("API key"))
        assertTrue(GeminiCloudVision.httpErrorMessage(429, "{}").contains("quota"))
        assertTrue(GeminiCloudVision.httpErrorMessage(503, "{}").contains("server"))
        val detail = GeminiCloudVision.httpErrorMessage(400, """{"error":{"message":"bad mime"}}""")
        assertTrue(detail.contains("400") && detail.contains("bad mime"))
        val other = GeminiCloudVision.httpErrorMessage(418, """{"error":{"message":"teapot"}}""")
        assertTrue(other.contains("418"))
        // The owner's key must never appear in an error message.
        assertFalse(GeminiCloudVision.httpErrorMessage(401, """{"error":{"message":"AIzaSySecretKey123456789012345"}}""")
            .contains("AIzaSySecretKey123456789012345"))
    }
}
