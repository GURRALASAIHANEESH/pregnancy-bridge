"""
Symptom Intake Module for PregnancyBridge
Production-grade structured maternal symptom capture
Author: PregnancyBridge Development Team
Version: 1.0.0
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SymptomIntake:
    """
    Structured symptom capture interface for maternal risk assessment.
    
    Validates and processes 9 clinical symptom fields with categorization
    for integration with temporal risk escalation engine.
    
    Thread-safe and stateless for production deployment.
    """
    
    # WHO/ACOG recognized maternal warning symptoms
    VALID_SYMPTOMS = {
        'headache',
        'blurred_vision',
        'facial_edema',
        'pedal_edema',
        'dizziness',
        'breathlessness',
        'reduced_fetal_movement',
        'abdominal_pain',
        'nausea_vomiting'
    }
    
    # Clinical symptom categories (evidence-based grouping)
    NEUROLOGICAL_SYMPTOMS = {'headache', 'blurred_vision', 'dizziness'}
    EDEMA_SYMPTOMS = {'facial_edema', 'pedal_edema'}
    RESPIRATORY_SYMPTOMS = {'breathlessness'}
    FETAL_CONCERN_SYMPTOMS = {'reduced_fetal_movement'}
    GI_SYMPTOMS = {'nausea_vomiting', 'abdominal_pain'}
    
    def __init__(self):
        """Initialize symptom intake module"""
        logger.info("SymptomIntake module initialized")
    
    def validate_symptoms(self, symptom_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate symptom input structure and data types.
        
        Args:
            symptom_data: Dictionary containing 'symptoms' key with boolean values
            
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
            
        Example:
            >>> intake = SymptomIntake()
            >>> valid, error = intake.validate_symptoms({
            ...     'symptoms': {'headache': True, 'blurred_vision': False}
            ... })
            >>> valid
            True
        """
        # Type validation
        if not isinstance(symptom_data, dict):
            return False, "Input must be a dictionary"
        
        if 'symptoms' not in symptom_data:
            return False, "Missing required 'symptoms' key"
        
        symptoms = symptom_data['symptoms']
        if not isinstance(symptoms, dict):
            return False, "'symptoms' value must be a dictionary"
        
        # Empty symptoms allowed (no symptoms reported)
        if len(symptoms) == 0:
            logger.warning("Empty symptom dictionary provided")
            return True, None
        
        # Validate symptom keys
        invalid_keys = set(symptoms.keys()) - self.VALID_SYMPTOMS
        if invalid_keys:
            return False, f"Invalid symptom keys: {sorted(invalid_keys)}"
        
        # Validate boolean values
        for key, value in symptoms.items():
            if not isinstance(value, bool):
                return False, f"Symptom '{key}' must be boolean, got {type(value).__name__}"
        
        return True, None
    
    def capture_symptoms(self, symptom_data: Dict, visit_id: Optional[str] = None) -> Dict:
        """
        Capture and structure symptom data with clinical categorization.
        
        Args:
            symptom_data: Validated symptom dictionary
            visit_id: Optional visit identifier for tracking
            
        Returns:
            Structured symptom record with categories and metadata
            
        Raises:
            ValueError: If symptom data validation fails
            
        Example:
            >>> intake = SymptomIntake()
            >>> record = intake.capture_symptoms({
            ...     'symptoms': {
            ...         'headache': True,
            ...         'blurred_vision': True,
            ...         'pedal_edema': False
            ...     }
            ... }, visit_id='V001')
        """
        # Validate input
        is_valid, error = self.validate_symptoms(symptom_data)
        if not is_valid:
            logger.error(f"Symptom validation failed: {error}")
            raise ValueError(f"Invalid symptom data: {error}")
        
        symptoms = symptom_data.get('symptoms', {})
        
        # Extract present symptoms (True values only)
        present_symptoms = sorted([k for k, v in symptoms.items() if v])
        
        # Categorize symptoms
        neurological = sorted(list(self.NEUROLOGICAL_SYMPTOMS & set(present_symptoms)))
        edema = sorted(list(self.EDEMA_SYMPTOMS & set(present_symptoms)))
        respiratory = sorted(list(self.RESPIRATORY_SYMPTOMS & set(present_symptoms)))
        fetal_concern = sorted(list(self.FETAL_CONCERN_SYMPTOMS & set(present_symptoms)))
        gi = sorted(list(self.GI_SYMPTOMS & set(present_symptoms)))
        
        # Count active categories
        active_categories = sum([
            len(neurological) > 0,
            len(edema) > 0,
            len(respiratory) > 0,
            len(fetal_concern) > 0,
            len(gi) > 0
        ])
        
        symptom_record = {
            'visit_id': visit_id,
            'timestamp': datetime.now().isoformat(),
            'raw_symptoms': symptoms,
            'present_symptoms': present_symptoms,
            'symptom_count': len(present_symptoms),
            'categories': {
                'neurological': neurological,
                'edema': edema,
                'respiratory': respiratory,
                'fetal_concern': fetal_concern,
                'gi': gi
            },
            'has_neurological': len(neurological) > 0,
            'has_edema': len(edema) > 0,
            'has_respiratory': len(respiratory) > 0,
            'has_fetal_concern': len(fetal_concern) > 0,
            'has_gi': len(gi) > 0,
            'multiple_categories': active_categories >= 2,
            'category_count': active_categories
        }
        
        logger.info(f"Captured {len(present_symptoms)} symptoms across {active_categories} categories")
        return symptom_record
    
    def attach_to_visit(self, visit_record: Dict, symptom_record: Dict) -> Dict:
        """
        Attach symptom data to an existing visit record.
        
        Args:
            visit_record: Existing clinical visit data
            symptom_record: Captured symptom data from capture_symptoms()
            
        Returns:
            Enhanced visit record with symptoms attached
        """
        if not isinstance(visit_record, dict):
            raise ValueError("visit_record must be a dictionary")
        
        if not isinstance(symptom_record, dict):
            raise ValueError("symptom_record must be a dictionary")
        
        enhanced_visit = visit_record.copy()
        enhanced_visit['symptoms'] = symptom_record
        
        logger.debug(f"Attached symptoms to visit {visit_record.get('date', 'unknown')}")
        return enhanced_visit
    
    def get_symptom_summary(self, symptom_record: Dict) -> str:
        """
        Generate human-readable symptom summary for clinical display.
        
        Args:
            symptom_record: Symptom record from capture_symptoms()
            
        Returns:
            Formatted string summary
        """
        if not symptom_record or symptom_record.get('symptom_count', 0) == 0:
            return "No symptoms reported"
        
        count = symptom_record['symptom_count']
        present = symptom_record['present_symptoms']
        
        if count <= 3:
            return f"{', '.join(present)}"
        else:
            return f"{count} symptoms: {', '.join(present[:3])}..."
    
    def export_to_json(self, symptom_record: Dict, filepath: str) -> None:
        """
        Export symptom record to JSON file.
        
        Args:
            symptom_record: Symptom record to export
            filepath: Destination file path
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(symptom_record, f, indent=2, ensure_ascii=False)
            logger.info(f"Symptom record exported to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export symptom record: {e}")
            raise


# Quick validation function for external use
def validate_symptom_input(data: Dict) -> bool:
    """
    Quick validation helper for external modules.
    
    Args:
        data: Symptom data to validate
        
    Returns:
        True if valid, False otherwise
    """
    intake = SymptomIntake()
    is_valid, _ = intake.validate_symptoms(data)
    return is_valid


if __name__ == "__main__":
    # Self-test
    print("Running SymptomIntake self-test...")
    
    intake = SymptomIntake()
    
    # Test case 1: Valid input
    test_data = {
        'symptoms': {
            'headache': True,
            'blurred_vision': True,
            'pedal_edema': False,
            'breathlessness': False
        }
    }
    
    try:
        record = intake.capture_symptoms(test_data, visit_id='TEST001')
        print(f"✓ Valid input processed: {intake.get_symptom_summary(record)}")
        print(f"  Categories: {list(k for k, v in record['categories'].items() if v)}")
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    # Test case 2: Invalid input
    invalid_data = {
        'symptoms': {
            'invalid_symptom': True
        }
    }
    
    is_valid, error = intake.validate_symptoms(invalid_data)
    if not is_valid:
        print(f"✓ Invalid input correctly rejected: {error}")
    
    print("\nSymptomIntake self-test complete.")
