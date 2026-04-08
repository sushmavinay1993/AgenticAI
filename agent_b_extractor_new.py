import sys
import config  # must be first — applies httpx proxy patch for Zscaler
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from models.state import GeneratedTest, AgentState, Requirement
from utils.locator_inspector import inspect_page_locators
import os

class PlaywrightGeneratorAgent:
    """Agent B: Generates Playwright test code"""

    def __init__(self, model_name: str, temperature: float):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            convert_system_message_to_human=True,
            client_args=config.GENAI_CLIENT_ARGS,
        )
        self.generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Playwright test automation engineer.
            Generate executable Playwright test code in Python that:

            1. Uses ONLY the locators listed in "Available Locators from Page" - DO NOT invent locators
            2. Uses pytest-playwright with the 'page: Page' fixture pattern
            3. Follows Playwright best practices (auto-waiting, expect() assertions)
            4. Uses page.goto(url) with the EXACT URL provided in the requirement
            5. Includes clear comments explaining each step
            6. Handles edge cases and validation

            CRITICAL RULES:
            - ONLY reference element IDs, text, labels, or placeholders that appear in "Available Locators"
            - If a locator is NOT in the provided list, DO NOT use it
            - Always start imports with: from playwright.sync_api import Page, expect
            - Always declare the test function as: def test_<name>(page: Page):
            - Use expect(page.locator(...)).to_be_visible() for element assertions
            - Use expect(page).to_have_url(...) for URL assertions
            - Prefer page.get_by_role(), page.get_by_text(), page.get_by_label(),
              page.get_by_placeholder() over raw CSS/XPath where locator data supports it"""),
            ("user", """Requirement:
            ID: {req_id}
            Description: {description}
            URL: {url}
            Test Scenario: {test_scenario}
            Expected Behavior: {expected_behavior}

            Available Locators from Page (USE ONLY THESE):
            {locators}

            Previous Validation Issues (if any):
            {previous_issues}

            Generate a complete, runnable pytest-playwright test function.
            The first lines must be: from playwright.sync_api import Page, expect""")
        ])
    
    def generate_tests(self, state: AgentState) -> AgentState:
        """Generate Playwright tests for requirements"""
        print("\n🔨 AGENT B: Generating Playwright test code...")
        
        requirements_to_generate = self._get_requirements_to_generate(state)
        
        new_tests = []
        for req in requirements_to_generate:
            test = self._generate_single_test(req, state)
            new_tests.append(test)
            print(f"✅ Generated test for {req.id}")
        
        # Update state (will be added to existing tests via operator.add)
        state["generated_tests"] = new_tests
        state["generation_metadata"] = {
            "generated_count": len(new_tests),
            "iteration": state["iteration_count"]
        }
        state["messages"].append(
            f"Agent B: Generated {len(new_tests)} test(s) in iteration {state['iteration_count']}"
        )
        
        return state
    
    def _get_requirements_to_generate(self, state: AgentState) -> List[Requirement]:
        """Determine which requirements need code generation"""
        if state["iteration_count"] == 0:
            # First iteration: generate all
            return state["requirements"]
        else:
            # Subsequent iterations: only regenerate flagged requirements
            requirements_to_fix = set(state["requirements_to_fix"])
            to_regenerate = [
                req for req in state["requirements"]
                if req.id in requirements_to_fix
            ]
            print(f"  🔄 Partial re-generation: {len(to_regenerate)} requirement(s) "
                  f"{[r.id for r in to_regenerate]} (skipping "
                  f"{len(state['requirements']) - len(to_regenerate)} already-passing)")
            return to_regenerate
    
    def _generate_single_test(self, req: Requirement, state: AgentState) -> GeneratedTest:
        """Generate code for a single requirement"""
        # Inspect actual page for locators
        locators = inspect_page_locators(req.url)
        
        # Get previous validation issues for this requirement
        previous_issues = self._get_previous_issues(req.id, state)
        
        # Generate code using LLM
        chain = self.generation_prompt | self.llm
        response = chain.invoke({
            "req_id": req.id,
            "description": req.description,
            "url": req.url,
            "test_scenario": req.test_scenario,
            "expected_behavior": req.expected_behavior,
            "locators": self._format_locators(locators),
            "previous_issues": previous_issues
        })
        
        # Extract code from response
        code = self._extract_code(response.content)
        
        return GeneratedTest(
            requirement_id=req.id,
            test_name=self._generate_test_name(req),
            code=code,
            locators_used=list(locators.keys()) if locators else [],
            dependencies=[]
        )
    
    def _get_previous_issues(self, req_id: str, state: AgentState) -> str:
        """Get validation issues from previous iteration"""
        if not state["validation_reports"]:
            return "None"
        
        last_report = state["validation_reports"][-1]
        issues = [
            issue for issue in last_report.issues
            if issue.requirement_id == req_id
        ]
        
        if not issues:
            return "None"
        
        return "\n".join([
            f"- {issue.issue_type}: {issue.description} (Suggestion: {issue.suggestion})"
            for issue in issues
        ])
    
    def _format_locators(self, locators: Dict) -> str:
        """Format locators for prompt"""
        if not locators:
            return "No locators available - inspect page manually"

        formatted = []
        for element_type, elements in locators.items():
            if not elements:
                continue
            formatted.append(f"\n{element_type}:")
            for i, elem in enumerate(elements):
                if isinstance(elem, dict):
                    parts = [f"{k}: {v!r}" for k, v in elem.items()]
                    formatted.append(f"  [{i+1}] {', '.join(parts)}")
                else:
                    formatted.append(f"  [{i+1}] {elem}")

        return "\n".join(formatted) if formatted else "No locators available - inspect page manually"
    
    def _extract_code(self, llm_output: str) -> str:
        """Extract Python code from LLM response"""
        # Try to extract code from markdown blocks
        import re
        code_match = re.search(r'```python\s*([\s\S]*?)\s*```', llm_output)
        if code_match:
            return code_match.group(1).strip()
        return llm_output.strip()
    
    def _generate_test_name(self, req: Requirement) -> str:
        """Generate test function name from requirement"""
        # Create snake_case name
        import re
        name = req.description.lower()
        name = re.sub(r'[^a-z0-9]+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return f"test_{req.id.lower()}_{name[:50]}"