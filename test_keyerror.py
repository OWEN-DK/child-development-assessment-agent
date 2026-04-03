from pydantic import BaseModel, Field
from typing import List
from langchain_core.output_parsers import PydanticOutputParser

class SynonymExpansionResult(BaseModel):
    synonyms: List[str] = Field(description="List of synonyms/related terms for the query")

parser = PydanticOutputParser(pydantic_object=SynonymExpansionResult)
text = '{"terms": ["老师", "teacher", "教育者", "导师"]}'
try:
    result = parser.parse(text)
except Exception as e:
    print(f"Type: {type(e)}")
    print(f"Str: {str(e)}")
