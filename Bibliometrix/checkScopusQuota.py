#!/usr/bin/env python3
"""
This script checks your Scopus API quota by performing a simple query and printing the following headers:
    X-RateLimit-Limit       : Total quota limit
    X-RateLimit-Remaining   : Number of remaining API calls
    X-RateLimit-Reset       : Epoch time when the quota resets
"""

import requests

# Global configuration
SCOPUS_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Replace with your actual Scopus API key

# Scopus Search API endpoint
url = "https://api.elsevier.com/content/search/scopus"
params = {
    "query": 'TITLE("test")',  # A simple query; any valid query works.
    "rows": 1
}
headers = {
    "X-ELS-APIKey": SCOPUS_API_KEY,
    "Accept": "application/json",
    "User-Agent": "QuotaChecker/1.0 (mailto:your_email@example.com)"
}


def check_scopus_quota():
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            # Retrieve rate limit headers
            rate_limit = response.headers.get("X-RateLimit-Limit", "N/A")
            remaining = response.headers.get("X-RateLimit-Remaining", "N/A")
            reset = response.headers.get("X-RateLimit-Reset", "N/A")

            print("Scopus API Quota Information:")
            print(f"X-RateLimit-Limit       : {rate_limit}")
            print(f"X-RateLimit-Remaining   : {remaining}")
            print(f"X-RateLimit-Reset       : {reset} (Epoch seconds)")
        else:
            print(f"Request failed with status code {response.status_code}")
    except Exception as e:
        print(f"Error during request: {e}")


if __name__ == "__main__":
    check_scopus_quota()
