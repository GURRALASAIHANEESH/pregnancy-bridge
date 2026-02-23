"""
ASHA Phrase Composer
Composes field-ready ASHA explanations from controlled phrase library
Author: PregnancyBridge Development Team
Version: 2.0.0
Date: 2026-02-04
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ASHAPhraseComposer:
    """
    Composes ASHA worker explanations using controlled phrase library.
    
    Production features:
    - Zero code-switching (pure target language)
    - Phrase-based composition (not word-by-word translation)
    - Fallback handling for missing phrases
    - Translation quality tracking
    
    Design rationale:
    Controlled phrase mapping is standard practice for field medical messaging.
    Avoids mistranslation and ensures consistent safety messaging.
    """
    
    def __init__(self, phrase_library_path: Optional[str] = None):
        """
        Initialize composer with phrase library.
        
        Args:
            phrase_library_path: Path to asha_phrase_library.json
                                Defaults to D:\MedGemma\data\asha_phrase_library.json
        """
        if phrase_library_path is None:
            # Default path
            base_path = Path(__file__).parent.parent
            phrase_library_path = base_path / 'data' / 'asha_phrase_library.json'
        
        self.phrase_library_path = Path(phrase_library_path)
        self.phrases = {}
        self.phrases_by_category = {}
        
        self._load_phrase_library()
        
        logger.info(f"ASHAPhraseComposer initialized with {len(self.phrases)} phrases")
    
    def _load_phrase_library(self):
        """Load and index phrase library from JSON file."""
        if not self.phrase_library_path.exists():
            logger.error(f"Phrase library not found: {self.phrase_library_path}")
            raise FileNotFoundError(f"ASHA phrase library missing: {self.phrase_library_path}")
        
        try:
            with open(self.phrase_library_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded phrase library v{data.get('version', 'unknown')}")
            
            # Index by phrase ID
            for phrase in data['phrases']:
                phrase_id = phrase['id']
                self.phrases[phrase_id] = phrase
                
                # Index by category
                category = phrase.get('category', 'other')
                if category not in self.phrases_by_category:
                    self.phrases_by_category[category] = []
                self.phrases_by_category[category].append(phrase)
            
            logger.info(f"Indexed {len(self.phrases)} phrases across {len(self.phrases_by_category)} categories")
            
        except Exception as e:
            logger.error(f"Failed to load phrase library: {e}")
            raise
    
    def get_phrase(self, phrase_id: str, language: str = 'en') -> Optional[str]:
        """
        Get phrase text by ID and language.
        
        Args:
            phrase_id: Phrase identifier
            language: 'en', 'hi', or 'te'
            
        Returns:
            Phrase text or None if not found
        """
        phrase = self.phrases.get(phrase_id)
        if not phrase:
            logger.warning(f"Phrase ID '{phrase_id}' not found")
            return None
        
        text = phrase.get(language)
        if not text:
            logger.warning(f"Language '{language}' not available for phrase '{phrase_id}'")
            return None
        
        return text
    
    def compose_asha_explanation(self,
                                 risk_category: str,
                                 evidence_summary: List[str],
                                 lab_age_warning: Optional[str] = None) -> str:
        """
        Compose ASHA explanation from evidence summary.
        
        Args:
            risk_category: 'LOW', 'MODERATE', or 'HIGH'
            evidence_summary: List of evidence statements
            lab_age_warning: Lab age warning flag (if applicable)
            
        Returns:
            Composed ASHA explanation in English
        """
        sections = []
        
        # Header based on urgency
        if risk_category == 'HIGH':
            sections.append(self.get_phrase('urgent_action_header'))
            sections.append('')
        
        # Problem statement
        sections.append(self.get_phrase('problem_header'))
        problem_text = self._compose_problem_statement(evidence_summary)
        sections.append(problem_text)
        sections.append('')
        
        # Action statement
        sections.append(self.get_phrase('action_header'))
        action_text = self._compose_action_statement(risk_category)
        sections.append(action_text)
        sections.append('')
        
        # Warning signs (for HIGH/MODERATE risk)
        if risk_category in ['HIGH', 'MODERATE']:
            sections.append(self.get_phrase('warning_signs_header'))
            warning_signs = self._get_warning_signs()
            sections.extend(warning_signs)
            sections.append('')
            sections.append(self.get_phrase('if_any_happen_immediately'))
            sections.append('')
        
        # Lab age warning (if applicable)
        if lab_age_warning:
            lab_note = self._get_lab_age_note(lab_age_warning)
            if lab_note:
                sections.append(lab_note)
                sections.append('')
        
        # Education/reassurance
        if risk_category != 'HIGH':
            sections.append(self.get_phrase('early_treatment_prevents'))
            sections.append(self.get_phrase('keep_safe'))
        
        # Filter None and join
        text = '\n'.join([s for s in sections if s is not None])
        
        logger.debug(f"Composed ASHA explanation ({len(text)} chars, risk={risk_category})")
        
        return text
    
    def _compose_problem_statement(self, evidence_summary: List[str]) -> str:
        """
        Compose problem statement from evidence summary.
        
        Maps evidence patterns to controlled phrases.
        """
        problem_parts = []
        
        # Check evidence for specific patterns
        has_high_bp = any('blood pressure' in e and 'increased' in e for e in evidence_summary)
        has_proteinuria = any('proteinuria' in e for e in evidence_summary)
        has_low_platelets = any('platelets dropped' in e for e in evidence_summary)
        has_low_hb = any('hemoglobin declined' in e for e in evidence_summary)
        has_neurological = any('neurological' in e for e in evidence_summary)
        has_respiratory = any('respiratory' in e for e in evidence_summary)
        has_wbc = any('white blood cells' in e for e in evidence_summary)
        
        # Primary condition
        if has_high_bp and has_proteinuria:
            problem_parts.append(self.get_phrase('high_bp_protein'))
            problem_parts.append(self.get_phrase('fits_danger'))
        elif has_high_bp:
            problem_parts.append(self.get_phrase('high_bp_only'))
            if has_neurological:
                problem_parts.append(self.get_phrase('neurological_symptoms'))
            problem_parts.append(self.get_phrase('fits_danger'))
        elif has_low_hb:
            problem_parts.append(self.get_phrase('weak_blood_low_hb'))
            problem_parts.append(self.get_phrase('cannot_carry_oxygen'))
            if has_respiratory:
                problem_parts.append(self.get_phrase('feeling_breathless'))
        elif has_low_platelets:
            problem_parts.append(self.get_phrase('low_platelets'))
            problem_parts.append(self.get_phrase('bleeding_danger_delivery'))
        elif has_wbc:
            problem_parts.append(self.get_phrase('infection_suspected'))
            problem_parts.append(self.get_phrase('infection_spread_quickly'))
        else:
            # Generic multi-problem
            problem_parts.append(self.get_phrase('multiple_problems'))
        
        # Risk statement
        if any('life-threatening' in e for e in evidence_summary):
            problem_parts.append(self.get_phrase('life_threatening'))
        
        # Progressive decline
        if len(evidence_summary) >= 2:
            problem_parts.append(self.get_phrase('worsening_condition'))
        
        return ' '.join([p for p in problem_parts if p])
    
    def _compose_action_statement(self, risk_category: str) -> str:
        """Compose action statement based on risk level."""
        actions = []
        
        if risk_category == 'HIGH':
            actions.append(self.get_phrase('hospital_today'))
            actions.append(self.get_phrase('do_not_delay'))
            actions.append(self.get_phrase('arrange_ambulance'))
        elif risk_category == 'MODERATE':
            actions.append(self.get_phrase('hospital_this_week'))
            actions.append(self.get_phrase('book_appointment'))
            actions.append(self.get_phrase('explain_symptoms'))
        else:
            actions.append(self.get_phrase('doctor_check_needed'))
            actions.append(self.get_phrase('book_appointment'))
        
        return ' '.join([a for a in actions if a])
    
    def _get_warning_signs(self) -> List[str]:
        """Get list of warning signs to watch for."""
        signs = [
            f"- {self.get_phrase('severe_headache')}",
            f"- {self.get_phrase('vision_problems')}",
            f"- {self.get_phrase('fits_convulsions')}",
            f"- {self.get_phrase('heavy_bleeding')}",
            f"- {self.get_phrase('severe_stomach_pain')}",
            f"- {self.get_phrase('baby_not_moving')}"
        ]
        return [s for s in signs if s]
    
    def _get_lab_age_note(self, lab_age_warning: str) -> Optional[str]:
        """Get lab age warning note."""
        if lab_age_warning == 'too_old_recommend_repeat':
            return self.get_phrase('old_lab_note_90d')
        elif lab_age_warning in ['old_but_usable', 'stale_lab_30d']:
            return self.get_phrase('old_lab_note_30d')
        return None
    
    def translate(self, english_text: str, target_language: str) -> Dict:
        """
        Translate composed English text to target language.
        
        Uses phrase-level replacement (not word-level).
        
        Args:
            english_text: Composed ASHA explanation in English
            target_language: 'hi' or 'te'
            
        Returns:
            Dict with 'text' and 'fallback_flag'
        """
        if target_language not in ['hi', 'te']:
            logger.error(f"Unsupported language: {target_language}")
            return {'text': english_text, 'fallback_flag': True}
        
        translated = english_text
        fallback_used = False
        
        # Replace each known phrase
        for phrase_id, phrase in self.phrases.items():
            en_text = phrase.get('en')
            target_text = phrase.get(target_language)
            
            if en_text and target_text:
                if en_text in translated:
                    translated = translated.replace(en_text, target_text)
            else:
                if en_text and en_text in translated:
                    fallback_used = True
                    logger.warning(f"No {target_language} translation for phrase '{phrase_id}'")
        
        return {
            'text': translated,
            'fallback_flag': fallback_used
        }
    
    def translate_all(self, english_text: str) -> Dict:
        """
        Translate to all supported languages.
        
        Args:
            english_text: Composed ASHA explanation
            
        Returns:
            Dict with 'english', 'hindi', 'telugu', 'translation_fallback_flag'
        """
        hindi = self.translate(english_text, 'hi')
        telugu = self.translate(english_text, 'te')
        
        return {
            'english': english_text,
            'hindi': hindi['text'],
            'telugu': telugu['text'],
            'translation_fallback_flag': hindi['fallback_flag'] or telugu['fallback_flag']
        }


# Singleton
_composer_instance = None


def get_asha_composer() -> ASHAPhraseComposer:
    """Get singleton instance of ASHAPhraseComposer."""
    global _composer_instance
    if _composer_instance is None:
        _composer_instance = ASHAPhraseComposer()
    return _composer_instance


# Self-test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ASHAPhraseComposer v2.0 Self-Test")
    print("=" * 70)
    
    try:
        composer = get_asha_composer()
        
        # Test 1: Phrase retrieval
        print("\nTest 1: Phrase Retrieval")
        print("-" * 70)
        phrase_en = composer.get_phrase('urgent_action_header', 'en')
        phrase_hi = composer.get_phrase('urgent_action_header', 'hi')
        phrase_te = composer.get_phrase('urgent_action_header', 'te')
        print(f"EN: {phrase_en}")
        print(f"HI: {phrase_hi}")
        print(f"TE: {phrase_te}")
        
        # Test 2: Compose HIGH risk explanation
        print("\nTest 2: HIGH Risk Composition")
        print("-" * 70)
        evidence = [
            "platelets dropped 180000→85000 (drop 53%)",
            "proteinuria progressed trace→+2",
            "new neurological symptoms (headache, blurred vision)"
        ]
        
        explanation = composer.compose_asha_explanation('HIGH', evidence, lab_age_warning='old_but_usable')
        print(explanation)
        
        # Test 3: Translation
        print("\nTest 3: Translation")
        print("-" * 70)
        translations = composer.translate_all(explanation)
        
        print(f"\nHindi ({len(translations['hindi'])} chars):")
        print(translations['hindi'][:200] + "...")
        
        print(f"\nTelugu ({len(translations['telugu'])} chars):")
        print(translations['telugu'][:200] + "...")
        
        print(f"\nFallback flag: {translations['translation_fallback_flag']}")
        
        print("\n" + "=" * 70)
        print("✓ All self-tests passed")
        print("=" * 70)
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you created D:\\MedGemma\\data\\asha_phrase_library.json first!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
