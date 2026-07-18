import os
import logging

logger = logging.getLogger("LocalLLM")

# Fast check if model exists before importing heavy libraries
MODEL_NAME = "qwen/Qwen2.5-0.5B-Instruct"
# ModelScope stores files in ~/.cache/modelscope/hub/qwen/Qwen2_dot_5-0_dot_5B-Instruct
# Check both standard and replaced directory formats for robustness
cache_dir_standard = os.path.expanduser(f"~/.cache/modelscope/hub/{MODEL_NAME}")
cache_dir_clean = os.path.expanduser(f"~/.cache/modelscope/hub/qwen/Qwen2.5-0.5B-Instruct")
cache_dir_ms = os.path.expanduser("~/.cache/modelscope/models/qwen--Qwen2.5-0.5B-Instruct/snapshots/master")

def _check_model_cached() -> bool:
    for cdir in [cache_dir_standard, cache_dir_clean, cache_dir_ms]:
        if os.path.exists(cdir):
            for root, dirs, files in os.walk(cdir):
                if "model.safetensors" in files or "pytorch_model.bin" in files:
                    return True
    return False

class LocalLLM:
    """
    Manages loading and text generation for a small local LLM (Qwen2.5-0.5B-Instruct)
    fetched from ModelScope, running entirely offline on the CPU.
    """

    def __init__(self):
        self.model_name = MODEL_NAME
        self.model = None
        self.tokenizer = None
        self._is_loaded = False

    def load_model(self):
        """
        Lazy-loads the model and tokenizer into CPU memory.
        """
        if self._is_loaded:
            return
            
        if not _check_model_cached():
            raise FileNotFoundError("Local Qwen model files are not fully cached on disk yet.")
            
        # Heavy imports done lazily only when model is confirmed cached
        import torch
        from modelscope import AutoModelForCausalLM, AutoTokenizer
            
        logger.info(f"Loading local model {self.model_name} from ModelScope cache...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                local_files_only=True
            )
            self._is_loaded = True
            logger.info("Local Qwen model loaded successfully on CPU!")
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
            raise e

    def generate(self, prompt: str, max_new_tokens: int = 150) -> str:
        """
        Generates text for the given prompt using local CPU execution.
        """
        import torch
        self.load_model()
        
        try:
            inputs = self.tokenizer([prompt], return_tensors="pt")
            inputs = {k: v.to("cpu") for k, v in inputs.items()}
            
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=0.1,
                    do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Trim the prompt tokens from the output
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs["input_ids"], generated_ids)
            ]
            
            response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return response.strip()
        except Exception as e:
            logger.error(f"Error during local text generation: {e}")
            raise e

local_llm = LocalLLM()
