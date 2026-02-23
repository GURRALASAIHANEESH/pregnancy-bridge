"""
Dual Explanation Generator
Generates clinical (doctor-level) and simplified (ASHA worker) explanations
Author: PregnancyBridge Development Team
Version: 1.0.0
Date: 2026-02-04
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DualExplanationGenerator:
    """
    Generate explanations tailored for two distinct audiences:
    1. Clinical explanation for doctors with medical terminology
    2. Simplified explanation for ASHA workers in plain language
    
    Ensures both audiences understand the risk and required actions.
    """
    
    def __init__(self, medgemma_bridge=None):
        """
        Initialize dual explanation generator.
        
        Args:
            medgemma_bridge: Optional MedGemma interface for AI-generated clinical explanations
        """
        self.medgemma = medgemma_bridge
        logger.info("DualExplanationGenerator initialized")
    
    def generate_explanations(self,
                            risk_assessment: Dict,
                            visits: List[Dict],
                            symptoms: Optional[Dict] = None,
                            lab_flags: Optional[List[str]] = None) -> Dict:
        """
        Generate both clinical and ASHA explanations for a case.
        
        Args:
            risk_assessment: Risk assessment output from symptom_risk_engine
            visits: List of visit records
            symptoms: Symptom dictionary from symptom_intake
            lab_flags: Laboratory risk flags from lab_risk_analyzer
            
        Returns:
            Dictionary containing:
                - clinical_explanation: Technical explanation for doctors
                - asha_explanation: Simplified explanation for ASHA workers
        """
        # Generate clinical explanation
        if self.medgemma and risk_assessment.get('risk_category') in ['HIGH', 'MODERATE']:
            try:
                clinical_exp = self._generate_clinical_medgemma(
                    risk_assessment, visits, symptoms, lab_flags
                )
            except Exception as e:
                logger.warning(f"MedGemma generation failed: {e}")
                clinical_exp = self._generate_clinical_fallback(
                    risk_assessment, visits, symptoms, lab_flags
                )
        else:
            clinical_exp = self._generate_clinical_fallback(
                risk_assessment, visits, symptoms, lab_flags
            )
        
        # Generate ASHA explanation (always rule-based for consistency)
        asha_exp = self._generate_asha_explanation(
            risk_assessment, visits, symptoms, lab_flags
        )
        
        return {
            'clinical_explanation': clinical_exp,
            'asha_explanation': asha_exp
        }
    
    def _generate_clinical_medgemma(self, 
                                   risk_assessment: Dict,
                                   visits: List[Dict],
                                   symptoms: Optional[Dict],
                                   lab_flags: Optional[List[str]]) -> str:
        """
        Generate clinical explanation using MedGemma AI model.
        
        Creates a structured prompt with clinical data and asks for
        diagnostic reasoning, differential diagnoses, and management.
        """
        prompt_parts = ["Clinical case requiring expert analysis:\n"]
        
        # Risk summary
        prompt_parts.append(f"Risk Level: {risk_assessment['risk_category']}")
        prompt_parts.append(f"Referral Status: {'URGENT' if risk_assessment['referral_required'] else 'Routine'}")
        prompt_parts.append(f"Primary Concern: {risk_assessment['trigger_reason']}\n")
        
        # Current clinical presentation
        if visits:
            latest = visits[-1]
            ga = latest.get('gestational_age', 'Unknown')
            prompt_parts.append(f"Gestational Age: {ga} weeks")
            
            if latest.get('bp'):
                bp = latest['bp']
                sys = bp.get('systolic', '?')
                dia = bp.get('diastolic', '?')
                prompt_parts.append(f"Blood Pressure: {sys}/{dia} mmHg")
            
            if latest.get('hemoglobin') is not None:
                prompt_parts.append(f"Hemoglobin: {latest['hemoglobin']} g/dL")
            
            if latest.get('platelets') is not None:
                prompt_parts.append(f"Platelet Count: {latest['platelets']:,} per uL")
            
            if latest.get('proteinuria'):
                prompt_parts.append(f"Proteinuria: {latest['proteinuria']}")
            
            if latest.get('wbc') is not None:
                prompt_parts.append(f"WBC: {latest['wbc']:,} per uL")
        
        # Temporal trends
        if len(visits) >= 2:
            prompt_parts.append(f"\nTemporal Pattern: {len(visits)} visits analyzed")
        
        # Symptoms
        if symptoms and symptoms.get('present_symptoms'):
            symptom_list = ', '.join(symptoms['present_symptoms'])
            prompt_parts.append(f"Active Symptoms: {symptom_list}")
        
        # Laboratory abnormalities
        if lab_flags:
            prompt_parts.append("\nLaboratory Abnormalities:")
            for flag in lab_flags[:5]:
                prompt_parts.append(f"  - {flag}")
        
        # Request structured output
        prompt_parts.append("\nProvide:")
        prompt_parts.append("1. Diagnostic reasoning for risk classification")
        prompt_parts.append("2. Differential diagnoses to consider")
        prompt_parts.append("3. Rationale for referral decision")
        prompt_parts.append("4. Maternal and fetal complications being prevented")
        
        prompt = "\n".join(prompt_parts)
        
        # Call MedGemma
        explanation = self.medgemma.generate_explanation(
            prompt,
            max_tokens=500,
            temperature=0.3
        )
        
        return explanation.strip()
    
    def _generate_clinical_fallback(self,
                                   risk_assessment: Dict,
                                   visits: List[Dict],
                                   symptoms: Optional[Dict],
                                   lab_flags: Optional[List[str]]) -> str:
        """
        Generate rule-based clinical explanation when MedGemma unavailable.
        
        Provides structured clinical reasoning based on deterministic rules.
        """
        sections = []
        
        # Header
        sections.append("CLINICAL RISK ASSESSMENT")
        sections.append("=" * 60)
        
        # Risk classification
        sections.append(f"\nRisk Category: {risk_assessment['risk_category']}")
        sections.append(f"Referral Required: {'YES - URGENT' if risk_assessment['referral_required'] else 'NO'}")
        
        # Primary trigger
        sections.append(f"\nClinical Reasoning:")
        sections.append(f"{risk_assessment['trigger_reason']}")
        
        # Laboratory findings
        if lab_flags:
            sections.append("\nLaboratory Findings:")
            for flag in lab_flags:
                sections.append(f"  - {flag}")
        
        # Temporal analysis
        if len(visits) >= 2:
            sections.append(f"\nTemporal Analysis: {len(visits)} visits reviewed")
            sections.append("Progressive escalation pattern detected requiring increased vigilance")
        
        # Symptom presentation
        if symptoms and symptoms.get('present_symptoms'):
            sections.append("\nClinical Symptoms:")
            symptom_categories = []
            
            if symptoms.get('has_neurological'):
                neuro = [s for s in symptoms['present_symptoms'] 
                        if s in ['headache', 'blurred_vision', 'visual_disturbance', 'dizziness']]
                if neuro:
                    symptom_categories.append(f"Neurological: {', '.join(neuro)}")
            
            if symptoms.get('has_respiratory'):
                resp = [s for s in symptoms['present_symptoms'] 
                       if s in ['breathlessness', 'chest_pain']]
                if resp:
                    symptom_categories.append(f"Respiratory: {', '.join(resp)}")
            
            if symptoms.get('has_gi'):
                gi = [s for s in symptoms['present_symptoms'] 
                     if s in ['nausea_vomiting', 'abdominal_pain', 'epigastric_pain']]
                if gi:
                    symptom_categories.append(f"Gastrointestinal: {', '.join(gi)}")
            
            for category in symptom_categories:
                sections.append(f"  - {category}")
        
        # Differential diagnoses
        sections.append("\nDifferential Diagnoses:")
        differentials = self._generate_differentials(risk_assessment, symptoms, lab_flags)
        for diff in differentials:
            sections.append(f"  - {diff}")
        
        # Management recommendation
        sections.append("\nManagement Recommendation:")
        if risk_assessment['referral_required']:
            sections.append("URGENT referral to higher-level facility required")
            sections.append("Referral should occur within 24 hours")
            sections.append("Patient should be counseled on warning signs during transport")
        else:
            sections.append("Continue routine antenatal care")
            sections.append("Schedule follow-up as per standard protocol")
            sections.append("Provide patient education on warning signs")
        
        return "\n".join(sections)
    
    def _generate_differentials(self,
                               risk_assessment: Dict,
                               symptoms: Optional[Dict],
                               lab_flags: Optional[List[str]]) -> List[str]:
        """
        Generate differential diagnoses based on clinical presentation.
        
        Returns list of possible diagnoses to consider.
        """
        differentials = []
        trigger = risk_assessment.get('trigger_reason', '').lower()
        
        # Preeclampsia spectrum
        if 'preeclampsia' in trigger or ('hypertension' in trigger and 'proteinuria' in trigger):
            if symptoms and symptoms.get('has_neurological'):
                differentials.append("Preeclampsia with severe features")
            else:
                differentials.append("Preeclampsia without severe features")
            differentials.append("Gestational hypertension")
            differentials.append("Chronic hypertension with superimposed preeclampsia")
        
        elif 'hypertension' in trigger:
            differentials.append("Gestational hypertension")
            differentials.append("Chronic hypertension")
            differentials.append("White coat hypertension (less likely given temporal pattern)")
        
        # HELLP syndrome
        if lab_flags and any('hellp' in flag.lower() for flag in lab_flags):
            differentials.append("HELLP syndrome (Hemolysis, Elevated Liver enzymes, Low Platelets)")
            differentials.append("Severe preeclampsia")
            differentials.append("Acute fatty liver of pregnancy")
        
        # Anemia spectrum
        if 'anemia' in trigger:
            differentials.append("Iron deficiency anemia")
            differentials.append("Folate deficiency anemia")
            differentials.append("Physiologic anemia of pregnancy")
            
            if symptoms and symptoms.get('has_respiratory'):
                differentials.append("Anemia with cardiopulmonary decompensation")
        
        # Thrombocytopenia
        if lab_flags and any('platelet' in flag.lower() or 'thrombocytopenia' in flag.lower() for flag in lab_flags):
            differentials.append("Gestational thrombocytopenia")
            differentials.append("Immune thrombocytopenic purpura (ITP)")
            differentials.append("Preeclampsia-associated thrombocytopenia")
        
        # Infection
        if 'infection' in trigger or (lab_flags and any('wbc' in flag.lower() or 'leukocytosis' in flag.lower() for flag in lab_flags)):
            differentials.append("Chorioamnionitis")
            differentials.append("Urinary tract infection")
            differentials.append("Respiratory infection")
        
        # Default if no specific pattern
        if not differentials:
            differentials.append("Multi-parameter maternal risk escalation")
            differentials.append("Atypical presentation requiring senior clinical assessment")
        
        return differentials
    
    def _generate_asha_explanation(self,
                                  risk_assessment: Dict,
                                  visits: List[Dict],
                                  symptoms: Optional[Dict],
                                  lab_flags: Optional[List[str]]) -> str:
        """
        Generate simplified explanation for ASHA workers in plain language.
        
        Uses controlled vocabulary, avoids medical jargon, provides clear actions.
        """
        sections = []
        
        risk = risk_assessment['risk_category']
        trigger = risk_assessment.get('trigger_reason', '').lower()
        
        # Urgency header
        if risk == 'HIGH':
            sections.append("URGENT ACTION NEEDED")
            sections.append("")
            urgency_word = "TODAY"
        elif risk == 'MODERATE':
            urgency_word = "this week"
        else:
            urgency_word = "at next scheduled visit"
        
        # Explain what is wrong in simple terms
        sections.append("What is the problem:")
        
        if 'preeclampsia' in trigger or ('blood pressure' in trigger and 'protein' in trigger):
            sections.append("Mother has high blood pressure and protein in urine.")
            sections.append("This is a dangerous condition that can cause fits (seizures).")
            sections.append("It can harm both mother and baby if not treated quickly.")
        
        elif 'hypertension' in trigger or 'blood pressure' in trigger:
            sections.append("Mother's blood pressure is too high.")
            if symptoms and symptoms.get('has_neurological'):
                sections.append("She also has headache or vision problems.")
                sections.append("This combination is dangerous and needs urgent attention.")
            else:
                sections.append("High blood pressure can harm mother and baby.")
        
        elif 'anemia' in trigger or 'hemoglobin' in trigger:
            sections.append("Mother's blood is very weak (low hemoglobin).")
            sections.append("Weak blood cannot carry enough oxygen to mother and baby.")
            
            if symptoms and symptoms.get('has_respiratory'):
                sections.append("Mother is feeling breathless because of this.")
                sections.append("This is a serious warning sign.")
        
        elif 'platelet' in trigger or (lab_flags and any('platelet' in f.lower() for f in lab_flags)):
            sections.append("Mother's blood clotting cells (platelets) are very low.")
            sections.append("This can cause dangerous bleeding during delivery.")
            sections.append("Mother needs urgent medical care.")
        
        elif 'hellp' in trigger or (lab_flags and any('hellp' in f.lower() for f in lab_flags)):
            sections.append("Mother has a serious condition affecting blood and liver.")
            sections.append("This is a medical emergency that can happen suddenly.")
            sections.append("Both mother and baby are at high risk.")
        
        elif 'infection' in trigger or (lab_flags and any('infection' in f.lower() or 'wbc' in f.lower() for f in lab_flags)):
            sections.append("Mother may have a serious infection.")
            sections.append("Infection during pregnancy can spread quickly.")
            sections.append("It can harm both mother and baby if not treated.")
        
        else:
            sections.append("Mother has warning signs that need doctor's attention.")
            sections.append("Multiple health signs are showing problems.")
        
        # Clear action steps
        sections.append("")
        sections.append("What to do:")
        sections.append(f"Take mother to hospital {urgency_word.upper()}.")
        
        if risk == 'HIGH':
            sections.append("Do NOT delay - this is urgent for mother and baby safety.")
            sections.append("If possible, arrange ambulance or vehicle immediately.")
            sections.append("Do not wait for symptoms to become worse.")
        else:
            sections.append("Book appointment with doctor for proper check-up.")
            sections.append("Explain all symptoms to the doctor.")
        
        # Warning signs to monitor
        if risk in ['HIGH', 'MODERATE']:
            sections.append("")
            sections.append("Warning signs to watch for:")
            sections.append("- Severe headache that does not go away")
            sections.append("- Vision problems or seeing spots")
            sections.append("- Fits or convulsions")
            sections.append("- Heavy bleeding from vagina")
            sections.append("- Severe stomach pain")
            sections.append("- Baby not moving as usual")
            sections.append("")
            sections.append("If ANY of these happen, go to hospital IMMEDIATELY.")
        
        # Reassurance and context
        if risk != 'HIGH':
            sections.append("")
            sections.append("Remember: Early treatment prevents serious problems.")
            sections.append("Taking mother to doctor now will keep both mother and baby safe.")
        
        return "\n".join(sections)
    
    def format_for_referral_letter(self,
                                   risk_assessment: Dict,
                                   visits: List[Dict],
                                   symptoms: Optional[Dict],
                                   lab_flags: Optional[List[str]]) -> str:
        """
        Format clinical information for referral letter to receiving facility.
        
        Returns structured referral summary suitable for handoff communication.
        """
        sections = []
        
        sections.append("MATERNAL RISK REFERRAL")
        sections.append("=" * 60)
        sections.append("")
        
        # Patient demographics
        if visits:
            latest = visits[-1]
            sections.append("Patient Information:")
            if latest.get('patient_name'):
                sections.append(f"  Name: {latest['patient_name']}")
            if latest.get('age'):
                sections.append(f"  Age: {latest['age']} years")
            if latest.get('gestational_age'):
                sections.append(f"  Gestational Age: {latest['gestational_age']} weeks")
            if latest.get('gravida'):
                sections.append(f"  Gravida: G{latest['gravida']}P{latest.get('para', '?')}")
            sections.append("")
        
        # Reason for referral
        sections.append("Reason for Referral:")
        sections.append(f"  {risk_assessment['trigger_reason']}")
        sections.append(f"  Risk Level: {risk_assessment['risk_category']}")
        sections.append("")
        
        # Clinical findings
        sections.append("Clinical Findings:")
        if visits:
            latest = visits[-1]
            if latest.get('bp'):
                bp = latest['bp']
                sections.append(f"  Blood Pressure: {bp.get('systolic')}/{bp.get('diastolic')} mmHg")
            if latest.get('hemoglobin') is not None:
                sections.append(f"  Hemoglobin: {latest['hemoglobin']} g/dL")
            if latest.get('platelets') is not None:
                sections.append(f"  Platelets: {latest['platelets']:,} per uL")
            if latest.get('proteinuria'):
                sections.append(f"  Proteinuria: {latest['proteinuria']}")
        sections.append("")
        
        # Symptoms
        if symptoms and symptoms.get('present_symptoms'):
            sections.append("Active Symptoms:")
            for symptom in symptoms['present_symptoms']:
                sections.append(f"  - {symptom.replace('_', ' ').title()}")
            sections.append("")
        
        # Laboratory abnormalities
        if lab_flags:
            sections.append("Laboratory Abnormalities:")
            for flag in lab_flags[:5]:
                sections.append(f"  - {flag}")
            sections.append("")
        
        # Temporal pattern
        if len(visits) >= 2:
            sections.append(f"Temporal Pattern: Progressive escalation over {len(visits)} visits")
            sections.append("")
        
        # Request for receiving facility
        sections.append("Requested Assessment:")
        sections.append("  - Complete clinical evaluation")
        sections.append("  - Laboratory workup as indicated")
        sections.append("  - Obstetric consultation")
        sections.append("  - Management plan and disposition")
        
        return "\n".join(sections)


# Singleton instance
_dual_explainer_instance = None


def get_dual_explainer(medgemma_bridge=None) -> DualExplanationGenerator:
    """
    Get singleton instance of DualExplanationGenerator.
    
    Args:
        medgemma_bridge: Optional MedGemma interface for AI explanations
        
    Returns:
        DualExplanationGenerator instance
    """
    global _dual_explainer_instance
    if _dual_explainer_instance is None:
        _dual_explainer_instance = DualExplanationGenerator(medgemma_bridge)
    return _dual_explainer_instance


if __name__ == "__main__":
    # Self-test
    print("\nDualExplanationGenerator Self-Test")
    print("=" * 70)
    
    explainer = get_dual_explainer()
    
    # Test case
    test_risk = {
        'risk_category': 'HIGH',
        'referral_required': True,
        'trigger_reason': 'Elevated BP 150/95 mmHg WITH neurological symptoms (headache, blurred_vision) - PREECLAMPSIA SUSPECTED'
    }
    
    test_visits = [
        {
            'date': '2026-01-10',
            'gestational_age': 34,
            'bp': {'systolic': 138, 'diastolic': 88},
            'hemoglobin': 11.2,
            'proteinuria': 'trace'
        },
        {
            'date': '2026-02-04',
            'gestational_age': 36,
            'bp': {'systolic': 150, 'diastolic': 95},
            'hemoglobin': 11.0,
            'proteinuria': '+1'
        }
    ]
    
    test_symptoms = {
        'present_symptoms': ['headache', 'blurred_vision'],
        'has_neurological': True,
        'symptom_count': 2
    }
    
    test_lab_flags = [
        'Mild proteinuria (+1) - monitor for preeclampsia',
        'Borderline blood pressure elevation'
    ]
    
    result = explainer.generate_explanations(
        test_risk, test_visits, test_symptoms, test_lab_flags
    )
    
    print("\nCLINICAL EXPLANATION:")
    print("-" * 70)
    print(result['clinical_explanation'][:500] + "...")
    
    print("\n\nASHA EXPLANATION:")
    print("-" * 70)
    print(result['asha_explanation'])
    
    print("\n" + "=" * 70)
    print("Self-test complete")
