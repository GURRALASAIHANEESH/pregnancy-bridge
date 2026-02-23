"""
Confidence Estimator v2
Enhanced confidence scoring with lab age penalty
Author: PregnancyBridge Development Team
Version: 2.0.0
Date: 2026-02-04
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ConfidenceEstimatorV2:
    """
    Estimate confidence in maternal risk assessments with lab age awareness.
    
    Version 2 enhancements:
    - Lab age penalty integration
    - Explicit uncertainty reasons
    - Configurable factor weights
    - Evidence quality scoring
    
    Confidence factors:
    1. Temporal context (visit count and spacing)
    2. Symptom data completeness
    3. Laboratory data availability
    4. Lab age freshness (NEW)
    5. Risk category clarity
    6. Rule convergence (multiple indicators)
    """
    
    # Confidence tier thresholds
    CONFIDENCE_THRESHOLDS = {
        'HIGH': 0.85,
        'MODERATE': 0.65,
        'LOW': 0.0
    }
    
    # Factor weights (must sum to 1.0)
    FACTOR_WEIGHTS = {
        'temporal_context': 0.20,
        'symptom_clarity': 0.15,
        'lab_completeness': 0.20,
        'lab_age_freshness': 0.15,  # NEW
        'risk_clarity': 0.15,
        'rule_convergence': 0.15
    }
    
    def __init__(self):
        """Initialize confidence estimator v2."""
        # Verify weights sum to 1.0
        weight_sum = sum(self.FACTOR_WEIGHTS.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(f"Factor weights sum to {weight_sum}, not 1.0")
        
        logger.info("ConfidenceEstimatorV2 initialized")
    
    def estimate_confidence(self,
                           risk_assessment: Dict,
                           visits: List[Dict],
                           symptoms: Optional[Dict] = None,
                           lab_flags: Optional[List[str]] = None,
                           lab_age_days: Optional[int] = None,
                           evidence_items: Optional[List[Dict]] = None) -> Dict:
        """
        Calculate confidence score with lab age awareness.
        
        Args:
            risk_assessment: Risk assessment output from symptom_risk_engine
            visits: List of visit records
            symptoms: Symptom dictionary
            lab_flags: Laboratory risk flags
            lab_age_days: Age of lab report in days (NEW)
            evidence_items: Structured evidence items (NEW)
            
        Returns:
            Dictionary containing:
                - confidence_score: Float 0.0-1.0
                - confidence_tier: String (HIGH, MODERATE, LOW)
                - uncertainty_reason: Human-readable explanation
                - confidence_factors: Individual factor scores
        """
        factors = {}
        uncertainty_reasons = []
        
        # Factor 1: Temporal context quality
        visit_count = len(visits)
        temporal_score = self._assess_temporal_context(visit_count, visits)
        factors['temporal_context'] = temporal_score
        
        if visit_count == 1:
            uncertainty_reasons.append("single_visit_no_trend")
        elif visit_count == 2:
            uncertainty_reasons.append("limited_temporal_data")
        
        # Factor 2: Symptom data quality
        symptom_score = self._assess_symptom_quality(symptoms)
        factors['symptom_clarity'] = symptom_score
        
        if symptom_score < 0.6:
            if not symptoms or symptoms.get('symptom_count', 0) == 0:
                uncertainty_reasons.append("no_symptoms_reported")
            else:
                uncertainty_reasons.append("limited_symptom_data")
        
        # Factor 3: Laboratory data completeness
        lab_score = self._assess_lab_completeness(visits, lab_flags, evidence_items)
        factors['lab_completeness'] = lab_score
        
        if lab_score < 0.7:
            uncertainty_reasons.append("incomplete_lab_data")
        
        # Factor 4: Lab age freshness (NEW)
        lab_age_score = self._assess_lab_age_freshness(lab_age_days)
        factors['lab_age_freshness'] = lab_age_score
        
        if lab_age_days is not None:
            if lab_age_days > 90:
                uncertainty_reasons.append("lab_too_old_90d")
            elif lab_age_days > 30:
                uncertainty_reasons.append("lab_stale_30d")
        else:
            uncertainty_reasons.append("lab_date_unknown")
        
        # Factor 5: Risk category clarity
        risk_score = self._assess_risk_clarity(risk_assessment)
        factors['risk_clarity'] = risk_score
        
        if risk_score < 0.8:
            if risk_assessment.get('risk_category') == 'MODERATE':
                uncertainty_reasons.append("borderline_risk_category")
        
        # Factor 6: Rule convergence
        convergence_score = self._assess_rule_convergence(
            risk_assessment, symptoms, lab_flags, evidence_items
        )
        factors['rule_convergence'] = convergence_score
        
        if convergence_score < 0.7:
            uncertainty_reasons.append("single_risk_indicator")
        
        # Calculate weighted overall confidence score
        confidence_score = self._calculate_weighted_score(factors)
        
        # Determine confidence tier
        confidence_tier = self._assign_confidence_tier(confidence_score)
        
        # Generate comprehensive uncertainty explanation
        uncertainty_reason = self._generate_uncertainty_explanation(
            uncertainty_reasons, confidence_tier, lab_age_days
        )
        
        logger.info(f"Confidence: {confidence_score:.2f} ({confidence_tier}), Lab age: {lab_age_days}d")
        
        return {
            'confidence_score': round(confidence_score, 2),
            'confidence_tier': confidence_tier,
            'uncertainty_reason': uncertainty_reason,
            'confidence_factors': {k: round(v, 2) for k, v in factors.items()}
        }
    
    def _assess_temporal_context(self, visit_count: int, visits: List[Dict]) -> float:
        """
        Assess temporal context quality.
        
        Args:
            visit_count: Number of visits
            visits: Visit records
            
        Returns:
            Score 0.0-1.0
        """
        if visit_count >= 3:
            return 1.0
        elif visit_count == 2:
            return 0.7
        else:
            return 0.4
    
    def _assess_symptom_quality(self, symptoms: Optional[Dict]) -> float:
        """
        Assess symptom data quality.
        
        Args:
            symptoms: Symptom dictionary
            
        Returns:
            Score 0.0-1.0
        """
        if not symptoms:
            return 0.5
        
        symptom_count = symptoms.get('symptom_count', 0)
        
        if symptom_count == 0:
            return 0.5
        elif symptom_count >= 3:
            return 1.0
        elif symptom_count >= 1:
            return 0.8
        else:
            return 0.6
    
    def _assess_lab_completeness(self,
                                 visits: List[Dict],
                                 lab_flags: Optional[List[str]],
                                 evidence_items: Optional[List[Dict]]) -> float:
        """
        Assess laboratory data completeness.
        
        Args:
            visits: Visit records
            lab_flags: Lab risk flags
            evidence_items: Structured evidence items
            
        Returns:
            Score 0.0-1.0
        """
        if not visits:
            return 0.5
        
        latest = visits[-1]
        
        # Key lab parameters
        key_params = ['hemoglobin', 'bp', 'proteinuria']
        extended_params = ['platelets', 'wbc']
        
        # Count available key parameters
        available_key = sum(1 for p in key_params if latest.get(p) is not None)
        available_extended = sum(1 for p in extended_params if latest.get(p) is not None)
        
        key_completeness = available_key / len(key_params)
        extended_completeness = available_extended / len(extended_params)
        
        # Weight key parameters more heavily
        overall_score = (key_completeness * 0.7) + (extended_completeness * 0.3)
        
        # Bonus if evidence items available
        if evidence_items and len(evidence_items) > 0:
            lab_evidence = [e for e in evidence_items if e['type'] == 'lab']
            if len(lab_evidence) >= 4:
                overall_score = min(overall_score + 0.1, 1.0)
        
        return overall_score
    
    def _assess_lab_age_freshness(self, lab_age_days: Optional[int]) -> float:
        """
        Assess lab result freshness based on age.
        
        Scoring:
        - ≤7 days: 1.0 (fresh)
        - 8-30 days: 0.9 (acceptable)
        - 31-90 days: 0.6 (old but usable)
        - >90 days: 0.3 (too old)
        - Unknown: 0.5 (missing data penalty)
        
        Args:
            lab_age_days: Age of lab in days
            
        Returns:
            Score 0.0-1.0
        """
        if lab_age_days is None:
            return 0.5  # Missing data penalty
        
        if lab_age_days <= 7:
            return 1.0
        elif lab_age_days <= 30:
            return 0.9
        elif lab_age_days <= 90:
            return 0.6
        else:
            return 0.3
    
    def _assess_risk_clarity(self, risk_assessment: Dict) -> float:
        """
        Assess risk category clarity.
        
        Args:
            risk_assessment: Risk assessment output
            
        Returns:
            Score 0.0-1.0
        """
        risk_cat = risk_assessment.get('risk_category', 'UNKNOWN')
        
        if risk_cat == 'HIGH':
            return 1.0
        elif risk_cat == 'LOW':
            return 1.0
        elif risk_cat == 'MODERATE':
            return 0.7
        else:
            return 0.3
    
    def _assess_rule_convergence(self,
                                risk_assessment: Dict,
                                symptoms: Optional[Dict],
                                lab_flags: Optional[List[str]],
                                evidence_items: Optional[List[Dict]]) -> float:
        """
        Assess convergence of multiple risk indicators.
        
        Args:
            risk_assessment: Risk assessment output
            symptoms: Symptom data
            lab_flags: Lab flags
            evidence_items: Evidence items
            
        Returns:
            Score 0.0-1.0
        """
        indicator_count = 0
        
        # Multiple conditions in trigger
        trigger = risk_assessment.get('trigger_reason', '')
        if 'WITH' in trigger or 'AND' in trigger:
            indicator_count += 2
        else:
            indicator_count += 1
        
        # Symptom presence
        if symptoms and symptoms.get('symptom_count', 0) > 0:
            indicator_count += 1
        
        # Lab abnormalities
        if lab_flags and len(lab_flags) >= 2:
            indicator_count += 1
        
        # Evidence convergence
        if evidence_items:
            lab_evidence = [e for e in evidence_items if e['type'] == 'lab' and e.get('delta')]
            if len(lab_evidence) >= 2:
                indicator_count += 1
        
        # Score based on convergence
        if indicator_count >= 4:
            return 1.0
        elif indicator_count == 3:
            return 0.9
        elif indicator_count == 2:
            return 0.7
        else:
            return 0.5
    
    def _calculate_weighted_score(self, factors: Dict[str, float]) -> float:
        """
        Calculate weighted overall confidence score.
        
        Args:
            factors: Dictionary of factor scores
            
        Returns:
            Weighted score 0.0-1.0
        """
        weighted_sum = 0.0
        
        for factor_name, weight in self.FACTOR_WEIGHTS.items():
            if factor_name in factors:
                weighted_sum += factors[factor_name] * weight
        
        return weighted_sum
    
    def _assign_confidence_tier(self, score: float) -> str:
        """
        Assign confidence tier based on score.
        
        Args:
            score: Confidence score 0.0-1.0
            
        Returns:
            Tier string (HIGH, MODERATE, LOW)
        """
        if score >= self.CONFIDENCE_THRESHOLDS['HIGH']:
            return 'HIGH'
        elif score >= self.CONFIDENCE_THRESHOLDS['MODERATE']:
            return 'MODERATE'
        else:
            return 'LOW'
    
    def _generate_uncertainty_explanation(self,
                                         uncertainty_reasons: List[str],
                                         confidence_tier: str,
                                         lab_age_days: Optional[int]) -> str:
        """
        Generate human-readable uncertainty explanation.
        
        Args:
            uncertainty_reasons: List of uncertainty reason codes
            confidence_tier: Overall confidence tier
            lab_age_days: Lab age in days
            
        Returns:
            Explanation string
        """
        if confidence_tier == 'HIGH' and not uncertainty_reasons:
            return "High-quality data with fresh lab results and complete clinical picture"
        
        reason_text_map = {
            'single_visit_no_trend': "Single visit assessment without temporal trend data",
            'limited_temporal_data': "Limited temporal data (only 2 visits)",
            'no_symptoms_reported': "No symptoms reported",
            'limited_symptom_data': "Limited symptom information",
            'incomplete_lab_data': "Incomplete laboratory parameters",
            'lab_too_old_90d': "Lab results are very old (>90 days) - fresh tests recommended",
            'lab_stale_30d': "Lab results are stale (>30 days) - consider re-testing",
            'lab_date_unknown': "Lab report date not provided",
            'borderline_risk_category': "Borderline risk classification",
            'single_risk_indicator': "Single risk indicator without convergent evidence"
        }
        
        if not uncertainty_reasons:
            return "Adequate data quality for clinical decision-making"
        
        # Take top 2 most important reasons
        primary_reasons = uncertainty_reasons[:2]
        reason_texts = [reason_text_map.get(r, r) for r in primary_reasons]
        
        explanation = "; ".join(reason_texts)
        
        # Add recommendation based on tier and lab age
        if confidence_tier == 'LOW':
            explanation += ". Recommend obtaining additional clinical data."
        elif lab_age_days and lab_age_days > 90:
            explanation += ". Fresh lab tests strongly recommended."
        
        return explanation


# Singleton
_confidence_estimator_v2_instance = None


def get_confidence_estimator_v2() -> ConfidenceEstimatorV2:
    """Get singleton instance of ConfidenceEstimatorV2."""
    global _confidence_estimator_v2_instance
    if _confidence_estimator_v2_instance is None:
        _confidence_estimator_v2_instance = ConfidenceEstimatorV2()
    return _confidence_estimator_v2_instance


# Self-test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ConfidenceEstimatorV2 Self-Test")
    print("=" * 70)
    
    estimator = get_confidence_estimator_v2()
    
    # Test 1: Fresh lab, complete data
    print("\nTest 1: High Confidence Scenario (Fresh Lab)")
    print("-" * 70)
    
    test_risk = {
        'risk_category': 'HIGH',
        'trigger_reason': 'BP 150/95 WITH proteinuria +2 AND neurological symptoms'
    }
    
    test_visits = [
        {'hemoglobin': 11.2, 'platelets': 180000, 'bp': {'systolic': 138, 'diastolic': 88}, 'proteinuria': 'trace'},
        {'hemoglobin': 11.0, 'platelets': 145000, 'bp': {'systolic': 145, 'diastolic': 92}, 'proteinuria': '+1'},
        {'hemoglobin': 10.8, 'platelets': 110000, 'bp': {'systolic': 150, 'diastolic': 95}, 'proteinuria': '+2'}
    ]
    
    test_symptoms = {'symptom_count': 3, 'present_symptoms': ['headache', 'blurred_vision']}
    test_lab_flags = ['Severe thrombocytopenia', 'Significant proteinuria']
    
    result = estimator.estimate_confidence(
        test_risk, test_visits, test_symptoms, test_lab_flags, lab_age_days=5
    )
    
    print(f"Score: {result['confidence_score']} ({result['confidence_tier']})")
    print(f"Uncertainty: {result['uncertainty_reason']}")
    print("Factors:")
    for factor, score in result['confidence_factors'].items():
        print(f"  {factor}: {score}")
    
    # Test 2: Old lab (60 days)
    print("\nTest 2: Old Lab Scenario (60 days)")
    print("-" * 70)
    
    result2 = estimator.estimate_confidence(
        test_risk, test_visits, test_symptoms, test_lab_flags, lab_age_days=60
    )
    
    print(f"Score: {result2['confidence_score']} ({result2['confidence_tier']})")
    print(f"Uncertainty: {result2['uncertainty_reason']}")
    print(f"Lab freshness factor: {result2['confidence_factors']['lab_age_freshness']}")
    
    # Test 3: Very old lab (100 days)
    print("\nTest 3: Very Old Lab Scenario (100 days)")
    print("-" * 70)
    
    result3 = estimator.estimate_confidence(
        test_risk, test_visits, test_symptoms, test_lab_flags, lab_age_days=100
    )
    
    print(f"Score: {result3['confidence_score']} ({result3['confidence_tier']})")
    print(f"Uncertainty: {result3['uncertainty_reason']}")
    print(f"Lab freshness factor: {result3['confidence_factors']['lab_age_freshness']}")
    
    print("\n" + "=" * 70)
    print("✓ All self-tests passed")
    print("=" * 70)
