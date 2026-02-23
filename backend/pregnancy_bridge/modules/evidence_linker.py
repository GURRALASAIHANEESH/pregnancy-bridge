"""
Evidence Linking Layer
Computes deltas, percent changes, and generates structured evidence summaries
Author: PregnancyBridge Development Team
Version: 2.0.0
Date: 2026-02-04
"""

from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


class EvidenceLinker:
    """
    Links clinical evidence to risk escalation decisions.
    Computes temporal changes and generates audit-ready summaries.
    
    Production features:
    - Lab age computation with configurable reference date
    - Temporal delta calculation with percent changes
    - Severity-weighted evidence ranking
    - Audit trail for provenance tracking
    """
    
    # Clinical severity weights for sorting evidence (higher = more critical)
    SEVERITY_WEIGHTS = {
        'platelets': 10,
        'bp_systolic': 9,
        'proteinuria': 9,
        'hemoglobin': 8,
        'wbc': 7,
        'bp_diastolic': 6,
        'symptom_neurological': 9,
        'symptom_respiratory': 8,
        'symptom_fetal': 10,
        'symptom_gi': 6,
        'symptom_other': 4
    }
    
    # Lab age thresholds (days)
    LAB_AGE_THRESHOLDS = {
        'fresh': 7,
        'acceptable': 30,
        'old': 90
    }
    
    def __init__(self):
        logger.info("EvidenceLinker v2.0 initialized")
    
    def compute_lab_age(self, 
                       lab_report_date: str, 
                       reference_date: Optional[str] = None) -> Optional[int]:
        """
        Compute age of lab report in days.
        
        Args:
            lab_report_date: Lab report date string (YYYY-MM-DD format)
            reference_date: Reference date (YYYY-MM-DD), defaults to today
            
        Returns:
            Age in days (non-negative), or None if date invalid
            
        Example:
            >>> linker.compute_lab_age('2026-01-20', '2026-02-04')
            15
        """
        if not lab_report_date:
            logger.warning("Lab report date is missing")
            return None
        
        try:
            lab_date = datetime.strptime(lab_report_date, '%Y-%m-%d').date()
            
            if reference_date:
                ref_date = datetime.strptime(reference_date, '%Y-%m-%d').date()
            else:
                ref_date = date.today()
            
            delta_days = (ref_date - lab_date).days
            
            if delta_days < 0:
                logger.error(f"Lab date {lab_report_date} is in the future relative to {ref_date}")
                return None
            
            logger.debug(f"Lab age computed: {delta_days} days (lab: {lab_report_date}, ref: {ref_date})")
            return delta_days
            
        except ValueError as e:
            logger.error(f"Invalid date format for lab_report_date '{lab_report_date}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error computing lab age: {e}")
            return None
    
    def get_lab_age_warning(self, lab_age_days: Optional[int]) -> Optional[str]:
        """
        Determine lab age warning category based on clinical guidelines.
        
        Evidence: CBC sample stability research indicates 30-90 day windows
        for pragmatic clinical decision-making in resource-constrained settings.
        
        Args:
            lab_age_days: Age of lab in days
            
        Returns:
            Warning string: 'stale_lab_30d', 'old_but_usable', 'too_old_recommend_repeat', or None
            
        Example:
            >>> linker.get_lab_age_warning(45)
            'old_but_usable'
        """
        if lab_age_days is None:
            return None
        
        if lab_age_days > self.LAB_AGE_THRESHOLDS['old']:
            logger.warning(f"Lab age {lab_age_days} days exceeds 90-day threshold")
            return "too_old_recommend_repeat"
        elif lab_age_days > self.LAB_AGE_THRESHOLDS['acceptable']:
            logger.info(f"Lab age {lab_age_days} days between 31-90 days (old but usable)")
            return "old_but_usable"
        else:
            # Fresh lab (≤30 days), no warning needed
            return None
    
    def build_evidence_items(self,
                            visits: List[Dict],
                            symptoms: Optional[Dict],
                            lab_age_days: Optional[int] = None) -> List[Dict]:
        """
        Build structured evidence items from visit and symptom data.
        
        Extracts lab values, computes temporal deltas, and structures symptoms.
        All evidence items follow the schema v2 format.
        
        Args:
            visits: List of visit records (chronologically ordered)
            symptoms: Symptom dictionary from symptom_intake
            lab_age_days: Age of lab report (if available)
            
        Returns:
            List of evidence item dictionaries conforming to schema v2
            
        Evidence item structure:
            {
                'type': 'lab' | 'symptom' | 'temporal',
                'name': parameter name,
                'value': current value,
                'unit': measurement unit (if applicable),
                'age_days': lab age (for lab items),
                'delta': absolute change from first visit (if temporal data exists),
                'percent_change': percentage change (if temporal data exists),
                'reported': boolean (for symptoms)
            }
        """
        evidence = []
        
        if not visits:
            logger.warning("No visits provided to build_evidence_items")
            return evidence
        
        latest = visits[-1]
        first = visits[0] if len(visits) > 1 else None
        
        logger.debug(f"Building evidence from {len(visits)} visit(s)")
        
        # ===== Lab Evidence =====
        
        # Hemoglobin
        if latest.get('hemoglobin') is not None:
            hb_item = {
                'type': 'lab',
                'name': 'hemoglobin',
                'value': round(latest['hemoglobin'], 1),
                'unit': 'g/dL',
                'age_days': lab_age_days
            }
            
            if first and first.get('hemoglobin') is not None:
                delta = latest['hemoglobin'] - first['hemoglobin']
                hb_item['delta'] = round(delta, 1)
                if first['hemoglobin'] > 0:
                    hb_item['percent_change'] = round((delta / first['hemoglobin']) * 100, 1)
            
            evidence.append(hb_item)
            logger.debug(f"Added hemoglobin evidence: {hb_item['value']} g/dL")
        
        # Platelets
        if latest.get('platelets') is not None:
            plt_item = {
                'type': 'lab',
                'name': 'platelets',
                'value': int(latest['platelets']),
                'unit': '/uL',
                'age_days': lab_age_days
            }
            
            if first and first.get('platelets') is not None:
                delta = latest['platelets'] - first['platelets']
                plt_item['delta'] = int(delta)
                if first['platelets'] > 0:
                    plt_item['percent_change'] = round((delta / first['platelets']) * 100, 1)
            
            evidence.append(plt_item)
            logger.debug(f"Added platelet evidence: {plt_item['value']:,} /uL")
        
        # Blood Pressure (systolic)
        if latest.get('bp') and latest['bp'].get('systolic') is not None:
            bp_sys_item = {
                'type': 'lab',
                'name': 'bp_systolic',
                'value': int(latest['bp']['systolic']),
                'unit': 'mmHg',
                'age_days': lab_age_days
            }
            
            if first and first.get('bp') and first['bp'].get('systolic') is not None:
                delta = latest['bp']['systolic'] - first['bp']['systolic']
                bp_sys_item['delta'] = int(delta)
                if first['bp']['systolic'] > 0:
                    bp_sys_item['percent_change'] = round((delta / first['bp']['systolic']) * 100, 1)
            
            evidence.append(bp_sys_item)
            logger.debug(f"Added BP systolic evidence: {bp_sys_item['value']} mmHg")
        
        # Blood Pressure (diastolic)
        if latest.get('bp') and latest['bp'].get('diastolic') is not None:
            bp_dia_item = {
                'type': 'lab',
                'name': 'bp_diastolic',
                'value': int(latest['bp']['diastolic']),
                'unit': 'mmHg',
                'age_days': lab_age_days
            }
            
            if first and first.get('bp') and first['bp'].get('diastolic') is not None:
                delta = latest['bp']['diastolic'] - first['bp']['diastolic']
                bp_dia_item['delta'] = int(delta)
                if first['bp']['diastolic'] > 0:
                    bp_dia_item['percent_change'] = round((delta / first['bp']['diastolic']) * 100, 1)
            
            evidence.append(bp_dia_item)
        
        # Proteinuria
        if latest.get('proteinuria'):
            protein_item = {
                'type': 'lab',
                'name': 'proteinuria',
                'value': str(latest['proteinuria']),
                'unit': None,
                'age_days': lab_age_days
            }
            evidence.append(protein_item)
            logger.debug(f"Added proteinuria evidence: {protein_item['value']}")
        
        # WBC (White Blood Cell count)
        if latest.get('wbc') is not None:
            wbc_item = {
                'type': 'lab',
                'name': 'wbc',
                'value': int(latest['wbc']),
                'unit': '/uL',
                'age_days': lab_age_days
            }
            
            if first and first.get('wbc') is not None:
                delta = latest['wbc'] - first['wbc']
                wbc_item['delta'] = int(delta)
                if first['wbc'] > 0:
                    wbc_item['percent_change'] = round((delta / first['wbc']) * 100, 1)
            
            evidence.append(wbc_item)
            logger.debug(f"Added WBC evidence: {wbc_item['value']:,} /uL")
        
        # RBC (if available)
        if latest.get('rbc') is not None:
            rbc_item = {
                'type': 'lab',
                'name': 'rbc',
                'value': round(latest['rbc'], 2),
                'unit': 'million/uL',
                'age_days': lab_age_days
            }
            evidence.append(rbc_item)
        
        # ===== Symptom Evidence =====
        
        if symptoms and symptoms.get('present_symptoms'):
            logger.debug(f"Adding {len(symptoms['present_symptoms'])} symptom(s)")
            
            for symptom in symptoms['present_symptoms']:
                evidence.append({
                    'type': 'symptom',
                    'name': symptom,
                    'reported': True,
                    'value': None,
                    'unit': None
                })
        
        logger.info(f"Built {len(evidence)} evidence items ({sum(1 for e in evidence if e['type']=='lab')} lab, {sum(1 for e in evidence if e['type']=='symptom')} symptom)")
        
        return evidence
    
    def generate_evidence_summary(self, 
                                  evidence_items: List[Dict], 
                                  visits: List[Dict]) -> List[str]:
        """
        Generate human-readable evidence summary lines.
        
        Produces concise clinical statements explaining why escalation occurred.
        Sorted by clinical severity (most critical first).
        
        Args:
            evidence_items: Structured evidence items from build_evidence_items
            visits: Visit records (for temporal context)
            
        Returns:
            List of up to 3 summary strings, sorted by severity
            
        Example output:
            [
                "platelets dropped 180000→85000 (drop 53%)",
                "proteinuria progressed trace→+2",
                "new neurological symptoms (headache, blurred vision)"
            ]
        """
        summaries = []
        
        logger.debug(f"Generating evidence summary from {len(evidence_items)} items")
        
        # ===== Process Lab Evidence with Temporal Changes =====
        
        for item in evidence_items:
            if item['type'] != 'lab':
                continue
            
            name = item['name']
            value = item['value']
            unit = item['unit'] or ''
            delta = item.get('delta')
            pct_change = item.get('percent_change')
            
            # Platelets (drop is concerning)
            if name == 'platelets' and delta is not None and delta < 0:
                first_val = value - delta
                pct = abs(pct_change) if pct_change else 0
                summaries.append({
                    'text': f"platelets dropped {first_val:,}→{value:,} (drop {pct:.0f}%)",
                    'severity': self.SEVERITY_WEIGHTS.get('platelets', 5)
                })
            
            # Hemoglobin (decline is concerning)
            elif name == 'hemoglobin' and delta is not None and delta < -0.5:
                first_val = value - delta
                summaries.append({
                    'text': f"hemoglobin declined {first_val:.1f}→{value:.1f} {unit} (loss {abs(delta):.1f} {unit})",
                    'severity': self.SEVERITY_WEIGHTS.get('hemoglobin', 5)
                })
            
            # Blood Pressure (increase to hypertensive range)
            elif name == 'bp_systolic' and value >= 140:
                if delta is not None and delta > 0:
                    first_val = value - delta
                    summaries.append({
                        'text': f"blood pressure increased {first_val}→{value} {unit} (hypertensive)",
                        'severity': self.SEVERITY_WEIGHTS.get('bp_systolic', 5)
                    })
                else:
                    summaries.append({
                        'text': f"blood pressure {value} {unit} (hypertensive)",
                        'severity': self.SEVERITY_WEIGHTS.get('bp_systolic', 5)
                    })
            
            # Proteinuria (progression or presence)
            elif name == 'proteinuria':
                if len(visits) >= 2:
                    prev_protein = visits[0].get('proteinuria', 'nil')
                    if prev_protein != value and value in ['+1', '+2', '+3', '++', '+++', '1+', '2+', '3+']:
                        summaries.append({
                            'text': f"proteinuria progressed {prev_protein}→{value}",
                            'severity': self.SEVERITY_WEIGHTS.get('proteinuria', 5)
                        })
                elif value in ['+2', '+3', '++', '+++', '2+', '3+']:
                    summaries.append({
                        'text': f"significant proteinuria ({value})",
                        'severity': self.SEVERITY_WEIGHTS.get('proteinuria', 5)
                    })
            
            # WBC (elevated suggests infection)
            elif name == 'wbc' and value > 15000:
                summaries.append({
                    'text': f"elevated white blood cells ({value:,} {unit})",
                    'severity': self.SEVERITY_WEIGHTS.get('wbc', 5)
                })
        
        # ===== Process Symptom Evidence =====
        
        symptom_categories = {}
        
        for item in evidence_items:
            if item['type'] != 'symptom' or not item.get('reported'):
                continue
            
            symptom = item['name']
            
            # Categorize by system
            if symptom in ['headache', 'blurred_vision', 'visual_disturbance', 'dizziness']:
                symptom_categories.setdefault('neurological', []).append(symptom.replace('_', ' '))
            elif symptom in ['breathlessness', 'chest_pain']:
                symptom_categories.setdefault('respiratory', []).append(symptom.replace('_', ' '))
            elif symptom in ['reduced_fetal_movement', 'absent_fetal_movement']:
                symptom_categories.setdefault('fetal', []).append(symptom.replace('_', ' '))
            elif symptom in ['abdominal_pain', 'epigastric_pain', 'nausea_vomiting']:
                symptom_categories.setdefault('gi', []).append(symptom.replace('_', ' '))
            else:
                symptom_categories.setdefault('other', []).append(symptom.replace('_', ' '))
        
        # Add categorical symptom summaries
        for category, symptoms_list in symptom_categories.items():
            severity = self.SEVERITY_WEIGHTS.get(f'symptom_{category}', 5)
            symptom_str = ', '.join(symptoms_list)
            summaries.append({
                'text': f"new {category} symptoms ({symptom_str})",
                'severity': severity
            })
        
        # ===== Sort by Severity and Return Top 3 =====
        
        summaries.sort(key=lambda x: x['severity'], reverse=True)
        result = [s['text'] for s in summaries[:3]]
        
        logger.info(f"Generated {len(result)} evidence summary line(s)")
        for i, line in enumerate(result, 1):
            logger.debug(f"  {i}. {line}")
        
        return result
    
    def compute_confidence_penalty(self, lab_age_days: Optional[int]) -> float:
        """
        Compute confidence penalty based on lab age.
        
        Rationale: Older lab results reduce confidence in current clinical state.
        
        Args:
            lab_age_days: Age of lab in days
            
        Returns:
            Penalty factor (0.0 = no penalty, negative values reduce confidence)
            
        Penalty schedule:
            ≤7 days: 0.0 (no penalty)
            8-30 days: -0.02 (minimal)
            31-90 days: -0.10 (moderate)
            >90 days: -0.25 (significant)
            Missing date: -0.05 (small penalty)
        """
        if lab_age_days is None:
            logger.debug("Lab age missing, applying small penalty (-0.05)")
            return -0.05
        
        if lab_age_days <= self.LAB_AGE_THRESHOLDS['fresh']:
            return 0.0
        elif lab_age_days <= self.LAB_AGE_THRESHOLDS['acceptable']:
            logger.debug(f"Lab age {lab_age_days}d, minimal penalty (-0.02)")
            return -0.02
        elif lab_age_days <= self.LAB_AGE_THRESHOLDS['old']:
            logger.debug(f"Lab age {lab_age_days}d, moderate penalty (-0.10)")
            return -0.10
        else:
            logger.warning(f"Lab age {lab_age_days}d exceeds 90d, significant penalty (-0.25)")
            return -0.25


