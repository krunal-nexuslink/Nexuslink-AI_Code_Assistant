#!/usr/bin/env python3
"""
CLI tool for AI Code Updater
Usage: python cli.py --repo https://github.com/user/repo --prompt "Add docstrings to all functions"
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from github_service import GitHubService
from claude_service import ClaudeService

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Update GitHub repository code using AI"
    )
    parser.add_argument(
        "--repo", "-r",
        required=True,
        help="GitHub repository URL (e.g., https://github.com/user/repo)"
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Instruction for code changes (e.g., 'Add error handling')"
    )
    parser.add_argument(
        "--base-branch", "-b",
        default="main",
        help="Base branch to create new branch from (default: main)"
    )
    parser.add_argument(
        "--new-branch", "-n",
        help="Name for new branch (auto-generated if not provided)"
    )
    parser.add_argument(
        "--pattern",
        help="File pattern to filter (e.g., '*.py', '*.js')"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview changes without committing"
    )
    parser.add_argument(
        "--create-file",
        help="Create a new file instead of updating existing ones (e.g., 'README.md')"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm without prompting"
    )
    
    args = parser.parse_args()
    
    # Check environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not github_token:
        print("Error: GITHUB_TOKEN not set in environment")
        print("Get a token at: https://github.com/settings/tokens")
        sys.exit(1)
    
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY not set in environment")
        print("Get a key at: https://console.anthropic.com/")
        sys.exit(1)
    
    # Initialize services
    github_service = GitHubService(github_token)
    claude_service = ClaudeService(anthropic_key)
    
    try:
        # Parse repo URL
        owner, repo = github_service.parse_repo_url(args.repo)
        print(f"Repository: {owner}/{repo}")
        
        # Generate branch name
        new_branch = args.new_branch or f"ai-update-{github_service.generate_timestamp()}"
        
        # Fetch files
        print(f"\nFetching files from {args.base_branch}...")
        files = github_service.get_repository_files(owner, repo, args.base_branch)
        
        if args.pattern:
            files = [f for f in files if f["path"].endswith(args.pattern.replace("*", ""))]
            print(f"Filtered to {len(files)} files matching '{args.pattern}'")
        else:
            print(f"Found {len(files)} files")
        
        # Generate changes
        print(f"\nGenerating changes with prompt: '{args.prompt}'")
        print("Processing files...")
        
        file_changes = []
        
        for i, file in enumerate(files, 1):
            if not file.get("content"):
                continue
                
            print(f"  [{i}/{len(files)}] {file['path']}...", end=" ")
            
            updated_content = claude_service.generate_code_update(
                file_path=file["path"],
                current_content=file["content"],
                prompt=args.prompt
            )
            
            if updated_content and updated_content != file["content"]:
                file_changes.append({
                    "path": file["path"],
                    "content": updated_content,
                    "sha": file["sha"]
                })
                print("✓ changed")
            else:
                print("✗ no change")
        
        # Check if we need to create a new file
        if args.create_file:
            print(f"\n📝 Creating new file: {args.create_file}")
            print("Analyzing project structure...")
            
            new_file_content = claude_service.generate_new_file(
                file_path=args.create_file,
                project_files=files,
                prompt=args.prompt
            )
            
            if new_file_content:
                file_changes.append({
                    "path": args.create_file,
                    "content": new_file_content,
                    "sha": None  # New file doesn't have a SHA
                })
                print(f"✓ Generated {args.create_file}")
            else:
                print(f"✗ Failed to generate {args.create_file}")
                sys.exit(1)
        
        if not file_changes:
            print("\nNo files were modified by the AI.")
            sys.exit(0)
        
        print(f"\n{len(file_changes)} files will be updated")
        
        if args.preview:
            print("\nPreview mode - no changes committed")
            print("\nFiles that would be changed:")
            for change in file_changes:
                print(f"  - {change['path']}")
            sys.exit(0)
        
        # Confirm before proceeding (unless --yes flag is used)
        if not args.yes:
            confirm = input(f"\nCreate branch '{new_branch}' and commit changes? [y/N]: ")
            if confirm.lower() != 'y':
                print("Aborted.")
                sys.exit(0)
        else:
            print(f"\nAuto-confirming creation of branch '{new_branch}'")
        
        # Create branch
        print(f"\nCreating branch: {new_branch}")
        github_service.create_branch(owner, repo, new_branch, args.base_branch)
        
        # Create commit
        print("Creating commit...")
        commit_sha = github_service.create_commit(
            owner=owner,
            repo=repo,
            branch=new_branch,
            message=f"AI Update: {args.prompt[:50]}{'...' if len(args.prompt) > 50 else ''}",
            file_changes=file_changes
        )
        
        print(f"\n✅ Success!")
        print(f"Branch: {new_branch}")
        print(f"Commit: {commit_sha[:7]}")
        print(f"Files changed: {len(file_changes)}")
        print(f"\nView changes: https://github.com/{owner}/{repo}/compare/{new_branch}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
