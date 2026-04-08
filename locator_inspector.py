from typing import Dict
from playwright.sync_api import sync_playwright
import time

def inspect_page_locators(url: str, timeout: int = 30000) -> Dict:
    """Inspect page and extract available locators"""
    locators = {}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout, wait_until="networkidle")
            
            # Wait for page to stabilize
            time.sleep(2)
            
            # Extract common interactive elements
            elements_to_check = {
                "buttons": "button, [type='button'], [type='submit'], [role='button']",
                "links": "a[href]",
                "inputs": "input, textarea",
                "selects": "select",
                "checkboxes": "[type='checkbox']",
                "radio_buttons": "[type='radio']",
                "headings": "h1, h2, h3, h4, h5, h6",
                "forms": "form",
                "tables": "table",
                "lists": "ul, ol"
            }
            
            for element_type, selector in elements_to_check.items():
                try:
                    elements = page.locator(selector).all()
                    if elements:
                        locators[element_type] = []
                        for i, elem in enumerate(elements[:10]):  # Limit to first 10
                            try:
                                # Try multiple locator strategies
                                elem_locators = {}
                                
                                # Get text content
                                text = elem.inner_text(timeout=1000).strip()[:50] if elem.is_visible() else ""
                                
                                # Get attributes
                                attrs = {}
                                for attr in ['id', 'name', 'class', 'data-testid', 'aria-label', 'placeholder']:
                                    try:
                                        val = elem.get_attribute(attr)
                                        if val:
                                            attrs[attr] = val
                                    except:
                                        pass
                                
                                if text:
                                    elem_locators['text'] = text
                                if attrs.get('id'):
                                    elem_locators['id'] = f"#{attrs['id']}"
                                if attrs.get('data-testid'):
                                    elem_locators['test_id'] = attrs['data-testid']
                                if attrs.get('aria-label'):
                                    elem_locators['aria_label'] = attrs['aria-label']
                                if attrs.get('placeholder'):
                                    elem_locators['placeholder'] = attrs['placeholder']
                                if attrs.get('name'):
                                    elem_locators['name'] = attrs['name']
                                
                                if elem_locators:
                                    locators[element_type].append(elem_locators)
                            except:
                                continue
                except:
                    continue
            
            browser.close()
            
    except Exception as e:
        print(f"⚠️  Error inspecting page {url}: {e}")
    
    return locators