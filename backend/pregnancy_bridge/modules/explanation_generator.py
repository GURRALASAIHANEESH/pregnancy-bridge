"""
MedGemma Explanation Generator - Symptom-Aware Clinical Reasoning
Production-grade explanation module for maternal risk escalation
Author: PregnancyBridge Development Team
Version: 2.0.0

CRITICAL: MedGemma is used ONLY for explanation generation.
It NEVER modifies risk classification or clinical decisions.
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClinicalExplanationGenerator:
    """
    Generate clinically grounded explanations for risk escalation decisions.
    
    Uses MedGemma model to provide human-readable rationale for:
    - Why symptoms are concerning
    - Why escalation is necessary
    - What complications are being prevented
    
    Safety: Explanation-only - does not influence risk classification.
    """
    
    def __init__(self, medgemma_bridge):
        """
        Initialize explanation generator.
        
        Args:
            medgemma_bridge: Instance of MedGemmaBridge for model inference
        """
        self.medgemma = medgemma_bridge
        logger.info("ClinicalExplanationGenerator initialized")
    
    def format_visit_timeline(self, visits: List[Dict]) -> str:
        """
        Format visit history for MedGemma prompt.
        
        Args:
            visits: List of visit records with measurements and symptoms
            
        Returns:
            Formatted timeline string
        """
        timeline = []
        
        for i, visit in enumerate(visits):
            visit_num = i + 1
            date = visit.get('date', 'Unknown date')
            ga = visit.get('gestational_age', '?')
            
            # Laboratory values
            bp = visit.get('bp', {})
            bp_str = f"{bp.get('systolic', '?')}/{bp.get('diastolic', '?')}" if bp else "Not recorded"
            hb = visit.get('hemoglobin', 'Not recorded')
            proteinuria = visit.get('proteinuria', 'nil')
            weight = visit.get('weight', 'Not recorded')
            
            visit_info = f"Visit {visit_num} ({date}, {ga} weeks):\n"
            visit_info += f"  Blood Pressure: {bp_str} mmHg\n"
            visit_info += f"  Hemoglobin: {hb} g/dL\n"
            visit_info += f"  Proteinuria: {proteinuria}\n"
            
            if weight != 'Not recorded':
                visit_info += f"  Weight: {weight} kg\n"
            
            # Symptoms if present
            if 'symptoms' in visit and visit['symptoms']:
                symptoms = visit['symptoms']
                if symptoms.get('symptom_count', 0) > 0:
                    symptom_list = ', '.join(symptoms['present_symptoms'])
                    visit_info += f"  Symptoms: {symptom_list}\n"
                else:
                    visit_info += f"  Symptoms: None reported\n"
            
            timeline.append(visit_info)
        
        return "\n".join(timeline)
    
    def format_symptom_list(self, symptom_record: Optional[Dict]) -> str:
        """
        Format current symptoms for MedGemma prompt.
        
        Args:
            symptom_record: Symptom record from SymptomIntake
            
        Returns:
            Formatted symptom description by category
        """
        if not symptom_record or symptom_record.get('symptom_count', 0) == 0:
            return "No symptoms currently reported"
        
        symptom_text = []
        categories = symptom_record.get('categories', {})
        
        if categories.get('neurological'):
            symptom_text.append(f"Neurological: {', '.join(categories['neurological'])}")
        
        if categories.get('edema'):
            symptom_text.append(f"Edema: {', '.join(categories['edema'])}")
        
        if categories.get('respiratory'):
            symptom_text.append(f"Respiratory: {', '.join(categories['respiratory'])}")
        
        if categories.get('fetal_concern'):
            symptom_text.append(f"Fetal concern: {', '.join(categories['fetal_concern'])}")
        
        if categories.get('gi'):
            symptom_text.append(f"Gastrointestinal: {', '.join(categories['gi'])}")
        
        return "\n".join(symptom_text) if symptom_text else "Symptoms present but uncategorized"
    
    def generate_escalation_explanation(self, 
                                        visits: List[Dict],
                                        risk_assessment: Dict,
                                        current_symptoms: Optional[Dict] = None,
                                        max_tokens: int = 400) -> str:
        """
        Generate clinical explanation for risk escalation using MedGemma.
        
        Uses mandatory prompt template to ensure:
        - Clinical accuracy
        - Focus on complications prevented
        - No alteration of risk classification
        
        Args:
            visits: Visit timeline with symptoms
            risk_assessment: Output from SymptomRiskEngine.evaluate_visit()
            current_symptoms: Current symptom record
            max_tokens: Maximum response length
            
        Returns:
            Clinical explanation text from MedGemma
        """
        logger.info(f"Generating explanation for {risk_assessment['risk_category']} risk case")
        
        # Build the mandatory prompt template
        prompt = f"""A rule-based maternal risk system has escalated this pregnancy.

