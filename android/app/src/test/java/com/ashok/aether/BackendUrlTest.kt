package com.ashok.aether

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class BackendUrlTest {
    @Test fun acceptsHttpsOriginsAndLanPorts() {
        assertEquals("https://192.168.1.10:8000", backendOrigin("https://192.168.1.10:8000/"))
        assertEquals("https://aether.example", backendOrigin("https://aether.example"))
    }
    @Test fun rejectsCredentialAndRoutingConfusion() {
        listOf("http://host", "https://user:pass@host", "https://host/path", "https://host?q=secret",
            "https://host#fragment", "https://host:0", "https://host:65536", "https://host\\evil",
            " https://host", "https://host\n").forEach { value ->
            assertThrows("Rejected: $value", IllegalArgumentException::class.java) { backendOrigin(value) }
        }
    }
}
