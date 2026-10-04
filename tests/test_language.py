from app.nlp.language import detect_language


def test_french_with_codes_stays_french():
    assert detect_language("Que faire en cas de E301 ?") == "fr"
    assert detect_language("Quelle référence pour RF-CAB-330 ?") == "fr"
    assert detect_language("Combien de fois cette machine a eu une maintenance ?") == "fr"


def test_darija_latin_is_detected():
    assert detect_language("kayn tsrib dyal zit f la presse, achno ndir ?") == "darija"
    assert detect_language("kifach nconsigni la machine ?") == "darija"
    assert detect_language("l 3tal dyal robot") == "darija"


def test_arabic_script_is_detected():
    assert detect_language("كيفاش نصلح مشكل Profinet؟") == "ar"