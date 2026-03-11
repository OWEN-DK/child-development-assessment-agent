import json
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from llama_index.core import Settings
from src.core.prompts import METADATA_EXTRACTION_PROMPT

class ExtractedMetadata(BaseModel):
    summary: str = Field(default="", description="A brief summary of the content (max 50 words)")
    topics: List[str] = Field(default_factory=list, description="A list of key topics")
    brain_regions: List[str] = Field(default_factory=list, description="A list of brain regions mentioned or implied")
    target_age_min: int = Field(default=0, description="The minimum applicable age")
    target_age_max: int = Field(default=18, description="The maximum applicable age")
    activity_type: str = Field(default="Theory", description="The type of content")

class MetadataExtractor:
    @staticmethod
    async def extract(text: str) -> ExtractedMetadata:
        """
        Extract structured metadata from text using LLM.
        """
        # Truncate text to avoid token limit issues (e.g., 2000 chars)
        truncated_text = text[:2000]
        
        # Format the prompt
        prompt = METADATA_EXTRACTION_PROMPT.format(text=truncated_text)
        
        try:
            if not Settings.llm:
                print("Warning: Settings.llm is not configured. Returning default metadata.")
                return ExtractedMetadata()
                
            # Call LLM
            response = await Settings.llm.acomplete(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from response
            # It might be wrapped in ```json ... ```
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find the first { and last }
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    json_str = response_text[start:end+1]
                else:
                    json_str = response_text
            
            # Parse JSON
            data = json.loads(json_str)
            return ExtractedMetadata(**data)
            
        except Exception as e:
            print(f"Metadata extraction failed: {e}")
            # Return default/empty metadata on failure
            return ExtractedMetadata(summary="Extraction failed")
