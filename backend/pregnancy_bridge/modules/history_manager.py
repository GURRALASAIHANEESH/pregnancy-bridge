import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


HISTORY_DIR = Path("data/patient_history")


def load_patient_history(patient_id: str) -> List[Dict]:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    filepath = HISTORY_DIR / f"{_sanitize_id(patient_id)}.json"
    
    if not filepath.exists():
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('visits', [])
    except (json.JSONDecodeError, KeyError):
        return []


def save_patient_visit(patient_id: str, visit_data: Dict) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    filepath = HISTORY_DIR / f"{_sanitize_id(patient_id)}.json"
    
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {'patient_id': patient_id, 'visits': []}
    else:
        data = {'patient_id': patient_id, 'visits': []}
    
    visit_record = {
        'visit_date': visit_data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'hemoglobin': visit_data.get('hemoglobin'),
        'bp_systolic': visit_data.get('bp_systolic'),
        'bp_diastolic': visit_data.get('bp_diastolic'),
        'gestational_age': visit_data.get('gestational_age'),
        'proteinuria': visit_data.get('proteinuria'),
        'weight': visit_data.get('weight'),
        'fundal_height': visit_data.get('fundal_height'),
        'edema': visit_data.get('edema'),
        'timestamp': datetime.now().isoformat()
    }
    
    data['visits'].append(visit_record)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def summarize_trends(history: List[Dict], current: Dict) -> Dict:
    if not history:
        return {
            'hb_drop': False,
            'hb_drop_magnitude': 0.0,
            'bp_rising': False,
            'bp_rise_magnitude': 0,
            'proteinuria_persistent': False,
            'proteinuria_worsening': False,
            'weight_concern': False,
            'visit_gap_exceeded': False,
            'trend_summary': []
        }
    
    latest_previous = history[-1]
    
    hb_analysis = _analyze_hb_trend(history, current)
    bp_analysis = _analyze_bp_trend(history, current)
    protein_analysis = _analyze_proteinuria_trend(history, current)
    weight_analysis = _analyze_weight_trend(latest_previous, current)
    gap_analysis = _analyze_visit_gap(latest_previous, current)
    
    trend_summary = []
    
    if hb_analysis['hb_drop']:
        trend_summary.append(hb_analysis['message'])
    
    if bp_analysis['bp_rising']:
        trend_summary.append(bp_analysis['message'])
    
    if protein_analysis['proteinuria_persistent']:
        trend_summary.append(protein_analysis['message'])
    
    if weight_analysis['weight_concern']:
        trend_summary.append(weight_analysis['message'])
    
    if gap_analysis['visit_gap_exceeded']:
        trend_summary.append(gap_analysis['message'])
    
    return {
        'hb_drop': hb_analysis['hb_drop'],
        'hb_drop_magnitude': hb_analysis['magnitude'],
        'bp_rising': bp_analysis['bp_rising'],
        'bp_rise_magnitude': bp_analysis['magnitude'],
        'proteinuria_persistent': protein_analysis['proteinuria_persistent'],
        'proteinuria_worsening': protein_analysis['proteinuria_worsening'],
        'weight_concern': weight_analysis['weight_concern'],
        'visit_gap_exceeded': gap_analysis['visit_gap_exceeded'],
        'trend_summary': trend_summary
    }


def _analyze_hb_trend(history: List[Dict], current: Dict) -> Dict:
    hb_values = [v.get('hemoglobin') for v in history if v.get('hemoglobin') is not None]
    current_hb = current.get('hemoglobin')
    
    if not hb_values or current_hb is None:
        return {'hb_drop': False, 'magnitude': 0.0, 'message': ''}
    
    previous_hb = hb_values[-1]
    drop = previous_hb - current_hb
    
    if drop >= 2.0:
        return {
            'hb_drop': True,
            'magnitude': drop,
            'message': f'CRITICAL: Hb dropped {drop:.1f} g/dL ({previous_hb} to {current_hb}) - Severe anemia progression'
        }
    elif drop >= 1.0:
        return {
            'hb_drop': True,
            'magnitude': drop,
            'message': f'Hb declining {drop:.1f} g/dL ({previous_hb} to {current_hb}) - Anemia worsening'
        }
    
    if len(hb_values) >= 2:
        is_declining = all(hb_values[i] >= hb_values[i + 1] for i in range(len(hb_values) - 1))
        if is_declining and current_hb < hb_values[-1]:
            return {
                'hb_drop': True,
                'magnitude': hb_values[0] - current_hb,
                'message': 'Persistent Hb decline across multiple visits - Uncontrolled anemia'
            }
    
    return {'hb_drop': False, 'magnitude': 0.0, 'message': ''}