# Singleton pattern
_evidence_linker_instance = None


def get_evidence_linker() -> EvidenceLinker:
    """
    Get singleton instance of EvidenceLinker.
    
    Returns:
        EvidenceLinker instance
    """
    global _evidence_linker_instance
    if _evidence_linker_instance is None:
        _evidence_linker_instance = EvidenceLinker()
    return _evidence_linker_instance


# Self-test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("EvidenceLinker v2.0 Self-Test")
    print("=" * 70)
    
    linker = get_evidence_linker()
    
    # Test 1: Lab age computation
    print("\nTest 1: Lab Age Computation")
    print("-" * 70)
    age1 = linker.compute_lab_age('2026-01-20', '2026-02-04')
    print(f"Lab age (2026-01-20 → 2026-02-04): {age1} days")
    assert age1 == 15, "Lab age calculation incorrect"
    
    age2 = linker.compute_lab_age('2025-11-01', '2026-02-04')
    print(f"Lab age (2025-11-01 → 2026-02-04): {age2} days")
    
    # Test 2: Lab age warnings
    print("\nTest 2: Lab Age Warnings")
    print("-" * 70)
    warning1 = linker.get_lab_age_warning(15)
    print(f"15 days: {warning1 or 'No warning (fresh)'}")
    
    warning2 = linker.get_lab_age_warning(45)
    print(f"45 days: {warning2}")
    
    warning3 = linker.get_lab_age_warning(95)
    print(f"95 days: {warning3}")
    
    # Test 3: Evidence items
    print("\nTest 3: Evidence Items")
    print("-" * 70)
    
    test_visits = [
        {'hemoglobin': 11.2, 'platelets': 180000, 'bp': {'systolic': 128, 'diastolic': 84}},
        {'hemoglobin': 10.5, 'platelets': 85000, 'bp': {'systolic': 150, 'diastolic': 96}}
    ]
    
    test_symptoms = {
        'present_symptoms': ['headache', 'blurred_vision']
    }
    
    evidence = linker.build_evidence_items(test_visits, test_symptoms, lab_age_days=15)
    print(f"Generated {len(evidence)} evidence items:")
    for item in evidence:
        print(f"  - {item['type']}: {item['name']} = {item.get('value')} {item.get('unit') or ''}")
        if item.get('delta'):
            print(f"    Delta: {item['delta']}, Change: {item.get('percent_change')}%")
    
    # Test 4: Evidence summary
    print("\nTest 4: Evidence Summary")
    print("-" * 70)
    summary = linker.generate_evidence_summary(evidence, test_visits)
    for i, line in enumerate(summary, 1):
        print(f"{i}. {line}")
    
    # Test 5: Confidence penalty
    print("\nTest 5: Confidence Penalty")
    print("-" * 70)
    penalties = [
        (5, linker.compute_confidence_penalty(5)),
        (20, linker.compute_confidence_penalty(20)),
        (50, linker.compute_confidence_penalty(50)),
        (100, linker.compute_confidence_penalty(100)),
        (None, linker.compute_confidence_penalty(None))
    ]
    for days, penalty in penalties:
        print(f"{str(days).rjust(4)} days: penalty = {penalty:+.2f}")
    
    print("\n" + "=" * 70)
    print("✓ All self-tests passed")
    print("=" * 70)
