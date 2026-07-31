from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import re
from collections import Counter

# A simplified URL pattern for generating valid URLs in tests,
# ensuring they match the candidate's more complex pattern.
# This pattern is a subset of the candidate's pattern.
SIMPLE_URL_PATTERN = r'https?://[a-zA-Z0-9-]+\.com'

@st.composite
def json_with_urls_in_lists(draw):
    """
    Strategy to generate JSON strings where URLs are primarily or exclusively
    nested within lists, to target the suspected omission.
    """
    max_depth = draw(st.integers(min_value=1, max_value=3))
    # max_items must be an integer literal for min_size/max_size in st.lists/st.dictionaries
    # We'll use a fixed small size for lists/dicts to satisfy the Hypothesis constraint.
    fixed_max_items = 3 

    def generate_value(current_depth):
        if current_depth >= max_depth:
            # At max depth, generate a string or a simple dict
            return draw(st.one_of(
                st.text(alphabet=st.characters(blacklist_characters='{}[]":,', min_size=1, max_size=5)),
                st.just("https://example.com"), # A guaranteed URL
                st.just("http://test.org"),     # Another guaranteed URL
                st.builds(dict, st.dictionaries(
                    st.text(min_size=1, max_size=5),
                    st.text(min_size=1, max_size=5),
                    min_size=1, max_size=2
                ))
            ))
        else:
            # Recursively generate lists or dicts
            return draw(st.one_of(
                st.lists(generate_value(current_depth + 1), min_size=1, max_size=fixed_max_items),
                st.builds(dict, st.dictionaries(
                    st.text(min_size=1, max_size=5),
                    generate_value(current_depth + 1),
                    min_size=1, max_size=fixed_max_items
                )),
                st.just("https://nested.net"), # A guaranteed URL
                st.just("http://deep.io")      # Another guaranteed URL
            ))

    # Ensure the top-level is a dictionary
    data = draw(st.dictionaries(
        st.text(min_size=1, max_size=5),
        generate_value(1),
        min_size=1, max_size=fixed_max_items
    ))
    return json.dumps(data)

@st.composite
def json_with_mixed_urls(draw):
    """
    Strategy to generate JSON strings with URLs in various places:
    directly in dicts, nested dicts, and lists.
    """
    max_depth = draw(st.integers(min_value=1, max_value=3))
    # max_items must be an integer literal for min_size/max_size in st.lists/st.dictionaries
    fixed_max_items = 3

    def generate_value(current_depth):
        if current_depth >= max_depth:
            # At max depth, generate a string (possibly a URL) or a simple dict
            return draw(st.one_of(
                st.text(alphabet=st.characters(blacklist_characters='{}[]":,', min_size=1, max_size=5)),
                st.just("https://example.com"),
                st.just("http://test.org"),
                st.builds(dict, st.dictionaries(
                    st.text(min_size=1, max_size=5),
                    st.text(min_size=1, max_size=5),
                    min_size=1, max_size=2
                ))
            ))
        else:
            # Recursively generate lists or dicts, or a string (possibly a URL)
            return draw(st.one_of(
                st.lists(generate_value(current_depth + 1), min_size=0, max_size=fixed_max_items),
                st.builds(dict, st.dictionaries(
                    st.text(min_size=1, max_size=5),
                    generate_value(current_depth + 1),
                    min_size=0, max_size=fixed_max_items
                )),
                st.text(alphabet=st.characters(blacklist_characters='{}[]":,', min_size=1, max_size=5)),
                st.just("https://nested.net"),
                st.just("http://deep.io")
            ))

    # Ensure the top-level is a dictionary
    data = draw(st.dictionaries(
        st.text(min_size=1, max_size=5),
        generate_value(1),
        min_size=1, max_size=fixed_max_items
    ))
    return json.dumps(data)


@settings(max_examples=50, deadline=None)
@given(json_str=st.json(
    min_size=1, max_size=10,
    min_depth=1, max_depth=3,
    average_depth=2,
    allow_nulls=False,
    allow_unicode_strings=False,
    # Ensure string values are simple enough to potentially be URLs or non-URLs
    # and avoid complex characters that might break the regex or JSON parsing
    strings=st.text(alphabet=st.characters(blacklist_characters='{}[]":,', min_size=1, max_size=10)).map(
        lambda s: s if not s.startswith('http') else 'https://' + s.replace(' ', '') + '.com'
    )
))
def test_return_type_is_dict(json_str):
    """
    SPEC BASIS: Returns: dict: A dict with URLs as keys and the number of times they appear as values.
    PROPERTY: The function should always return a dictionary.
    STRATEGY: General JSON strings.
    """
    try:
        result = task_func(json_str)
    except Exception:
        result = None
    assert isinstance(result, dict), f"Expected a dict, but got {type(result)}"


