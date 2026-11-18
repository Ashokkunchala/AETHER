package com.ashok.aether

import org.junit.Assert.*
import org.junit.Test

class SelectedPhoneNumberTest {
    @Test fun visualSeparatorsOnlyAreRemoved() {
        assertEquals("+919876543210", selectedInternationalNumber("+91 (987) 654-3210"))
        assertEquals("+14155552671", selectedInternationalNumber("+1.415.555.2671"))
        assertEquals("+919876543210", selectedInternationalNumber("+919876543210"))
    }

    @Test fun noCountryPrefixOrRecipientInference() {
        for (value in listOf(null, "", "9876543210", "00919876543210", "+0", "+123456", "+1234567890123456")) {
            assertNull(value, selectedInternationalNumber(value))
        }
    }

    @Test fun codesExtensionsMultipleNumbersAndUnicodeRefused() {
        for (value in listOf("+919876543210;123", "+919876543210,123", "+919876543210 ext 4", "+919876543210x4", "*123#", "tel:+919876543210", "+919876543210\n", "+919876543210\t", "+91/9876543210", "+919876543210 +14155552671", "+９１９８７６５４３２１０", "+1" + " ".repeat(81))) {
            assertNull(value, selectedInternationalNumber(value))
        }
    }
    @Test fun onlySpecificSystemPhoneDataRowRoutesAllowed() {
        assertTrue(selectedPhoneRouteAllowed("com.android.contacts", listOf("data", "123"), null, null))
        assertTrue(selectedPhoneRouteAllowed("com.android.contacts", listOf("data", "phones", "123"), null, null))
        for (path in listOf(emptyList<String>(), listOf("data"), listOf("data", "phones"), listOf("contacts", "123"), listOf("data", "phones", "bad"), listOf("data", "-1"), listOf("data", "0"))) {
            assertFalse(selectedPhoneRouteAllowed("com.android.contacts", path, null, null))
        }
        assertFalse(selectedPhoneRouteAllowed("unrecognized.provider", listOf("data", "123"), null, null))
        assertFalse(selectedPhoneRouteAllowed("com.android.contacts", listOf("data", "123"), "limit=1", null))
        assertFalse(selectedPhoneRouteAllowed("com.android.contacts", listOf("data", "123"), null, "fragment"))
    }
}
