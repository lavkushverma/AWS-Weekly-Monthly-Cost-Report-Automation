import os
import csv
import io
import boto3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from email.message import EmailMessage

ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME", "Omni_Channel")
CE_REGION = os.environ.get("CE_REGION", "us-east-1")
SES_REGION = os.environ.get("SES_REGION", "ap-south-1")
FROM_EMAIL = os.environ["FROM_EMAIL"]
TO_EMAILS = [x.strip() for x in os.environ["TO_EMAILS"].split(",") if x.strip()]
LINKED_ACCOUNT_ID = os.environ.get("LINKED_ACCOUNT_ID", "").strip()
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
METRIC = os.environ.get("METRIC", "UnblendedCost")

ce = boto3.client("ce", region_name=CE_REGION)
ses = boto3.client("ses", region_name=SES_REGION)

def get_previous_week():
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    current_monday = today - timedelta(days=today.weekday())
    start = current_monday - timedelta(days=7)
    end_exclusive = current_monday
    return start.isoformat(), end_exclusive.isoformat()

def get_cost_data(start, end_exclusive):
    request = {
        "TimePeriod": {"Start": start, "End": end_exclusive},
        "Granularity": "DAILY",
        "Metrics": [METRIC],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]
    }
    if LINKED_ACCOUNT_ID:
        request["Filter"] = {
            "Dimensions": {
                "Key": "LINKED_ACCOUNT",
                "Values": [LINKED_ACCOUNT_ID]
            }
        }

    daily = {}
    next_token = None
    while True:
        if next_token:
            request["NextPageToken"] = next_token
        response = ce.get_cost_and_usage(**request)

        for result in response.get("ResultsByTime", []):
            day = result["TimePeriod"]["Start"]
            daily.setdefault(day, {})
            for group in result.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"][METRIC]["Amount"])
                daily[day][service] = amount

        next_token = response.get("NextPageToken")
        if not next_token:
            break
    return daily

def format_date(iso_date):
    d = date.fromisoformat(iso_date)
    return f"{d.day}/{d.month}/{d.year}"

def build_transposed_csv(daily):
    days = sorted(daily.keys())
    services = set()
    for values in daily.values():
        services.update(values.keys())

    totals = {
        service: sum(daily.get(day, {}).get(service, 0.0) for day in days)
        for service in services
    }
    services = sorted(services, key=lambda service: totals[service], reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Service", "Service total"] + [format_date(day) for day in days])

    for service in services:
        row = [service, f"{totals[service]:.9f}"]
        for day in days:
            row.append(f"{daily.get(day, {}).get(service, 0.0):.9f}")
        writer.writerow(row)

    total = sum(totals.values())
    total_row = ["Total costs", f"{total:.9f}"]
    for day in days:
        total_row.append(f"{sum(daily.get(day, {}).values()):.9f}")
    writer.writerow(total_row)

    return output.getvalue()

def send_report(filename, csv_text, start, end_exclusive):
    end_inclusive = date.fromisoformat(end_exclusive) - timedelta(days=1)

    message = EmailMessage()
    message["Subject"] = f"{ACCOUNT_NAME} - Weekly Cost Report ({start} to {end_inclusive.isoformat()})"
    message["From"] = FROM_EMAIL
    message["To"] = ", ".join(TO_EMAILS)
    message.set_content(
        f"Dear Team,\n\n"
        f"Please find attached the {ACCOUNT_NAME} weekly AWS cost report.\n\n"
        f"Billing period: {start} to {end_inclusive.isoformat()}\n"
        f"Period: Monday to Sunday\n\n"
        f"Regards,\nAWS Cost Reporting"
    )
    message.add_attachment(
        csv_text.encode("utf-8"),
        maintype="text",
        subtype="csv",
        filename=filename
    )

    ses.send_raw_email(
        Source=FROM_EMAIL,
        Destinations=TO_EMAILS,
        RawMessage={"Data": message.as_bytes()}
    )

def lambda_handler(event, context):
    start, end_exclusive = get_previous_week()
    daily = get_cost_data(start, end_exclusive)
    csv_text = build_transposed_csv(daily)

    end_inclusive = date.fromisoformat(end_exclusive) - timedelta(days=1)
    filename = f"{ACCOUNT_NAME}_Weekly_Cost_Report_{start}_to_{end_inclusive.isoformat()}.csv"

    send_report(filename, csv_text, start, end_exclusive)

    return {
        "statusCode": 200,
        "account": ACCOUNT_NAME,
        "period": f"{start} to {end_inclusive.isoformat()}",
        "filename": filename,
        "message": "Weekly Monday-to-Sunday cost report emailed successfully."
    }
