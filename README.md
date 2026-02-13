# AI Code Updater Application

An application that takes a user's GitHub repository and updates code using AI based on prompts.

## Features

- Access GitHub repositories via REST API
- Use Claude AI to generate code changes based on prompts
- Create new branches automatically
- Commit and push changes with appropriate commit messages
- Serverless-friendly (no local git clone needed)

## Architecture

This application uses:
- **GitHub REST API** - For repository operations (fetching files, creating branches, committing changes)
- **Anthropic Claude API** - For AI-powered code generation and editing
- **FastAPI** - Web framework for API endpoints
- **GitHub API Token** - For authentication

## Why REST API over Git Clone?

- Serverless-friendly (works on Vercel, AWS Lambda, etc.)
- No need to install git on the server
- More secure (token-based authentication)
- Faster for small to medium repositories
- No local disk space needed for cloning

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```
GITHUB_TOKEN=your_github_personal_access_token
ANTHROPIC_API_KEY=your_anthropic_api_key
```

3. Run the application:
```bash
python main.py
```

## API Endpoints

### POST /api/update-repo
Update a GitHub repository with AI-generated changes.

**Request Body:**
```json
{
  "repo_url": "https://github.com/username/repo",
  "prompt": "Add error handling to all API endpoints",
  "base_branch": "main",
  "new_branch": "feature/ai-updates"
}
```

**Response:**
```json
{
  "success": true,
  "branch": "feature/ai-updates",
  "commits": 3,
  "files_changed": ["file1.py", "file2.py"],
  "commit_sha": "abc123..."
}
```

## GitHub Token Permissions Required

Your GitHub Personal Access Token needs:
- `repo` - Full control of private repositories
- `read:org` - Read org and team membership (optional)

## How It Works

1. **Fetch Repository Contents** - Uses GitHub API to get file tree and contents
2. **Generate Code Changes** - Sends files + prompt to Claude API
3. **Create Branch** - Creates a new branch from the base branch
4. **Apply Changes** - Creates blobs, tree, and commits via GitHub API
5. **Push Changes** - Updates the new branch reference to the new commit

## License

MIT
