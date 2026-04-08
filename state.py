from typing import TypedDict, List, Dict, Optional, Annotated
from pydantic import BaseModel, Field
import operator

class Requirement(BaseModel):
    """Individual testable requirement"""
    id: str
    description: str
    url: str
    test_scenario: str
    expected_behavior: str
    priority: str = "medium"
    
class GeneratedTest(BaseModel):
    """Generated Playwright test code"""
    requirement_id: str
    test_name: str
    code: str
    locators_used: List[str] = []
    dependencies: List[str] = []

class ValidationIssue(BaseModel):
    """Issue found during validation"""
    requirement_id: str
    issue_type: str  # hallucination, missing, edge_case, coverage
    severity: str  # critical, major, minor
    description: str
    suggestion: str

class ValidationReport(BaseModel):
    """Complete validation report from Agent C"""
    attempt: int
    issues: List[ValidationIssue]
    coverage_score: float
    hallucination_count: int
    missing_scenarios: List[str]
    passed_requirements: List[str]
    overall_status: str  # pass, needs_fix, failed

class AgentState(TypedDict):
    """Shared state between all agents"""
    # Input
    pdf_path: str
    base_url: str
    
    # Agent A Output
    requirements: List[Requirement]
    extraction_summary: str
    
    # Agent B Output
    generated_tests: Annotated[List[GeneratedTest], operator.add]
    generation_metadata: Dict
    
    # Agent C Output
    validation_reports: Annotated[List[ValidationReport], operator.add]
    current_report: Optional[ValidationReport]
    
    # Control Flow
    iteration_count: int
    needs_regeneration: bool
    requirements_to_fix: List[str]
    final_status: str
    
    # History for incremental updates
    previously_validated: Dict[str, bool]
    
    # Messages between agents
    messages: Annotated[List[str], operator.add]