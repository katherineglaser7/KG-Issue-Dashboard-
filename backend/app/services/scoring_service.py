"""
Scoring service for calculating ticket confidence scores.

This module analyzes GitHub issues and calculates a confidence score indicating
how well-defined and safe a ticket is for development.

FOUR SCORING DIMENSIONS (each 0-25 points, total 0-100):
1. Requirement Clarity - Is the issue well-specified?
2. Blast Radius - How contained is the change?
3. System Sensitivity - Does this touch critical systems?
4. Testability - Can we verify the fix?

Each dimension returns a score and a list of factors explaining the score.
This makes the scoring auditable and explainable to users.

To modify scoring logic:
1. Adjust the scoring methods for each dimension
2. Update factor descriptions to be clear and actionable
3. Ensure factors use format "Description (+N)" or "Description (-N)"
"""

import re
from typing import Tuple
from app.schemas.models import (
    ConfidenceScore, ConfidenceBreakdown, ScoreFactors, TicketAnalysis
)
from app.config import Settings


class ScoringService:
    """Service for calculating confidence scores and analyzing tickets."""
    
    def __init__(self, settings: Settings):
        """Initialize with application settings."""
        self.settings = settings
    
    def analyze_ticket(self, issue: dict) -> TicketAnalysis:
        """
        Perform full analysis of a ticket including scoring, root issue, and action plan.
        
        Args:
            issue: GitHub issue dictionary with title, body, labels fields
        
        Returns:
            TicketAnalysis with root_issue, action_plan, and confidence_score
        """
        body = issue.get("body", "") or ""
        title = issue.get("title", "") or ""
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        
        confidence_score = self._calculate_confidence_score(body, title, labels)
        root_issue = self._extract_root_issue(body)
        action_plan = self._generate_action_plan(body)
        
        return TicketAnalysis(
            root_issue=root_issue,
            action_plan=action_plan,
            confidence_score=confidence_score,
        )
    
    def _calculate_confidence_score(self, body: str, title: str, labels: list[str]) -> ConfidenceScore:
        """Calculate confidence score with detailed breakdown."""
        requirement_clarity = self._score_requirement_clarity(body, title)
        blast_radius = self._score_blast_radius(body, labels)
        system_sensitivity = self._score_system_sensitivity(body)
        testability = self._score_testability(body)
        
        total = (
            requirement_clarity.score + 
            blast_radius.score + 
            system_sensitivity.score + 
            testability.score
        )
        
        return ConfidenceScore(
            total=total,
            breakdown=ConfidenceBreakdown(
                requirement_clarity=requirement_clarity,
                blast_radius=blast_radius,
                system_sensitivity=system_sensitivity,
                testability=testability,
            )
        )
    
    def _score_requirement_clarity(self, body: str, title: str) -> ScoreFactors:
        """
        Score requirement clarity (0-25 points).
        Question: Is the issue well-specified?
        """
        score = 10
        factors = []
        
        has_sections = "## Description" in body or "## Requirements" in body
        if has_sections:
            score += 5
            factors.append("Has markdown sections (+5)")
        
        has_acceptance = "## Acceptance Criteria" in body or "definition of done" in body.lower()
        if has_acceptance:
            score += 5
            factors.append("Has acceptance criteria (+5)")
        
        if len(body) > 200:
            score += 3
            factors.append("Detailed description (+3)")
        
        file_pattern = r'\.(py|ts|js|tsx|jsx|css|html)\b'
        if re.search(file_pattern, body):
            score += 2
            factors.append("Specifies files to modify (+2)")
        
        if not body or len(body) < 50:
            score -= 5
            factors.append("Empty or minimal description (-5)")
        
        is_vague_title = len(title) < 30 and title.lower() in ["bug", "issue", "fix", "problem", "error"]
        if is_vague_title:
            score -= 3
            factors.append("Vague title (-3)")
        
        score = max(0, min(25, score))
        return ScoreFactors(score=score, factors=factors)
    
    def _score_blast_radius(self, body: str, labels: list[str]) -> ScoreFactors:
        """
        Score blast radius (0-25 points).
        Question: How contained is the change?
        """
        score = 20
        factors = []
        
        file_pattern = r'`[^`]+\.(py|js|ts|tsx|jsx|css|html)`'
        files_mentioned = re.findall(file_pattern, body)
        file_count = len(files_mentioned)
        
        if file_count <= 1:
            score += 5
            factors.append("Single file or no files mentioned (+5)")
        elif file_count > 2:
            penalty = (file_count - 2) * 3
            score -= penalty
            factors.append(f"Multiple files mentioned ({file_count}) (-{penalty})")
        
        label_names_lower = [lab.lower() for lab in labels]
        if "bug" in label_names_lower or "fix" in label_names_lower:
            score += 3
            factors.append("Bug/fix label - usually contained (+3)")
        
        body_lower = body.lower()
        if "refactor" in body_lower or "restructure" in body_lower:
            score -= 5
            factors.append("Contains refactor/restructure (-5)")
        
        if " all " in body_lower or " every " in body_lower:
            score -= 3
            factors.append("Broad scope (all/every) (-3)")
        
        dir_pattern = r'(/[a-zA-Z_]+){2,}'
        dirs_mentioned = re.findall(dir_pattern, body)
        if len(dirs_mentioned) > 1:
            score -= 5
            factors.append("Mentions multiple directories (-5)")
        
        score = max(0, min(25, score))
        return ScoreFactors(score=score, factors=factors)
    
    def _score_system_sensitivity(self, body: str) -> ScoreFactors:
        """
        Score system sensitivity (0-25 points).
        Question: Does this touch critical systems?
        """
        score = 20
        factors = []
        body_lower = body.lower()
        
        critical_keywords = {
            "auth|authentication|login|password|token": ("authentication", 7),
            "payment|billing|stripe|subscription": ("payment/billing", 7),
            "database|migration|schema": ("database/migration", 5),
            "delete|remove|drop": ("delete/remove operations", 5),
            "dependency|package|upgrade": ("dependency changes", 3),
            "api|endpoint": ("API changes", 3),
        }
        
        found_critical = False
        for pattern, (name, penalty) in critical_keywords.items():
            if re.search(pattern, body_lower):
                score -= penalty
                factors.append(f"Touches {name} (-{penalty})")
                found_critical = True
        
        if not found_critical:
            score += 5
            factors.append("No critical system keywords (+5)")
        
        if "non-breaking" in body_lower or "backwards compatible" in body_lower:
            score += 3
            factors.append("Explicitly non-breaking (+3)")
        
        score = max(0, min(25, score))
        return ScoreFactors(score=score, factors=factors)
    
    def _score_testability(self, body: str) -> ScoreFactors:
        """
        Score testability (0-25 points).
        Question: Can we verify the fix?
        """
        score = 15
        factors = []
        body_lower = body.lower()
        
        has_error = bool(re.search(r'error|exception|traceback|stack trace', body_lower))
        if has_error:
            score += 5
            factors.append("Contains error message/stack trace (+5)")
        
        if "test" in body_lower:
            score += 5
            factors.append("Mentions testing (+5)")
        
        if "steps to reproduce" in body_lower or "reproduction" in body_lower:
            score += 3
            factors.append("Has steps to reproduce (+3)")
        
        func_pattern = r'`[a-zA-Z_][a-zA-Z0-9_]*\(`|def [a-zA-Z_]|function [a-zA-Z_]|class [A-Z]'
        if re.search(func_pattern, body):
            score += 2
            factors.append("References specific function/class (+2)")
        
        if "sometimes" in body_lower or "intermittent" in body_lower:
            score -= 5
            factors.append("Intermittent issue (-5)")
        
        if "not sure" in body_lower or "might be" in body_lower:
            score -= 3
            factors.append("Uncertainty in description (-3)")
        
        score = max(0, min(25, score))
        return ScoreFactors(score=score, factors=factors)
    
    def _extract_root_issue(self, body: str) -> str:
        """
        Extract the root issue from the ticket body.
        
        Priority:
        1. First 1-2 sentences from ## Description section
        2. First paragraph of body (up to 200 chars)
        3. Default message if body is empty
        """
        if not body or len(body.strip()) < 10:
            return "Insufficient detail - please add description"
        
        desc_match = re.search(r'## Description\s*\n(.*?)(?=\n##|\Z)', body, re.DOTALL | re.IGNORECASE)
        if desc_match:
            desc_text = desc_match.group(1).strip()
            sentences = re.split(r'(?<=[.!?])\s+', desc_text)
            root = ' '.join(sentences[:2]).strip()
            if root:
                return root[:300] if len(root) > 300 else root
        
        first_para = body.split('\n\n')[0].strip()
        first_para = re.sub(r'^#+\s*', '', first_para)
        if first_para:
            return first_para[:200] if len(first_para) > 200 else first_para
        
        return "Insufficient detail - please add description"
    
    def _generate_action_plan(self, body: str) -> list[str]:
        """
        Generate an action plan from the ticket body.
        
        Priority:
        1. Use numbered lists from body if found (max 4 items)
        2. Generate based on context (files mentioned, testing, etc.)
        """
        numbered_items = re.findall(r'^\s*\d+\.\s+(.+)$', body, re.MULTILINE)
        if numbered_items:
            return [item.strip() for item in numbered_items[:4]]
        
        plan = []
        
        file_pattern = r'`([^`]+\.(py|js|ts|tsx|jsx|css|html))`'
        files = re.findall(file_pattern, body)
        for file_match in files[:2]:
            plan.append(f"Modify {file_match[0]}")
        
        plan.append("Implement fix")
        
        if "test" in body.lower():
            plan.append("Add/update tests")
        
        plan.append("Verify solution")
        
        return plan


def get_scoring_service(settings: Settings) -> ScoringService:
    """Factory function for dependency injection."""
    return ScoringService(settings)
