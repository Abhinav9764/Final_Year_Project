import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RAGService:
    """
    RAG utility to respond to user messages using
    context from the agent pipelines and SLM.
    """
    def __init__(self, config: dict):
        self.config = config
        self.slm_model = config.get("slm_model", "HuggingFaceH4/zephyr-7b-beta")
        self.vector_store_dir = Path(config.get("vector_store", {}).get("persist_dir", "data/vector_store"))
        
        self.tokenizer = None
        self.model = None
        self.pipe = None
        self._load_model()
        
    def _load_model(self):
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch
            
            logger.info(f"Loading SLM: {self.slm_model}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.slm_model)
            
            # Use float16 on GPU if available, else bfloat16 or float32 based on device
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.slm_model,
                torch_dtype=dtype,
                device_map="auto"
            )
            self.pipe = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer, max_new_tokens=256)
            logger.info("SLM loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load full SLM (using fallback mode): {e}")
            self.pipe = None
            
    def generate_response(self, user_prompt: str) -> str:
        """
        Generate answer. In a real scenario, this queries FAISS first.
        Here we generate directly based on the intent for Demo purposes.
        """
        if not self.pipe:
            # Fallback mock response
            return (
                f"Understood. I will analyze your request: '{user_prompt}'.\n\n"
                "I am orchestrating the Data Collection Agent to gather domain data, "
                "and then the RAD-ML Code Generator will construct, train, and test "
                "the model before providing you the deployment link."
            )
            
        try:
            prompt = (
                "<|system|>\n"
                "You are an intelligent orchestrator chatbot for an automated ML system. "
                "Your job is to acknowledge the user's request, explain what the underlying "
                "Data Collection and Code Generation agents will do, and assure them you "
                "are starting the process. Keep it concise. "
                "Always respond in English only, regardless of the language of the user's input.\n"
                f"<|user|>\n{user_prompt}\n"
                "<|assistant|>\n"
            )
            result = self.pipe(prompt, max_new_tokens=150, return_full_text=False)[0]['generated_text']
            return result.strip()
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "Ok, I am starting the pipeline now."
