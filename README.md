# Omni Channel AWS Weekly Cost Report

Automated AWS cost reporting for the `Omni_Channel` workload.

The solution runs every Monday, retrieves the **previous Monday-Sunday** AWS cost data from Cost Explorer, transposes the data by service and date, creates a CSV attachment in Lambda memory, and sends it through Amazon SES.

## Architecture

```text
EventBridge Scheduler
        |
        v
AWS Lambda
        |
        +---- Cost Explorer API
        |
        +---- CSV generated in Lambda memory
        |
        v
Amazon SES
        |
        v
Email recipients
```

**No S3 bucket is required.**

## Report format

The CSV contains:

```text
Service,Service total,05/10/2026,06/10/2026,...
Amazon EC2,...
Amazon S3,...
Amazon Bedrock,...
Total costs,...
```

Services are sorted by total cost in descending order.

## Repository structure

```text
omni-channel-weekly-cost-report/
├── README.md
├── .gitignore
├── lambda/
│   └── lambda_function.py
├── iam/
│   ├── lambda-execution-policy.json
│   └── scheduler-trust-policy.json
└── scheduler/
    └── scheduler-invoke-policy.json
```

## Prerequisites

- AWS Lambda
- Amazon EventBridge Scheduler
- AWS Cost Explorer enabled
- Amazon SES sender email verified
- SES production access, or all recipients verified while SES is in sandbox
- IAM permissions for Cost Explorer and SES

## Lambda configuration

### Runtime

- Python 3.12
- Architecture: x86_64
- Handler: `lambda_function.lambda_handler`
- Memory: 512 MB
- Timeout: 1 minute
- VPC: **Do not attach a VPC** unless required by your environment.

Boto3 is included in the standard AWS Lambda Python runtime, so no third-party dependency is required.

### Environment variables

```text
ACCOUNT_NAME=Omni_Channel
FROM_EMAIL=verified-sender@example.com
TO_EMAILS=recipient1@example.com,recipient2@example.com
SES_REGION=ap-south-1
CE_REGION=us-east-1
TIMEZONE=Asia/Kolkata
METRIC=UnblendedCost
```

If the Lambda runs in a management/Landing Zone account and should report only the Omni member account, also set:

```text
LINKED_ACCOUNT_ID=123456789012
```

If Lambda runs directly in the Omni account, leave `LINKED_ACCOUNT_ID` empty.

## IAM permissions

Attach `iam/lambda-execution-policy.json` to the Lambda execution role.

Also attach the AWS managed policy:

```text
arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

The custom policy grants only:

- `ce:GetCostAndUsage`
- `ses:SendRawEmail`

## EventBridge Scheduler

Create a recurring EventBridge Scheduler schedule:

```text
Name: Omni_Channel_Weekly_Cost_Report
Schedule: 0 10 ? * MON *
Timezone: Asia/Kolkata
Flexible time window: OFF
Target: Omni_Channel_Cost_Report Lambda
Payload: {}
```

The scheduler invokes the Lambda every Monday at 10:00 AM IST.

The Lambda automatically calculates the previous Monday-Sunday period.

Example:

```text
Run date: Monday, 12 Oct 2026
Report: Monday, 05 Oct 2026 - Sunday, 11 Oct 2026
```

Give the Scheduler execution role permission to invoke the Lambda using `scheduler/scheduler-invoke-policy.json`.

## Deploy Lambda with AWS CLI

Create a deployment ZIP:

```bash
cd lambda
zip -j ../omni-channel-weekly-cost-report.zip lambda_function.py
cd ..
```

Create the Lambda function:

```bash
aws lambda create-function \
  --function-name Omni_Channel_Cost_Report \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role arn:aws:iam::<ACCOUNT_ID>:role/Omni_Channel_Cost_Report_Lambda_Role \
  --zip-file fileb://omni-channel-weekly-cost-report.zip \
  --timeout 60 \
  --memory-size 512 \
  --region ap-south-1
```

Update code later:

```bash
aws lambda update-function-code \
  --function-name Omni_Channel_Cost_Report \
  --zip-file fileb://omni-channel-weekly-cost-report.zip \
  --region ap-south-1
```

## Test Lambda manually

Test event:

```json
{}
```

CLI:

```bash
aws lambda invoke \
  --function-name Omni_Channel_Cost_Report \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --region ap-south-1 \
  response.json

cat response.json
```

Expected response:

```json
{
  "statusCode": 200,
  "account": "Omni_Channel",
  "period": "YYYY-MM-DD to YYYY-MM-DD",
  "filename": "Omni_Channel_Weekly_Cost_Report_YYYY-MM-DD_to_YYYY-MM-DD.csv",
  "message": "Weekly Monday-to-Sunday cost report emailed successfully."
}
```

## Git commands

```bash
git init
git add .
git commit -m "Add Omni Channel weekly AWS cost report"
git branch -M main
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

## Security notes

- Do **not** commit AWS access keys, secret keys, SMTP credentials, SES credentials, or real passwords.
- Do not hard-code email addresses if they are sensitive; use Lambda environment variables.
- Keep the Lambda role least-privilege.
- Do not put AWS account IDs or internal infrastructure details into public repositories unless approved.
- If the repository is public, review all files before pushing.

## Cost notes

This design avoids S3 storage and uses Lambda, EventBridge Scheduler, Cost Explorer API, and SES. AWS service pricing and free-tier eligibility can change, so review current AWS pricing for your account before treating the solution as permanently free.

## License

Internal use. Add your organization's approved license before publishing publicly.
