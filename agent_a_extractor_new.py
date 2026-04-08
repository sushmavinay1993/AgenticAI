import sys
import config  # must be first — applies corporate proxy/SSL settings
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
from typing import List
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from models.state import Requirement, AgentState
from utils.pdf_parser import extract_text_from_pdf

class RequirementExtractorAgent:
    """Agent A: Extracts testable requirements from PDF"""

    def __init__(self, model_name: str, temperature: float):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            convert_system_message_to_human=True,
            client_args=config.GENAI_CLIENT_ARGS,
        )
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert QA analyst specializing in extracting testable requirements 
            from software requirements documents. Your task is to:
            
            1. Identify all testable functional requirements
            2. Extract UI component details and expected behaviors
            3. Map requirements to specific URLs/pages
            4. Identify user interactions and expected outcomes
            5. Prioritize requirements based on importance
            6. Focus on observable behaviors only
            
            For each requirement, provide:
            - Unique ID
            - Clear description
            - Target URL/page path
            - Test scenario description
            - Expected behavior
            - Priority (high/medium/low)
            
            Format output as structured JSON array."""),
            ("user", """PDF Content:\n{pdf_content}\n\nBase URL: {base_url}\n\n
            Extract all testable requirements. Focus on UI interactions, 
            form validations, navigation flows, and observable behaviors.""")
        ])
    
    def extract_requirements(self, state: AgentState) -> AgentState:
        """Extract requirements from PDF"""
        print("\n🔍 AGENT A: Extracting requirements from PDF...")
        
        # Extract text from PDF
        pdf_text = extract_text_from_pdf(state["pdf_path"])
        
        # Use LLM to extract structured requirements
        chain = self.extraction_prompt | self.llm
        response = chain.invoke({
            "pdf_content": pdf_text,
            "base_url": state["base_url"]
        })
        
        # Parse LLM response into requirements
        requirements = self._parse_requirements(response.content, state["base_url"])
        
        # Update state
        state["requirements"] = requirements
        state["extraction_summary"] = f"Extracted {len(requirements)} testable requirements"
        state["messages"].append(
            f"Agent A: Extracted {len(requirements)} requirements from PDF"
        )
        
        print(f"✅ Extracted {len(requirements)} requirements")
        for req in requirements:
            print(f"  - {req.id}: {req.description[:60]}...")
        
        return state
    
    def _parse_requirements(self, llm_output: str, base_url: str) -> List[Requirement]:
        """Parse LLM output into Requirement objects"""
        import json
        
        try:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', llm_output)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = llm_output
            
            data = json.loads(json_str)
            requirements = []
            
            if isinstance(data, list):
                for item in data:
                    raw_url = (item.get("url") or "").strip()
                    if raw_url.startswith(("http://", "https://")):
                        url = raw_url
                    elif raw_url:
                        # Join relative path with base_url
                        url = base_url.rstrip("/") + "/" + raw_url.lstrip("/")
                    else:
                        url = base_url
                    req = Requirement(
                        id=item.get("id", f"REQ-{len(requirements)+1}"),
                        description=item["description"],
                        url=url,
                        test_scenario=item["test_scenario"],
                        expected_behavior=item["expected_behavior"],
                        priority=item.get("priority", "medium")
                    )
                    requirements.append(req)
            
            return requirements
            
        except Exception as e:
            print(f"⚠️  Error parsing requirements: {e}")
            # Fallback: create a basic requirement
            return [Requirement(
                id="REQ-1",
                description="Test main page functionality",
                url=base_url,
                test_scenario="Navigate to main page",
                expected_behavior="Page loads successfully",
                priority="high"
            )]