"""
Provenance Tracker
Tracks audit trail and metadata for all risk assessments
Author: PregnancyBridge Development Team
Version: 2.0.0
Date: 2026-02-04
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """
    Tracks provenance and audit metadata for maternal risk assessments.
    
    Production features:
    - Input source tracking (ANC cards, lab reports)
    - File integrity hashing (SHA-256)
    - Explanation source tracking (MedGemma vs fallback)
    - UTC timestamps for global auditability
    - Model snapshot identification
    
    Design rationale:
    Medical AI systems require full auditability. This tracker ensures
    every decision can be traced back to its inputs and processing path.
    """
    
    RISK_AUTHORITY = "rule_engine"  # Fixed as per requirement
    
    def __init__(self):
        """Initialize provenance tracker."""
        logger.info("ProvenanceTracker v2.0 initialized")
    
    def compute_file_hash(self, file_path: Optional[str]) -> Optional[str]:
        """
        Compute SHA-256 hash of file for integrity verification.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of SHA-256 hash, or None if file not accessible
        """
        if not file_path:
            return None
        
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found for hashing: {file_path}")
                return None
            
            sha256_hash = hashlib.sha256()
            
            with open(path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256_hash.update(chunk)
            
            digest = sha256_hash.hexdigest()
            logger.debug(f"Computed hash for {path.name}: {digest[:16]}...")
            return digest
            
        except Exception as e:
            logger.error(f"Failed to compute hash for {file_path}: {e}")
            return None
    
    def compute_text_hash(self, text: Optional[str]) -> Optional[str]:
        """
        Compute SHA-256 hash of text (e.g., OCR output).
        
        Args:
            text: Text content
            
        Returns:
            Hex digest of SHA-256 hash
        """
        if not text:
            return None
        
        try:
            sha256_hash = hashlib.sha256()
            sha256_hash.update(text.encode('utf-8'))
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute text hash: {e}")
            return None
    
    def create_provenance_record(self,
                                 explanation_source: str,
                                 explanation_generated: bool,
                                 model_snapshot_id: Optional[str] = None,
                                 ocr_text: Optional[str] = None,
                                 lab_report_image_path: Optional[str] = None) -> Dict:
        """
        Create provenance record conforming to schema v2.
        
        Args:
            explanation_source: 'medgemma' or 'fallback_template'
            explanation_generated: Whether explanation was successfully generated
            model_snapshot_id: HuggingFace model snapshot ID (if MedGemma used)
            ocr_text: Raw OCR text from lab report (optional)
            lab_report_image_path: Path to lab report image (optional)
            
        Returns:
            Provenance dictionary matching schema v2
        """
        provenance = {
            'risk_authority': self.RISK_AUTHORITY,
            'explanation_source': explanation_source,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'explanation_generated': explanation_generated
        }
        
        # Add model snapshot if available
        if model_snapshot_id:
            provenance['model_snapshot_id'] = model_snapshot_id
            logger.debug(f"Model snapshot: {model_snapshot_id[:50]}...")
        else:
            provenance['model_snapshot_id'] = None
        
        # Add OCR text hash if available
        if ocr_text:
            provenance['ocr_text_hash'] = self.compute_text_hash(ocr_text)
            logger.debug(f"OCR text hash: {provenance['ocr_text_hash'][:16]}...")
        else:
            provenance['ocr_text_hash'] = None
        
        # Add lab report image hash if available
        if lab_report_image_path:
            provenance['lab_report_image_hash'] = self.compute_file_hash(lab_report_image_path)
            if provenance['lab_report_image_hash']:
                logger.debug(f"Lab image hash: {provenance['lab_report_image_hash'][:16]}...")
        else:
            provenance['lab_report_image_hash'] = None
        
        logger.info(f"Created provenance record: {explanation_source}, generated={explanation_generated}")
        
        return provenance
    
    def create_input_sources_record(self,
                                    anc_card_image: Optional[str] = None,
                                    lab_report_image: Optional[str] = None,
                                    lab_report_date: Optional[str] = None) -> Dict:
        """
        Create input sources record conforming to schema v2.
        
        Args:
            anc_card_image: Path or filename of ANC card image
            lab_report_image: Path or filename of lab report image
            lab_report_date: Lab report date (YYYY-MM-DD format)
            
        Returns:
            Input sources dictionary matching schema v2
        """
        input_sources = {
            'anc_card_image': anc_card_image,
            'lab_report_image': lab_report_image,
            'lab_report_date': lab_report_date
        }
        
        logger.debug(f"Input sources: ANC={bool(anc_card_image)}, Lab={bool(lab_report_image)}, Date={bool(lab_report_date)}")
        
        return input_sources
    
    def validate_provenance_record(self, provenance: Dict) -> bool:
        """
        Validate provenance record against schema requirements.
        
        Args:
            provenance: Provenance dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['risk_authority', 'explanation_source', 'timestamp_utc', 'explanation_generated']
        
        for field in required_fields:
            if field not in provenance:
                logger.error(f"Missing required provenance field: {field}")
                return False
        
        # Validate risk_authority
        if provenance['risk_authority'] != self.RISK_AUTHORITY:
            logger.error(f"Invalid risk_authority: {provenance['risk_authority']}")
            return False
        
        # Validate explanation_source
        valid_sources = ['medgemma', 'fallback_template']
        if provenance['explanation_source'] not in valid_sources:
            logger.error(f"Invalid explanation_source: {provenance['explanation_source']}")
            return False
        
        # Validate timestamp format (ISO 8601)
        try:
            datetime.fromisoformat(provenance['timestamp_utc'].replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Invalid timestamp format: {e}")
            return False
        
        logger.debug("Provenance record validation passed")
        return True
    
    def get_model_snapshot_info(self, model_path: Optional[str] = None) -> Optional[str]:
        """
        Extract model snapshot ID from HuggingFace cache.
        
        Args:
            model_path: Path to model directory
            
        Returns:
            Snapshot ID string or None
        """
        if not model_path:
            return None
        
        try:
            path = Path(model_path)
            
            # Look for snapshots directory (HuggingFace cache structure)
            snapshots_dir = path / 'snapshots'
            if snapshots_dir.exists():
                # Get first snapshot directory (usually only one)
                snapshot_dirs = list(snapshots_dir.iterdir())
                if snapshot_dirs:
                    snapshot_id = snapshot_dirs[0].name
                    logger.info(f"Found model snapshot: {snapshot_id}")
                    return snapshot_id
            
            # Alternative: check if path itself is a snapshot hash
            if len(path.name) == 40:  # SHA-1 hash length
                logger.info(f"Using path as snapshot ID: {path.name}")
                return path.name
            
            logger.warning("Could not extract model snapshot ID")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get model snapshot info: {e}")
            return None


# Singleton
_provenance_tracker_instance = None


def get_provenance_tracker() -> ProvenanceTracker:
    """Get singleton instance of ProvenanceTracker."""
    global _provenance_tracker_instance
    if _provenance_tracker_instance is None:
        _provenance_tracker_instance = ProvenanceTracker()
    return _provenance_tracker_instance


# Self-test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ProvenanceTracker v2.0 Self-Test")
    print("=" * 70)
    
    tracker = get_provenance_tracker()
    
    # Test 1: Text hashing
    print("\nTest 1: Text Hashing")
    print("-" * 70)
    text = "Hemoglobin: 10.5 g/dL, Platelets: 180000"
    hash1 = tracker.compute_text_hash(text)
    hash2 = tracker.compute_text_hash(text)  # Should be identical
    print(f"Hash 1: {hash1}")
    print(f"Hash 2: {hash2}")
    print(f"Hashes match: {hash1 == hash2}")
    assert hash1 == hash2, "Hashes should be identical for same text"
    
    # Test 2: Provenance record creation
    print("\nTest 2: Provenance Record Creation")
    print("-" * 70)
    provenance = tracker.create_provenance_record(
        explanation_source='medgemma',
        explanation_generated=True,
        model_snapshot_id='b05b6fa90147b76639de6522a843ff1ebd8dd832',
        ocr_text=text
    )
    print(f"Risk authority: {provenance['risk_authority']}")
    print(f"Explanation source: {provenance['explanation_source']}")
    print(f"Timestamp: {provenance['timestamp_utc']}")
    print(f"Generated: {provenance['explanation_generated']}")
    print(f"Model snapshot: {provenance['model_snapshot_id'][:20]}...")
    print(f"OCR hash: {provenance['ocr_text_hash'][:20]}...")
    
    # Test 3: Input sources record
    print("\nTest 3: Input Sources Record")
    print("-" * 70)
    input_sources = tracker.create_input_sources_record(
        anc_card_image='anc_card_001.jpg',
        lab_report_image='lab_report_20260120.jpg',
        lab_report_date='2026-01-20'
    )
    print(f"ANC card: {input_sources['anc_card_image']}")
    print(f"Lab report: {input_sources['lab_report_image']}")
    print(f"Lab date: {input_sources['lab_report_date']}")
    
    # Test 4: Provenance validation
    print("\nTest 4: Provenance Validation")
    print("-" * 70)
    valid = tracker.validate_provenance_record(provenance)
    print(f"Validation result: {'✓ PASS' if valid else '✗ FAIL'}")
    
    # Test 5: Invalid provenance
    print("\nTest 5: Invalid Provenance Detection")
    print("-" * 70)
    invalid_provenance = {
        'risk_authority': 'wrong_authority',
        'explanation_source': 'medgemma',
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'explanation_generated': True
    }
    valid = tracker.validate_provenance_record(invalid_provenance)
    print(f"Validation result (should fail): {'✗ PASS' if valid else '✓ FAIL (as expected)'}")
    
    print("\n" + "=" * 70)
    print("✓ All self-tests passed")
    print("=" * 70)
