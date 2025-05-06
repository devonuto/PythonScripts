#!/usr/bin/env python3
"""
Bing-Spellcheck.py - Script to check spelling using the Bing Spell Check API
https://api.bing.microsoft.com/v7.0/spellcheck
"""

import os
import sys
import json
import logging
import argparse
import requests
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.splitext(os.path.basename(__file__))[0] + '.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_argument_parser():
    """Set up and parse command line arguments."""
    parser = argparse.ArgumentParser(description='Check spelling using Bing Spell Check API')
    parser.add_argument('-t', '--text', type=str, help='Text to check for spelling')
    parser.add_argument('-f', '--file', type=str, help='File containing text to check')
    parser.add_argument('-m', '--mode', type=str, default='proof', 
                        choices=['proof', 'spell'], 
                        help='Mode for spell checking: proof (default) or spell')
    parser.add_argument('-k', '--key', type=str, help='API subscription key. Can also be set via BING_SPELLCHECK_KEY env variable')
    return parser.parse_args()

def check_spelling(text, subscription_key, mode='proof'):
    """
    Send text to Bing Spell Check API and return results
    
    Args:
        text (str): The text to check for spelling errors
        subscription_key (str): The Bing Spell Check API subscription key
        mode (str): The mode to use - 'proof' (default) or 'spell'
    
    Returns:
        dict: JSON response from the API
    """
    endpoint = "https://api.bing.microsoft.com/v7.0/spellcheck"
    
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    params = {
        'mode': mode,
        'mkt': 'en-US',
    }
    
    data = {
        'text': text
    }
    
    try:
        logger.info(f"Sending request to Bing Spell Check API in {mode} mode")
        response = requests.post(endpoint, headers=headers, params=params, data=data)
        response.raise_for_status()  # Raise exception for 4XX/5XX errors
        
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Bing Spell Check API: {e}")
        return None

def format_corrections(result):
    """
    Format the corrections from the API response
    
    Args:
        result (dict): The API response
    
    Returns:
        list: Formatted corrections
    """
    if not result or 'flaggedTokens' not in result:
        return []
    
    corrections = []
    for token in result['flaggedTokens']:
        word = token['token']
        offset = token['offset']
        suggestions = [suggestion['suggestion'] for suggestion in token['suggestions']]
        
        correction = {
            'original': word,
            'offset': offset,
            'suggestions': suggestions
        }
        corrections.append(correction)
    
    return corrections

def display_results(text, corrections):
    """
    Display the original text and suggested corrections
    
    Args:
        text (str): The original text
        corrections (list): The corrections from the API
    """
    print("\nOriginal text:")
    print(text)
    
    print("\nSpelling suggestions:")
    if not corrections:
        print("No spelling errors detected!")
        return
    
    for i, correction in enumerate(corrections, 1):
        print(f"\n{i}. Error: '{correction['original']}' at position {correction['offset']}")
        print(f"   Suggestions: {', '.join(correction['suggestions'])}")
    
    # Create a marked version of the text with corrections
    print("\nText with potential corrections:")
    sorted_corrections = sorted(corrections, key=lambda x: x['offset'], reverse=True)
    
    marked_text = text
    for correction in sorted_corrections:
        offset = correction['offset']
        word = correction['original']
        suggestion = correction['suggestions'][0] if correction['suggestions'] else word
        
        marked_text = marked_text[:offset] + f"[{word} -> {suggestion}]" + marked_text[offset + len(word):]
    
    print(marked_text)

def main():
    """Main function to run the script."""
    args = setup_argument_parser()
    
    # Get subscription key from arguments or environment variable
    subscription_key = args.key or os.environ.get('BING_SPELLCHECK_KEY')
    if not subscription_key:
        logger.error("No subscription key provided. Please provide a key using -k/--key or set the BING_SPELLCHECK_KEY environment variable.")
        sys.exit(1)
    
    # Get text to check from arguments or file
    if args.text:
        text = args.text
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as file:
                text = file.read()
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            sys.exit(1)
    else:
        logger.error("No text provided. Please provide text using -t/--text or -f/--file")
        sys.exit(1)
    
    # Check if text is empty
    if not text.strip():
        logger.error("Empty text provided. Nothing to check.")
        sys.exit(1)
    
    # Perform spell check
    result = check_spelling(text, subscription_key, args.mode)
    if not result:
        logger.error("Failed to get spell check results")
        sys.exit(1)
    
    # Format and display results
    corrections = format_corrections(result)
    display_results(text, corrections)
    
    # Output summary
    if corrections:
        logger.info(f"Found {len(corrections)} spelling errors in the text")
    else:
        logger.info("No spelling errors found in the text")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)