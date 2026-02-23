"""
MedGemma AI Model Bridge - Clinical Explanation Generator
Production-ready interface for MedGemma medical reasoning model
Author: PregnancyBridge Team
Version: 1.0.0

CRITICAL: Used ONLY for explanations - NEVER for risk decisions
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Try importing transformers for full model
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not available - fallback mode only")


class MedGemmaModel:
    """
    AI model interface for clinical explanation generation.
    
    Safety: Explanation-only - never modifies risk classification
    """
    
    def __init__(self, 
                 model_name: str = "google/medgemma-2b",
                 device: str = "auto",
                 load_in_4bit: bool = True):
        """
        Initialize MedGemma AI model.
        
        Args:
            model_name: Model identifier
            device: 'cuda', 'cpu', or 'auto'
            load_in_4bit: Use 4-bit quantization (recommended)
        """
        self.model_name = model_name
        self.device = self._determine_device(device)
        self.model = None
        self.tokenizer = None
        
        if TRANSFORMERS_AVAILABLE:
            try:
                self._load_model(load_in_4bit)
                logger.info(f"✓ MedGemma model loaded on {self.device}")
            except Exception as e:
                logger.error(f"Model loading failed: {e}")
                logger.info("Falling back to rule-based explanations")
        else:
            logger.info("Using rule-based explanations (transformers not installed)")
    
    def _determine_device(self, device: str) -> str:
        """Determine computation device"""
        if device == "auto":
            if TRANSFORMERS_AVAILABLE and torch.cuda.is_available():
                return "cuda"
            return "cpu"
        return device
    
    def _load_model(self, load_in_4bit: bool):
        """Load model and tokenizer"""
        logger.info(f"Loading {self.model_name}...")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        
        # Model loading kwargs
        model_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32
        }
        
        # 4-bit quantization for memory efficiency
        if load_in_4bit and self.device == "cuda":
            try:
                from transformers import BitsAndBytesConfig
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                model_kwargs["quantization_config"] = quantization_config
                logger.info("Using 4-bit quantization")
            except ImportError:
                logger.warning("bitsandbytes not available, loading in fp16")
        
        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **model_kwargs
        )
        
        if not load_in_4bit:
            self.model = self.model.to(self.device)
        
        self.model.eval()
    
    def generate_explanation(self,
                            prompt: str,
                            max_tokens: int = 400,
                            temperature: float = 0.3) -> str:
        """
        Generate clinical explanation from prompt.
        
        Args:
            prompt: Clinical scenario (use mandatory template)
            max_tokens: Maximum generation length
            temperature: Sampling temperature (lower = more consistent)
            
        Returns:
            Generated explanation text
        """
        # If model not loaded, use fallback
        if self.model is None or self.tokenizer is None:
            return self._fallback_explanation(prompt)
        
        try:
            # Tokenize
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode
            generated = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract only new generation
            if prompt in generated:
                explanation = generated.split(prompt)[-1].strip()
            else:
                explanation = generated.strip()
            
            return explanation
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return self._fallback_explanation(prompt)
    
    def _fallback_explanation(self, prompt: str) -> str:
        """Rule-based fallback when model unavailable"""
        prompt_lower = prompt.lower()
        
        if "preeclampsia" in prompt_lower:
            return """1. Clinical Concerns:
The combination of elevated blood pressure with neurological symptoms (headache, blurred vision) 
indicates possible preeclampsia with severe features. These neurological manifestations suggest 
CNS involvement and increased risk of eclamptic seizures.

2. Why Escalation is Necessary:
Progressive hypertension with proteinuria and neurological symptoms meets criteria for severe 
preeclampsia. Immediate evaluation is required to prevent maternal stroke, seizure, organ damage, 
and potential fetal compromise from placental insufficiency.

3. Complications Prevented:
- Maternal: Eclamptic seizures, stroke, HELLP syndrome, renal failure, pulmonary edema
- Fetal: Growth restriction, placental abruption, preterm delivery complications"""
        
        elif "anemia" in prompt_lower:
            return """1. Clinical Concerns:
Progressive decline in hemoglobin with respiratory symptoms (breathlessness, dizziness) suggests 
severe anemia causing cardiopulmonary decompensation. The patient may be approaching the threshold 
where oxygen delivery to vital organs is compromised.

2. Why Escalation is Necessary:
Severe anemia (Hb <9 g/dL) in pregnancy, especially with symptoms, requires urgent intervention. 
Breathlessness indicates cardiovascular strain, and dizziness suggests cerebral hypoperfusion. 
Risk of cardiac failure and poor fetal outcomes increases significantly.

3. Complications Prevented:
- Maternal: Cardiac failure, severe fatigue, increased operative risk, postpartum hemorrhage complications
- Fetal: Preterm delivery, low birth weight, perinatal mortality"""
        
        elif "proteinuria" in prompt_lower:
            return """1. Clinical Concerns:
Progressive proteinuria with multiple symptom categories indicates multi-system involvement 
consistent with evolving preeclampsia. Visual symptoms suggest posterior circulation involvement, 
while GI symptoms may indicate hepatic involvement (HELLP syndrome consideration).

2. Why Escalation is Necessary:
Persistent and worsening proteinuria represents renal endothelial damage. Combined with symptoms 
across multiple organ systems, this pattern requires immediate comprehensive evaluation to determine 
disease severity and delivery timing.

3. Complications Prevented:
- Maternal: Progression to severe preeclampsia/eclampsia, HELLP syndrome, renal failure
- Fetal: Uteroplacental insufficiency, IUGR, stillbirth"""
        
        else:
            return """1. Clinical Concerns:
Temporal analysis reveals progressive deterioration across multiple parameters with concerning 
symptoms. This pattern indicates evolving maternal risk that requires immediate specialist evaluation.

2. Why Escalation is Necessary:
Single-visit assessment may miss progressive trends. Temporal reasoning combined with symptom 
correlation reveals escalating risk patterns requiring urgent intervention to prevent complications.

3. Complications Prevented:
Early escalation enables timely intervention, preventing progression to severe maternal morbidity 
and adverse fetal outcomes. Specialist evaluation can guide optimal timing and mode of delivery."""
    
    def is_available(self) -> bool:
        """Check if AI model is loaded and available"""
        return self.model is not None and self.tokenizer is not None
    
    def get_info(self) -> Dict:
        """Get model information"""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'available': self.is_available(),
            'transformers_installed': TRANSFORMERS_AVAILABLE
        }


# Convenience function
def create_medgemma_model(**kwargs):
    """Factory function to create MedGemma model"""
    return MedGemmaModel(**kwargs)


if __name__ == "__main__":
    # Self-test
    print("MedGemmaModel Self-Test")
    print("=" * 70)
    
    model = MedGemmaModel()
    info = model.get_info()
    
    print(f"Model Available: {info['available']}")
    print(f"Device: {info['device']}")
    print(f"Transformers Installed: {info['transformers_installed']}")
    
    # Test generation
    test_prompt = """A rule-based maternal risk system has escalated this pregnancy.
Risk category: HIGH
Escalation reason: Elevated BP with neurological symptoms - PREECLAMPSIA SUSPECTED

Explain why escalation is necessary."""
    
    print("\nGenerating test explanation...")
    explanation = model.generate_explanation(test_prompt, max_tokens=200)
    print(f"\n{explanation}")
    
    print("\n✓ MedGemmaModel self-test complete")