def _analyze_bp_trend(history: List[Dict], current: Dict) -> Dict:
    bp_values = [
        v.get('bp_systolic')
        for v in history
        if v.get('bp_systolic') is not None
    ]
    current_bp = current.get('bp_systolic')
    
    if not bp_values or current_bp is None:
        return {'bp_rising': False, 'magnitude': 0, 'message': ''}
    
    previous_bp = bp_values[-1]
    rise = current_bp - previous_bp
    
    if rise >= 20:
        return {
            'bp_rising': True,
            'magnitude': rise,
            'message': f'CRITICAL: BP surge +{rise} mmHg ({previous_bp} to {current_bp}) - Eclampsia risk'
        }
    elif rise >= 15:
        return {
            'bp_rising': True,
            'magnitude': rise,
            'message': f'BP rising +{rise} mmHg ({previous_bp} to {current_bp}) - Pre-eclampsia concern'
        }
    
    if len(bp_values) >= 2:
        is_rising = all(bp_values[i] <= bp_values[i + 1] for i in range(len(bp_values) - 1))
        if is_rising and current_bp > bp_values[-1]:
            return {
                'bp_rising': True,
                'magnitude': current_bp - bp_values[0],
                'message': 'Progressive BP elevation across visits - Pre-eclampsia pattern'
            }
    
    return {'bp_rising': False, 'magnitude': 0, 'message': ''}


def _analyze_proteinuria_trend(history: List[Dict], current: Dict) -> Dict:
    protein_scale = {'negative': 0, 'nil': 0, 'trace': 1, '1+': 2, '2+': 3, '3+': 4, '4+': 5}
    
    protein_values = [
        protein_scale.get(v.get('proteinuria', '').lower(), 0)
        for v in history
        if v.get('proteinuria')
    ]
    
    current_protein = protein_scale.get(current.get('proteinuria', '').lower(), 0)
    
    persistent = len([v for v in protein_values if v >= 2]) >= 2 and current_protein >= 2
    
    worsening = False
    message = ''
    
    if protein_values and current_protein > 0:
        previous_protein = protein_values[-1]
        if current_protein > previous_protein and current_protein >= 3:
            worsening = True
            message = f'Proteinuria worsening to {current.get("proteinuria")} - Immediate evaluation required'
        elif persistent:
            message = 'Persistent proteinuria (2+ or higher) across multiple visits - Kidney dysfunction'
    
    return {
        'proteinuria_persistent': persistent,
        'proteinuria_worsening': worsening,
        'message': message
    }


def _analyze_weight_trend(previous: Dict, current: Dict) -> Dict:
    prev_weight = previous.get('weight')
    curr_weight = current.get('weight')
    
    if prev_weight is None or curr_weight is None:
        return {'weight_concern': False, 'message': ''}
    
    change = curr_weight - prev_weight
    
    if change > 3.0:
        return {
            'weight_concern': True,
            'message': f'Rapid weight gain +{change:.1f} kg - Assess for edema/fluid retention'
        }
    elif change < -2.0:
        return {
            'weight_concern': True,
            'message': f'Weight loss {change:.1f} kg - Nutritional assessment required'
        }
    
    return {'weight_concern': False, 'message': ''}


def _analyze_visit_gap(previous: Dict, current: Dict) -> Dict:
    prev_ga = previous.get('gestational_age')
    curr_ga = current.get('gestational_age')
    
    if prev_ga is None or curr_ga is None:
        return {'visit_gap_exceeded': False, 'message': ''}
    
    gap = curr_ga - prev_ga
    
    if gap > 6:
        return {
            'visit_gap_exceeded': True,
            'message': f'Missed ANC visits - {gap} week gap since last visit'
        }
    
    return {'visit_gap_exceeded': False, 'message': ''}


def _sanitize_id(patient_id: str) -> str:
    return "".join(c for c in patient_id if c.isalnum() or c in ('_', '-'))
