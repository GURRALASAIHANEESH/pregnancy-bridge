import os
from pathlib import Path

HF_CACHE = "D:/huggingface_cache"
OFFLOAD_DIR = "D:/medgemma_offload"

os.environ['HF_HOME'] = HF_CACHE
os.environ['TRANSFORMERS_CACHE'] = HF_CACHE
os.environ['HF_DATASETS_CACHE'] = HF_CACHE
os.environ['TORCH_HOME'] = HF_CACHE
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

Path(OFFLOAD_DIR).mkdir(parents=True, exist_ok=True)

print(f"HF_HOME: {HF_CACHE}")
print(f"Offload: {OFFLOAD_DIR}")
print("Offline mode: ENABLED")
print("Configuration applied")
