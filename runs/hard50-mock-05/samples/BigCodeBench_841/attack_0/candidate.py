import re
import json
from collections import defaultdict
import string

def task_func(json_string):
    try:
        # Load JSON and extract text
        data = json.loads(json_string)
        text = data.get('text', '')
    except json.JSONDecodeError:
        return {}

    # Strip out anything that is not a letter, digit or whitespace, then
    # normalise case. Whitespace (spaces, tabs, newlines, carriage returns)
    # is kept so that word boundaries survive the cleaning step.
    text = re.sub(r'[^a-zA-Z0-9 \t\n\r]', '', text).lower().strip()
    text = text.translate({ord(c): None for c in string.punctuation})

    # Count words
    word_counts = defaultdict(int)
    for word in text.split():
        word_counts[word] += 1

    return dict(word_counts)
