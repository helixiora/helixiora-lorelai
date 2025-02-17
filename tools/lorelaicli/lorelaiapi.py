#! /usr/bin/env python3

"""Query the Lorelai API in the CLI."""

import logging
import requests
import time
import urllib3
import sys
import argparse

# At the top of the file, add these lines to suppress the SSL warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Base URL of the API
# BASE_URL = "https://lorelai.walter.helixiora.com/api/v1"
BASE_URL = "https://localhost:5000/api/v1"
API_KEY = "f2dc2afe431245f93e1398e0468a9ea6"


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


def ask_question(message, access_token, debug=False):
    """Ask a question to the Lorelai API."""
    chat_post_url = f"{BASE_URL}/chat"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

    payload = {"message": message}
    try:
        if debug:
            logging.debug(f"Sending request to {chat_post_url}")
            logging.debug(f"Headers: {headers}")
            logging.debug(f"Payload: {payload}")
        response = requests.post(chat_post_url, json=payload, headers=headers, verify=False)
        if debug:
            logging.debug(f"Response status code: {response.status_code}")
            logging.debug(f"Response headers: {response.headers}")

        if response.status_code == 200:
            data = response.json()
            job_id = data.get("job")
            conversation_id = data.get("conversation_id")
            if debug:
                logging.debug(f"Job ID: {job_id}, Conversation ID: {conversation_id}")

            result = poll_for_result(job_id, conversation_id, access_token, debug)
            if result:
                formatted_result = format_answer(result)
                print(formatted_result)
            else:
                logging.error("Failed to retrieve the result.")
        else:
            logging.error(f"Error {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection error: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def poll_for_result(job_id, conversation_id, access_token, debug=False):
    """Poll for the result of a question."""
    chat_get_url = f"{BASE_URL}/chat"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    params = {"job_id": job_id, "conversation_id": conversation_id}

    if debug:
        logging.debug("Polling for results...")
    try:
        while True:
            response = requests.get(chat_get_url, headers=headers, params=params, verify=False)
            if debug:
                logging.debug(f"Poll response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                result = data.get("result")
                if result:
                    return result
                print(".", end="", flush=True)
                time.sleep(2)
            elif response.status_code == 202:
                print(".", end="", flush=True)
                time.sleep(2)
            else:
                logging.error(f"Error during polling: {response.status_code}: {response.text}")
                return None
    except Exception as e:
        logging.error(f"Error during polling: {e}")
        return None


def mask_sensitive_data(data: str, visible_start: int = 2, visible_end: int = 2) -> str:
    """Mask sensitive data, showing only the first and last few characters.

    Args:
        data: The string to mask
        visible_start: Number of characters to show at start
        visible_end: Number of characters to show at end

    Returns
    -------
        Masked string with only specified characters visible
    """
    if not data or len(data) <= (visible_start + visible_end):
        return "*" * len(data) if data else ""

    return f"{data[:visible_start]}{'*' * (len(data) - visible_start - visible_end)}\
{data[-visible_end:]}"


def get_access_token(api_key, debug=False):
    """Get an access token."""
    auth_url = f"{BASE_URL}/auth/login"
    headers = {
        "Content-Type": "application/json",
    }
    payload = {"email": "walterheck@helixiora.com", "apikey": api_key}

    try:
        if debug:
            masked_key = mask_sensitive_data(api_key)
            logging.debug(f"Authenticating with API key: {masked_key} at {auth_url}")
        response = requests.post(auth_url, json=payload, headers=headers, verify=False)
        if debug:
            logging.debug(f"Auth response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                if debug:
                    logging.debug("Successfully obtained access token")
                return token
            else:
                logging.error("No access token in response")
                return None
        else:
            logging.error(f"Authentication failed: {response.status_code}: {response.text}")
            return None
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection error during authentication: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during authentication: {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the Lorelai API from the command line.")
    parser.add_argument("-q", "--question", help="Question to ask Lorelai")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Configure logging based on debug flag
    log_level = logging.DEBUG if args.debug else logging.ERROR
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        access_token = get_access_token(API_KEY, args.debug)
        if access_token:
            if args.question:
                ask_question(args.question, access_token, args.debug)
            else:
                question = input("\nEnter your question: ")
                ask_question(question, access_token, args.debug)
        else:
            logging.error(
                "Failed to get access token. Please check your credentials and server availability."
            )
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Script error: {e}")
        sys.exit(1)
