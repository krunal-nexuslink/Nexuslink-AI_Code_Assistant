from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv

from github_service import GitHubService
from claude_service import ClaudeService

load_dotenv()

app = FastAPI(title="AI Code Updater", version="1.0.0")

# Mount static files (HTML frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
github_service = GitHubService(os.getenv("GITHUB_TOKEN"))
claude_service = ClaudeService(os.getenv("ANTHROPIC_API_KEY"))


class RepoUpdateRequest(BaseModel):
    repo_url: str
    prompt: str
    base_branch: str = "main"
    new_branch: Optional[str] = None
    file_pattern: Optional[str] = None  # e.g., "*.py" to only update Python files


class RepoUpdateResponse(BaseModel):
    success: bool
    branch: str
    commits: int
    files_changed: List[str]
    commit_sha: str
    message: str


@app.get("/")
async def root():
    return {"message": "AI Code Updater API", "version": "1.0.0", "docs": "/docs", "frontend": "/static/index.html"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "github_token_set": bool(os.getenv("GITHUB_TOKEN")),
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY"))
    }


@app.post("/api/update-repo", response_model=RepoUpdateResponse)
async def update_repository(request: RepoUpdateRequest):
    """
    Update a GitHub repository with AI-generated changes.
    
    - Fetches repository contents
    - Generates code changes using Claude
    - Creates a new branch
    - Commits and pushes changes
    """
    try:
        # Parse repository URL
        owner, repo = github_service.parse_repo_url(request.repo_url)
        
        # Generate branch name if not provided
        new_branch = request.new_branch or f"ai-update-{github_service.generate_timestamp()}"
        
        # Step 1: Get repository contents
        print(f"Fetching repository contents for {owner}/{repo}...")
        files = github_service.get_repository_files(owner, repo, request.base_branch)
        
        if request.file_pattern:
            files = [f for f in files if f["path"].endswith(request.file_pattern.replace("*", ""))]
        
        print(f"Found {len(files)} files to process")
        
        # Step 2: Generate code changes using Claude
        print("Generating code changes with Claude...")
        file_changes = []
        
        for file in files:
            if file.get("content"):
                # Ask Claude to generate updated content
                updated_content = claude_service.generate_code_update(
                    file_path=file["path"],
                    current_content=file["content"],
                    prompt=request.prompt
                )
                
                if updated_content and updated_content != file["content"]:
                    file_changes.append({
                        "path": file["path"],
                        "content": updated_content,
                        "sha": file["sha"]
                    })
                    print(f"  ✓ Updated: {file['path']}")
        
        if not file_changes:
            return RepoUpdateResponse(
                success=False,
                branch=new_branch,
                commits=0,
                files_changed=[],
                commit_sha="",
                message="No changes were made. The AI didn't find any files to update based on your prompt."
            )
        
        # Step 3: Create new branch
        print(f"Creating branch: {new_branch}")
        github_service.create_branch(owner, repo, new_branch, request.base_branch)
        
        # Step 4: Create commit with all changes
        print("Creating commit...")
        commit_sha = github_service.create_commit(
            owner=owner,
            repo=repo,
            branch=new_branch,
            message=f"AI Update: {request.prompt[:50]}{'...' if len(request.prompt) > 50 else ''}",
            file_changes=file_changes
        )
        
        return RepoUpdateResponse(
            success=True,
            branch=new_branch,
            commits=1,
            files_changed=[f["path"] for f in file_changes],
            commit_sha=commit_sha,
            message=f"Successfully created branch '{new_branch}' with {len(file_changes)} file changes"
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/preview-changes")
async def preview_changes(request: RepoUpdateRequest):
    """
    Preview what changes would be made without actually committing them.
    """
    try:
        owner, repo = github_service.parse_repo_url(request.repo_url)
        files = github_service.get_repository_files(owner, repo, request.base_branch)
        
        if request.file_pattern:
            files = [f for f in files if f["path"].endswith(request.file_pattern.replace("*", ""))]
        
        preview_changes = []
        
        for file in files[:10]:  # Limit to 10 files for preview
            if file.get("content"):
                updated_content = claude_service.generate_code_update(
                    file_path=file["path"],
                    current_content=file["content"],
                    prompt=request.prompt
                )
                
                if updated_content and updated_content != file["content"]:
                    preview_changes.append({
                        "path": file["path"],
                        "original": file["content"][:500] + "..." if len(file["content"]) > 500 else file["content"],
                        "updated": updated_content[:500] + "..." if len(updated_content) > 500 else updated_content
                    })
        
        return {
            "files_to_update": len(preview_changes),
            "changes": preview_changes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
