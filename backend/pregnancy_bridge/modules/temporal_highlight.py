"""
Temporal Highlight Generator
Creates human-readable explanations of temporal escalation patterns
Author: PregnancyBridge Development Team
Version: 1.0.0
Date: 2026-02-04
"""

from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TemporalHighlightGenerator:
    """
    Generate temporal highlights explaining WHY escalation happened NOW.
    
    Analyzes visit timelines to identify and explain progressive changes
    in clinical parameters that justify risk escalation.
    
    Key features:
        - Detects trends in BP, hemoglobin, platelets, proteinuria
        - Explains symptom onset timing
        - Quantifies rate of change
        - Highlights concerning patterns
    """
    
    # Thresholds for significant changes
    SIGNIFICANT_CHANGES = {
        'bp_systolic': 10,      # mmHg
        'bp_diastolic': 5,      # mmHg
        'hemoglobin': 0.8,      # g/dL
        'platelets': 30000,     # per uL
        'weight': 2.0           # kg
    }
    
    def __init__(self):
        """Initialize temporal highlight generator"""
        logger.info("TemporalHighlightGenerator initialized")
    
    def generate_highlight(self, 
                          visits: List[Dict],
                          symptoms: Optional[Dict] = None) -> str:
        """
        Generate temporal highlight from visit timeline.
        
        Args:
            visits: List of visit records in chronological order
            symptoms: Current symptom data
            
        Returns:
            Human-readable temporal highlight string
        """
        if len(visits) < 2:
            return self._single_visit_message()
        
        highlights = []
        
        # Analyze each parameter for trends
        bp_highlight = self._analyze_bp_trend(visits)
        if bp_highlight:
            highlights.append(bp_highlight)
        
        hb_highlight = self._analyze_hemoglobin_trend(visits)
        if hb_highlight:
            highlights.append(hb_highlight)
        
        plt_highlight = self._analyze_platelet_trend(visits)
        if plt_highlight:
            highlights.append(plt_highlight)
        
        protein_highlight = self._analyze_proteinuria_trend(visits)
        if protein_highlight:
            highlights.append(protein_highlight)
        
        weight_highlight = self._analyze_weight_trend(visits)
        if weight_highlight:
            highlights.append(weight_highlight)
        
        wbc_highlight = self._analyze_wbc_trend(visits)
        if wbc_highlight:
            highlights.append(wbc_highlight)
        
        # Add symptom onset information
        symptom_highlight = self._analyze_symptom_onset(symptoms)
        if symptom_highlight:
            highlights.append(symptom_highlight)
        
        # Construct final highlight
        return self._construct_highlight(highlights, visits)
    
    def _single_visit_message(self) -> str:
        """Message for single visit assessments"""
        return "Single visit assessment - no temporal trend data available"
    
    def _analyze_bp_trend(self, visits: List[Dict]) -> Optional[str]:
        """
        Analyze blood pressure trend across visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Highlight string if significant trend detected
        """
        bp_values = []
        for v in visits:
            if v.get('bp'):
                sys = v['bp'].get('systolic')
                dia = v['bp'].get('diastolic')
                if sys is not None and dia is not None:
                    bp_values.append((sys, dia))
        
        if len(bp_values) < 2:
            return None
        
        sys_first, dia_first = bp_values[0]
        sys_last, dia_last = bp_values[-1]
        
        sys_change = sys_last - sys_first
        dia_change = dia_last - dia_first
        
        # Check for significant change
        if abs(sys_change) >= self.SIGNIFICANT_CHANGES['bp_systolic']:
            direction = "increased" if sys_change > 0 else "decreased"
            
            # Format BP progression
            bp_progression = " → ".join([f"{s}/{d}" for s, d in bp_values])
            
            # Assess severity
            if sys_last >= 160:
                severity = " (severe hypertension range)"
            elif sys_last >= 140:
                severity = " (hypertensive range)"
            else:
                severity = ""
            
            return f"Blood pressure {direction} from {sys_first}/{dia_first} to {sys_last}/{dia_last} mmHg{severity}"
        
        return None
    
    def _analyze_hemoglobin_trend(self, visits: List[Dict]) -> Optional[str]:
        """
        Analyze hemoglobin trend across visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Highlight string if significant trend detected
        """
        hb_values = [v.get('hemoglobin') for v in visits if v.get('hemoglobin') is not None]
        
        if len(hb_values) < 2:
            return None
        
        hb_change = hb_values[-1] - hb_values[0]
        
        if abs(hb_change) >= self.SIGNIFICANT_CHANGES['hemoglobin']:
            direction = "declined" if hb_change < 0 else "increased"
            
            # Format progression
            hb_progression = " → ".join([f"{h:.1f}" for h in hb_values])
            
            # Calculate rate of decline
            visits_span = len(hb_values)
            rate = abs(hb_change) / visits_span
            
            # Assess severity
            if hb_values[-1] < 7.0:
                severity = " (critical anemia - transfusion may be required)"
            elif hb_values[-1] < 9.0:
                severity = " (severe anemia)"
            elif hb_values[-1] < 11.0:
                severity = " (moderate anemia)"
            else:
                severity = ""
            
            if hb_change < 0:
                return f"Hemoglobin {direction} from {hb_values[0]:.1f} to {hb_values[-1]:.1f} g/dL (loss of {abs(hb_change):.1f} g/dL){severity}"
            else:
                return f"Hemoglobin improved from {hb_values[0]:.1f} to {hb_values[-1]:.1f} g/dL"
        
        return None
    
    def _analyze_platelet_trend(self, visits: List[Dict]) -> Optional[str]:
        """
        Analyze platelet count trend across visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Highlight string if significant trend detected
        """
        plt_values = [v.get('platelets') for v in visits if v.get('platelets') is not None]
        
        if len(plt_values) < 2:
            return None
        
        plt_change = plt_values[-1] - plt_values[0]
        
        if abs(plt_change) >= self.SIGNIFICANT_CHANGES['platelets']:
            direction = "declined" if plt_change < 0 else "increased"
            
            # Format progression
            plt_progression = " → ".join([f"{p:,}" for p in plt_values])
            
            # Assess severity
            if plt_values[-1] < 50000:
                severity = " (critical - HELLP syndrome risk)"
            elif plt_values[-1] < 100000:
                severity = " (severe thrombocytopenia)"
            elif plt_values[-1] < 150000:
                severity = " (mild thrombocytopenia)"
            else:
                severity = ""
            
            if plt_change < 0:
                return f"Platelet count {direction} from {plt_values[0]:,} to {plt_values[-1]:,} per uL (drop of {abs(plt_change):,}){severity}"
            else:
                return f"Platelet count improved from {plt_values[0]:,} to {plt_values[-1]:,} per uL"
        
        return None
    
    def _analyze_proteinuria_trend(self, visits: List[Dict]) -> Optional[str]:
        """
        Analyze proteinuria progression across visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Highlight string if significant trend detected
        """
        protein_values = [v.get('proteinuria') for v in visits if v.get('proteinuria') is not None]
        
        if len(protein_values) < 2:
            return None
        
        # Map proteinuria to severity scores
        severity_map = {
            'nil': 0, 'negative': 0, 'trace': 1,
            '+1': 2, '+': 2, '1+': 2,
            '+2': 3, '++': 3, '2+': 3,
            '+3': 4, '+++': 4, '3+': 4
        }
        
        protein_scores = []
        for p in protein_values:
            score = severity_map.get(p.lower() if isinstance(p, str) else str(p), 0)
            protein_scores.append(score)
        
        score_change = protein_scores[-1] - protein_scores[0]
        
        if score_change > 0:
            # Worsening proteinuria
            progression = " → ".join(protein_values)
            
            # Assess clinical significance
            if protein_scores[-1] >= 4:
                severity = " (severe proteinuria - preeclampsia highly likely)"
            elif protein_scores[-1] >= 3:
                severity = " (significant proteinuria - preeclampsia concern)"
            elif protein_scores[-1] >= 2:
                severity = " (mild proteinuria - monitor for preeclampsia)"
            else:
                severity = ""
            
            return f"Proteinuria worsened from {protein_values[0]} to {protein_values[-1]}{severity}"
        
        return None
    
    def _analyze_weight_trend(self, visits: List[Dict]) -> Optional[str]:
        """
        Analyze weight gain pattern across visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Highlight string if significant trend detected
        """
        weight_values = [v.get('weight') for v in visits if v.get('weight') is not None]
        
        if len(weight_values) < 2:
            return None
        
        weight_change = weight_values[-1] - weight_values[0]
        
        if abs(weight_change) >= self.SIGNIFICANT_CHANGES['weight']:
            # Rapid weight gain can indicate fluid retention
            if weight_change > 0:
                # Calculate weeks if dates available
                weeks_span = len(visits) - 1
                rate_per_visit = weight_change / weeks_span if weeks_span > 0 else weight_change
                
                if weight_change >= 4.0:
                    severity = " (excessive - possible fluid retention)"
                elif weight_change >= 3.0:
                    severity = " (rapid gain - monitor for edema)"
                else:
                    severity = ""
                
                return f"Rapid weight gain: {weight_values[0]:.1f} to {weight_values[-1]:.1f} kg (gained {weight_change:.1f} kg){severity}"
        
        return None
    
    def _analyze_wbc_trend(self, visits: List[Dict]) -> Optional[str]:
        """
        Analyze white blood cell count trend across visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Highlight string if significant trend detected
        """
        wbc_values = [v.get('wbc') for v in visits if v.get('wbc') is not None]
        
        if len(wbc_values) < 2:
            return None
        
        wbc_change = wbc_values[-1] - wbc_values[0]
        
        if wbc_change > 5000:
            # Rising WBC suggests infection
            if wbc_values[-1] > 20000:
                severity = " (severe leukocytosis - sepsis concern)"
            elif wbc_values[-1] > 15000:
                severity = " (leukocytosis - infection suspected)"
            else:
                severity = ""
            
            return f"White blood cell count increased from {wbc_values[0]:,} to {wbc_values[-1]:,} per uL{severity}"
        
        return None
    
    def _analyze_symptom_onset(self, symptoms: Optional[Dict]) -> Optional[str]:
        """
        Analyze symptom onset and significance.
        
        Args:
            symptoms: Symptom dictionary
            
        Returns:
            Highlight string if significant symptoms present
        """
        if not symptoms or symptoms.get('symptom_count', 0) == 0:
            return None
        
        symptom_categories = []
        
        if symptoms.get('has_neurological'):
            neuro_symptoms = [s for s in symptoms.get('present_symptoms', []) 
                            if s in ['headache', 'blurred_vision', 'visual_disturbance', 'dizziness']]
            if neuro_symptoms:
                symptom_categories.append(f"neurological symptoms ({', '.join(neuro_symptoms).replace('_', ' ')})")
        
        if symptoms.get('has_respiratory'):
            resp_symptoms = [s for s in symptoms.get('present_symptoms', [])
                           if s in ['breathlessness', 'chest_pain']]
            if resp_symptoms:
                symptom_categories.append(f"respiratory symptoms ({', '.join(resp_symptoms).replace('_', ' ')})")
        
        if symptoms.get('has_fetal_concern'):
            fetal_symptoms = [s for s in symptoms.get('present_symptoms', [])
                            if s in ['reduced_fetal_movement', 'absent_fetal_movement']]
            if fetal_symptoms:
                symptom_categories.append(f"fetal concerns ({', '.join(fetal_symptoms).replace('_', ' ')})")
        
        if symptoms.get('has_gi'):
            gi_symptoms = [s for s in symptoms.get('present_symptoms', [])
                         if s in ['nausea_vomiting', 'abdominal_pain', 'epigastric_pain']]
            if gi_symptoms:
                symptom_categories.append(f"gastrointestinal symptoms ({', '.join(gi_symptoms).replace('_', ' ')})")
        
        if symptom_categories:
            if len(symptom_categories) > 1:
                return f"New onset of {' and '.join(symptom_categories)}"
            else:
                return f"New onset of {symptom_categories[0]}"
        
        return None
    
    def _construct_highlight(self, highlights: List[str], visits: List[Dict]) -> str:
        """
        Construct final temporal highlight from individual components.
        
        Args:
            highlights: List of highlight strings
            visits: Visit records
            
        Returns:
            Formatted temporal highlight
        """
        if not highlights:
            return self._no_significant_changes(visits)
        
        # Get time span information
        time_span = self._get_time_span(visits)
        
        # Combine highlights
        if len(highlights) == 1:
            return f"{highlights[0]} {time_span}"
        elif len(highlights) == 2:
            return f"{highlights[0]} and {highlights[1]} {time_span}"
        else:
            # Take top 3 most important
            primary = "; ".join(highlights[:3])
            if len(highlights) > 3:
                return f"Progressive escalation: {primary}; plus {len(highlights) - 3} additional parameter changes {time_span}"
            else:
                return f"Progressive escalation: {primary} {time_span}"
    
    def _no_significant_changes(self, visits: List[Dict]) -> str:
        """Message when no significant temporal changes detected"""
        time_span = self._get_time_span(visits)
        return f"No significant temporal changes detected {time_span}"
    
    def _get_time_span(self, visits: List[Dict]) -> str:
        """
        Calculate time span of visits.
        
        Args:
            visits: List of visit records
            
        Returns:
            Time span description
        """
        if len(visits) < 2:
            return ""
        
        first_date = visits[0].get('date')
        last_date = visits[-1].get('date')
        
        if first_date and last_date:
            return f"from {first_date} to {last_date}"
        else:
            return f"over {len(visits)} visits"
    
    def get_trend_severity(self, visits: List[Dict]) -> str:
        """
        Assess overall severity of temporal trends.
        
        Args:
            visits: List of visit records
            
        Returns:
            Severity assessment (stable, worsening, critical)
        """
        if len(visits) < 2:
            return "insufficient_data"
        
        severity_score = 0
        
        # Check each parameter
        bp_values = [(v['bp']['systolic'], v['bp']['diastolic']) 
                    for v in visits if v.get('bp')]
        if len(bp_values) >= 2:
            if bp_values[-1][0] >= 160:
                severity_score += 3
            elif bp_values[-1][0] >= 140 and bp_values[-1][0] > bp_values[0][0]:
                severity_score += 2
        
        hb_values = [v['hemoglobin'] for v in visits if v.get('hemoglobin') is not None]
        if len(hb_values) >= 2:
            if hb_values[-1] < 7.0:
                severity_score += 3
            elif hb_values[-1] < 9.0 and hb_values[-1] < hb_values[0]:
                severity_score += 2
        
        plt_values = [v['platelets'] for v in visits if v.get('platelets') is not None]
        if len(plt_values) >= 2:
            if plt_values[-1] < 50000:
                severity_score += 3
            elif plt_values[-1] < 100000 and plt_values[-1] < plt_values[0]:
                severity_score += 2
        
        # Determine overall severity
        if severity_score >= 5:
            return "critical_deterioration"
        elif severity_score >= 3:
            return "significant_worsening"
        elif severity_score >= 1:
            return "mild_worsening"
        else:
            return "stable"


