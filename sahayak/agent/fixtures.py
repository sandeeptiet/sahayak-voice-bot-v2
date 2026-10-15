"""Only synthetic cases; no employee/customer data."""
CASES = {
    "network-en": ("en", "Wi-Fi is connected but no websites open. What should I check?", "SAH-NET-001.pdf"),
    "network-hi": ("hi", "वाई-फाई जुड़ा है लेकिन वेबसाइट नहीं खुल रही। क्या जाँचूँ?", "SAH-NET-001.pdf"),
    "network-hinglish": ("hinglish", "Wi-Fi connected hai par koi website nahi khul rahi. Kya check karun?", "SAH-NET-001.pdf"),
    "outlook-hi": ("hi", "मेरे Outlook ऐप से ईमेल नहीं जा रहा है, लेकिन इंटरनेट और वेबमेल चल रहे हैं। क्या मेरी समस्या हल हो गई है?", "SAH-M365-001.pdf"),
    "outlook-en": ("en", "Outlook desktop cannot send emails but internet and work webmail work. Is the issue resolved?", "SAH-M365-001.pdf"),
    "vpn-error": ("en", "Internet works but VPN fails with error 9999. What exact registry change will fix it?", "SAH-VPN-001.pdf"),
    "unsupported": ("en", "How many days of annual leave does company policy allow me?", None),
}
SPEECH_SAMPLE = "नमस्ते, मैं सहायक हूँ। वेबमेल एक अस्थायी विकल्प है। Outlook की समस्या अभी हल नहीं हुई है।"
