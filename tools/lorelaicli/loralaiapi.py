#! /usr/bin/env python3

"""Query the Lorelai API in the CLI."""

import logging
import requests
import time
import urllib3

# At the top of the file, add these lines to suppress the SSL warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Base URL of the API
# BASE_URL = "https://lorelai.walter.helixiora.com/api/v1"
BASE_URL = "https://localhost:5000/api/v1"
API_KEY = "ccb5b555a183bb669078467965ad7ddc"


def format_answer(response_dict):
    """Format the API response into a readable format."""
    answer = response_dict.get("answer", "")

    # Split the answer into main text and sources
    parts = answer.split("### Sources")
    main_text = parts[0].strip()
    sources = parts[1] if len(parts) > 1 else ""

    # Format the output
    formatted_output = f"""
{main_text}

Sources:
{sources}
"""
    return formatted_output


def ask_question(message, access_token):
    """Ask a question to the Lorelai API."""
    chat_post_url = f"{BASE_URL}/chat/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

    payload = {"message": message}
    response = requests.post(chat_post_url, json=payload, headers=headers, verify=False)

    if response.status_code == 200:
        data = response.json()
        job_id = data.get("job")
        conversation_id = data.get("conversation_id")
        logging.info("\nProcessing your question...\n")  # Simplified message

        result = poll_for_result(job_id, conversation_id, access_token)
        if result:
            formatted_result = format_answer(result)
            logging.info(formatted_result)  # Removed extra newlines and "Answer:" prefix
        else:
            logging.info("Failed to retrieve the result.")
    else:
        logging.info(f"Error {response.status_code}: {response.text}")


def poll_for_result(job_id, conversation_id, access_token):
    """Poll for the result of a question."""
    chat_get_url = f"{BASE_URL}/chat/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

    params = {"job_id": job_id, "conversation_id": conversation_id}

    logging.info("Waiting for response", end="", flush=True)  # Initial message
    while True:
        response = requests.get(chat_get_url, headers=headers, params=params, verify=False)
        if response.status_code == 200:
            data = response.json()
            result = data.get("result")
            if result:
                logging.info("\n")  # Clear the progress line
                return result
            logging.info(".", end="", flush=True)  # Show progress
            time.sleep(2)
        elif response.status_code == 202:
            logging.info(".", end="", flush=True)  # Show progress
            time.sleep(2)
        else:
            logging.error(f"\nError {response.status_code}: {response.text}")
            return None


def get_access_token(api_key):
    """Get an access token."""
    auth_url = f"{BASE_URL}/auth/login"
    headers = {
        "Content-Type": "application/json",
    }
    payload = {"email": "walterheck@helixiora.com", "apikey": api_key}
    logging.info(f"Getting access token with API key: {api_key} from {auth_url}")
    response = requests.post(auth_url, json=payload, headers=headers, verify=False)
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        logging.error(f"Error {response.status_code}: {response.text}")
        return None


if __name__ == "__main__":
    # Set logging to only show WARNING and above
    logging.basicConfig(level=logging.WARNING)

    access_token = get_access_token(API_KEY)
    if access_token:
        question = input("\nEnter your question: ")
        ask_question(question, access_token)
    else:
        logging.error("Failed to get access token. Please check your credentials.")
