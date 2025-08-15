import os
import requests
import json
import argparse
import time
import re
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

# --- グローバル設定 ---
SENTRY_API_TOKEN = os.environ.get("YOUR_SENTRY_API_TOKEN")
SENTRY_API_BASE_URL = "https://sentry.io/api/0"
RATE_LIMIT_SLEEP = 0.2

def get_from_precedence(args_val, env_var_name):
    """優先順位に従って値を取得するヘルパー関数"""
    if args_val:
        return args_val
    return os.environ.get(env_var_name)

def get_project_slug_from_issue(org_slug, issue_id):
    """Issue情報からProjectのスラッグを取得する"""
    url = f"{SENTRY_API_BASE_URL}/issues/{issue_id}/"
    headers = {"Authorization": f"Bearer {SENTRY_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        project_slug = response.json().get("project", {}).get("slug")
        if not project_slug:
            print(f"Error: Could not find project slug for issue {issue_id}.")
            return None
        return project_slug
    except requests.exceptions.RequestException as e:
        print(f"Error fetching issue details: {e}")
        return None

def get_event_ids_for_issue(issue_id):
    """指定されたIssue IDのすべてのイベントIDをページネーションを考慮して取得する"""
    url = f"{SENTRY_API_BASE_URL}/issues/{issue_id}/events/"
    headers = {"Authorization": f"Bearer {SENTRY_API_TOKEN}"}
    print(f"Getting all event IDs for issue: {issue_id} (handling pagination)...")
    all_event_ids = []
    page_count = 1
    while url:
        print(f"Fetching page {page_count}...")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            all_event_ids.extend([event.get('eventID') for event in data if event.get('eventID')])
            link_header = response.headers.get("Link", "")
            match = re.search(r'<([^>]+)>; rel="next"; results="true"', link_header)
            if match:
                url = match.group(1)
                page_count += 1
            else:
                url = None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching events for issue: {e}")
            url = None
    print(f"Found a total of {len(all_event_ids)} events across {page_count} page(s).")
    return all_event_ids

def get_event_breadcrumbs(org_slug, project_slug, event_id):
    """イベントの詳細を取得し、パンくずリストを返す"""
    url = f"{SENTRY_API_BASE_URL}/projects/{org_slug}/{project_slug}/events/{event_id}/"
    headers = {"Authorization": f"Bearer {SENTRY_API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        event_data = response.json()
        for entry in event_data.get("entries", []):
            if entry.get("type") == "breadcrumbs":
                return entry.get("data", {}).get("values", [])
        return event_data.get("breadcrumbs", {}).get("values", [])
    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code != 404:
            print(f"Warning: Could not fetch details for event {event_id}. Status: {e.response.status_code}")
        return []

def extract_pattern_from_crumb(crumb, regex_pattern):
    """パンくずデータから正規表現でパターンを抽出する"""
    if not crumb:
        return None
    crumb_str = json.dumps(crumb)
    match = re.search(regex_pattern, crumb_str)
    if match:
        if match.groups():
            return match.group(1)
        else:
            return match.group(0)
    return None

def main():
    parser = argparse.ArgumentParser(description="Extract a pattern from breadcrumbs of all events for a given Sentry issue.")
    parser.add_argument("issue_id", help="The ID of the Sentry issue.")
    parser.add_argument("regex", help="The regular expression to search for. Use a capture group () to extract a specific part.")
    parser.add_argument("--organization", help="Sentry organization slug. Can also be set via SENTRY_ORGANIZATION env var.")
    parser.add_argument("--project", help="Sentry project slug. If omitted, it will be derived from the issue. Can also be set via SENTRY_PROJECT env var.")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of events to process (0 for all).")
    args = parser.parse_args()

    if not SENTRY_API_TOKEN:
        print("Error: Sentry API Token is not set. Please check your .env file or YOUR_SENTRY_API_TOKEN environment variable.")
        return

    org_slug = get_from_precedence(args.organization, "SENTRY_ORGANIZATION")
    if not org_slug:
        print("Error: Organization slug is required. Use --organization or set SENTRY_ORGANIZATION.")
        return

    project_slug = get_from_precedence(args.project, "SENTRY_PROJECT")
    if not project_slug:
        print("Project slug not provided, will derive it from the issue...")
        project_slug = get_project_slug_from_issue(org_slug, args.issue_id)
        if not project_slug:
            return

    print(f"Organization: {org_slug}")
    print(f"Project: {project_slug}")
    print(f"Searching in issue '{args.issue_id}' with regex: '{args.regex}'")

    event_ids = get_event_ids_for_issue(args.issue_id)
    if not event_ids:
        return

    events_to_process = event_ids
    if args.limit > 0:
        print(f"\n--- Limiting to the first {args.limit} events. ---")
        events_to_process = event_ids[:args.limit]

    found_items = set()
    for i, event_id in enumerate(events_to_process):
        print(f"Checking event {i+1}/{len(events_to_process)}: {event_id}")
        breadcrumbs = get_event_breadcrumbs(org_slug, project_slug, event_id)
        
        if breadcrumbs:
            for crumb in breadcrumbs:
                extracted_pattern = extract_pattern_from_crumb(crumb, args.regex)
                if extracted_pattern:
                    found_items.add(extracted_pattern)
                    print(f"  -> Found: {extracted_pattern}")

        time.sleep(RATE_LIMIT_SLEEP)

    print("\n----------------------------------------")
    print(f"Search complete. Found {len(found_items)} unique item(s).")
    if found_items:
        print("\nItems found:")
        for item in sorted(found_items):
            print(item)
    print("----------------------------------------")

if __name__ == "__main__":
    main()