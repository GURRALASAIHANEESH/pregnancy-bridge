"""
Temporal Risk Engine - Detects escalation across ANC visits
Decision authority for PregnancyBridge
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TemporalRiskEngine:
    """Analyzes risk trends across multiple ANC visits"""
    
    def __init__(self):
        # Clinical thresholds
        self.HB_SEVERE = 7.0
        self.HB_MODERATE = 9.0
        self.HB_MILD = 11.0
        
        self.BP_SEVERE_SYS = 160
        self.BP_STAGE2_SYS = 150
        self.BP_STAGE1_SYS = 140
        
        self.PROTEINURIA_LEVELS = {
            'negative': 0, 'trace': 1, '+1': 2, '+2': 3, '+3': 4
        }
    
    def assess_timeline(self, visits: List[Dict]) -> Dict:
        """
        Analyze visit timeline for escalation patterns
        
        Args:
            visits: List of visit dicts with keys:
                - gestational_age (weeks)
                - hemoglobin (g/dL)
                - bp_systolic, bp_diastolic (mmHg)
                - proteinuria (string level)
                - visit_date (optional)
        
        Returns:
            {
                'risk_category': 'LOW|MODERATE|HIGH',
                'escalation_trigger': str or None,
                'trigger_visit': int (index),
                'rule_reason': str,
                'visit_summaries': List[Dict]
            }
        """
        if not visits or len(visits) == 0:
            return self._unknown_risk("No visit data")
        
        # Sort by gestational age
        visits = sorted(visits, key=lambda v: v.get('gestational_age', 0))
        
        # Check each escalation pattern
        escalations = []
        
        # Pattern 1: Progressive anemia
        anemia_risk = self._check_anemia_trend(visits)
        if anemia_risk:
            escalations.append(anemia_risk)
        
        # Pattern 2: BP escalation
        bp_risk = self._check_bp_trend(visits)
        if bp_risk:
            escalations.append(bp_risk)
        
        # Pattern 3: Persistent/worsening proteinuria
        protein_risk = self._check_proteinuria_trend(visits)
        if protein_risk:
            escalations.append(protein_risk)
        
        # Pattern 4: Pre-eclampsia (BP + proteinuria combined)
        preeclampsia_risk = self._check_preeclampsia_pattern(visits)
        if preeclampsia_risk:
            escalations.append(preeclampsia_risk)
        
        # Pattern 5: Platelet drop (HELLP risk)
        platelet_risk = self._check_platelet_trend(visits)
        if platelet_risk:
            escalations.append(platelet_risk)

        # Pattern 6: Multi-factor moderate risks
        multifactor_risk = self._check_multi_factor_risk(visits)
        if multifactor_risk:
            escalations.append(multifactor_risk)
        
        # Select highest risk
        if not escalations:
            return {
                'risk_category': 'LOW',
                'escalation_trigger': None,
                'trigger_visit': None,
                'rule_reason': 'No escalation patterns detected across visits',
                'visit_summaries': self._summarize_visits(visits)
            }
        
        # Return highest severity escalation
        escalations.sort(key=lambda x: {'HIGH': 3, 'MODERATE': 2, 'LOW': 1}[x['risk_category']], reverse=True)
        top_risk = escalations[0]
        top_risk['visit_summaries'] = self._summarize_visits(visits)
        
        return top_risk
    
    def _check_anemia_trend(self, visits: List[Dict]) -> Optional[Dict]:
        """Detect progressive anemia (declining Hb)"""
        hb_values = [(i, v.get('hemoglobin')) for i, v in enumerate(visits) if v.get('hemoglobin')]
        
        if len(hb_values) < 2:
            return None
        
        # Check for decline
        hb_trend = [hb for _, hb in hb_values]
        latest_hb = hb_trend[-1]
        
        # Critical anemia (single value)
        if latest_hb < self.HB_SEVERE:
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'critical_anemia',
                'trigger_visit': hb_values[-1][0],
                'rule_reason': f'Critical anemia: Hb {latest_hb} g/dL (< 7.0). Transfusion may be required.'
            }
        
        # Progressive decline
        if len(hb_trend) >= 3:
            decline_count = sum(1 for i in range(1, len(hb_trend)) if hb_trend[i] < hb_trend[i-1])
            if decline_count >= 2 and latest_hb < self.HB_MODERATE:
                return {
                    'risk_category': 'HIGH',
                    'escalation_trigger': 'progressive_anemia',
                    'trigger_visit': hb_values[-1][0],
                    'rule_reason': f'Progressive anemia: Hb declining over {len(hb_trend)} visits ({hb_trend[0]} → {latest_hb} g/dL). Current level {latest_hb} < 9.0 g/dL.'
                }
        
        # Severe anemia (single point)
        if latest_hb < self.HB_MODERATE:
            return {
                'risk_category': 'MODERATE',
                'escalation_trigger': 'severe_anemia',
                'trigger_visit': hb_values[-1][0],
                'rule_reason': f'Severe anemia: Hb {latest_hb} g/dL (< 9.0).'
            }
        
        return None
    
    def _check_bp_trend(self, visits: List[Dict]) -> Optional[Dict]:
        """Detect BP escalation"""
        bp_values = [(i, v.get('bp_systolic'), v.get('gestational_age')) 
                     for i, v in enumerate(visits) if v.get('bp_systolic')]
        
        if len(bp_values) < 2:
            return None
        
        latest_idx, latest_bp, latest_ga = bp_values[-1]
        
        # Severe hypertension (immediate risk)
        if latest_bp >= self.BP_SEVERE_SYS:
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'severe_hypertension',
                'trigger_visit': latest_idx,
                'rule_reason': f'Severe hypertension: BP {latest_bp} mmHg (≥ 160) at {latest_ga} weeks.'
            }
        
        # Escalating BP trend
        if len(bp_values) >= 3:
            bp_trend = [bp for _, bp, _ in bp_values]
            rise_count = sum(1 for i in range(1, len(bp_trend)) if bp_trend[i] > bp_trend[i-1])
            
            if rise_count >= 2 and latest_bp >= self.BP_STAGE1_SYS:
                return {
                    'risk_category': 'HIGH',
                    'escalation_trigger': 'bp_escalation',
                    'trigger_visit': latest_idx,
                    'rule_reason': f'Progressive BP rise over {len(bp_trend)} visits ({bp_trend[0]} → {latest_bp} mmHg). Now ≥ 140 mmHg.'
                }
        
        # Stage 2 hypertension
        if latest_bp >= self.BP_STAGE2_SYS:
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'stage2_hypertension',
                'trigger_visit': latest_idx,
                'rule_reason': f'Stage 2 hypertension: BP {latest_bp} mmHg (≥ 150).'
            }
        
        return None
    
    def _check_proteinuria_trend(self, visits: List[Dict]) -> Optional[Dict]:
        """Detect persistent or worsening proteinuria"""
        protein_values = [(i, v.get('proteinuria'), v.get('gestational_age')) 
                          for i, v in enumerate(visits) if v.get('proteinuria')]
        
        if len(protein_values) < 2:
            return None
        
        # Convert to numeric
        protein_levels = []
        for idx, p, ga in protein_values:
            level = self.PROTEINURIA_LEVELS.get(p.lower() if p else 'negative', 0)
            protein_levels.append((idx, level, ga, p))
        
        latest_idx, latest_level, latest_ga, latest_str = protein_levels[-1]
        
        # Significant proteinuria (≥ +2)
        if latest_level >= 3:
            return {
                'risk_category': 'MODERATE',
                'escalation_trigger': 'significant_proteinuria',
                'trigger_visit': latest_idx,
                'rule_reason': f'Significant proteinuria: {latest_str} at {latest_ga} weeks.'
            }
        
        # Persistent proteinuria (≥ trace for 2+ visits)
        if len(protein_levels) >= 2:
            persistent_count = sum(1 for _, lvl, _, _ in protein_levels[-3:] if lvl >= 1)
            if persistent_count >= 2 and latest_level >= 1:
                return {
                    'risk_category': 'MODERATE',
                    'escalation_trigger': 'persistent_proteinuria',
                    'trigger_visit': latest_idx,
                    'rule_reason': f'Persistent proteinuria over {persistent_count} visits. Current: {latest_str}.'
                }
        
        return None
    
    def _check_platelet_trend(self, visits: List[Dict]) -> Optional[Dict]:
        """Detect platelet drop (thrombocytopenia / HELLP risk)"""
        platelet_values = [(i, v.get('platelets'), v.get('gestational_age')) 
                           for i, v in enumerate(visits) if v.get('platelets')]
        
        if not platelet_values:
            return None
        
        latest_idx, latest_count, latest_ga = platelet_values[-1]
        
        # Critical thrombocytopenia
        if latest_count <= 50000:
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'critical_thrombocytopenia',
                'trigger_visit': latest_idx,
                'rule_reason': f'Critical thrombocytopenia: platelets {latest_count}/µL (≤ 50,000). HELLP risk.'
            }
        
        # Low platelets
        if latest_count <= 100000:
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'thrombocytopenia',
                'trigger_visit': latest_idx,
                'rule_reason': f'Thrombocytopenia: platelets {latest_count}/µL (≤ 100,000) at {latest_ga} weeks.'
            }
        
        # Progressive platelet drop
        if len(platelet_values) >= 2:
            first_count = platelet_values[0][1]
            drop_percent = ((first_count - latest_count) / first_count) * 100
            
            if drop_percent >= 30 and latest_count < 150000:
                return {
                    'risk_category': 'HIGH',
                    'escalation_trigger': 'platelet_drop',
                    'trigger_visit': latest_idx,
                    'rule_reason': f'Progressive platelet drop: {drop_percent:.0f}% decline ({first_count} → {latest_count}/µL).'
                }
        
        return None

    def _check_multi_factor_risk(self, visits: List[Dict]) -> Optional[Dict]:
        """Detect when 2+ moderate factors combine to HIGH risk"""
        if not visits:
            return None
        
        latest = visits[-1]
        latest_idx = len(visits) - 1
        moderate_factors = []
        
        # Check BP (moderate threshold: 140-159) - CHANGED FROM 135
        bp_sys = latest.get('bp_systolic', 0)
        if 140 <= bp_sys < 160:  # Changed from 135
            moderate_factors.append(f"BP {bp_sys} mmHg")
        
        # Check Hb (moderate: 9.0-10.5)
        hb = latest.get('hb', 12)
        if 9.0 <= hb < 10.5:
            moderate_factors.append(f"Hb {hb} g/dL")
        
        # Check proteinuria (moderate: +1, severe: +2/+3)
        protein = latest.get('proteinuria', 'nil')
        protein_level = self.PROTEINURIA_LEVELS.get(protein.lower() if protein else 'negative', 0)
        
        if protein_level == 2:  # +1 only
            moderate_factors.append(f"proteinuria {protein}")
        elif protein_level >= 3:  # +2 or +3 is already significant
            # Severe proteinuria alone should escalate
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'severe_proteinuria_escalation',
                'trigger_visit': latest_idx,
                'rule_reason': f'Severe proteinuria {protein} with BP {bp_sys} mmHg. Pre-eclampsia risk.'
            }
        
        # If 2+ moderate factors, escalate to HIGH
        if len(moderate_factors) >= 2:
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'multi_factor_risk',
                'trigger_visit': latest_idx,
                'rule_reason': f'Multi-factor risk: {", ".join(moderate_factors)}. Combined risk escalates to HIGH.'
            }
        
        return None
    
    def _check_preeclampsia_pattern(self, visits: List[Dict]) -> Optional[Dict]:
        """Detect pre-eclampsia (BP + proteinuria combined)"""
        latest = visits[-1]
        bp = latest.get('bp_systolic', 0)
        protein = latest.get('proteinuria', 'negative')
        ga = latest.get('gestational_age', 0)
        
        protein_level = self.PROTEINURIA_LEVELS.get(protein.lower() if protein else 'negative', 0)
        
        # Classic pre-eclampsia criteria: BP ≥ 140 + proteinuria ≥ +1 after 20 weeks
        if ga >= 20 and bp >= self.BP_STAGE1_SYS and protein_level >= 2:
            # Check if pattern is new or worsening
            visit_idx = len(visits) - 1
            
            return {
                'risk_category': 'HIGH',
                'escalation_trigger': 'preeclampsia_criteria',
                'trigger_visit': visit_idx,
                'rule_reason': f'Pre-eclampsia criteria met: BP {bp} mmHg (≥ 140) + proteinuria {protein} at {ga} weeks.'
            }
        
        return None
    
    def _summarize_visits(self, visits: List[Dict]) -> List[Dict]:
        """Create timeline summary for MedGemma prompt"""
        summaries = []
        for i, v in enumerate(visits):
            summary = {
                'visit_number': i + 1,
                'gestational_age': v.get('gestational_age'),
                'hemoglobin': v.get('hemoglobin'),
                'bp_systolic': v.get('bp_systolic'),
                'bp_diastolic': v.get('bp_diastolic'),
                'proteinuria': v.get('proteinuria')
            }
            summaries.append(summary)
        return summaries
    
    def _unknown_risk(self, reason: str) -> Dict:
        return {
            'risk_category': 'UNKNOWN',
            'escalation_trigger': None,
            'trigger_visit': None,
            'rule_reason': reason,
            'visit_summaries': []
        }
