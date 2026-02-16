import anthropic
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ActionType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class FileAction:
    action: ActionType
    path: str
    reason: str
    current_content: Optional[str] = None


class PlanningService:
    """
    Two-phase planning service:
    Phase 1: Analyze repository and create action plan
    Phase 2: Execute the plan
    """
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
    
    def create_action_plan(
        self,
        user_prompt: str,
        repository_files: List[Dict],
        repo_metadata: Dict
    ) -> List[FileAction]:
        """
        Phase 1: Analyze the repository and create a plan of actions.
        
        Returns a list of FileAction objects describing what needs to be done.
        """
        # Build repository context
        file_list = "\n".join([f"- {f['path']}" for f in repository_files])
        
        # Sample some file contents for context (first 500 chars of each)
        file_samples = ""
        for file in repository_files[:8]:  # Limit to 8 files for context
            if file.get("content"):
                content_preview = file["content"][:500]
                file_samples += f"\n\n--- {file['path']} ---\n{content_preview}\n"
        
        system_prompt = f"""You are an expert software architect and engineer. Your task is to analyze a user's request and create a detailed action plan for modifying a codebase.

REPOSITORY STRUCTURE:
{file_list}

SAMPLE FILE CONTENTS:
{file_samples}

REPOSITORY METADATA:
- Owner: {repo_metadata.get('owner', 'unknown')}
- Repo: {repo_metadata.get('repo', 'unknown')}
- Default Branch: {repo_metadata.get('default_branch', 'main')}

USER REQUEST:
"{user_prompt}"

YOUR TASK:
Analyze the request and create a detailed action plan. You must decide:
1. Which existing files need to be UPDATED
2. Which NEW files need to be CREATED  
3. Which files should be DELETED (if any)

IMPORTANT GUIDELINES:
- Be comprehensive - consider all files that might need changes
- Think about dependencies (e.g., if you add auth, update requirements.txt)
- Consider tests, documentation, configuration files
- Only suggest DELETING files if explicitly requested
- Be specific about what each file needs

RESPONSE FORMAT:
You MUST respond with valid JSON only, in this exact format:
{{
  "plan": [
    {{
      "action": "create",
      "path": "path/to/new/file.py",
      "reason": "Detailed explanation of why this file needs to be created and what it should contain"
    }},
    {{
      "action": "update", 
      "path": "path/to/existing/file.py",
      "reason": "Detailed explanation of what changes are needed in this file"
    }}
  ],
  "summary": "Brief summary of the overall changes"
}}

Respond with JSON only, no markdown, no explanations outside the JSON."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Create an action plan for this request."
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = message.content[0].text
            plan_data = self._extract_json(response_text)
            
            # Convert to FileAction objects
            actions = []
            for item in plan_data.get("plan", []):
                action_type = ActionType(item["action"].lower())
                
                # Find current content if updating
                current_content = None
                if action_type == ActionType.UPDATE:
                    for file in repository_files:
                        if file["path"] == item["path"]:
                            current_content = file.get("content")
                            break
                
                actions.append(FileAction(
                    action=action_type,
                    path=item["path"],
                    reason=item["reason"],
                    current_content=current_content
                ))
            
            return actions
            
        except Exception as e:
            print(f"Error creating action plan: {str(e)}")
            # Fallback: try to do something reasonable
            return self._fallback_plan(user_prompt, repository_files)
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from text, handling markdown code blocks"""
        # Try to find JSON in markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        return json.loads(text)
    
    def _fallback_plan(self, prompt: str, files: List[Dict]) -> List[FileAction]:
        """Fallback plan if AI fails"""
        actions = []
        
        # Check if prompt mentions creating a file
        if "readme" in prompt.lower():
            actions.append(FileAction(
                action=ActionType.CREATE,
                path="README.md",
                reason="Create README as requested"
            ))
        
        # Add updates for existing files
        for file in files:
            if file.get("content"):
                actions.append(FileAction(
                    action=ActionType.UPDATE,
                    path=file["path"],
                    reason=f"Update based on prompt: {prompt[:50]}",
                    current_content=file["content"]
                ))
        
        return actions
    
    def generate_file_content(
        self,
        action: FileAction,
        all_actions: List[FileAction],
        user_prompt: str
    ) -> Optional[str]:
        """
        Phase 2: Generate content for a specific file action.
        """
        try:
            if action.action == ActionType.CREATE:
                return self._generate_new_file(action, all_actions, user_prompt)
            elif action.action == ActionType.UPDATE:
                return self._update_existing_file(action, all_actions, user_prompt)
            elif action.action == ActionType.DELETE:
                return None  # Deletion doesn't need content
            
        except Exception as e:
            print(f"Error generating content for {action.path}: {str(e)}")
            return None
    
    def _generate_new_file(
        self,
        action: FileAction,
        all_actions: List[FileAction],
        user_prompt: str
    ) -> str:
        """Generate content for a new file"""
        
        # Build context about other files being created/modified
        related_files = "\n".join([
            f"- {a.action.value}: {a.path} - {a.reason}"
            for a in all_actions if a.path != action.path
        ])
        
        system_prompt = f"""You are an expert software engineer. Create a new file for a project.

FILE TO CREATE: {action.path}

REASON FOR CREATION:
{action.reason}

USER'S OVERALL REQUEST:
{user_prompt}

OTHER FILES BEING MODIFIED:
{related_files}

IMPORTANT GUIDELINES:
1. Generate complete, production-ready code
2. Follow best practices for the file type and language
3. Include proper imports, error handling, and documentation
4. Ensure consistency with modern coding standards
5. Only return the file content, no markdown code blocks
6. Return ONLY the code - no additional text or explanations

Generate the complete content for {action.path}:"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Create the file {action.path}"
                }
            ]
        )
        
        return self._clean_response(message.content[0].text)
    
    def _update_existing_file(
        self,
        action: FileAction,
        all_actions: List[FileAction],
        user_prompt: str
    ) -> str:
        """Update content of an existing file"""
        
        related_files = "\n".join([
            f"- {a.action.value}: {a.path} - {a.reason}"
            for a in all_actions if a.path != action.path
        ])
        
        system_prompt = f"""You are an expert software engineer. Update an existing file based on the user's request.

FILE TO UPDATE: {action.path}

REASON FOR UPDATE:
{action.reason}

USER'S OVERALL REQUEST:
{user_prompt}

CURRENT FILE CONTENT:
```
{action.current_content}
```

OTHER FILES BEING MODIFIED:
{related_files}

IMPORTANT GUIDELINES:
1. Make only the necessary changes to fulfill the request
2. Preserve the existing structure, style, and patterns
3. Maintain backward compatibility unless breaking changes are required
4. Only return the complete updated file content
5. Return ONLY the code - no markdown code blocks or explanations

Return the complete updated content for {action.path}:"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Update the file {action.path}"
                }
            ]
        )
        
        return self._clean_response(message.content[0].text)
    
    def _clean_response(self, text: str) -> str:
        """Clean up AI response to extract just the code/content"""
        # Remove markdown code block markers
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```python or similar)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        
        return text.strip()
