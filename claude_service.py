import anthropic
from typing import Optional


class ClaudeService:
    """Service for interacting with Anthropic Claude API"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet model
    
    def generate_code_update(
        self, 
        file_path: str, 
        current_content: str, 
        prompt: str
    ) -> Optional[str]:
        """
        Generate updated code content using Claude.
        
        Args:
            file_path: Path to the file being edited
            current_content: Current content of the file
            prompt: User's instruction for changes
            
        Returns:
            Updated content or None if no changes needed
        """
        try:
            system_prompt = f"""You are an expert software engineer. Your task is to update code files based on user instructions.

FILE PATH: {file_path}

INSTRUCTION: {prompt}

IMPORTANT GUIDELINES:
1. Only return the updated code content, nothing else (no markdown code blocks, no explanations)
2. If the file doesn't need changes based on the instruction, return the original content unchanged
3. Preserve the file's original structure, indentation, and style
4. Only make changes relevant to the instruction
5. Do not add comments explaining what you changed
6. Return ONLY the code - no additional text, headers, or explanations

Current file content:
```
{current_content}
```

Return the complete updated file content:"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Update this code according to the instruction: {prompt}"
                    }
                ]
            )
            
            # Get the response content
            updated_content = message.content[0].text
            
            # Clean up the response (remove code block markers if present)
            updated_content = self._clean_code_response(updated_content)
            
            return updated_content
            
        except Exception as e:
            print(f"Error generating update for {file_path}: {str(e)}")
            return None
    
    def _clean_code_response(self, content: str) -> str:
        """Clean up Claude's response to extract just the code"""
        # Remove markdown code block markers
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```python or similar)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        
        # Remove leading/trailing whitespace
        return content.strip()
    
    def analyze_code(self, file_path: str, content: str, prompt: str) -> dict:
        """
        Analyze code and determine if changes are needed.
        Returns analysis result with reasoning.
        """
        try:
            system_prompt = f"""You are a code analysis assistant. Analyze the following code and determine if changes are needed based on the instruction.

FILE: {file_path}

INSTRUCTION: {prompt}

CODE:
```
{content[:2000]}
```

Respond in this exact format:
SHOULD_UPDATE: [yes/no]
REASON: [brief explanation of what needs to be changed or why no changes are needed]"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Analyze this code"
                    }
                ]
            )
            
            response = message.content[0].text
            
            # Parse response
            should_update = "SHOULD_UPDATE: yes" in response.lower()
            
            return {
                "should_update": should_update,
                "reason": response
            }
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}")
            return {"should_update": False, "reason": str(e)}
    
    def generate_new_file(
        self, 
        file_path: str, 
        project_files: list,
        prompt: str
    ) -> Optional[str]:
        """
        Generate content for a new file based on project analysis.
        
        Args:
            file_path: Path for the new file (e.g., "README.md")
            project_files: List of all project files with their content
            prompt: User's instruction for what to create
            
        Returns:
            Content for the new file or None if generation fails
        """
        try:
            # Build project context from all files
            project_context = ""
            for file in project_files[:10]:  # Limit to first 10 files for context
                if file.get("content"):
                    project_context += f"\n\n--- {file['path']} ---\n{file['content'][:1000]}"  # Limit content length
            
            system_prompt = f"""You are an expert software engineer. Create a new file for the project based on the existing codebase.

NEW FILE: {file_path}

PROJECT FILES CONTEXT:
{project_context}

INSTRUCTION: {prompt}

IMPORTANT GUIDELINES:
1. Generate complete, production-ready content for the file
2. Make it consistent with the existing codebase style and conventions
3. Only return the file content, nothing else (no markdown code blocks, no explanations)
4. Return ONLY the file content - no additional text, headers, or explanations

Generate the complete content for {file_path}:"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Create the file {file_path} according to this instruction: {prompt}"
                    }
                ]
            )
            
            # Get the response content
            content = message.content[0].text
            
            # Clean up the response (remove code block markers if present)
            content = self._clean_code_response(content)
            
            return content
            
        except Exception as e:
            print(f"Error generating new file {file_path}: {str(e)}")
            return None
