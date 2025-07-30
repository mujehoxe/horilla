#!/bin/bash

echo "🔍 Monitoring GitHub Actions workflow..."
echo "Repository: mujehoxe/horilla"
echo "Workflow: Validate, Test and Deploy"
echo "=================================="

# Function to check workflow status
check_workflow() {
    echo "⏰ $(date): Checking workflow status..."
    
    # Try to get workflow runs
    RUNS=$(gh run list --workflow=validate.yml --limit 1 --json status,conclusion,name,headBranch,createdAt,url 2>/dev/null)
    
    if [ -n "$RUNS" ] && [ "$RUNS" != "[]" ]; then
        echo "📋 Latest workflow run:"
        echo "$RUNS" | jq -r '.[0] | "Status: \(.status), Conclusion: \(.conclusion // "N/A"), Branch: \(.headBranch), Created: \(.createdAt)"'
        echo "$RUNS" | jq -r '.[0] | "URL: \(.url)"'
        
        STATUS=$(echo "$RUNS" | jq -r '.[0].status')
        CONCLUSION=$(echo "$RUNS" | jq -r '.[0].conclusion // empty')
        
        if [ "$STATUS" = "completed" ]; then
            if [ "$CONCLUSION" = "success" ]; then
                echo "✅ Workflow completed successfully!"
                return 0
            else
                echo "❌ Workflow failed with conclusion: $CONCLUSION"
                echo "🔗 Check logs at: $(echo "$RUNS" | jq -r '.[0].url')"
                return 1
            fi
        else
            echo "🔄 Workflow is still running..."
        fi
    else
        echo "⏳ No workflow runs found yet..."
    fi
    
    return 2  # Continue monitoring
}

# Monitor for up to 20 minutes (40 checks, 30 seconds each)
for i in {1..40}; do
    check_workflow
    RESULT=$?
    
    if [ $RESULT -eq 0 ]; then
        echo "🎉 Monitoring completed - workflow succeeded!"
        exit 0
    elif [ $RESULT -eq 1 ]; then
        echo "💥 Monitoring completed - workflow failed!"
        exit 1
    fi
    
    echo "⏱️  Waiting 30 seconds before next check... ($i/40)"
    sleep 30
    echo ""
done

echo "⏰ Monitoring timeout reached (20 minutes)"
echo "🔗 Please check manually at: https://github.com/mujehoxe/horilla/actions"
exit 2
