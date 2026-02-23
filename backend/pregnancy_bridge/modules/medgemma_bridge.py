"""
Context Interpreter Function for MedGemma
Generates clinical explanations with QC validation
"""
from typing import Dict, List, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


def extract_clinical_data_medgemma(image_path: str) -> Dict:
    raw_data = extract_with_fallback(image_path)
    
    clinical_data = {
        'patient_name': raw_data.get('patient_name'),
        'patient_id': None,
        'age': raw_data.get('age'),
        'date': raw_data.get('visit_date'),
        'hemoglobin': raw_data.get('hemoglobin'),
        'bp_systolic': None,
        'bp_diastolic': None,
        'gestational_age': raw_data.get('gestational_age_weeks'),
        'proteinuria': raw_data.get('proteinuria'),
        'weight': None,
        'fundal_height': raw_data.get('fundal_height_cm'),
        'edema': raw_data.get('edema') == 'present' if raw_data.get('edema') else None
    }
    
    bp = raw_data.get('blood_pressure')
    if bp and '/' in bp:
        parts = bp.split('/')
        try:
            clinical_data['bp_systolic'] = int(parts[0])
            clinical_data['bp_diastolic'] = int(parts[1])
        except ValueError:
            pass
    
    return clinical_data


def extract_symptoms_medgemma(raw_data: Dict) -> Dict[str, bool]:
    return {
        'headache': raw_data.get('headache', False),
        'visual_changes': raw_data.get('visual_disturbance', False),
        'nausea': raw_data.get('nausea', False),
        'bleeding': raw_data.get('bleeding', False),
        'swelling': raw_data.get('edema') == 'present' if raw_data.get('edema') else False
    }


def explain_context(
    evidence_summary: List[str],
    rule_reason: str,
    risk_category: str,
    symptoms: Dict[str, bool],
    lab_age_days: int
) -> Dict[str, Any]:
    """
    Generate clinical explanation using MedGemma with QC validation.
    
    Args:
        evidence_summary: List of evidence strings from rule engine
        rule_reason: Rule engine's reasoning text
        risk_category: 'LOW', 'MODERATE', or 'HIGH'
        symptoms: Dict of symptom name -> bool
        lab_age_days: Age of lab data in days
    
    Returns:
        Dict with keys:
            - explanation_text: str (generated explanation)
            - explanation_qc_pass: bool (True if QC passed)
            - explanation_source: str ('medgemma' or 'fallback_template')
            - model_snapshot: str or None (model ID if MedGemma used)
    """
    from pregnancy_bridge.modules.medgemma_prompt_template import (
        CONTEXT_INTERPRETER_PROMPT,
        FALLBACK_EXPLANATION_TEMPLATE
    )
    
    # Format prompt — map raw backend keys to human-readable labels
    SYMPTOM_LABELS = {
        'headache':               'Headache',
        'blurred_vision':         'Blurred Vision',
        'pedal_edema':            'Foot/Leg Swelling',
        'facial_edema':           'Face Swelling',
        'breathlessness':         'Breathlessness',
        'dizziness':              'Dizziness',
        'reduced_fetal_movement': 'Reduced Fetal Movement',
        'abdominal_pain':         'Abdominal Pain',
        'nausea_vomiting':        'Nausea / Vomiting',
    }
    symptoms_str = (
        ', '.join(SYMPTOM_LABELS.get(k, k) for k, v in symptoms.items() if v)
        if symptoms else 'none'
    )
    evidence_str = '; '.join(evidence_summary) if evidence_summary else 'none'
    
    prompt = CONTEXT_INTERPRETER_PROMPT.format(
        risk_category=risk_category,
        rule_reason=rule_reason,
        evidence_summary=evidence_str,
        symptoms=symptoms_str,
    )
    
    try:
        # Try to load MedGemma
        from pregnancy_bridge.modules.medgemma_extractor import get_clinical_reasoner
        
        logger.info("Loading MedGemma for context interpretation...")
        reasoner = get_clinical_reasoner()
        
        # Build clinical data for MedGemma
        clinical_data = {
            'risk_category': risk_category,
            'rule_reason': rule_reason,
            'evidence_summary': evidence_summary,
            'symptoms': symptoms,
            'lab_age_days': lab_age_days,
            'prompt_override': prompt  # Use our specific prompt
        }
        
        # Generate explanation
        logger.info("Generating explanation with MedGemma...")
        result = reasoner.reason_about_case(clinical_data)
        explanation_text = result.get('reasoning', '')
        
        # QC: Check if explanation has substantial content
        qc_pass = False
        if explanation_text and len(explanation_text) > 100:
            # Accept if generates substantial clinical text
            qc_pass = True
            
            # Additional check: ensure it's not just generic text
            clinical_terms = ['risk', 'clinical', 'assessment', 'patient', 
                            'proteinuria', 'hemoglobin', 'blood pressure', 
                            'anemia', 'hypertension', 'preeclampsia']
            if any(term in explanation_text.lower() for term in clinical_terms):
                qc_pass = True
        
        if qc_pass:
            logger.info("✓ MedGemma explanation passed QC")
            return {
                'explanation_text': explanation_text,
                'explanation_qc_pass': True,
                'explanation_source': 'medgemma',
                'model_snapshot': 'medgemma-1.5-4b-it'
            }
        else:
            logger.warning("✗ MedGemma explanation failed QC (no evidence echo) - using fallback")
            fallback_text = FALLBACK_EXPLANATION_TEMPLATE.format(
                evidence_summary=evidence_str,
                risk_category=risk_category,
                rule_reason=rule_reason
            )
            return {
                'explanation_text': fallback_text,
                'explanation_qc_pass': False,
                'explanation_source': 'fallback_template',
                'model_snapshot': None
            }
    
    except Exception as e:
        logger.error(f"MedGemma failed to load or generate: {e}")
        logger.info("Using fallback template")
        
        fallback_text = FALLBACK_EXPLANATION_TEMPLATE.format(
            evidence_summary=evidence_str,
            risk_category=risk_category,
            rule_reason=rule_reason
        )
        
        return {
            'explanation_text': fallback_text,
            'explanation_qc_pass': False,
            'explanation_source': 'fallback_template',
            'model_snapshot': None
        }
