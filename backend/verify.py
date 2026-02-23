"""
Artifact Integrity Verification Utility
Verifies HMAC signatures and SHA256 hashes for immutability
"""

import os
import sys
import json
import hashlib
import hmac
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ARTIFACT_HMAC_KEY = os.getenv('ARTIFACT_HMAC_KEY')
if not ARTIFACT_HMAC_KEY:
    print("ERROR: ARTIFACT_HMAC_KEY not set in environment")
    sys.exit(1)

ARTIFACT_HMAC_KEY = ARTIFACT_HMAC_KEY.encode()

def compute_hmac(data: bytes) -> str:
    return hmac.new(ARTIFACT_HMAC_KEY, data, hashlib.sha256).hexdigest()

def verify_run(run_id: str, artifacts_dir: str = 'artifacts/backend_runs'):
    """Verify integrity of a run"""
    run_dir = Path(artifacts_dir) / run_id
    
    if not run_dir.exists():
        print(f"✗ Run directory not found: {run_dir}")
        return False
    
    print(f"Verifying run: {run_id}")
    print(f"Directory: {run_dir}\n")
    
    all_passed = True
    
    # Verify raw request HMAC
    raw_request_file = run_dir / 'raw_request.json'
    hmac_file = run_dir / 'raw_request.hmac'
    
    if raw_request_file.exists() and hmac_file.exists():
        with open(raw_request_file, 'rb') as f:
            request_data = f.read()
        
        expected_hmac = hmac_file.read_text().strip()
        computed_hmac = compute_hmac(request_data)
        
        if expected_hmac == computed_hmac:
            print("✓ Raw request HMAC valid")
        else:
            print("✗ Raw request HMAC INVALID - file may have been tampered")
            all_passed = False
    else:
        print("⚠ Raw request or HMAC file missing")
        all_passed = False
    
    # Verify artifact hash
    hash_file = run_dir / 'artifact.sha256'
    if hash_file.exists():
        stored_hash = hash_file.read_text().strip()
        
        # Recompute hash
        artifact_content = ''
        for fname in ['pipeline_output.json', 'medgemma_raw.txt', 'rule_engine_decision.json']:
            fpath = run_dir / fname
            if fpath.exists():
                artifact_content += fpath.read_text()
        
        computed_hash = hashlib.sha256(artifact_content.encode()).hexdigest()
        
        if stored_hash == computed_hash:
            print("✓ Artifact SHA256 hash valid")
        else:
            print("✗ Artifact SHA256 hash INVALID - artifacts may have been modified")
            all_passed = False
    else:
        print("⚠ Artifact hash file missing")
        all_passed = False
    
    # Verify artifact signature
    sig_file = run_dir / 'artifact.signature'
    if sig_file.exists() and hash_file.exists():
        stored_sig = sig_file.read_text().strip()
        artifact_hash = hash_file.read_text().strip()
        computed_sig = compute_hmac(artifact_hash.encode())
        
        if stored_sig == computed_sig:
            print("✓ Artifact signature valid")
        else:
            print("✗ Artifact signature INVALID - may have been tampered")
            all_passed = False
    else:
        print("⚠ Artifact signature file missing")
        all_passed = False
    
    # Check for required files
    required_files = [
        'normalized_input.json',
        'rule_engine_decision.json',
        'pipeline_output.json',
        'qc_result.json'
    ]
    
    print("\nRequired files:")
    for fname in required_files:
        if (run_dir / fname).exists():
            print(f"  ✓ {fname}")
        else:
            print(f"  ✗ {fname} MISSING")
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("VERIFICATION: PASSED ✓")
        print("All integrity checks passed. Artifacts are immutable.")
    else:
        print("VERIFICATION: FAILED ✗")
        print("One or more integrity checks failed.")
    print("="*50)
    
    return all_passed

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify.py <run_id>")
        sys.exit(1)
    
    run_id = sys.argv[1]
    success = verify_run(run_id)
    sys.exit(0 if success else 1)
