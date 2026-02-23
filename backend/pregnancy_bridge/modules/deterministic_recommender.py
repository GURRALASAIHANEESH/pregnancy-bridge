"""
Deterministic Recommender
Conservative rule-based recommendations for field safety
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def get_deterministic_recommendations(
    risk_category: str,
    evidence_summary: List[str],
    lab_age_days: int,
    latest_values: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate deterministic, field-safe recommendations based on rules.
    
    Args:
        risk_category: 'LOW', 'MODERATE', or 'HIGH'
        evidence_summary: List of evidence strings from rule engine
        lab_age_days: Age of lab data in days
        latest_values: Dict with latest clinical values:
            - bp_systolic, bp_diastolic
            - hemoglobin
            - platelets
            - proteinuria
    
    Returns:
        List of recommendation dicts with keys:
            - action: str (action code)
            - priority: str ('urgent', 'near-term', 'follow-up')
            - why: str (clinical reason)
            - practical_note: str (field advice)
            - source: 'deterministic_rule'
    """
    recommendations = []
    
    # Extract values
    bp_sys = latest_values.get('bp_systolic') or 0
    bp_dia = latest_values.get('bp_diastolic') or 0
    hb     = latest_values.get('hemoglobin') or 12.0
    platelets = latest_values.get('platelets')
    proteinuria = latest_values.get('proteinuria', 'nil')
    
    logger.info(f"Generating deterministic recommendations for {risk_category} risk")
    
    # RULE 1: Critical diastolic hypertension (≥110) → URGENT REFER
    if bp_dia >= 110:
        recommendations.append({
            'action': 'urgent_refer_facility',
            'priority': 'urgent',
            'why': f'Critical diastolic BP {bp_dia} mmHg (≥110). Risk of hypertensive crisis.',
            'practical_note': 'Call ambulance immediately. Monitor BP every 15 min during transport.',
            'source': 'deterministic_rule'
        })
    
    # RULE 2: Severe systolic hypertension (≥160) → URGENT REFER
    elif bp_sys >= 160:
        recommendations.append({
            'action': 'urgent_refer_facility',
            'priority': 'urgent',
            'why': f'Severe systolic BP {bp_sys} mmHg (≥160). Risk of stroke/eclampsia.',
            'practical_note': 'Arrange immediate transport to facility with ICU capability.',
            'source': 'deterministic_rule'
        })
    
    # RULE 3: Pre-eclampsia criteria (BP ≥140 + proteinuria ≥+2) → URGENT REFER
    elif bp_sys >= 140 and proteinuria in ['+2', '++', '+3', '+++']:
        recommendations.append({
            'action': 'urgent_refer_preeclampsia',
            'priority': 'urgent',
            'why': f'Pre-eclampsia criteria: BP {bp_sys}/{bp_dia} + proteinuria {proteinuria}.',
            'practical_note': 'Facility must have magnesium sulfate and emergency delivery capability.',
            'source': 'deterministic_rule'
        })
    
    # RULE 4: Critical thrombocytopenia (≤50k) → URGENT REFER
    if platelets and platelets <= 50000:
        recommendations.append({
            'action': 'urgent_refer_hellp',
            'priority': 'urgent',
            'why': f'Critical thrombocytopenia: platelets {platelets}/µL (≤50k). HELLP syndrome risk.',
            'practical_note': 'Facility must have blood bank and emergency C-section capability.',
            'source': 'deterministic_rule'
        })
    
    # RULE 5: Low platelets (≤100k) → NEAR-TERM REFER
    elif platelets and platelets <= 100000:
        recommendations.append({
            'action': 'near_term_refer_platelets',
            'priority': 'near-term',
            'why': f'Low platelets: {platelets}/µL (≤100k). Monitor for HELLP progression.',
            'practical_note': 'Arrange facility referral within 24 hours. Repeat CBC at facility.',
            'source': 'deterministic_rule'
        })
    
    # RULE 6: Severe anemia (<7 g/dL) → URGENT REFER
    if hb < 7.0:
        recommendations.append({
            'action': 'urgent_refer_anemia',
            'priority': 'urgent',
            'why': f'Severe anemia: Hb {hb} g/dL (<7). Transfusion may be required.',
            'practical_note': 'Arrange transport to facility with blood bank. Avoid exertion.',
            'source': 'deterministic_rule'
        })
    
    # RULE 7: Moderate anemia (<9 g/dL) → NEAR-TERM ACTION
    elif hb < 9.0:
        recommendations.append({
            'action': 'near_term_cbc_iron',
            'priority': 'near-term',
            'why': f'Moderate anemia: Hb {hb} g/dL (<9). Needs evaluation and treatment.',
            'practical_note': 'Refer to PHC for CBC and iron supplementation within 3 days.',
            'source': 'deterministic_rule'
        })
    
    # RULE 8: Lab data too old (>90 days) with any elevated values → REPEAT TESTS
    if lab_age_days > 90:
        if bp_sys >= 135 or proteinuria != 'nil' or hb < 11.0:
            recommendations.append({
                'action': 'repeat_essential_labs',
                'priority': 'near-term',
                'why': f'Lab data aged {lab_age_days} days with abnormal values. Need current assessment.',
                'practical_note': 'Repeat CBC, urine dip, and BP at PHC within 1 week.',
                'source': 'deterministic_rule'
            })
    
    # RULE 9: Moderate BP (140-159) without severe complications → MONITOR + RETEST
    if 140 <= bp_sys < 160 and bp_dia < 110 and not recommendations:
        recommendations.append({
            'action': 'monitor_bp_home',
            'priority': 'near-term',
            'why': f'Stage 1 hypertension: BP {bp_sys}/{bp_dia}. Needs close monitoring.',
            'practical_note': 'Check BP twice daily at home. Return if headache/vision changes occur.',
            'source': 'deterministic_rule'
        })
        recommendations.append({
            'action': 'repeat_bp_phc',
            'priority': 'near-term',
            'why': 'Confirm BP elevation and check for proteinuria.',
            'practical_note': 'Visit PHC in 3-5 days for BP measurement and urine dip.',
            'source': 'deterministic_rule'
        })
    
    # RULE 10: HIGH risk but no specific urgent triggers → SAFETY-FIRST REFER
    if risk_category == 'HIGH' and not recommendations:
        recommendations.append({
            'action': 'refer_high_risk',
            'priority': 'urgent',
            'why': 'High risk pregnancy detected. Comprehensive evaluation needed.',
            'practical_note': 'Arrange transport to facility for complete assessment.',
            'source': 'deterministic_rule'
        })

    # RULE 10b: MODERATE risk with no specific vital triggers → PHC REFERRAL
    if risk_category == 'MODERATE' and not recommendations:
        recommendations.append({
            'action': 'phc_referral_moderate',
            'priority': 'near-term',
            'why': 'Moderate risk detected. Multiple concerning symptoms require clinical evaluation.',
            'practical_note': 'Refer to PHC within 24-48 hours. Bring all previous lab reports.',
            'source': 'deterministic_rule'
        })
        recommendations.append({
            'action': 'monitor_symptoms',
            'priority': 'near-term',
            'why': 'Monitor for worsening: headache, vision changes, severe abdominal pain.',
            'practical_note': 'Return immediately if symptoms worsen or any new symptoms appear.',
            'source': 'deterministic_rule'
        })

    # RULE 11: LOW risk, routine monitoring
    if risk_category == 'LOW' and not recommendations:
        recommendations.append({
            'action': 'routine_monitoring',
            'priority': 'follow-up',
            'why': 'No immediate concerns. Continue routine antenatal care.',
            'practical_note': 'Next scheduled ANC visit as per protocol. Contact if symptoms develop.',
            'source': 'deterministic_rule'
        })
    
    # Limit to max 3 recommendations
    recommendations = recommendations[:3]
    
    logger.info(f"Generated {len(recommendations)} deterministic recommendations")
    for rec in recommendations:
        logger.info(f"  - {rec['priority']}: {rec['action']}")
    
    return recommendations
