import os
import google.generativeai as genai
from typing import Optional

class SummaryEngine:
    """AI-powered document summarization engine"""
    
    def __init__(self):
        self.model = None
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        print(f"Gemini API Key configured: {'Yes' if self.api_key else 'No'}")
        if self.api_key:
            print(f"API Key starts with: {self.api_key[:10]}...")
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                print("Gemini model initialized successfully")
            except Exception as e:
                print(f"Error initializing Gemini model: {e}")
                self.model = None
    
    def generate_summary(self, text: str) -> Optional[str]:
        """
        Generate a concise summary of the document
        
        Args:
            text: Document text to summarize
            
        Returns:
            Summary text, or None if Gemini is not configured
        """
        if not self.model:
            return "⚠️ Gemini API key not configured. Summary generation requires GEMINI_API_KEY environment variable."
        
        if not text or len(text.strip()) < 50:
            return "Document is too short to summarize."
        
        try:
            text_preview = text[:8000]  # Gemini can handle more text
            
            prompt = f"""You are a legal document analyst. Provide a clear, concise summary of this legal document focusing on:
            - Key terms and obligations
            - Parties involved
            - Document's purpose and main clauses
            - Important dates or conditions
            
            Keep the summary under 200 words and make it easy to understand.
            
            Legal Document:
            {text_preview}
            
            Summary:"""
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
        
        except Exception as e:
            print(f"Error generating summary: {e}")
            return f"Unable to generate summary: {str(e)}"
