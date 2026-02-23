import json
from pathlib import Path
from typing import List, Dict, Optional


def load_patient_history(patient_name: str, history_file: str = "data/sample_records.json") -> List[Dict[str, any]]:
    if not Path(history_file).exists():
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
    except json.JSONDecodeError:
        return []
    
    normalized_name = patient_name.replace(' ', '_')
    patient_records = history_data.get(normalized_name, [])
    
    return _convert_records_to_dict(patient_records)


def save_patient_history(
    patient_name: str,
    new_record: Dict[str, any],
    history_file: str = "data/sample_records.json"
) -> None:
    Path(history_file).parent.mkdir(parents=True, exist_ok=True)
    
    if Path(history_file).exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        except json.JSONDecodeError:
            history_data = {}
    else:
        history_data = {}
    
    normalized_name = patient_name.replace(' ', '_')
    
    if normalized_name not in history_data:
        history_data[normalized_name] = []
    
    history_data[normalized_name].append(_convert_dict_to_record(new_record))
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)


def _convert_records_to_dict(records: List[Dict]) -> List[Dict[str, any]]:
    converted = []
    
    for record in records:
        converted.append({
            'visit_date': record.get('visit_date'),
            'hemoglobin': record.get('hemoglobin'),
            'bp_systolic': record.get('bp_systolic'),
            'bp_diastolic': record.get('bp_diastolic'),
            'gestational_age': record.get('gestational_age'),
            'weight': record.get('weight'),
            'proteinuria': record.get('proteinuria'),
            'fundal_height': record.get('fundal_height'),
            'edema': record.get('edema'),
        })
    
    return converted


def _convert_dict_to_record(data: Dict[str, any]) -> Dict:
    return {
        'visit_date': data.get('date'),
        'hemoglobin': data.get('hemoglobin'),
        'bp_systolic': data.get('bp_systolic'),
        'bp_diastolic': data.get('bp_diastolic'),
        'gestational_age': data.get('gestational_age'),
        'weight': data.get('weight'),
        'proteinuria': data.get('proteinuria'),
        'fundal_height': data.get('fundal_height'),
        'edema': data.get('edema'),
    }
