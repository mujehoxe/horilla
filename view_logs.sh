#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO="mujehoxe/horilla"
WORKFLOW_NAME="Validate, Test and Deploy"

echo -e "${BLUE}📋 Fetching latest workflow logs...${NC}"
echo "Repository: $REPO"
echo "Workflow: $WORKFLOW_NAME"
echo "=================================="

# Get the latest workflow run
run_info=$(gh run list --repo="$REPO" --workflow="$WORKFLOW_NAME" --limit=1 --json status,conclusion,headBranch,createdAt,url,databaseId)

if [ $? -ne 0 ] || [ -z "$run_info" ]; then
    echo -e "${RED}❌ Failed to fetch workflow information${NC}"
    exit 1
fi

# Parse the JSON response
status=$(echo "$run_info" | jq -r '.[0].status // "unknown"')
conclusion=$(echo "$run_info" | jq -r '.[0].conclusion // ""')
branch=$(echo "$run_info" | jq -r '.[0].headBranch // "unknown"')
created_at=$(echo "$run_info" | jq -r '.[0].createdAt // "unknown"')
url=$(echo "$run_info" | jq -r '.[0].url // "unknown"')
run_id=$(echo "$run_info" | jq -r '.[0].databaseId // "unknown"')

echo "📋 Latest workflow run:"
echo "Status: $status, Conclusion: $conclusion, Branch: $branch, Created: $created_at"
echo "URL: $url"
echo "Run ID: $run_id"
echo "=================================="

# Display logs using cat
echo -e "${BLUE}📜 Workflow Logs:${NC}"
echo "=================================="

gh run view "$run_id" --repo="$REPO" --log | cat

echo "=================================="
echo -e "${BLUE}📋 Log display complete${NC}"

if [ "$conclusion" = "success" ]; then
    echo -e "${GREEN}✅ Workflow completed successfully!${NC}"
elif [ "$conclusion" = "failure" ]; then
    echo -e "${RED}❌ Workflow failed${NC}"
elif [ "$status" = "in_progress" ]; then
    echo -e "${YELLOW}🔄 Workflow is still running...${NC}"
else
    echo -e "${YELLOW}ℹ️ Workflow status: $status, conclusion: $conclusion${NC}"
fi
