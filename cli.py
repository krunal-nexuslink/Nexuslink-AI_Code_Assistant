#!/usr/bin/env python3
"""
CLI tool for AI Code Updater - Two-Phase Planning Approach
Usage: python cli.py --repo https://github.com/user/repo --prompt "Add authentication system"
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from github_service import GitHubService
from planning_service import PlanningService, ActionType

load_dotenv()


def print_plan(actions):
    """Display the action plan in a readable format"""
    print("\n" + "="*60)
    print("📋 ACTION PLAN")
    print("="*60)
    
    creates = [a for a in actions if a.action == ActionType.CREATE]
    updates = [a for a in actions if a.action == ActionType.UPDATE]
    deletes = [a for a in actions if a.action == ActionType.DELETE]
    
    if creates:
        print(f"\n📝 FILES TO CREATE ({len(creates)}):")
        for action in creates:
            print(f"   + {action.path}")
            print(f"     → {action.reason}")
    
    if updates:
        print(f"\n✏️  FILES TO UPDATE ({len(updates)}):")
        for action in updates:
            print(f"   ~ {action.path}")
            print(f"     → {action.reason}")
    
    if deletes:
        print(f"\n🗑️  FILES TO DELETE ({len(deletes)}):")
        for action in deletes:
            print(f"   - {action.path}")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Update GitHub repository code using AI with intelligent planning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Let AI decide what to do
  python cli.py --repo https://github.com/user/repo --prompt "Add authentication system"
  
  # Auto-confirm without prompting
  python cli.py --repo https://github.com/user/repo --prompt "Add tests" --yes
  
  # Preview the plan without executing
  python cli.py --repo https://github.com/user/repo --prompt "Refactor code" --plan-only
        """
    )
    parser.add_argument(
        "--repo", "-r",
        required=True,
        help="GitHub repository URL (e.g., https://github.com/user/repo)"
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="What you want to accomplish (e.g., 'Add JWT authentication')"
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
        "--plan-only",
        action="store_true",
        help="Only show the action plan, don't execute"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm without prompting"
    )
    parser.add_argument(
        "--skip-plan",
        action="store_true",
        help="Skip showing the plan (use with --yes for fully automated mode)"
    )
    
    args = parser.parse_args()
    
    # Check environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not github_token:
        print("❌ Error: GITHUB_TOKEN not set in environment")
        print("Get a token at: https://github.com/settings/tokens")
        sys.exit(1)
    
    if not anthropic_key:
        print("❌ Error: ANTHROPIC_API_KEY not set in environment")
        print("Get a key at: https://console.anthropic.com/")
        sys.exit(1)
    
    # Initialize services
    github_service = GitHubService(github_token)
    planning_service = PlanningService(anthropic_key)
    
    try:
        # Parse repo URL
        owner, repo = github_service.parse_repo_url(args.repo)
        print(f"\n📦 Repository: {owner}/{repo}")
        
        # Generate branch name
        new_branch = args.new_branch or f"ai-update-{github_service.generate_timestamp()}"
        
        # Phase 0: Fetch repository files
        print(f"\n🔍 Phase 0: Fetching repository structure from {args.base_branch}...")
        files = github_service.get_repository_files(owner, repo, args.base_branch)
        print(f"   Found {len(files)} files")
        
        # Phase 1: Create Action Plan
        print(f"\n🧠 Phase 1: Creating action plan...")
        print(f"   Analyzing prompt: '{args.prompt}'")
        
        repo_metadata = {
            "owner": owner,
            "repo": repo,
            "default_branch": args.base_branch
        }
        
        actions = planning_service.create_action_plan(
            user_prompt=args.prompt,
            repository_files=files,
            repo_metadata=repo_metadata
        )
        
        if not actions:
            print("\n❌ No actions planned. The AI couldn't determine what changes to make.")
            sys.exit(1)
        
        # Display the plan
        if not args.skip_plan:
            print_plan(actions)
        
        if args.plan_only:
            print("\n✅ Plan created. Use without --plan-only to execute.")
            sys.exit(0)
        
        # Confirm before proceeding
        if not args.yes:
            confirm = input(f"\nExecute this plan and create branch '{new_branch}'? [y/N]: ")
            if confirm.lower() != 'y':
                print("Aborted.")
                sys.exit(0)
        else:
            if not args.skip_plan:
                print(f"\n✅ Auto-confirming plan execution...")
        
        # Phase 2: Execute Plan
        print(f"\n⚙️  Phase 2: Executing action plan...")
        
        file_changes = []
        
        for i, action in enumerate(actions, 1):
            print(f"\n   [{i}/{len(actions)}] {action.action.value.upper()}: {action.path}")
            
            if action.action == ActionType.DELETE:
                # For deletion, we'd need to handle differently in GitHub API
                print(f"      → Skipping delete (not yet implemented)")
                continue
            
            # Generate content for this action
            content = planning_service.generate_file_content(
                action=action,
                all_actions=actions,
                user_prompt=args.prompt
            )
            
            if content:
                # Find SHA if updating existing file
                file_sha = None
                if action.action == ActionType.UPDATE:
                    for file in files:
                        if file["path"] == action.path:
                            file_sha = file.get("sha")
                            break
                
                file_changes.append({
                    "path": action.path,
                    "content": content,
                    "sha": file_sha
                })
                print(f"      ✓ Generated content ({len(content)} chars)")
            else:
                print(f"      ✗ Failed to generate content")
        
        if not file_changes:
            print("\n❌ No files were generated.")
            sys.exit(1)
        
        # Create branch and commit
        print(f"\n🚀 Creating branch: {new_branch}")
        github_service.create_branch(owner, repo, new_branch, args.base_branch)
        
        print("📤 Committing changes...")
        commit_sha = github_service.create_commit(
            owner=owner,
            repo=repo,
            branch=new_branch,
            message=f"AI Update: {args.prompt[:50]}{'...' if len(args.prompt) > 50 else ''}",
            file_changes=file_changes
        )
        
        # Success!
        print("\n" + "="*60)
        print("✅ SUCCESS!")
        print("="*60)
        print(f"\n📁 Branch: {new_branch}")
        print(f"📝 Commit: {commit_sha[:7]}")
        print(f"📊 Files changed: {len(file_changes)}")
        print(f"\n🔗 View changes:")
        print(f"   https://github.com/{owner}/{repo}/compare/{new_branch}")
        print("\n💡 Next steps:")
        print(f"   1. Review the changes on GitHub")
        print(f"   2. Create a pull request if satisfied")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
