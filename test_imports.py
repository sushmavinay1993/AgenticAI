#!/usr/bin/env python3
"""Test all imports before running main script"""

print("Testing imports...")

try:
    from langchain_openai import ChatOpenAI
    print("✅ langchain_openai.ChatOpenAI")
except ImportError as e:
    print(f"❌ langchain_openai.ChatOpenAI: {e}")

try:
    from langchain_core.prompts import ChatPromptTemplate
    print("✅ langchain_core.prompts.ChatPromptTemplate")
except ImportError as e:
    print(f"❌ langchain_core.prompts.ChatPromptTemplate: {e}")

try:
    from langgraph.graph import StateGraph
    print("✅ langgraph.graph.StateGraph")
except ImportError as e:
    print(f"❌ langgraph.graph.StateGraph: {e}")

try:
    from playwright.sync_api import sync_playwright
    print("✅ playwright.sync_api.sync_playwright")
except ImportError as e:
    print(f"❌ playwright.sync_api.sync_playwright: {e}")

try:
    from models.state import AgentState
    print("✅ models.state.AgentState")
except ImportError as e:
    print(f"❌ models.state.AgentState: {e}")

try:
    from agents.agent_a_extractor_new import RequirementExtractorAgent
    print("✅ agents.agent_a_extractor.RequirementExtractorAgent")
except ImportError as e:
    print(f"❌ agents.agent_a_extractor.RequirementExtractorAgent: {e}")
    import traceback
    traceback.print_exc()

try:
    from agents.agent_b_extractor_new import PlaywrightGeneratorAgent
    print("✅ agents.agent_b_generator.PlaywrightGeneratorAgent")
except ImportError as e:
    print(f"❌ agents.agent_b_generator.PlaywrightGeneratorAgent: {e}")

try:
    from agents.agent_c_extractor_new import CodeValidatorAgent
    print("✅ agents.agent_c_validator.CodeValidatorAgent")
except ImportError as e:
    print(f"❌ agents.agent_c_validator.CodeValidatorAgent: {e}")

print("\n✨ All imports successful!" if all else "⚠️ Some imports failed!")