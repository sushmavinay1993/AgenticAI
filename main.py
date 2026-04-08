import os
import sys

# Ensure UTF-8 output on Windows so emoji in print() don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from typing import Literal
from langgraph.graph import StateGraph, END
from models.state import AgentState
from agents.agent_a_extractor_new import RequirementExtractorAgent
from agents.agent_b_extractor_new import PlaywrightGeneratorAgent
from agents.agent_c_extractor_new import CodeValidatorAgent
import config
from datetime import datetime

class PlaywrightAgentSystem:
    """Multi-agent system orchestrator using LangGraph"""
    
    def __init__(self):
        # Initialize agents
        self.agent_a = RequirementExtractorAgent(
            model_name=config.MODEL_NAME,
            temperature=config.TEMPERATURE
        )
        self.agent_b = PlaywrightGeneratorAgent(
            model_name=config.MODEL_NAME,
            temperature=config.TEMPERATURE
        )
        self.agent_c = CodeValidatorAgent(
            model_name=config.MODEL_NAME,
            temperature=config.TEMPERATURE
        )
        
        # Build workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("extract_requirements", self.agent_a.extract_requirements)
        workflow.add_node("generate_tests", self.agent_b.generate_tests)
        workflow.add_node("validate_tests", self.agent_c.validate_tests)
        workflow.add_node("save_results", self._save_results)
        
        # Define edges
        workflow.set_entry_point("extract_requirements")
        workflow.add_edge("extract_requirements", "generate_tests")
        workflow.add_edge("generate_tests", "validate_tests")
        
        # Conditional edge: regenerate or finish
        workflow.add_conditional_edges(
            "validate_tests",
            self._should_regenerate,
            {
                "regenerate": "generate_tests",
                "finish": "save_results"
            }
        )
        
        workflow.add_edge("save_results", END)
        
        return workflow.compile()
    
    def _should_regenerate(self, state: AgentState) -> Literal["regenerate", "finish"]:
        """Decide whether to regenerate or finish"""
        if not state["needs_regeneration"]:
            return "finish"
        
        if state["iteration_count"] >= config.MAX_REGENERATION_ATTEMPTS - 1:
            return "finish"
        
        # Increment iteration counter
        state["iteration_count"] += 1
        return "regenerate"
    
    def _save_results(self, state: AgentState) -> AgentState:
        """Save final generated tests to files"""
        print("\n💾 Saving results...")
        
        # Create output directory
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save each test to a separate file
        for test in state["generated_tests"]:
            filename = f"{test.test_name}_{timestamp}.py"
            filepath = os.path.join(config.OUTPUT_DIR, filename)
            
            with open(filepath, 'w') as f:
                f.write(test.code)
            
            print(f"  ✅ Saved: {filename}")
        
        # Save validation report
        if state["validation_reports"]:
            report_file = os.path.join(config.OUTPUT_DIR, f"validation_report_{timestamp}.json")
            with open(report_file, 'w') as f:
                import json
                reports = [r.model_dump() for r in state["validation_reports"]]
                json.dump(reports, f, indent=2)
            print(f"  ✅ Saved: validation_report_{timestamp}.json")
        
        # Generate summary report
        self._generate_summary_report(state, timestamp)
        
        state["final_status"] = state["current_report"].overall_status if state["current_report"] else "unknown"
        return state
    
    def _generate_summary_report(self, state: AgentState, timestamp: str):
        """Generate human-readable summary"""
        summary_file = os.path.join(config.OUTPUT_DIR, f"summary_{timestamp}.md")
        
        with open(summary_file, 'w') as f:
            f.write("# Playwright Test Generation Summary\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Overview\n")
            f.write(f"- **Total Requirements**: {len(state['requirements'])}\n")
            f.write(f"- **Tests Generated**: {len(state['generated_tests'])}\n")
            f.write(f"- **Iterations**: {state['iteration_count'] + 1}\n\n")
            
            if state["current_report"]:
                report = state["current_report"]
                f.write("## Final Validation Results\n")
                f.write(f"- **Status**: {report.overall_status.upper()}\n")
                f.write(f"- **Coverage**: {report.coverage_score:.1f}%\n")
                f.write(f"- **Issues Found**: {len(report.issues)}\n")
                f.write(f"- **Hallucinations**: {report.hallucination_count}\n\n")
                
                if report.issues:
                    f.write("### Issues\n")
                    for issue in report.issues:
                        f.write(f"- **{issue.requirement_id}** [{issue.severity.upper()}]: ")
                        f.write(f"{issue.description}\n")
                        f.write(f"  *Suggestion*: {issue.suggestion}\n\n")
            
            f.write("## Requirements\n")
            for req in state["requirements"]:
                status = "✅ PASSED" if req.id in state.get("previously_validated", {}) else "⚠️ NEEDS REVIEW"
                f.write(f"### {req.id}: {req.description} {status}\n")
                f.write(f"- **URL**: {req.url}\n")
                f.write(f"- **Scenario**: {req.test_scenario}\n\n")
        
        print(f"  ✅ Saved: summary_{timestamp}.md")
    
    def run(self, pdf_path: str, base_url: str) -> AgentState:
        """Execute the multi-agent workflow"""
        print("="*70)
        print("🚀 PLAYWRIGHT MULTI-AGENT TEST GENERATION SYSTEM")
        print("="*70)
        
        # Initialize state
        initial_state: AgentState = {
            "pdf_path": pdf_path,
            "base_url": base_url,
            "requirements": [],
            "extraction_summary": "",
            "generated_tests": [],
            "generation_metadata": {},
            "validation_reports": [],
            "current_report": None,
            "iteration_count": 0,
            "needs_regeneration": False,
            "requirements_to_fix": [],
            "final_status": "",
            "previously_validated": {},
            "messages": []
        }
        
        # Run workflow
        final_state = self.workflow.invoke(initial_state)
        
        # Print final summary
        print("\n" + "="*70)
        print("📊 FINAL RESULTS")
        print("="*70)
        print(f"Status: {final_state['final_status'].upper()}")
        print(f"Requirements: {len(final_state['requirements'])}")
        print(f"Tests Generated: {len(final_state['generated_tests'])}")
        print(f"Iterations: {final_state['iteration_count'] + 1}")
        
        if final_state["current_report"]:
            print(f"Coverage: {final_state['current_report'].coverage_score:.1f}%")
            print(f"Issues: {len(final_state['current_report'].issues)}")
        
        print("\nAgent Communication Log:")
        for msg in final_state["messages"]:
            print(f"  • {msg}")
        
        print("\n✨ Complete! Check the 'output/generated_tests' directory for results.")
        
        return final_state


def main():
    """Entry point"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python main.py <pdf_path> <base_url>")
        print("Example: python main.py requirements.pdf https://the-internet.herokuapp.com/")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    base_url = sys.argv[2]
    
    # Validate inputs
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Create system and run
    system = PlaywrightAgentSystem()
    system.run(pdf_path, base_url)


if __name__ == "__main__":
    main()