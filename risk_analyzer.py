import re
from typing import List, Dict
import hashlib

RISK_PATTERNS = [
    {
        "name": "Unlimited Liability",
        "pattern": r"(unlimited liability|without limitation|no limit on damages|liable for all|full liability)",
        "severity": "high",
        "explanation": "This clause may expose you to unlimited financial liability without any cap on damages."
    },
    {
        "name": "Automatic Renewal",
        "pattern": r"(automatically renew|auto-renew|automatic extension|renew automatically)",
        "severity": "medium",
        "explanation": "The contract may automatically renew without your explicit consent, potentially locking you into unwanted terms."
    },
    {
        "name": "Arbitration Clause",
        "pattern": r"(binding arbitration|arbitration agreement|resolve.*arbitration|submit to arbitration)",
        "severity": "medium",
        "explanation": "This clause requires disputes to be resolved through arbitration rather than court, which may limit your legal options."
    },
    {
        "name": "Waiver of Rights",
        "pattern": r"(waive.*rights|waiver of|give up.*rights|surrender.*rights|forfeit.*rights)",
        "severity": "high",
        "explanation": "You may be waiving important legal rights, which could limit your ability to seek remedies."
    },
    {
        "name": "Indemnification",
        "pattern": r"(shall indemnify|agree to indemnify|indemnify.*hold harmless|defend.*indemnify)",
        "severity": "high",
        "explanation": "You may be required to compensate the other party for losses, even those not caused by you."
    },
    {
        "name": "Non-Compete Clause",
        "pattern": r"(non-compete|non compete|shall not compete|refrain from competing|prohibited from competing)",
        "severity": "high",
        "explanation": "This restricts your ability to work in similar fields or industries after termination."
    },
    {
        "name": "Confidentiality Obligations",
        "pattern": r"(confidential information|maintain confidentiality|non-disclosure|NDA|trade secrets)",
        "severity": "medium",
        "explanation": "You may have ongoing obligations to protect confidential information, even after contract termination."
    },
    {
        "name": "Termination Penalties",
        "pattern": r"(early termination.*fee|penalty.*termination|liquidated damages|termination.*penalty)",
        "severity": "high",
        "explanation": "Ending the contract early may result in significant financial penalties."
    },
    {
        "name": "Intellectual Property Transfer",
        "pattern": r"(transfer.*intellectual property|assign.*IP|all rights.*belong|ownership.*work product)",
        "severity": "high",
        "explanation": "You may be transferring ownership of intellectual property or creative work without retaining any rights."
    },
    {
        "name": "Unilateral Modification",
        "pattern": r"(modify.*at.*discretion|change.*without notice|reserve.*right.*modify|unilaterally.*change)",
        "severity": "high",
        "explanation": "The other party can change the terms without your consent or notification."
    },
    {
        "name": "Broad Disclaimers",
        "pattern": r"(as is|without warranty|no warranties|disclaim.*warranties|all warranties.*disclaimed)",
        "severity": "medium",
        "explanation": "The provider disclaims warranties, meaning you may have no recourse if the product or service is defective."
    },
    {
        "name": "Limitation of Liability",
        "pattern": r"(limit.*liability|liability.*limited|not liable for|no liability|exclude.*liability)",
        "severity": "medium",
        "explanation": "The other party limits their liability, potentially capping damages you can recover."
    },
    {
        "name": "Assignment Rights",
        "pattern": r"(may assign|right to assign|transfer.*agreement|assign.*rights|assignment of)",
        "severity": "medium",
        "explanation": "The contract may be transferred to another party without your consent."
    },
    {
        "name": "Governing Law",
        "pattern": r"(governed by.*laws|jurisdiction.*shall be|exclusive jurisdiction|venue.*shall be)",
        "severity": "low",
        "explanation": "Disputes must be resolved under specific laws or in specific jurisdictions, which may be inconvenient."
    },
    {
        "name": "Entire Agreement",
        "pattern": r"(entire agreement|complete agreement|supersedes.*agreements|prior.*agreements.*void)",
        "severity": "low",
        "explanation": "This clause voids all previous agreements or understandings not included in this document."
    },
    {
        "name": "Force Majeure",
        "pattern": r"(force majeure|act of god|beyond.*control|unforeseen circumstances)",
        "severity": "low",
        "explanation": "The contract may be suspended or terminated due to events beyond either party's control."
    },
    {
        "name": "Payment Terms",
        "pattern": r"(payment.*due|non-refundable|no refund|refund.*not.*available|all sales final)",
        "severity": "medium",
        "explanation": "Payment terms may be restrictive, with limited or no refund options."
    },
    {
        "name": "Data Collection",
        "pattern": r"(collect.*data|personal information|user data|tracking|cookies|analytics)",
        "severity": "medium",
        "explanation": "Your personal data may be collected, stored, or shared with third parties."
    },
    {
        "name": "Class Action Waiver",
        "pattern": r"(waive.*class action|no class action|class action.*waived|individual basis only)",
        "severity": "high",
        "explanation": "You cannot join a class action lawsuit and must pursue claims individually."
    },
    {
        "name": "Severability",
        "pattern": r"(severability|severable|invalid.*provision|unenforceable.*provision)",
        "severity": "low",
        "explanation": "If part of the contract is invalid, the rest remains in effect."
    },
    {
        "name": "Notice Requirements",
        "pattern": r"(written notice|notice.*required|provide.*notice|notify.*in writing)",
        "severity": "low",
        "explanation": "Specific notice procedures must be followed, which could affect your ability to exercise rights."
    },
    {
        "name": "Survival Clauses",
        "pattern": r"(survive.*termination|survive expiration|obligations.*continue|remain in effect)",
        "severity": "medium",
        "explanation": "Certain obligations continue even after the contract ends."
    }
]

class RiskAnalyzer:
    """Enhanced rule-based risk detection engine for legal documents"""
    
    def __init__(self):
        self.risk_patterns = RISK_PATTERNS
    
    def analyze(self, text: str) -> List[Dict]:
        """
        Analyze text for risky clauses using pattern matching
        
        Args:
            text: Document text to analyze
            
        Returns:
            List of detected risks with details and unique IDs
        """
        risks = []
        text_lower = text.lower()
        
        sentences = re.split(r'[.!?]\s+', text)
        
        for pattern_info in self.risk_patterns:
            matches = re.finditer(pattern_info["pattern"], text_lower, re.IGNORECASE)
            
            for match in matches:
                match_start = match.start()
                match_end = match.end()
                
                context_start = max(0, match_start - 100)
                context_end = min(len(text), match_end + 100)
                context = text[context_start:context_end].strip()
                
                for sentence in sentences:
                    if match.group(0) in sentence.lower():
                        context = sentence.strip()
                        break
                
                clause_id = hashlib.md5(
                    f"{pattern_info['name']}:{context}".encode()
                ).hexdigest()[:12]
                
                risk = {
                    "id": clause_id,
                    "clause": context,
                    "risk_type": pattern_info["name"],
                    "severity": pattern_info["severity"],
                    "explanation": pattern_info["explanation"],
                    "original_text": match.group(0),
                    "start_position": match_start,
                    "end_position": match_end
                }
                
                if not any(r["id"] == clause_id for r in risks):
                    risks.append(risk)
        
        severity_order = {"high": 0, "medium": 1, "low": 2}
        risks.sort(key=lambda x: severity_order[x["severity"]])
        
        return risks
