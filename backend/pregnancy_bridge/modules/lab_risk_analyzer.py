"""
Enhanced Laboratory Risk Analyzer
Integrates complete blood count and urinalysis into maternal risk assessment
Author: PregnancyBridge Development Team
Version: 1.0.0
Date: 2026-02-04
"""

from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class LabRiskAnalyzer:
    """
    Analyze laboratory values for maternal risk assessment.
    
    Implements evidence-based thresholds from WHO and ACOG guidelines.
    All rules are deterministic and medically validated.
    """
    
    # Clinical thresholds based on international guidelines
    THRESHOLDS = {
        'hemoglobin': {
            'critical': 7.0,      # Requires transfusion
            'severe': 9.0,        # Severe anemia
            'moderate': 11.0      # Mild anemia in pregnancy
        },
        'platelets': {
            'critical': 50000,    # HELLP/severe bleeding risk
            'severe': 100000,     # Severe preeclampsia concern
            'moderate': 150000    # Mild thrombocytopenia
        },
        'wbc': {
            'severe_high': 20000,
            'elevated': 15000,
            'normal_upper': 12000
        },
        'rbc': {
            'low': 3.5
        }
    }
    
    # Proteinuria grading
    PROTEINURIA_SEVERITY = {
        'nil': 0,
        'negative': 0,
        'trace': 1,
        '+1': 2,
        '++': 2,
        '1+': 2,
        '+2': 3,
        '+++': 3,
        '2+': 3,
        '+3': 4,
        '++++': 4,
        '3+': 4
    }
    
    def __init__(self):
        """Initialize lab risk analyzer"""
        logger.info("LabRiskAnalyzer initialized with evidence-based thresholds")
    
    def analyze_labs(self, lab_data: Dict) -> Dict:
        """
        Analyze laboratory values and generate risk flags.
        
        Args:
            lab_data: Dictionary containing lab values:
                - hemoglobin: float (g/dL)
                - platelets: int (per microliter)
                - wbc: int (per microliter)
                - rbc: float (million per microliter)
                - proteinuria: str (nil, trace, +1, +2, +3)
                
        Returns:
            Dictionary containing:
                - lab_risk_flags: List of clinical findings
                - lab_risk_score: Integer 0-10
                - critical_flags: List of critical findings requiring immediate action
                - abnormal_count: Number of abnormal parameters
        """
        flags = []
        critical_flags = []
        risk_score = 0
        
        # Hemoglobin analysis
        if 'hemoglobin' in lab_data and lab_data['hemoglobin'] is not None:
            hb = lab_data['hemoglobin']
            
            if hb < self.THRESHOLDS['hemoglobin']['critical']:
                flags.append(f"Critical anemia: Hemoglobin {hb} g/dL - transfusion required")
                critical_flags.append("CRITICAL_ANEMIA")
                risk_score += 5
                
            elif hb < self.THRESHOLDS['hemoglobin']['severe']:
                flags.append(f"Severe anemia: Hemoglobin {hb} g/dL - urgent treatment needed")
                critical_flags.append("SEVERE_ANEMIA")
                risk_score += 4
                
            elif hb < self.THRESHOLDS['hemoglobin']['moderate']:
                flags.append(f"Moderate anemia: Hemoglobin {hb} g/dL - iron therapy indicated")
                risk_score += 2
        
        # Platelet analysis (key HELLP/preeclampsia indicator)
        if 'platelets' in lab_data and lab_data['platelets'] is not None:
            plt = lab_data['platelets']
            
            if plt < self.THRESHOLDS['platelets']['critical']:
                flags.append(f"Critical thrombocytopenia: {plt:,} per uL - HELLP syndrome risk")
                critical_flags.append("CRITICAL_THROMBOCYTOPENIA")
                risk_score += 6
                
            elif plt < self.THRESHOLDS['platelets']['severe']:
                flags.append(f"Severe thrombocytopenia: {plt:,} per uL - preeclampsia concern")
                critical_flags.append("SEVERE_THROMBOCYTOPENIA")
                risk_score += 4
                
            elif plt < self.THRESHOLDS['platelets']['moderate']:
                flags.append(f"Mild thrombocytopenia: {plt:,} per uL - monitor closely")
                risk_score += 2
        
        # White blood cell analysis (infection indicator)
        if 'wbc' in lab_data and lab_data['wbc'] is not None:
            wbc = lab_data['wbc']
            
            if wbc > self.THRESHOLDS['wbc']['severe_high']:
                flags.append(f"Severe leukocytosis: {wbc:,} per uL - sepsis concern")
                critical_flags.append("SEVERE_LEUKOCYTOSIS")
                risk_score += 4
                
            elif wbc > self.THRESHOLDS['wbc']['elevated']:
                flags.append(f"Leukocytosis: {wbc:,} per uL - infection suspected")
                risk_score += 2
        
        # Red blood cell analysis
        if 'rbc' in lab_data and lab_data['rbc'] is not None:
            rbc = lab_data['rbc']
            
            if rbc < self.THRESHOLDS['rbc']['low']:
                flags.append(f"Low RBC count: {rbc} million per uL - chronic anemia")
                risk_score += 1
        
        # Proteinuria analysis (preeclampsia marker)
        if 'proteinuria' in lab_data and lab_data['proteinuria'] is not None:
            protein = lab_data['proteinuria'].lower()
            severity = self.PROTEINURIA_SEVERITY.get(protein, 0)
            
            if severity >= 4:
                flags.append(f"Severe proteinuria: {protein} - preeclampsia highly likely")
                critical_flags.append("SEVERE_PROTEINURIA")
                risk_score += 4
                
            elif severity >= 3:
                flags.append(f"Significant proteinuria: {protein} - preeclampsia risk")
                risk_score += 3
                
            elif severity >= 2:
                flags.append(f"Mild proteinuria: {protein} - monitor for preeclampsia")
                risk_score += 1
        
        # Multi-parameter abnormality detection
        abnormal_count = len([f for f in flags if not f.startswith("MULTI")])
        if abnormal_count >= 3:
            flags.append("MULTI-PARAMETER ABNORMALITY: Multiple organ systems affected")
            risk_score += 3
        
        # HELLP syndrome pattern detection
        hellp_score = self._assess_hellp_risk(lab_data, flags)
        if hellp_score >= 2:
            flags.append("HELLP SYNDROME PATTERN: Hemolysis, elevated enzymes, low platelets suspected")
            critical_flags.append("HELLP_PATTERN")
            risk_score += 5
        
        # Cap risk score at 10
        risk_score = min(risk_score, 10)
        
        return {
            'lab_risk_flags': flags,
            'lab_risk_score': risk_score,
            'critical_flags': critical_flags,
            'abnormal_count': abnormal_count
        }
    
    def _assess_hellp_risk(self, lab_data: Dict, existing_flags: List[str]) -> int:
        """
        Assess risk of HELLP syndrome based on lab pattern.
        
        HELLP = Hemolysis, Elevated Liver enzymes, Low Platelets
        
        Returns:
            Integer score 0-3 indicating HELLP likelihood
        """
        hellp_indicators = 0
        
        # Low platelets
        if lab_data.get('platelets') and lab_data['platelets'] < 100000:
            hellp_indicators += 1
        
        # Anemia (hemolysis indicator)
        if lab_data.get('hemoglobin') and lab_data['hemoglobin'] < 9.0:
            hellp_indicators += 1
        
        # Elevated liver enzymes (if available)
        if lab_data.get('ast') and lab_data['ast'] > 70:
            hellp_indicators += 1
        if lab_data.get('alt') and lab_data['alt'] > 70:
            hellp_indicators += 1
        
        # Elevated bilirubin (hemolysis)
        if lab_data.get('bilirubin') and lab_data['bilirubin'] > 1.2:
            hellp_indicators += 1
        
        return hellp_indicators
    
    def compare_temporal_labs(self, visits: List[Dict]) -> Dict:
        """
        Analyze laboratory trends across multiple visits.
        
        Args:
            visits: List of visit dictionaries with lab data
            
        Returns:
            Dictionary containing:
                - trends: List of trend descriptions
                - concerning_patterns: List of concerning pattern codes
                - trend_severity: String (stable, worsening, critical)
        """
        if len(visits) < 2:
            return {
                'trends': [],
                'concerning_patterns': [],
                'trend_severity': 'insufficient_data'
            }
        
        trends = []
        concerning = []
        severity_score = 0
        
        # Hemoglobin trend analysis
        hb_values = [v.get('hemoglobin') for v in visits if v.get('hemoglobin') is not None]
        if len(hb_values) >= 2:
            hb_change = hb_values[-1] - hb_values[0]
            hb_decline_rate = hb_change / len(hb_values)
            
            if hb_change < -2.0:
                trends.append(f"Rapid hemoglobin decline: {hb_values[0]:.1f} to {hb_values[-1]:.1f} g/dL")
                concerning.append("RAPID_HB_DECLINE")
                severity_score += 3
                
            elif hb_change < -1.0:
                trends.append(f"Progressive anemia: {hb_values[0]:.1f} to {hb_values[-1]:.1f} g/dL")
                concerning.append("PROGRESSIVE_ANEMIA")
                severity_score += 2
        
        # Platelet trend analysis
        plt_values = [v.get('platelets') for v in visits if v.get('platelets') is not None]
        if len(plt_values) >= 2:
            plt_change = plt_values[-1] - plt_values[0]
            
            if plt_change < -75000:
                trends.append(f"Severe platelet decline: {plt_values[0]:,} to {plt_values[-1]:,} per uL")
                concerning.append("SEVERE_PLT_DECLINE")
                severity_score += 4
                
            elif plt_change < -50000:
                trends.append(f"Significant platelet decline: {plt_values[0]:,} to {plt_values[-1]:,} per uL")
                concerning.append("SIGNIFICANT_PLT_DECLINE")
                severity_score += 3
        
        # Proteinuria progression analysis
        protein_values = [v.get('proteinuria') for v in visits if v.get('proteinuria') is not None]
        if len(protein_values) >= 2:
            protein_scores = [self.PROTEINURIA_SEVERITY.get(p.lower(), 0) for p in protein_values]
            
            if protein_scores[-1] > protein_scores[0]:
                score_increase = protein_scores[-1] - protein_scores[0]
                trends.append(f"Worsening proteinuria: {protein_values[0]} to {protein_values[-1]}")
                
                if score_increase >= 2:
                    concerning.append("RAPID_PROTEINURIA_PROGRESSION")
                    severity_score += 3
                else:
                    concerning.append("PROTEINURIA_PROGRESSION")
                    severity_score += 2
        
        # WBC trend (infection progression)
        wbc_values = [v.get('wbc') for v in visits if v.get('wbc') is not None]
        if len(wbc_values) >= 2:
            wbc_change = wbc_values[-1] - wbc_values[0]
            
            if wbc_change > 5000:
                trends.append(f"Rising WBC: {wbc_values[0]:,} to {wbc_values[-1]:,} per uL")
                concerning.append("RISING_WBC")
                severity_score += 2
        
        # Determine overall trend severity
        if severity_score >= 6:
            trend_severity = 'critical'
        elif severity_score >= 3:
            trend_severity = 'worsening'
        elif len(trends) > 0:
            trend_severity = 'mild_changes'
        else:
            trend_severity = 'stable'
        
        return {
            'trends': trends,
            'concerning_patterns': concerning,
            'trend_severity': trend_severity,
            'severity_score': severity_score
        }
    
    def combine_lab_and_clinical(self, lab_flags: List[str], 
                                 bp_systolic: Optional[int],
                                 symptoms: Optional[Dict]) -> List[str]:
        """
        Identify dangerous combinations of lab abnormalities with clinical findings.
        
        Args:
            lab_flags: Laboratory risk flags
            bp_systolic: Systolic blood pressure
            symptoms: Symptom dictionary
            
        Returns:
            List of combination risk patterns
        """
        combinations = []
        
        # Thrombocytopenia + Hypertension = Severe preeclampsia/HELLP
        has_low_platelets = any('platelet' in flag.lower() for flag in lab_flags)
        has_hypertension = bp_systolic and bp_systolic >= 140
        
        if has_low_platelets and has_hypertension:
            combinations.append("SEVERE_PREECLAMPSIA_PATTERN: Low platelets with hypertension")
        
        # Anemia + Respiratory symptoms = Cardiopulmonary compromise
        has_anemia = any('anemia' in flag.lower() for flag in lab_flags)
        has_respiratory = symptoms and symptoms.get('has_respiratory', False)
        
        if has_anemia and has_respiratory:
            combinations.append("CARDIOPULMONARY_RISK: Anemia with respiratory symptoms")
        
        # Leukocytosis + Fever = Severe infection
        has_leukocytosis = any('leukocytosis' in flag.lower() for flag in lab_flags)
        has_fever = symptoms and 'fever' in symptoms.get('present_symptoms', [])
        
        if has_leukocytosis and has_fever:
            combinations.append("SEVERE_INFECTION_RISK: Elevated WBC with fever")
        
        # Proteinuria + Neurological symptoms = Preeclampsia with CNS involvement
        has_proteinuria = any('proteinuria' in flag.lower() for flag in lab_flags)
        has_neurological = symptoms and symptoms.get('has_neurological', False)
        
        if has_proteinuria and has_neurological:
            combinations.append("PREECLAMPSIA_CNS: Proteinuria with neurological symptoms")
        
        return combinations


