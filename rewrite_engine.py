import os
from typing import List, Optional, Dict
import google.generativeai as genai

class RewriteEngine:
    """Gemini-powered clause rewriting engine"""
    
    def __init__(self):
        self.model = None
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        print(f"Rewrite Engine - Gemini API Key configured: {'Yes' if self.api_key else 'No'}")
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                print("Rewrite Engine - Gemini model initialized successfully")
            except Exception as e:
                print(f"Rewrite Engine - Error initializing Gemini model: {e}")
                self.model = None
    
    def rewrite_clauses(self, clauses: List[str]) -> Optional[List[str]]:
        """
        Rewrite risky clauses to be safer and more balanced
        
        Args:
            clauses: List of risky clause texts to rewrite
            
        Returns:
            List of rewritten clauses, or None if OpenAI is not configured
        """
        if not self.model:
            return None
        
        if not clauses:
            return []
        
        try:
            # Batch process multiple clauses in a single API call to minimize costs
            prompt = self._build_rewrite_prompt(clauses)
            
            response = self.model.generate_content(prompt)
            
            # Parse the response
            rewritten_text = response.text
            rewrites = self._parse_rewrites(rewritten_text, len(clauses))
            
            return rewrites
        
        except Exception as e:
            print(f"Error rewriting clauses: {e}")
            return None
    
    def _build_rewrite_prompt(self, clauses: List[str]) -> str:
        """Build prompt for batch rewriting"""
        prompt = "You are a legal expert helping to rewrite contract clauses to be more balanced and fair to both parties. "
        prompt += "Provide clear, concise alternatives that protect both sides.\n\n"
        prompt += "Please rewrite the following contract clauses to be more balanced and fair. "
        prompt += "For each clause, provide a safer alternative that protects both parties.\n\n"
        
        for i, clause in enumerate(clauses, 1):
            prompt += f"CLAUSE {i}:\n{clause}\n\n"
        
        prompt += "Provide rewrites in this format:\n"
        prompt += "REWRITE 1: [your rewrite]\n"
        prompt += "REWRITE 2: [your rewrite]\n"
        prompt += "etc."
        
        return prompt
    
    def _parse_rewrites(self, response_text: str, expected_count: int) -> List[str]:
        """Parse the AI response into individual rewrites"""
        rewrites = []
        
        # Split by "REWRITE X:" pattern
        import re
        parts = re.split(r'REWRITE \d+:', response_text)
        
        # Skip the first part (before first REWRITE marker)
        for part in parts[1:]:
            rewrite = part.strip()
            if rewrite:
                rewrites.append(rewrite)
        
        # If parsing failed, return the whole response as a single rewrite
        if len(rewrites) == 0 and response_text.strip():
            rewrites.append(response_text.strip())
        
        # Ensure we have the right number of rewrites (pad with empty if needed)
        while len(rewrites) < expected_count:
            rewrites.append("Unable to generate rewrite for this clause.")
        
        return rewrites[:expected_count]
