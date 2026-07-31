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

    # Normalise case up front, then process the text word by word.
    text = text.lower().strip()

    # For each whitespace-separated token, drop punctuation and any other
    # non-alphanumeric characters before tallying it.
    word_counts = defaultdict(int)
    for token in text.split():
        word = re.sub(r'[^a-z0-9]', '', token)
        word = word.translate({ord(c): None for c in string.punctuation})
        word_counts[word] += 1

    return dict(word_counts)