# Singleton instance
_lab_analyzer_instance = None


def get_lab_analyzer() -> LabRiskAnalyzer:
    """
    Get singleton instance of LabRiskAnalyzer.
    
    Returns:
        LabRiskAnalyzer instance
    """
    global _lab_analyzer_instance
    if _lab_analyzer_instance is None:
        _lab_analyzer_instance = LabRiskAnalyzer()
    return _lab_analyzer_instance


if __name__ == "__main__":
    # Self-test
    print("\nLabRiskAnalyzer Self-Test")
    print("=" * 70)
    
    analyzer = get_lab_analyzer()
    
    # Test case: HELLP syndrome pattern
    test_labs = {
        'hemoglobin': 8.5,
        'platelets': 75000,
        'wbc': 12000,
        'proteinuria': '+2'
    }
    
    result = analyzer.analyze_labs(test_labs)
    
    print("\nTest Labs:")
    for key, value in test_labs.items():
        print(f"  {key}: {value}")
    
    print(f"\nRisk Score: {result['lab_risk_score']}/10")
    print(f"\nFlags ({len(result['lab_risk_flags'])}):")
    for flag in result['lab_risk_flags']:
        print(f"  - {flag}")
    
    if result['critical_flags']:
        print(f"\nCritical Flags:")
        for flag in result['critical_flags']:
            print(f"  ! {flag}")
    
    print("\n" + "=" * 70)
    print("Self-test complete")
