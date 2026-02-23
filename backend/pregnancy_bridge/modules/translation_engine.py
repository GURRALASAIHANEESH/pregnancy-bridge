"""
Offline Multi-Language Translation Engine
Translates ASHA explanations to Telugu and Hindi using controlled vocabulary
Author: PregnancyBridge Development Team
Version: 1.0.0
Date: 2026-02-04
"""

from typing import Dict, List
import logging
import re

logger = logging.getLogger(__name__)


class TranslationEngine:
    """
    Controlled vocabulary translation for medical explanations.
    
    Uses phrase-based translation with medical terminology mappings.
    Designed for offline operation without external API dependencies.
    
    Supported languages:
        - English (source)
        - Telugu
        - Hindi
    """
    
    # Translation dictionaries - phrase-based for accuracy
    TRANSLATIONS = {
        'telugu': {
            # Medical conditions
            'high blood pressure': 'అధిక రక్తపోటు',
            'blood pressure': 'రక్తపోటు',
            'protein in urine': 'మూత్రంలో ప్రోటీన్',
            'hemoglobin': 'హిమోగ్లోబిన్',
            'weak blood': 'బలహీనమైన రక్తం',
            'low hemoglobin': 'తక్కువ హిమోగ్లోబిన్',
            'anemia': 'రక్తహీనత',
            'platelets': 'ప్లేట్‌లెట్స్',
            'blood clotting cells': 'రక్తం గడ్డకట్టే కణాలు',
            'clotting cells': 'గడ్డకట్టే కణాలు',
            'infection': 'ఇన్‌ఫెక్షన్',
            'serious infection': 'తీవ్రమైన ఇన్‌ఫెక్షన్',
            'fits': 'మూర్ఛలు',
            'seizures': 'మూర్ఛలు',
            'convulsions': 'మూర్ఛలు',
            'bleeding': 'రక్తస్రావం',
            'dangerous bleeding': 'ప్రమాదకరమైన రక్తస్రావం',
            'heavy bleeding': 'తీవ్రమైన రక్తస్రావం',
            
            # Body parts and symptoms
            'headache': 'తలనొప్పి',
            'severe headache': 'తీవ్రమైన తలనొప్పి',
            'vision problems': 'చూపు సమస్యలు',
            'seeing spots': 'మచ్చలు కనిపించడం',
            'stomach pain': 'కడుపు నొప్పి',
            'severe stomach pain': 'తీవ్రమైన కడుపు నొప్పి',
            'breathless': 'ఊపిరి ఆడకపోవడం',
            'feeling breathless': 'ఊపిరి ఆడకపోవడం అనిపించడం',
            'vagina': 'యోని',
            
            # People
            'mother': 'తల్లి',
            'baby': 'బిడ్డ',
            'doctor': 'వైద్యుడు',
            
            # Places and actions
            'hospital': 'ఆసుపత్రి',
            'delivery': 'ప్రసవం',
            'during delivery': 'ప్రసవ సమయంలో',
            'pregnancy': 'గర్భధారణ',
            'during pregnancy': 'గర్భధారణ సమయంలో',
            'ambulance': 'అంబులెన్స్',
            'vehicle': 'వాహనం',
            'treatment': 'చికిత్స',
            'medical care': 'వైద్య సంరక్షణ',
            'urgent medical care': 'తక్షణ వైద్య సంరక్షణ',
            
            # Severity terms
            'dangerous': 'ప్రమాదకరమైన',
            'serious': 'తీవ్రమైన',
            'urgent': 'అత్యవసరం',
            'emergency': 'అత్యవసర పరిస్థితి',
            'warning signs': 'హెచ్చరిక సంకేతాలు',
            
            # Action phrases
            'URGENT ACTION NEEDED': 'అత్యవసర చర్య అవసరం',
            'What is the problem': 'సమస్య ఏమిటి',
            'What to do': 'ఏమి చేయాలి',
            'Take mother to hospital': 'తల్లిని ఆసుపత్రికి తీసుకెళ్ళండి',
            'go to hospital': 'ఆసుపత్రికి వెళ్ళండి',
            'TODAY': 'ఈరోజే',
            'this week': 'ఈ వారం',
            'Do NOT delay': 'ఆలస్యం చేయవద్దు',
            'Do not delay': 'ఆలస్యం చేయవద్దు',
            'Do not wait': 'వేచి ఉండవద్దు',
            'arrange ambulance': 'అంబులెన్స్ ఏర్పాటు చేయండి',
            'Book appointment': 'అపాయింట్‌మెంట్ బుక్ చేయండి',
            'Warning signs to watch for': 'గమనించవలసిన హెచ్చరిక సంకేతాలు',
            'If ANY of these happen': 'వీటిలో ఏదైనా జరిగితే',
            'IMMEDIATELY': 'వెంటనే',
            'Early treatment prevents serious problems': 'ముందస్తు చికిత్స తీవ్రమైన సమస్యలను నివారిస్తుంది',
            
            # Conditional phrases
            'can cause': 'కలిగించవచ్చు',
            'can harm': 'హాని కలిగించవచ్చు',
            'can harm both mother and baby': 'తల్లి మరియు బిడ్డ ఇద్దరికీ హాని కలిగించవచ్చు',
            'needs urgent attention': 'తక్షణ శ్రద్ధ అవసరం',
            'is a serious warning sign': 'తీవ్రమైన హెచ్చరిక సంకేతం',
            'is a medical emergency': 'వైద్య అత్యవసర పరిస్థితి',
            'Both mother and baby are at high risk': 'తల్లి మరియు బిడ్డ ఇద్దరూ అధిక ప్రమాదంలో ఉన్నారు',
            
            # Specific medical explanations
            'This is a dangerous condition that can cause fits': 'ఇది మూర్ఛలను కలిగించే ప్రమాదకరమైన పరిస్థితి',
            'cannot carry enough oxygen': 'తగినంత ఆక్సిజన్ తీసుకెళ్లలేదు',
            'cannot carry enough oxygen to mother and baby': 'తల్లి మరియు బిడ్డకు తగినంత ఆక్సిజన్ తీసుకెళ్లలేదు',
            'can spread quickly': 'త్వరగా వ్యాపించవచ్చు',
            'if not treated': 'చికిత్స చేయకపోతే',
            'if not treated quickly': 'త్వరగా చికిత్స చేయకపోతే',
            'needs doctor attention': 'వైద్యుని శ్రద్ధ అవసరం',
            'Baby not moving as usual': 'బిడ్డ ఎప్పటిలా కదలడం లేదు',
            'does not go away': 'తగ్గడం లేదు',
        },
        
        'hindi': {
            # Medical conditions
            'high blood pressure': 'उच्च रक्तचाप',
            'blood pressure': 'रक्तचाप',
            'protein in urine': 'पेशाब में प्रोटीन',
            'hemoglobin': 'हीमोग्लोबिन',
            'weak blood': 'कमजोर खून',
            'low hemoglobin': 'कम हीमोग्लोबिन',
            'anemia': 'खून की कमी',
            'platelets': 'प्लेटलेट्स',
            'blood clotting cells': 'खून जमाने वाली कोशिकाएं',
            'clotting cells': 'जमाने वाली कोशिकाएं',
            'infection': 'संक्रमण',
            'serious infection': 'गंभीर संक्रमण',
            'fits': 'दौरे',
            'seizures': 'दौरे',
            'convulsions': 'दौरे',
            'bleeding': 'खून बहना',
            'dangerous bleeding': 'खतरनाक रक्तस्राव',
            'heavy bleeding': 'भारी रक्तस्राव',
            
            # Body parts and symptoms
            'headache': 'सिरदर्द',
            'severe headache': 'गंभीर सिरदर्द',
            'vision problems': 'दृष्टि समस्याएं',
            'seeing spots': 'धब्बे दिखना',
            'stomach pain': 'पेट दर्द',
            'severe stomach pain': 'गंभीर पेट दर्द',
            'breathless': 'सांस फूलना',
            'feeling breathless': 'सांस फूलने का अहसास',
            'vagina': 'योनि',
            
            # People
            'mother': 'माँ',
            'baby': 'बच्चा',
            'doctor': 'डॉक्टर',
            
            # Places and actions
            'hospital': 'अस्पताल',
            'delivery': 'प्रसव',
            'during delivery': 'प्रसव के दौरान',
            'pregnancy': 'गर्भावस्था',
            'during pregnancy': 'गर्भावस्था के दौरान',
            'ambulance': 'एम्बुलेंस',
            'vehicle': 'वाहन',
            'treatment': 'इलाज',
            'medical care': 'चिकित्सा देखभाल',
            'urgent medical care': 'तत्काल चिकित्सा देखभाल',
            
            # Severity terms
            'dangerous': 'खतरनाक',
            'serious': 'गंभीर',
            'urgent': 'तत्काल',
            'emergency': 'आपातकाल',
            'warning signs': 'चेतावनी संकेत',
            
            # Action phrases
            'URGENT ACTION NEEDED': 'तत्काल कार्रवाई की जरूरत',
            'What is the problem': 'समस्या क्या है',
            'What to do': 'क्या करें',
            'Take mother to hospital': 'माँ को अस्पताल ले जाएं',
            'go to hospital': 'अस्पताल जाएं',
            'TODAY': 'आज',
            'this week': 'इस सप्ताह',
            'Do NOT delay': 'देरी न करें',
            'Do not delay': 'देरी न करें',
            'Do not wait': 'प्रतीक्षा न करें',
            'arrange ambulance': 'एम्बुलेंस की व्यवस्था करें',
            'Book appointment': 'अपॉइंटमेंट बुक करें',
            'Warning signs to watch for': 'देखने के लिए चेतावनी संकेत',
            'If ANY of these happen': 'यदि इनमें से कोई भी हो',
            'IMMEDIATELY': 'तुरंत',
            'Early treatment prevents serious problems': 'शीघ्र उपचार गंभीर समस्याओं को रोकता है',
            
            # Conditional phrases
            'can cause': 'पैदा कर सकता है',
            'can harm': 'नुकसान पहुंचा सकता है',
            'can harm both mother and baby': 'माँ और बच्चे दोनों को नुकसान पहुंचा सकता है',
            'needs urgent attention': 'तत्काल ध्यान की आवश्यकता है',
            'is a serious warning sign': 'गंभीर चेतावनी संकेत है',
            'is a medical emergency': 'चिकित्सा आपातकाल है',
            'Both mother and baby are at high risk': 'माँ और बच्चे दोनों उच्च जोखिम में हैं',
            
            # Specific medical explanations
            'This is a dangerous condition that can cause fits': 'यह एक खतरनाक स्थिति है जो दौरे पैदा कर सकती है',
            'cannot carry enough oxygen': 'पर्याप्त ऑक्सीजन नहीं ले जा सकता',
            'cannot carry enough oxygen to mother and baby': 'माँ और बच्चे को पर्याप्त ऑक्सीजन नहीं ले जा सकता',
            'can spread quickly': 'जल्दी फैल सकता है',
            'if not treated': 'अगर इलाज न किया जाए',
            'if not treated quickly': 'अगर जल्दी इलाज न किया जाए',
            'needs doctor attention': 'डॉक्टर का ध्यान चाहिए',
            'Baby not moving as usual': 'बच्चा सामान्य रूप से हिल नहीं रहा',
            'does not go away': 'दूर नहीं होता',
        }
    }
    
    def __init__(self):
        """Initialize translation engine with controlled vocabularies"""
        logger.info("TranslationEngine initialized: Telugu, Hindi")
        
        # Pre-compile regex patterns for performance
        self._compiled_patterns = {}
        for lang in self.TRANSLATIONS:
            self._compiled_patterns[lang] = self._compile_patterns(lang)
    
    def _compile_patterns(self, language: str) -> List[tuple]:
        """
        Compile regex patterns for efficient translation.
        
        Args:
            language: Target language code
            
        Returns:
            List of (compiled_pattern, replacement) tuples
        """
        translations = self.TRANSLATIONS[language]
        
        # Sort phrases by length (longest first) to avoid partial matches
        sorted_phrases = sorted(translations.keys(), key=len, reverse=True)
        
        compiled = []
        for english_phrase in sorted_phrases:
            local_phrase = translations[english_phrase]
            # Create case-insensitive pattern with word boundaries
            pattern = re.compile(r'\b' + re.escape(english_phrase) + r'\b', re.IGNORECASE)
            compiled.append((pattern, local_phrase))
        
        return compiled
    
    def translate(self, text: str, target_language: str) -> str:
        """
        Translate English text to target language.
        
        Args:
            text: English text (typically ASHA explanation)
            target_language: 'telugu' or 'hindi'
            
        Returns:
            Translated text. Returns original if language not supported.
        """
        if target_language not in self.TRANSLATIONS:
            logger.warning(f"Unsupported language: {target_language}")
            return text
        
        translated = text
        
        # Apply pre-compiled patterns
        for pattern, replacement in self._compiled_patterns[target_language]:
            translated = pattern.sub(replacement, translated)
        
        return translated
    
    def translate_all(self, text: str) -> Dict[str, str]:
        """
        Translate text to all supported languages.
        
        Args:
            text: English source text
            
        Returns:
            Dictionary with translations in all languages including English
        """
        return {
            'english': text,
            'telugu': self.translate(text, 'telugu'),
            'hindi': self.translate(text, 'hindi')
        }
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported target languages.
        
        Returns:
            List of language codes
        """
        return list(self.TRANSLATIONS.keys())
    
    def add_custom_translation(self, 
                              language: str,
                              english_phrase: str,
                              translated_phrase: str) -> None:
        """
        Add custom translation mapping at runtime.
        
        Useful for domain-specific terms or local variations.
        
        Args:
            language: Target language code
            english_phrase: English source phrase
            translated_phrase: Translated phrase
        """
        if language not in self.TRANSLATIONS:
            logger.error(f"Cannot add translation for unsupported language: {language}")
            return
        
        self.TRANSLATIONS[language][english_phrase] = translated_phrase
        
        # Recompile patterns for this language
        self._compiled_patterns[language] = self._compile_patterns(language)
        
        logger.info(f"Added custom translation for '{english_phrase}' in {language}")
    
    def get_translation_coverage(self, text: str, target_language: str) -> Dict:
        """
        Analyze what percentage of text was successfully translated.
        
        Args:
            text: Source English text
            target_language: Target language
            
        Returns:
            Dictionary with coverage statistics
        """
        if target_language not in self.TRANSLATIONS:
            return {
                'coverage_percent': 0.0,
                'untranslated_words': [],
                'translated_phrases': []
            }
        
        translated = self.translate(text, target_language)
        
        # Count how many words remain in English (basic heuristic)
        words = text.lower().split()
        translated_words = translated.split()
        
        # Words that appear in both are likely untranslated
        english_alphabet = set('abcdefghijklmnopqrstuvwxyz')
        untranslated_count = 0
        untranslated_words = []
        
        for word in translated_words:
            if any(c in english_alphabet for c in word.lower()):
                untranslated_count += 1
                if word.lower() in words and word.lower() not in ['a', 'an', 'the', 'to', 'of']:
                    untranslated_words.append(word)
        
        coverage = (1 - (untranslated_count / len(translated_words))) * 100 if translated_words else 0
        
        return {
            'coverage_percent': round(coverage, 1),
            'total_words': len(translated_words),
            'untranslated_count': untranslated_count,
            'untranslated_words': list(set(untranslated_words))[:10]
        }


# Singleton instance
_translator_instance = None


def get_translator() -> TranslationEngine:
    """
    Get singleton instance of TranslationEngine.
    
    Returns:
        TranslationEngine instance
    """
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = TranslationEngine()
    return _translator_instance


if __name__ == "__main__":
    # Self-test
    print("\nTranslationEngine Self-Test")
    print("=" * 70)
    
    translator = get_translator()
    
    # Test English text
    test_text = """URGENT ACTION NEEDED

