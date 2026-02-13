import requests
import base64
from typing import List, Dict, Tuple
from datetime import datetime


class GitHubService:
    """Service for interacting with GitHub API"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def parse_repo_url(self, repo_url: str) -> Tuple[str, str]:
        """Parse owner and repo from GitHub URL"""
        # Handle different URL formats
        # https://github.com/owner/repo
        # https://github.com/owner/repo.git
        # github.com/owner/repo
        
        repo_url = repo_url.replace("https://", "").replace("http://", "").replace("github.com/", "")
        parts = repo_url.replace(".git", "").split("/")
        
        if len(parts) < 2:
            raise ValueError("Invalid repository URL. Expected format: https://github.com/owner/repo")
        
        return parts[0], parts[1]
    
    def generate_timestamp(self) -> str:
        """Generate timestamp for branch names"""
        return datetime.now().strftime("%Y%m%d-%H%M%S")
    
    def get_repository_files(self, owner: str, repo: str, branch: str = "main") -> List[Dict]:
        """
        Get all files from a repository recursively.
        Returns list of files with their content.
        """
        files = []
        
        # Get the tree recursively
        url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        tree_data = response.json()
        
        for item in tree_data.get("tree", []):
            if item["type"] == "blob":  # Only files, not directories
                # Get file content
                content = self.get_file_content(owner, repo, item["path"], branch)
                if content:
                    files.append({
                        "path": item["path"],
                        "sha": item["sha"],
                        "content": content
                    })
        
        return files
    
    def get_file_content(self, owner: str, repo: str, path: str, branch: str = "main") -> str:
        """Get the content of a specific file"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        data = response.json()
        
        # Decode base64 content
        if "content" in data:
            try:
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            except:
                # Binary file or encoding issue
                return None
        
        return None
    
    def create_branch(self, owner: str, repo: str, new_branch: str, base_branch: str = "main"):
        """Create a new branch from an existing branch"""
        # First, get the SHA of the base branch
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{base_branch}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        base_sha = response.json()["object"]["sha"]
        
        # Create new branch
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs"
        data = {
            "ref": f"refs/heads/{new_branch}",
            "sha": base_sha
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        
        if response.status_code == 422:
            # Branch already exists
            raise ValueError(f"Branch '{new_branch}' already exists")
        
        response.raise_for_status()
        return response.json()
    
    def create_commit(
        self, 
        owner: str, 
        repo: str, 
        branch: str, 
        message: str, 
        file_changes: List[Dict]
    ) -> str:
        """
        Create a commit with multiple file changes.
        Uses the Git Data API to create blobs, tree, and commit.
        """
        # Step 1: Get the current commit SHA for the branch
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        parent_sha = response.json()["object"]["sha"]
        
        # Step 2: Get the current tree
        url = f"{self.base_url}/repos/{owner}/{repo}/git/commits/{parent_sha}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        base_tree_sha = response.json()["tree"]["sha"]
        
        # Step 3: Create blobs for each file change
        tree_entries = []
        for change in file_changes:
            # Create blob
            url = f"{self.base_url}/repos/{owner}/{repo}/git/blobs"
            blob_data = {
                "content": change["content"],
                "encoding": "utf-8"
            }
            response = requests.post(url, json=blob_data, headers=self.headers)
            response.raise_for_status()
            
            blob_sha = response.json()["sha"]
            
            # Add to tree entries
            tree_entries.append({
                "path": change["path"],
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha
            })
        
        # Step 4: Create new tree
        url = f"{self.base_url}/repos/{owner}/{repo}/git/trees"
        tree_data = {
            "base_tree": base_tree_sha,
            "tree": tree_entries
        }
        response = requests.post(url, json=tree_data, headers=self.headers)
        response.raise_for_status()
        
        new_tree_sha = response.json()["sha"]
        
        # Step 5: Create commit
        url = f"{self.base_url}/repos/{owner}/{repo}/git/commits"
        commit_data = {
            "message": message,
            "tree": new_tree_sha,
            "parents": [parent_sha]
        }
        response = requests.post(url, json=commit_data, headers=self.headers)
        response.raise_for_status()
        
        new_commit_sha = response.json()["sha"]
        
        # Step 6: Update branch reference
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        ref_data = {
            "sha": new_commit_sha
        }
        response = requests.patch(url, json=ref_data, headers=self.headers)
        response.raise_for_status()
        
        return new_commit_sha
    
    def get_default_branch(self, owner: str, repo: str) -> str:
        """Get the default branch for a repository"""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get("default_branch", "main")
