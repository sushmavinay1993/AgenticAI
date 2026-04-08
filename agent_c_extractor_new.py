import sys
import config  # must be first — applies httpx proxy patch for Zscaler
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
from typing import List, Dict
import ast
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from models.state import ValidationIssue, ValidationReport, AgentState, GeneratedTest
from playwright.sync_api import sync_playwright
import subprocess
import tempfile
import os

class CodeValidatorAgent:
    """Agent C: Validates generated Playwright code"""

    def __init__(self, model_name: str, temperature: float):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            convert_system_message_to_human=True,
            client_args=config.GENAI_CLIENT_ARGS,
        )
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert code reviewer specializing in test automation. 
            Analyze the generated Playwright test code for:
            
            1. **Hallucinations**: Locators or elements that don't exist on the page
            2. **Missing Scenarios**: Test scenarios from requirements not covered
            3. **Edge Cases**: Missing boundary conditions, error states, validations
            4. **Test Coverage**: Completeness of testing the requirement
            5. **Code Quality**: Proper assertions, error handling, maintainability
            
            For each issue found, provide:
            - Issue type (hallucination/missing/edge_case/coverage)
            - Severity (critical/major/minor)
            - Clear description
            - Specific suggestion for fix
            
            Be precise and actionable."""),
            ("user", """Requirement:
            {requirement}
            
            Generated Test Code:
            ```python
            {test_code}
            ```
            
            Actual Page Elements (from inspection):
            {page_elements}
            
            Analyze this code for issues. Return structured JSON.""")
        ])
    
    def validate_tests(self, state: AgentState) -> AgentState:
        """Validate all generated tests"""
        print(f"\n🔎 AGENT C: Validating generated code (Attempt {state['iteration_count'] + 1})...")
        
        all_issues = []
        passed_requirements = []
        hallucination_count = 0
        missing_scenarios = []

        # Deduplicate: when Agent B re-generates a requirement, a newer test is
        # appended to generated_tests. Always validate only the latest version.
        latest_tests: Dict[str, GeneratedTest] = {}
        for test in state["generated_tests"]:
            latest_tests[test.requirement_id] = test  # last write wins
        tests_to_validate = list(latest_tests.values())

        for test in tests_to_validate:
            # Skip if already validated in previous iteration
            if state["previously_validated"].get(test.requirement_id, False):
                passed_requirements.append(test.requirement_id)
                continue
            
            # Get corresponding requirement
            requirement = next(
                (r for r in state["requirements"] if r.id == test.requirement_id),
                None
            )
            
            if not requirement:
                continue
            
            # Validate test
            issues = self._validate_single_test(test, requirement)
            
            if issues:
                all_issues.extend(issues)
                # Count hallucinations
                hallucination_count += sum(
                    1 for issue in issues if issue.issue_type == "hallucination"
                )
                # Track missing scenarios
                missing_scenarios.extend([
                    issue.description for issue in issues
                    if issue.issue_type == "missing"
                ])
            else:
                passed_requirements.append(test.requirement_id)
                state["previously_validated"][test.requirement_id] = True
        
        # Calculate coverage score
        total_requirements = len(state["requirements"])
        covered_requirements = len(passed_requirements)
        coverage_score = (covered_requirements / total_requirements * 100) if total_requirements > 0 else 0
        
        # Determine overall status
        critical_issues = sum(1 for issue in all_issues if issue.severity == "critical")
        if critical_issues == 0 and coverage_score >= 80:
            overall_status = "pass"
            needs_regeneration = False
        elif state["iteration_count"] >= 4:  # Max attempts reached
            overall_status = "failed"
            needs_regeneration = False
        else:
            overall_status = "needs_fix"
            needs_regeneration = True
        
        # Create validation report
        report = ValidationReport(
            attempt=state["iteration_count"] + 1,
            issues=all_issues,
            coverage_score=coverage_score,
            hallucination_count=hallucination_count,
            missing_scenarios=missing_scenarios,
            passed_requirements=passed_requirements,
            overall_status=overall_status
        )
        
        # Update state
        state["validation_reports"] = [report]
        state["current_report"] = report
        state["needs_regeneration"] = needs_regeneration
        # Deduplicate requirement IDs while preserving order
        state["requirements_to_fix"] = list(dict.fromkeys(
            issue.requirement_id for issue in all_issues
        ))
        state["messages"].append(
            f"Agent C: Validation complete - {overall_status.upper()} "
            f"(Coverage: {coverage_score:.1f}%, Issues: {len(all_issues)})"
        )
        
        print(f"📊 Validation Results:")
        print(f"  - Coverage: {coverage_score:.1f}%")
        print(f"  - Issues Found: {len(all_issues)}")
        print(f"  - Hallucinations: {hallucination_count}")
        print(f"  - Status: {overall_status.upper()}")
        
        return state
    
    def _validate_single_test(
        self, 
        test: GeneratedTest, 
        requirement
    ) -> List[ValidationIssue]:
        """Validate a single test"""
        issues = []
        
        # 1. Syntax validation
        syntax_issues = self._check_syntax(test)
        issues.extend(syntax_issues)
        
        # 2. Locator validation (check if locators exist on page)
        locator_issues = self._check_locators(test, requirement.url)
        issues.extend(locator_issues)
        
        # 3. LLM-based semantic validation
        semantic_issues = self._llm_semantic_validation(test, requirement)
        issues.extend(semantic_issues)
        
        return issues
    
    def _check_syntax(self, test: GeneratedTest) -> List[ValidationIssue]:
        """Check Python syntax"""
        issues = []
        try:
            ast.parse(test.code)
        except SyntaxError as e:
            issues.append(ValidationIssue(
                requirement_id=test.requirement_id,
                issue_type="syntax_error",
                severity="critical",
                description=f"Syntax error in generated code: {str(e)}",
                suggestion="Fix the Python syntax error"
            ))
        return issues
    
    def _check_locators(self, test: GeneratedTest, url: str) -> List[ValidationIssue]:
        """Check if locators in code exist on actual page"""
        issues = []
        
        # Extract locators from code
        locators_in_code = self._extract_locators_from_code(test.code)
        
        if not locators_in_code:
            return issues
        
        # Try to verify locators exist on page
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                
                for locator in locators_in_code:
                    try:
                        element = page.locator(locator)
                        count = element.count()
                        if count == 0:
                            issues.append(ValidationIssue(
                                requirement_id=test.requirement_id,
                                issue_type="hallucination",
                                severity="critical",
                                description=f"Locator '{locator}' not found on page",
                                suggestion=f"Inspect the page at {url} and use a valid locator"
                            ))
                    except Exception as e:
                        issues.append(ValidationIssue(
                            requirement_id=test.requirement_id,
                            issue_type="hallucination",
                            severity="major",
                            description=f"Invalid locator '{locator}': {str(e)}",
                            suggestion="Use a valid Playwright locator syntax"
                        ))
                
                browser.close()
        except Exception as e:
            print(f"⚠️  Could not verify locators: {e}")
        
        return issues
    
    def _extract_locators_from_code(self, code: str) -> List[str]:
        """Extract Playwright locators from code"""
        locators = []
        
        # Patterns for common Playwright locator methods
        patterns = [
            r'locator\(["\']([^"\']+)["\']\)',
            r'get_by_role\(["\']([^"\']+)["\']\)',
            r'get_by_text\(["\']([^"\']+)["\']\)',
            r'get_by_label\(["\']([^"\']+)["\']\)',
            r'get_by_placeholder\(["\']([^"\']+)["\']\)',
            r'get_by_test_id\(["\']([^"\']+)["\']\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, code)
            locators.extend(matches)
        
        return locators
    
    def _llm_semantic_validation(
        self, 
        test: GeneratedTest, 
        requirement
    ) -> List[ValidationIssue]:
        """Use LLM to check semantic correctness"""
        # Inspect page elements
        from utils.locator_inspector import inspect_page_locators
        page_elements = inspect_page_locators(requirement.url)
        
        # Call LLM for validation
        chain = self.validation_prompt | self.llm
        response = chain.invoke({
            "requirement": requirement.model_dump_json(indent=2),
            "test_code": test.code,
            "page_elements": str(page_elements)
        })
        
        # Parse issues from LLM response
        issues = self._parse_validation_response(response.content, test.requirement_id)
        
        return issues
    
    def _parse_validation_response(
        self, 
        llm_output: str, 
        requirement_id: str
    ) -> List[ValidationIssue]:
        """Parse LLM validation output"""
        import json
        issues = []
        
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', llm_output)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = llm_output
            
            data = json.loads(json_str)
            
            if isinstance(data, dict) and "issues" in data:
                data = data["issues"]
            
            if isinstance(data, list):
                for item in data:
                    issue = ValidationIssue(
                        requirement_id=requirement_id,
                        issue_type=item.get("issue_type", "unknown"),
                        severity=item.get("severity", "minor"),
                        description=item.get("description", ""),
                        suggestion=item.get("suggestion", "")
                    )
                    issues.append(issue)
        except Exception as e:
            print(f"⚠️  Could not parse validation response: {e}")
        
        return issues