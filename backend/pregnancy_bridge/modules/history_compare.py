from typing import List, Dict, Optional


def compare_with_previous(current: Dict[str, any], previous: Dict[str, any]) -> List[str]:
    trends = []
    
    hb_trend = _analyze_hemoglobin_trend(
        current.get('hemoglobin'),
        previous.get('hemoglobin')
    )
    if hb_trend:
        trends.append(hb_trend)
    
    bp_trend = _analyze_blood_pressure_trend(
        current.get('bp_systolic'),
        current.get('bp_diastolic'),
        previous.get('bp_systolic'),
        previous.get('bp_diastolic')
    )
    if bp_trend:
        trends.append(bp_trend)
    
    weight_trend = _analyze_weight_trend(
        current.get('weight'),
        previous.get('weight')
    )
    if weight_trend:
        trends.append(weight_trend)
    
    protein_trend = _analyze_proteinuria_trend(
        current.get('proteinuria'),
        previous.get('proteinuria')
    )
    if protein_trend:
        trends.append(protein_trend)
    
    ga_gap = _analyze_visit_gap(
        current.get('gestational_age'),
        previous.get('gestational_age')
    )
    if ga_gap:
        trends.append(ga_gap)
    
    return trends if trends else ["No significant changes from previous visit"]


def detect_high_risk_patterns(history: List[Dict[str, any]]) -> List[str]:
    if len(history) < 2:
        return []
    
    patterns = []
    
    hb_pattern = _detect_declining_hemoglobin_pattern(history)
    if hb_pattern:
        patterns.append(hb_pattern)
    
    bp_pattern = _detect_progressive_hypertension_pattern(history)
    if bp_pattern:
        patterns.append(bp_pattern)
    
    protein_pattern = _detect_persistent_proteinuria_pattern(history)
    if protein_pattern:
        patterns.append(protein_pattern)
    
    return patterns


def _analyze_hemoglobin_trend(current: Optional[float], previous: Optional[float]) -> Optional[str]:
    if current is None or previous is None:
        return None
    
    change = current - previous
    
    if change <= -1.0:
        return f"Hb dropped from {previous} to {current} g/dL (delta {change:.1f}) - Anemia worsening"
    elif change <= -0.5:
        return f"Hb declining: {previous} to {current} g/dL - Monitor iron supplementation"
    elif change >= 1.0:
        return f"Hb improved from {previous} to {current} g/dL - Good response to treatment"
    
    return None


def _analyze_blood_pressure_trend(
    current_sys: Optional[int],
    current_dia: Optional[int],
    previous_sys: Optional[int],
    previous_dia: Optional[int]
) -> Optional[str]:
    if not all([current_sys, current_dia, previous_sys, previous_dia]):
        return None
    
    sys_change = current_sys - previous_sys
    dia_change = current_dia - previous_dia
    
    if sys_change >= 15 or dia_change >= 10:
        return (
            f"BP rising: {previous_sys}/{previous_dia} to {current_sys}/{current_dia} mmHg - "
            f"Monitor for pre-eclampsia"
        )
    elif sys_change >= 10 or dia_change >= 5:
        return (
            f"BP increasing: {previous_sys}/{previous_dia} to {current_sys}/{current_dia} mmHg - "
            f"Repeat measurement"
        )
    elif sys_change <= -10 or dia_change <= -5:
        return f"BP improved: {previous_sys}/{previous_dia} to {current_sys}/{current_dia} mmHg"
    
    return None


def _analyze_weight_trend(current: Optional[float], previous: Optional[float]) -> Optional[str]:
    if current is None or previous is None:
        return None
    
    change = current - previous
    
    if change > 2.0:
        return f"Rapid weight gain: +{change:.1f} kg - Check for edema/fluid retention"
    elif change < -1.0:
        return f"Weight loss: {change:.1f} kg - Assess nutrition, rule out hyperemesis"
    elif change < 0.3:
        return f"Insufficient weight gain: +{change:.1f} kg - Nutritional counseling"
    
    return None


def _analyze_proteinuria_trend(current: Optional[str], previous: Optional[str]) -> Optional[str]:
    if not current or not previous:
        return None
    
    protein_scale = {
        'negative': 0,
        'nil': 0,
        'trace': 1,
        '1+': 2,
        '2+': 3,
        '3+': 4,
        '4+': 5
    }
    
    current_level = protein_scale.get(current.lower(), 0)
    previous_level = protein_scale.get(previous.lower(), 0)
    
    if current_level > previous_level and current_level >= 2:
        return (
            f"Proteinuria worsening: {previous} to {current} - "
            f"Urgent pre-eclampsia workup"
        )
    elif current_level > previous_level:
        return f"Proteinuria increasing: {previous} to {current}"
    
    return None


def _analyze_visit_gap(current_ga: Optional[int], previous_ga: Optional[int]) -> Optional[str]:
    if current_ga is None or previous_ga is None:
        return None
    
    weeks_elapsed = current_ga - previous_ga
    
    if weeks_elapsed > 6:
        return f"Large gap between visits ({weeks_elapsed} weeks) - Review missed ANC visits"
    
    return None


def _detect_declining_hemoglobin_pattern(history: List[Dict[str, any]]) -> Optional[str]:
    hb_values = [v.get('hemoglobin') for v in history if v.get('hemoglobin') is not None]
    
    if len(hb_values) < 2:
        return None
    
    is_declining = all(
        hb_values[i] >= hb_values[i + 1]
        for i in range(len(hb_values) - 1)
    )
    
    if is_declining:
        return "Persistent declining Hb trend - Uncontrolled anemia"
    
    return None


def _detect_progressive_hypertension_pattern(history: List[Dict[str, any]]) -> Optional[str]:
    bp_values = [
        v.get('bp_systolic')
        for v in history
        if v.get('bp_systolic') is not None
    ]
    
    if len(bp_values) < 2:
        return None
    
    is_rising = all(
        bp_values[i] <= bp_values[i + 1]
        for i in range(len(bp_values) - 1)
    )
    
    if is_rising:
        return "Progressive BP elevation - Pre-eclampsia risk increasing"
    
    return None


def _detect_persistent_proteinuria_pattern(history: List[Dict[str, any]]) -> Optional[str]:
    protein_values = [
        v.get('proteinuria')
        for v in history
        if v.get('proteinuria') and v.get('proteinuria') not in ['negative', 'nil']
    ]
    
    if len(protein_values) >= 2:
        return "Persistent proteinuria across multiple visits - Kidney/pre-eclampsia concern"
    
    return None
