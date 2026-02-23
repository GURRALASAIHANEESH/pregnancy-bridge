"""
Missing Data Recommender
Generates field-safe next-action recommendations when data is incomplete
"""
import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def recommend_next_actions(
    evidence_summary: List[str],
    available_tests: List[str],
    context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate prioritized next-action recommendations using MedGemma.
    
    Args:
        evidence_summary: List of evidence strings from rule engine
        available_tests: List of available test codes (e.g., ['CBC', 'UrineDip', 'LFT', 'BP_machine'])
        context: Context dict with keys:
            - lab_age_days: int (age of lab data)
            - distance_to_facility_km: int (distance to facility)
    
    Returns:
        List of recommendation dicts with keys:
            - action: str (action code like 'refer', 'retest', 'monitor')
            - priority: str ('urgent', 'near-term', or 'follow-up')
            - why: str (short clinical reason)
            - practical_note: str (one-line field advice)
    """
    from pregnancy_bridge.modules.medgemma_prompt_template import MISSING_DATA_PROMPT
    
    # Format prompt
    evidence_str = json.dumps(evidence_summary)
    available_tests_str = json.dumps(available_tests)
    context_str = json.dumps(context)
    
    prompt = MISSING_DATA_PROMPT.format(
        evidence_summary=evidence_str,
        available_tests=available_tests_str,
        context=context_str
    )
    
    try:
        # Try to load MedGemma
        from pregnancy_bridge.modules.medgemma_extractor import get_clinical_reasoner
        
        logger.info("Loading MedGemma for missing-data recommendations...")
        reasoner = get_clinical_reasoner()
        
        # Build clinical data for MedGemma
        clinical_data = {
            'evidence_summary': evidence_summary,
            'available_tests': available_tests,
            'context': context,
            'prompt_override': prompt
        }
        
        # Generate recommendations
        logger.info("Generating recommendations with MedGemma...")
        result = reasoner.reason_about_case(clinical_data)
        response_text = result.get('reasoning', '')
        
        # Try to parse JSON from response
        recommendations = _parse_recommendations_json(response_text)
        
        if recommendations and _validate_recommendations(recommendations):
            logger.info(f"✓ MedGemma generated {len(recommendations)} valid recommendations")
            return recommendations[:3]  # Max 3
        else:
            logger.warning("✗ MedGemma recommendations invalid or unparseable - using fallback")
            return _get_fallback_recommendations()
    
    except Exception as e:
        logger.error(f"MedGemma failed to load or generate: {e}")
        logger.info("Using fallback recommendations")
        return _get_fallback_recommendations()


def recommend_next_actions_with_deterministic(
    evidence_summary: List[str],
    available_tests: List[str],
    context: Dict[str, Any],
    risk_category: str,
    latest_values: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate recommendations with deterministic fallback.
    
    This is the production-ready version that uses deterministic rules
    for speed and reliability. AI recommendations are disabled for now
    to avoid resource contention with context interpreter.
    
    Args:
        evidence_summary: List of evidence strings from rule engine
        available_tests: List of available test codes
        context: Context dict (lab_age_days, distance_to_facility_km)
        risk_category: 'LOW', 'MODERATE', or 'HIGH'
        latest_values: Dict with latest clinical values for deterministic rules
    
    Returns:
        List of recommendation dicts with 'source' field indicating origin
    """
    from pregnancy_bridge.modules.deterministic_recommender import get_deterministic_recommendations
    
    # Skip AI for now (resource contention issue)
    # TODO: Enable AI recommendations after optimizing model caching
    USE_AI_RECOMMENDATIONS = False
    
    if USE_AI_RECOMMENDATIONS:
        # Try AI first
        try:
            ai_recommendations = recommend_next_actions(
                evidence_summary=evidence_summary,
                available_tests=available_tests,
                context=context
            )
            
            # Check if AI returned valid recommendations (not just fallback)
            if ai_recommendations and len(ai_recommendations) > 0:
                # Check if it's not just the fallback
                if ai_recommendations[0].get('source') != 'fallback_safety_first':
                    logger.info(f"Using AI recommendations ({len(ai_recommendations)} items)")
                    return ai_recommendations
        
        except Exception as e:
            logger.warning(f"AI recommendations failed: {e}")
    
    # Use deterministic rules (fast, reliable, safe)
    logger.info("Using deterministic rule-based recommendations")
    deterministic_recs = get_deterministic_recommendations(
        risk_category=risk_category,
        evidence_summary=evidence_summary,
        lab_age_days=context.get('lab_age_days', 0),
        latest_values=latest_values
    )
    
    return deterministic_recs


def _parse_recommendations_json(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Try to parse JSON recommendations from model output.
    
    Args:
        text: Raw model output text
    
    Returns:
        List of recommendation dicts, or None if parsing fails
    """
    try:
        # Try direct JSON parse
        recommendations = json.loads(text)
        if isinstance(recommendations, list):
            return recommendations
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON array in text
    try:
        start_idx = text.find('[')
        end_idx = text.rfind(']')
        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            recommendations = json.loads(json_str)
            if isinstance(recommendations, list):
                return recommendations
    except:
        pass
    
    return None


def _validate_recommendations(recommendations: List[Dict[str, Any]]) -> bool:
    """
    Validate that recommendations have required structure.
    
    Args:
        recommendations: List of recommendation dicts
    
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(recommendations, list) or len(recommendations) == 0:
        return False
    
    required_keys = ['action', 'priority', 'why']
    valid_priorities = ['urgent', 'near-term', 'follow-up']
    
    for rec in recommendations:
        if not isinstance(rec, dict):
            return False
        
        # Check required keys present
        if not all(key in rec for key in required_keys):
            return False
        
        # Check priority value valid
        if rec['priority'] not in valid_priorities:
            return False
        
        # Check all values are strings
        if not all(isinstance(rec[key], str) for key in required_keys):
            return False
    
    return True


def _get_fallback_recommendations() -> List[Dict[str, Any]]:
    """
    Get deterministic fallback recommendation when MedGemma fails.
    
    Returns:
        List with single safety-first recommendation
    """
    return [{
        "action": "refer",
        "priority": "urgent",
        "why": "insufficient_data - safety-first",
        "practical_note": "Arrange transport to PHC for complete evaluation",
        "source": "fallback_safety_first"
    }]
