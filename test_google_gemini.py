#!/usr/bin/env python3
"""Test Google Gemini setup"""

import os
import ssl
import warnings

# Disable SSL verification
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')

print("Testing Google Gemini configuration...")

try:
    from dotenv import load_dotenv
    print("✅ dotenv imported")
    
    load_dotenv()
    print("✅ .env file loaded")
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        print(f"✅ API Key found: {api_key[:20]}...")
    else:
        print("❌ API Key not found in .env")
        exit(1)
    
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("✅ langchain_google_genai imported")
    
    # Simple initialization - SSL already disabled above
    llm = ChatGoogleGenerativeAI(
        model='gemini-pro',
        temperature=0.1
    )
    print("✅ LLM initialized")
    
    # Test a simple invocation
    print("🔄 Testing API call...")
    response = llm.invoke("Say 'Hello' in one word")
    print(f"✅ LLM response: {response.content}")
    
    print("\n🎉 All tests passed! Ready to run main system.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()