@settings(max_examples=50, deadline=None)
@given(json_str=st.json(
    min_size=1, max_size=10,
    min_depth=1, max_depth=3,
    average_depth=2,
    allow_nulls=False,
    allow_unicode_strings=False,
    strings=st.text(alphabet=st.characters(blacklist_characters='{}[]":,', min_size=1, max_size=10))
), top_n=st.integers(min_value=1, max_value=10))
def test_top_n_limit(json_str, top_n):
    """
    SPEC BASIS: top_n (int, Optional): The number of URLs to return. Defaults to 10.
                Returns: dict: A dict with URLs as keys and the number of times they appear as values.
    PROPERTY: The number of keys in the returned dictionary should not exceed top_n,
              unless the total number of unique URLs is less than or equal to top_n.
    STRATEGY: General JSON strings with varying top_n.
    """
    # The candidate's URL pattern
    pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
    
    all_urls_in_json = []
    def find_all_urls_in_data(data):
        if isinstance(data, dict):
            for value in data.values():
                find_all_urls_in_data(value)
        elif isinstance(data, list): # Reference implementation correctly traverses lists
            for item in data:
                find_all_urls_in_data(item)
        elif isinstance(data, str):
            if re.match(pattern, data): # Using re.match as per candidate's logic
                all_urls_in_json.append(data)

    try:
        data_obj = json.loads(json_str)
        find_all_urls_in_data(data_obj)
        result = task_func(json_str, top_n=top_n)
    except Exception:
        result = None
    
    if result is not None:
        unique_urls_count = len(set(all_urls_in_json))
        if unique_urls_count <= top_n:
            assert len(result) == unique_urls_count, \
                f"Expected {unique_urls_count} URLs when total <= top_n, got {len(result)}. JSON: {json_str}"
        else:
            assert len(result) <= top_n, \
                f"Expected at most {top_n} URLs, got {len(result)}. JSON: {json_str}"


@settings(max_examples=50, deadline=None)
@given(json_str=json_with_urls_in_lists())
def test_urls_in_lists_are_extracted(json_str):
    """
    SPEC BASIS: Extract all URLs from a string-serialized JSON dict...
    PROPERTY: If URLs are present within JSON list structures, the function should still find them.
              The current implementation is suspected to miss URLs in lists.
    STRATEGY: JSON strings where URLs are embedded within lists, targeting the recursive traversal logic.
    """
    # The candidate's URL pattern
    pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
    
    # Manually extract all URLs from the generated JSON string, including those in lists
    # This is a reference extraction to compare against the candidate's output
    expected_urls = []
    def reference_extract(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                reference_extract(value)
        elif isinstance(obj, list): # Correctly traverse lists
            for item in obj:
                reference_extract(item)
        elif isinstance(obj, str):
            if re.match(pattern, obj): # Use re.match as per candidate's interpretation
                expected_urls.append(obj)

    try:
        data_obj = json.loads(json_str)
        reference_extract(data_obj)
        result = task_func(json_str)
    except Exception:
        result = None

    if expected_urls: # If there are URLs that should be found by a correct implementation
        assert result is not None, f"Function raised an exception for valid input. JSON: {json_str}"
        # The suspicion is that URLs in lists are missed. So, if expected_urls is not empty,
        # the result should also not be empty and contain all expected URLs.
        assert len(result) > 0, \
            f"Expected to find URLs in list-heavy JSON, but got an empty result. JSON: {json_str}"
        
        # Check that all expected URLs are present in the result
        for url in expected_urls:
            assert url in result, f"Expected URL '{url}' not found in result: {result}. JSON: {json_str}"
        
        # Check counts for all expected URLs
        expected_counts = Counter(expected_urls)
        for url, count in expected_counts.items():
            assert result.get(url) == count, \
                f"Count mismatch for URL '{url}'. Expected {count}, got {result.get(url)}. Result: {result}. JSON: {json_str}"
    else:
        # If no URLs were expected by the reference extractor, the result should be empty.
        assert result == {}, f"Expected empty result when no URLs are present, got {result}. JSON: {json_str}"


@settings(max_examples=50, deadline=None)
@given(json_str=st.json(
    min_size=1, max_size=10,
    min_depth=1, max_depth=3,
    average_depth=2,
    allow_nulls=False,
    allow_unicode_strings=False,
    strings=st.text(alphabet=st.characters(blacklist_characters='{}[]":,', min_size=1, max_size=10))
), top_n=st.integers(min_value=1, max_value=10))
def test_counts_are_positive(json_str, top_n):
    """
    SPEC BASIS: Returns: dict: A dict with URLs as keys and the number of times they appear as values.
    PROPERTY: All URL counts in the returned dictionary must be positive integers.
    STRATEGY: General JSON strings with varying top_n.
    """
    try:
        result = task_func(json_str, top_n=top_n)
    except Exception:
        result = None
    
    if result is not None:
        for url, count in result.items():
            assert isinstance(count, int) and count > 0, \
                f"Count for URL '{url}' is not a positive integer: {count}. JSON: {json_str}"


@settings(max_examples=50, deadline=None)
@given(json_str=json_with_mixed_urls(), top_n=st.integers(min_value=1, max_value=10))
def test_extracted_urls_match_pattern(json_str, top_n):
    """
    SPEC BASIS: Extract all URLs from a string-serialized JSON dict using a specific URL pattern
    PROPERTY: All keys (URLs) in the returned dictionary must conform to the specified URL pattern.
    STRATEGY: JSON strings with mixed URL placements, including lists, to ensure all found URLs are valid.
    """
    # The candidate's URL pattern
    pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
    
    try:
        result = task_func(json_str, top_n=top_n)
    except Exception:
        result = None
    
    if result is not None:
        for url in result.keys():
            assert re.match(pattern, url), \
                f"Extracted URL '{url}' does not match the specified pattern. JSON: {json_str}"