Risk category: {risk_assessment['risk_category']}
Referral required: {risk_assessment['referral_required']}
Escalation reason: {risk_assessment['trigger_reason']}

Patient visit timeline:
{self.format_visit_timeline(visits)}

Reported symptoms:
{self.format_symptom_list(current_symptoms)}

Explain:
1. Why these symptoms are clinically concerning
2. Why escalation is necessary now
3. What maternal or fetal complications this referral aims to prevent

Do not change risk classification.
Do not invent new data.
Respond in concise clinical language."""
        
        # Call MedGemma for explanation generation
        try:
            logger.debug("Calling MedGemma for explanation generation")
            explanation = self.medgemma.generate_explanation(
                prompt, 
                max_tokens=max_tokens,
                temperature=0.3  # Lower temperature for clinical consistency
            )
            
            logger.info("Explanation generated successfully")
            return explanation.strip()
            
        except Exception as e:
            error_msg = f"Explanation generation failed: {str(e)}"
            logger.error(error_msg)
            return f"[{error_msg}]\n\nFallback: {risk_assessment['trigger_reason']}"
    
    def generate_no_escalation_summary(self, visits: List[Dict]) -> str:
        """
        Generate summary when no escalation occurs (LOW/MODERATE risk without referral).
        
        Args:
            visits: Visit records
            
        Returns:
            Clinical summary string
        """
        if not visits:
            return "No visit data available for assessment."
        
        latest = visits[-1]
        date = latest.get('date', 'current visit')
        ga = latest.get('gestational_age', '?')
        
        # Extract latest values
        bp = latest.get('bp', {})
        bp_str = f"{bp.get('systolic', '?')}/{bp.get('diastolic', '?')}"
        hb = latest.get('hemoglobin', 'Not recorded')
        proteinuria = latest.get('proteinuria', 'nil')
        
        summary = f"Assessment as of {date} ({ga} weeks gestation):\n"
        summary += f"Blood Pressure: {bp_str} mmHg\n"
        summary += f"Hemoglobin: {hb} g/dL\n"
        summary += f"Proteinuria: {proteinuria}\n"
        
        # Add symptom note
        if 'symptoms' in latest and latest['symptoms']:
            symptom_count = latest['symptoms'].get('symptom_count', 0)
            if symptom_count > 0:
                symptoms = ', '.join(latest['symptoms']['present_symptoms'])
                summary += f"\nReported symptoms: {symptoms}\n"
            else:
                summary += f"\nNo concerning symptoms reported.\n"
        
        summary += "\nClinical parameters within acceptable limits for gestational age."
        summary += "\nRecommendation: Continue routine antenatal care with scheduled follow-up."
        
        return summary
    
    def generate_trend_explanation(self, visits: List[Dict], parameter: str) -> str:
        """
        Generate explanation for a specific parameter trend.
        
        Args:
            visits: Visit records
            parameter: Parameter name ('bp', 'hemoglobin', 'proteinuria')
            
        Returns:
            Trend explanation string
        """
        if len(visits) < 2:
            return f"Insufficient data for {parameter} trend analysis (need 2+ visits)"
        
        if parameter == 'bp':
            values = []
            for v in visits:
                bp = v.get('bp', {})
                systolic = bp.get('systolic')
                diastolic = bp.get('diastolic')
                if systolic and diastolic:
                    values.append(f"{systolic}/{diastolic}")
            
            if len(values) >= 2:
                trend = " → ".join(values)
                return f"Blood pressure trend: {trend} mmHg"
        
        elif parameter == 'hemoglobin':
            values = [v.get('hemoglobin') for v in visits if v.get('hemoglobin')]
            if len(values) >= 2:
                trend = " → ".join([str(v) for v in values])
                change = values[-1] - values[0]
                direction = "declined" if change < 0 else "increased"
                return f"Hemoglobin trend: {trend} g/dL ({direction} {abs(change):.1f})"
        
        elif parameter == 'proteinuria':
            values = [v.get('proteinuria', 'nil') for v in visits]
            trend = " → ".join(values)
            return f"Proteinuria trend: {trend}"
        
        return f"No trend data available for {parameter}"
    
    def generate_differential_diagnosis(self, 
                                        risk_assessment: Dict,
                                        symptom_record: Optional[Dict]) -> List[str]:
        """
        Generate list of differential diagnoses based on assessment.
        
        Args:
            risk_assessment: Risk assessment from engine
            symptom_record: Symptom data
            
        Returns:
            List of possible diagnoses to consider
        """
        differentials = []
        
        trigger = risk_assessment.get('trigger_reason', '').lower()
        
        # Preeclampsia indicators
        if 'hypertension' in trigger or 'bp' in trigger:
            if symptom_record and symptom_record.get('has_neurological'):
                differentials.append("Preeclampsia with severe features")
            elif 'proteinuria' in trigger:
                differentials.append("Preeclampsia")
            else:
                differentials.append("Gestational hypertension")
        
        # Anemia-related
        if 'anemia' in trigger:
            differentials.append("Iron deficiency anemia")
            if symptom_record and symptom_record.get('has_respiratory'):
                differentials.append("Severe anemia with cardiopulmonary compromise")
        
        # Proteinuria without hypertension
        if 'proteinuria' in trigger and 'hypertension' not in trigger:
            differentials.append("Renal disease in pregnancy")
            differentials.append("Urinary tract infection")
        
        # Fetal concerns
        if symptom_record and symptom_record.get('has_fetal_concern'):
            differentials.append("Reduced fetal movements - placental insufficiency")
            differentials.append("Oligohydramnios")
        
        return differentials if differentials else ["Multi-parameter maternal risk escalation"]
    
    def generate_referral_talking_points(self, 
                                         visits: List[Dict],
                                         risk_assessment: Dict,
                                         symptom_record: Optional[Dict]) -> str:
        """
        Generate structured talking points for referral communication.
        
        Args:
            visits: Visit timeline
            risk_assessment: Risk assessment
            symptom_record: Symptom data
            
        Returns:
            Structured talking points for healthcare handoff
        """
        talking_points = []
        
        # Patient context
        latest = visits[-1] if visits else {}
        ga = latest.get('gestational_age', '?')
        talking_points.append(f"Patient at {ga} weeks gestation")
        
        # Primary concern
        talking_points.append(f"Risk level: {risk_assessment['risk_category']}")
        talking_points.append(f"Reason: {risk_assessment['trigger_reason']}")
        
        # Temporal trends
        if len(visits) >= 2:
            talking_points.append(f"Temporal escalation detected across {len(visits)} visits")
        
        # Symptoms
        if symptom_record and symptom_record.get('symptom_count', 0) > 0:
            symptoms = ', '.join(symptom_record['present_symptoms'])
            talking_points.append(f"Active symptoms: {symptoms}")
        
        # Differential diagnoses
        differentials = self.generate_differential_diagnosis(risk_assessment, symptom_record)
        if differentials:
            talking_points.append(f"Consider: {', '.join(differentials)}")
        
        # Urgency
        if risk_assessment['referral_required']:
            talking_points.append("URGENT REFERRAL REQUIRED")
        
        return "\n• ".join([""] + talking_points)
    
    def export_explanation(self, 
                          explanation: str,
                          filepath: str,
                          metadata: Optional[Dict] = None) -> None:
        """
        Export explanation to file with optional metadata.
        
        Args:
            explanation: Generated explanation text
            filepath: Output file path
            metadata: Optional metadata dictionary
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if metadata:
                    f.write("=" * 70 + "\n")
                    f.write("PREGNANCYBRIDGE CLINICAL EXPLANATION\n")
                    f.write("=" * 70 + "\n\n")
                    
                    for key, value in metadata.items():
                        f.write(f"{key}: {value}\n")
                    
                    f.write("\n" + "=" * 70 + "\n\n")
                
                f.write(explanation)
                f.write("\n\n" + "=" * 70 + "\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("PregnancyBridge Maternal Early Warning System\n")
            
            logger.info(f"Explanation exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export explanation: {e}")
            raise


# Fallback explanation generator (when MedGemma unavailable)
class FallbackExplanationGenerator:
    """
    Rule-based explanation generator for offline/fallback scenarios.
    Used when MedGemma model is unavailable.
    """
    
    def __init__(self):
        logger.info("FallbackExplanationGenerator initialized (rule-based mode)")
    
    def generate_escalation_explanation(self,
                                        visits: List[Dict],
                                        risk_assessment: Dict,
                                        current_symptoms: Optional[Dict] = None) -> str:
        """Generate rule-based explanation without AI model"""
        
        explanation = []
        explanation.append("CLINICAL ESCALATION RATIONALE")
        explanation.append("=" * 50)
        explanation.append(f"\nRisk Category: {risk_assessment['risk_category']}")
        explanation.append(f"Referral Required: {'YES' if risk_assessment['referral_required'] else 'NO'}")
        explanation.append(f"\nEscalation Trigger: {risk_assessment['trigger_reason']}")
        
        # Add symptom context
        if current_symptoms and current_symptoms.get('symptom_count', 0) > 0:
            explanation.append(f"\nPresent Symptoms:")
            for category, items in current_symptoms.get('categories', {}).items():
                if items:
                    explanation.append(f"  • {category.capitalize()}: {', '.join(items)}")
        
        # Add temporal context
        if len(visits) >= 2:
            explanation.append(f"\nTemporal Analysis: {len(visits)} visits reviewed")
            explanation.append("Progressive escalation pattern detected across multiple visits.")
        
        # Add clinical concern
        explanation.append("\nClinical Concerns:")
        if 'preeclampsia' in risk_assessment['trigger_reason'].lower():
            explanation.append("  • Preeclampsia suspected - requires urgent evaluation")
            explanation.append("  • Risk of maternal seizure, stroke, organ damage")
            explanation.append("  • Risk of fetal growth restriction, placental abruption")
        elif 'anemia' in risk_assessment['trigger_reason'].lower():
            explanation.append("  • Severe anemia requires intervention")
            explanation.append("  • Risk of maternal cardiac decompensation")
            explanation.append("  • Risk of preterm delivery complications")
        
        explanation.append("\nRecommendation: Immediate referral to higher facility for comprehensive evaluation.")
        
        return "\n".join(explanation)


if __name__ == "__main__":
    # Self-test
    print("Running ClinicalExplanationGenerator self-test...\n")
    
    # Test with fallback generator
    fallback = FallbackExplanationGenerator()
    
    test_visits = [
        {'date': '2026-01-10', 'gestational_age': 32, 'bp': {'systolic': 138, 'diastolic': 88}, 
         'hemoglobin': 11.0, 'proteinuria': 'nil'},
        {'date': '2026-02-04', 'gestational_age': 36, 'bp': {'systolic': 145, 'diastolic': 95}, 
         'hemoglobin': 10.5, 'proteinuria': '+1'}
    ]
    
    test_assessment = {
        'risk_category': 'HIGH',
        'referral_required': True,
        'trigger_reason': 'Elevated BP: 145/95 mmHg WITH neurological symptoms (headache, blurred_vision) - PREECLAMPSIA SUSPECTED'
    }
    
    test_symptoms = {
        'symptom_count': 2,
        'present_symptoms': ['headache', 'blurred_vision'],
        'categories': {'neurological': ['headache', 'blurred_vision']}
    }
    
    explanation = fallback.generate_escalation_explanation(test_visits, test_assessment, test_symptoms)
    print(explanation)
    print("\n✓ ClinicalExplanationGenerator self-test complete")