# Singleton instance
_highlight_generator_instance = None


def get_highlight_generator() -> TemporalHighlightGenerator:
    """
    Get singleton instance of TemporalHighlightGenerator.
    
    Returns:
        TemporalHighlightGenerator instance
    """
    global _highlight_generator_instance
    if _highlight_generator_instance is None:
        _highlight_generator_instance = TemporalHighlightGenerator()
    return _highlight_generator_instance


if __name__ == "__main__":
    # Self-test
    print("\nTemporalHighlightGenerator Self-Test")
    print("=" * 70)
    
    generator = get_highlight_generator()
    
    # Test case: Progressive preeclampsia
    test_visits = [
        {
            'date': '2026-01-10',
            'gestational_age': 32,
            'bp': {'systolic': 128, 'diastolic': 84},
            'hemoglobin': 11.2,
            'platelets': 180000,
            'proteinuria': 'nil',
            'weight': 72.0
        },
        {
            'date': '2026-01-24',
            'gestational_age': 34,
            'bp': {'systolic': 136, 'diastolic': 88},
            'hemoglobin': 11.0,
            'platelets': 145000,
            'proteinuria': 'trace',
            'weight': 74.5
        },
        {
            'date': '2026-02-04',
            'gestational_age': 36,
            'bp': {'systolic': 150, 'diastolic': 96},
            'hemoglobin': 10.8,
            'platelets': 110000,
            'proteinuria': '+2',
            'weight': 76.5
        }
    ]
    
    test_symptoms = {
        'symptom_count': 3,
        'present_symptoms': ['headache', 'blurred_vision', 'pedal_edema'],
        'has_neurological': True
    }
    
    highlight = generator.generate_highlight(test_visits, test_symptoms)
    
    print("\nTemporal Highlight:")
    print("-" * 70)
    print(highlight)
    
    severity = generator.get_trend_severity(test_visits)
    print(f"\nTrend Severity: {severity}")
    
    print("\n" + "=" * 70)
    print("Self-test complete")
