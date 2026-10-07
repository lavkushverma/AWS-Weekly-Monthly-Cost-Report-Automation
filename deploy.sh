#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="Omni_Channel_Cost_Report"
REGION="ap-south-1"
ROLE_ARN="${ROLE_ARN:?Set ROLE_ARN first, e.g. arn:aws:iam::123456789012:role/Omni_Channel_Cost_Report_Lambda_Role}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

rm -f omni-channel-weekly-cost-report.zip
zip -j omni-channel-weekly-cost-report.zip lambda/lambda_function.py

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://omni-channel-weekly-cost-report.zip \
    --region "$REGION"
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --handler lambda_function.lambda_handler \
    --role "$ROLE_ARN" \
    --zip-file fileb://omni-channel-weekly-cost-report.zip \
    --timeout 60 \
    --memory-size 512 \
    --region "$REGION"
fi

echo "Lambda deployment completed: $FUNCTION_NAME"
