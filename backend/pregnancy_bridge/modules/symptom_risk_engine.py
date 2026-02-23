"""
Symptom-Aware Temporal Risk Escalation Engine
Production-grade deterministic maternal risk assessment
Author: PregnancyBridge Development Team
Version: 1.0.0
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Human-readable labels for raw symptom keys ────────────────────────────────
_SYMPTOM_LABELS: Dict[str, str] = {
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

def _label(key: str) -> str:
    """Return a human-readable label for a symptom key, falling back to the key itself."""
    return _SYMPTOM_LABELS.get(key, key)


class SymptomRiskEngine:
    """
    Evidence-based deterministic risk engine for maternal health assessment.
    
    Combines temporal laboratory trends with structured symptom reporting
    to detect escalating maternal risk patterns.
    
    Clinical Evidence Base:
    - MEOWS (Maternal Early Obstetric Warning System)
    - ACOG Preeclampsia Guidelines
    - WHO Maternal Health Protocols
    
    Safety-Critical: All decisions are deterministic and rule-based.
    """
    
    # Clinical thresholds (evidence-based)
    BP_HIGH_SBP = 140  # mmHg
    BP_HIGH_DBP = 90   # mmHg
    BP_SEVERE_SBP = 160  # mmHg
    BP_SEVERE_DBP = 110  # mmHg
    
    HB_MODERATE_ANEMIA = 9.0  # g/dL
    HB_SEVERE_ANEMIA = 7.0    # g/dL
    
    PROTEINURIA_TRACE = 'trace'
    PROTEINURIA_POSITIVE_1 = '+1'
    PROTEINURIA_POSITIVE_2 = '+2'
    PROTEINURIA_POSITIVE_3 = '+3'
    PROTEINURIA_POSITIVE_4 = '+4'
    
    def __init__(self, log_assessments: bool = True):
        """
        Initialize risk engine.
        
        Args:
            log_assessments: Whether to maintain assessment history
        """
        self.risk_history = [] if log_assessments else None
        logger.info("SymptomRiskEngine initialized")
    
    def assess_bp_risk(self, visits: List[Dict]) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Assess blood pressure risk with temporal trend analysis.
        
        Args:
            visits: List of visit records with BP measurements
            
        Returns:
            Tuple of (risk_level, reason, trigger_visit_index)
            risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'UNKNOWN'
        """
        if not visits:
            return "UNKNOWN", None, None
        
        latest_visit = visits[-1]
        bp = latest_visit.get('bp', {})
        systolic = bp.get('systolic')
        diastolic = bp.get('diastolic')
        
        if systolic is None or diastolic is None:
            logger.warning("BP data missing in latest visit")
            return "UNKNOWN", None, None
        
        # Severe hypertension (immediate HIGH risk)
        if systolic >= self.BP_SEVERE_SBP or diastolic >= self.BP_SEVERE_DBP:
            reason = f"Severe hypertension: {systolic}/{diastolic} mmHg (≥160/110)"
            logger.warning(f"SEVERE HYPERTENSION DETECTED: {reason}")
            return "HIGH", reason, len(visits) - 1
        
        # Elevated BP (requires trend analysis)
        if systolic >= self.BP_HIGH_SBP or diastolic >= self.BP_HIGH_DBP:
            # Check for persistence across visits
            if len(visits) >= 2:
                prev_bp = visits[-2].get('bp', {})
                prev_systolic = prev_bp.get('systolic')
                prev_diastolic = prev_bp.get('diastolic')
                
                if prev_systolic and prev_diastolic:
                    if prev_systolic >= self.BP_HIGH_SBP or prev_diastolic >= self.BP_HIGH_DBP:
                        reason = f"Persistent hypertension: {systolic}/{diastolic} mmHg (2+ visits ≥140/90)"
                        logger.warning(f"PERSISTENT HYPERTENSION: {reason}")
                        return "HIGH", reason, len(visits) - 1
            
            reason = f"Elevated BP: {systolic}/{diastolic} mmHg (≥140/90)"
            return "MODERATE", reason, len(visits) - 1
        
        return "LOW", None, None
    
    def assess_anemia_risk(self, visits: List[Dict]) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Assess hemoglobin risk with trend detection.
        
        Args:
            visits: List of visit records with Hb measurements
            
        Returns:
            Tuple of (risk_level, reason, trigger_visit_index)
        """
        if not visits:
            return "UNKNOWN", None, None
        
        latest_visit = visits[-1]
        hb = latest_visit.get('hemoglobin')
        
        if hb is None:
            logger.debug("Hemoglobin data not available")
            return "UNKNOWN", None, None
        
        # Severe anemia
        if hb < self.HB_SEVERE_ANEMIA:
            reason = f"Severe anemia: Hb {hb} g/dL (<7.0)"
            logger.warning(f"SEVERE ANEMIA DETECTED: {reason}")
            return "HIGH", reason, len(visits) - 1
        
        # Moderate anemia with trend analysis
        if hb < self.HB_MODERATE_ANEMIA:
            # Check for worsening trend
            if len(visits) >= 2:
                prev_hb = visits[-2].get('hemoglobin')
                if prev_hb and prev_hb > hb:
                    decline = prev_hb - hb
                    reason = f"Worsening anemia: Hb {hb} g/dL (declined {decline:.1f} from previous visit)"
                    logger.warning(f"DECLINING HEMOGLOBIN: {reason}")
                    return "MODERATE", reason, len(visits) - 1
            
            reason = f"Moderate anemia: Hb {hb} g/dL (<9.0)"
            return "MODERATE", reason, len(visits) - 1
        
        return "LOW", None, None
    
    def assess_proteinuria_risk(self, visits: List[Dict]) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Assess proteinuria risk with persistence detection.
        
        Args:
            visits: List of visit records with proteinuria measurements
            
        Returns:
            Tuple of (risk_level, reason, trigger_visit_index)
        """
        if not visits:
            return "UNKNOWN", None, None
        
        latest_visit = visits[-1]
        proteinuria = latest_visit.get('proteinuria', 'nil').lower()
        
        # Significant proteinuria
        if proteinuria in ['+2', '+3', '+4']:
            reason = f"Significant proteinuria: {proteinuria}"
            logger.warning(f"SIGNIFICANT PROTEINURIA: {reason}")
            return "HIGH", reason, len(visits) - 1
        
        # Mild proteinuria with persistence check
        if proteinuria in ['+1', 'trace']:
            if len(visits) >= 2:
                prev_proteinuria = visits[-2].get('proteinuria', 'nil').lower()
                if prev_proteinuria in ['+1', '+2', '+3', '+4', 'trace']:
                    reason = f"Persistent proteinuria: {proteinuria} (2+ visits)"
                    logger.info(f"PERSISTENT PROTEINURIA: {reason}")
                    return "MODERATE", reason, len(visits) - 1
            
            reason = f"New proteinuria detected: {proteinuria}"
            return "MODERATE", reason, len(visits) - 1
        
        return "LOW", None, None
    
    def combine_with_symptoms(self, 
                              lab_risk: str, 
                              lab_reason: Optional[str], 
                              symptom_data: Optional[Dict], 
                              visit_index: Optional[int]) -> Tuple[str, str, bool]:
        """
        Apply evidence-based escalation rules combining lab + symptom data.
        
        This is the core safety-critical decision logic.
        
        Args:
            lab_risk: Laboratory-based risk level
            lab_reason: Laboratory risk explanation
            symptom_data: Structured symptom record from SymptomIntake
            visit_index: Index of triggering visit
            
        Returns:
            Tuple of (final_risk_level, combined_reason, referral_required)
        """
        # No symptoms - use laboratory risk only
        if not symptom_data or symptom_data.get('symptom_count', 0) == 0:
            referral = lab_risk == "HIGH"
            return lab_risk, lab_reason or "No clinical abnormalities detected", referral
        
        # Extract symptom flags
        has_neuro = symptom_data.get('has_neurological', False)
        has_edema = symptom_data.get('has_edema', False)
        has_respiratory = symptom_data.get('has_respiratory', False)
        has_fetal_concern = symptom_data.get('has_fetal_concern', False)
        has_gi = symptom_data.get('has_gi', False)
        multiple_categories = symptom_data.get('multiple_categories', False)
        
        present_symptoms = symptom_data.get('present_symptoms', [])
        categories = symptom_data.get('categories', {})
        
        # EVIDENCE-BASED ESCALATION RULES
        
        # RULE 1: BP elevation + Neurological symptoms → HIGH (Preeclampsia)
        if lab_risk in ["MODERATE", "HIGH"]:
            if "bp" in (lab_reason or "").lower() or "hypertension" in (lab_reason or "").lower():
                if has_neuro:
                    neuro_list = ', '.join(_label(s) for s in categories.get('neurological', []))
                    reason = f"{lab_reason} WITH neurological symptoms ({neuro_list}) - PREECLAMPSIA SUSPECTED"
                    logger.critical(f"ESCALATION RULE 1: {reason}")
                    return "HIGH", reason, True
        
        # RULE 2: Proteinuria + Visual/Neurological → HIGH (Preeclampsia)
        if "proteinuria" in (lab_reason or "").lower():
            if has_neuro:
                neuro_list = ', '.join(_label(s) for s in categories.get('neurological', []))
                reason = f"{lab_reason} WITH neurological symptoms ({neuro_list}) - PREECLAMPSIA SUSPECTED"
                logger.critical(f"ESCALATION RULE 2: {reason}")
                return "HIGH", reason, True
        
        # RULE 3: Anemia + Respiratory symptoms → HIGH (Cardiopulmonary)
        if lab_risk in ["MODERATE", "HIGH"]:
            if "anemia" in (lab_reason or "").lower() and has_respiratory:
                reason = f"{lab_reason} WITH breathlessness - CARDIOPULMONARY COMPROMISE SUSPECTED"
                logger.critical(f"ESCALATION RULE 3: {reason}")
                return "HIGH", reason, True
        
        # RULE 4: Fetal concern symptoms → Always HIGH (Urgent assessment)
        if has_fetal_concern:
            reason = "Reduced fetal movement reported - URGENT FETAL ASSESSMENT REQUIRED"
            logger.critical(f"ESCALATION RULE 4: {reason}")
            return "HIGH", reason, True
        
        # RULE 5: HIGH lab + Any symptoms → HIGH (Compounded risk)
        if lab_risk == "HIGH":
            symptom_list = ', '.join(_label(s) for s in present_symptoms[:3])
            if len(present_symptoms) > 3:
                symptom_list += f" (+{len(present_symptoms)-3} more)"
            reason = f"{lab_reason} WITH symptoms ({symptom_list})"
            logger.critical(f"ESCALATION RULE 5: {reason}")
            return "HIGH", reason, True
        
        # RULE 6: MODERATE lab + Multiple symptom categories → HIGH
        if lab_risk == "MODERATE" and multiple_categories:
            symptom_list = ', '.join(_label(s) for s in present_symptoms)
            reason = f"{lab_reason} WITH multiple symptom categories ({symptom_list})"
            logger.warning(f"ESCALATION RULE 6: {reason}")
            return "HIGH", reason, True
        
        # RULE 7: MODERATE lab + Edema → Maintain MODERATE with note
        if lab_risk == "MODERATE" and has_edema:
            edema_list = ', '.join(_label(s) for s in categories.get('edema', []))
            reason = f"{lab_reason} with edema ({edema_list})"
            return "MODERATE", reason, False
        
        # RULE 8: LOW lab + Multiple symptoms → MODERATE (Clinical concern)
        if lab_risk == "LOW" and len(present_symptoms) >= 2:
            symptom_list = ', '.join(_label(s) for s in present_symptoms)
            reason = f"Multiple symptoms present ({symptom_list}) despite normal laboratory values"
            logger.info(f"ESCALATION RULE 8: {reason}")
            return "MODERATE", reason, False
        
        # Default: Maintain laboratory risk level
        referral = lab_risk == "HIGH"
        if present_symptoms:
            symptom_labels = ', '.join(_label(s) for s in present_symptoms)
            count          = len(present_symptoms)
            symptom_note   = (
                f"Single symptom reported: {symptom_labels}. No critical combinations detected."
                if count == 1
                else f"Symptoms reported: {symptom_labels}. No critical combinations detected."
            )
            return lab_risk, symptom_note, referral
        return lab_risk, lab_reason or "No clinical abnormalities detected", referral
    
    def evaluate_visit(self, 
                       visits: List[Dict], 
                       current_visit_symptoms: Optional[Dict] = None) -> Dict:
        """
        Comprehensive temporal risk assessment.
        
        Args:
            visits: List of visit records (oldest to newest)
            current_visit_symptoms: Symptom record for latest visit
            
        Returns:
            Risk assessment dictionary with decision rationale
        """
        if not visits:
            logger.error("No visit data provided for evaluation")
            return {
                'risk_category': 'UNKNOWN',
                'referral_required': False,
                'trigger_reason': 'No visit data available',
                'trigger_visit': None,
                'timestamp': datetime.now().isoformat(),
                'component_risks': {}
            }
        
        logger.info(f"Evaluating {len(visits)} visits with temporal reasoning")
        
        # Assess individual risk components
        bp_risk, bp_reason, bp_visit = self.assess_bp_risk(visits)
        anemia_risk, anemia_reason, anemia_visit = self.assess_anemia_risk(visits)
        proteinuria_risk, proteinuria_reason, proteinuria_visit = self.assess_proteinuria_risk(visits)
        
        # Determine primary laboratory concern
        risk_levels = {'HIGH': 3, 'MODERATE': 2, 'LOW': 1, 'UNKNOWN': 0}
        
        primary_risk = max([
            (risk_levels[bp_risk], bp_risk, bp_reason, bp_visit),
            (risk_levels[anemia_risk], anemia_risk, anemia_reason, anemia_visit),
            (risk_levels[proteinuria_risk], proteinuria_risk, proteinuria_reason, proteinuria_visit)
        ])
        
        lab_risk = primary_risk[1]
        lab_reason = primary_risk[2]
        trigger_visit = primary_risk[3]
        
        # Get symptoms for latest visit
        latest_symptoms = current_visit_symptoms
        if not latest_symptoms and visits[-1].get('symptoms'):
            latest_symptoms = visits[-1]['symptoms']
        
        # Apply symptom-aware escalation rules
        final_risk, combined_reason, referral_required = self.combine_with_symptoms(
            lab_risk, lab_reason, latest_symptoms, trigger_visit
        )
        
        # Construct comprehensive assessment
        assessment = {
            'risk_category': final_risk,
            'referral_required': referral_required,
            'trigger_reason': combined_reason,
            'trigger_visit': trigger_visit,
            'timestamp': datetime.now().isoformat(),
            'component_risks': {
                'blood_pressure': {'risk': bp_risk, 'reason': bp_reason, 'visit': bp_visit},
                'anemia': {'risk': anemia_risk, 'reason': anemia_reason, 'visit': anemia_visit},
                'proteinuria': {'risk': proteinuria_risk, 'reason': proteinuria_reason, 'visit': proteinuria_visit}
            },
            'symptoms_present': latest_symptoms.get('symptom_count', 0) if latest_symptoms else 0,
            'visit_count': len(visits)
        }
        
        # Log assessment history if enabled
        if self.risk_history is not None:
            self.risk_history.append(assessment)
        
        logger.info(f"Assessment complete: {final_risk} risk, referral={'YES' if referral_required else 'NO'}")
        return assessment
    
    def get_assessment_history(self) -> List[Dict]:
        """Return all stored risk assessments"""
        return self.risk_history if self.risk_history is not None else []
    
    def clear_history(self) -> None:
        """Clear assessment history"""
        if self.risk_history is not None:
            self.risk_history.clear()
            logger.info("Assessment history cleared")


if __name__ == "__main__":
    # Self-test
    print("Running SymptomRiskEngine self-test...\n")
    
    engine = SymptomRiskEngine()
    
    # Test visits
    test_visits = [
        {'date': '2026-01-10', 'bp': {'systolic': 138, 'diastolic': 88}, 'hemoglobin': 11.0, 'proteinuria': 'nil'},
        {'date': '2026-02-04', 'bp': {'systolic': 145, 'diastolic': 95}, 'hemoglobin': 10.5, 'proteinuria': '+1'}
    ]
    
    # Test symptoms
    test_symptoms = {
        'symptom_count': 2,
        'present_symptoms': ['headache', 'blurred_vision'],
        'has_neurological': True,
        'has_edema': False,
        'has_respiratory': False,
        'has_fetal_concern': False,
        'multiple_categories': False,
        'categories': {'neurological': ['headache', 'blurred_vision']}
    }
    
    assessment = engine.evaluate_visit(test_visits, test_symptoms)
    
    print(f"Risk Category: {assessment['risk_category']}")
    print(f"Referral Required: {assessment['referral_required']}")
    print(f"Reason: {assessment['trigger_reason']}")
    print(f"\n✓ SymptomRiskEngine self-test complete")