What is the problem:
Mother has high blood pressure and protein in urine.
This is a dangerous condition that can cause fits.
It can harm both mother and baby if not treated quickly.

What to do:
Take mother to hospital TODAY.
Do NOT delay - this is urgent for mother and baby safety.
If possible, arrange ambulance immediately.

Warning signs to watch for:
- Severe headache that does not go away
- Vision problems or seeing spots
- Heavy bleeding from vagina
- Baby not moving as usual"""
    
    print("\nOriginal (English):")
    print("-" * 70)
    print(test_text)
    
    print("\n\nTelugu Translation:")
    print("-" * 70)
    telugu = translator.translate(test_text, 'telugu')
    print(telugu)
    
    print("\n\nHindi Translation:")
    print("-" * 70)
    hindi = translator.translate(test_text, 'hindi')
    print(hindi)
    
    # Coverage analysis
    print("\n\nTranslation Coverage Analysis:")
    print("-" * 70)
    for lang in ['telugu', 'hindi']:
        coverage = translator.get_translation_coverage(test_text, lang)
        print(f"\n{lang.title()}:")
        print(f"  Coverage: {coverage['coverage_percent']}%")
        print(f"  Total words: {coverage['total_words']}")
        print(f"  Untranslated: {coverage['untranslated_count']}")
        if coverage['untranslated_words']:
            print(f"  Sample untranslated: {', '.join(coverage['untranslated_words'][:5])}")
    
    print("\n" + "=" * 70)
    print("Self-test complete")
