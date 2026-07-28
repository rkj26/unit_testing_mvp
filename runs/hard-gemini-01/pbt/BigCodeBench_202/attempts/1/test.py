# SEARCH PLAN:
# - Empty JSON, JSON with no URLs, and JSON with a single URL (boundary cases).
# - JSON with multiple URLs, including duplicates, to test counting and `top_n` behavior.
# - JSON with URLs embedded in various string contexts (e.g., with surrounding text, in lists, nested dicts).
# - Varying `top_n` values, including 0, 1, and values larger than the total number of unique URLs.

import re
import json
from collections import Counter
from hypothesis import given, settings, strategies as st
import string
from candidate import task_func

# --- Helper Strategies for URL and JSON generation ---

# Strategy for generating parts of a URL
url_protocol = st.sampled_from(['http://', 'https://'])
url_subdomain = st.one_of(st.just('www.'), st.just(''))
url_domain_part = st.text(string.ascii_lowercase + string.digits + '-', min_size=1, max_size=8)
url_tld = st.sampled_from(['.com', '.org', '.net', '.io'])
url_path_part = st.text(string.ascii_lowercase + string.digits + '/', min_size=0, max_size=5)

# Strategy for generating a full URL
url_strategy = st.builds(
    lambda proto, sub, domain, tld, path: f"{proto}{sub}{domain}{tld}{path}",
    proto=url_protocol,
    sub=url_subdomain,
    domain=url_domain_part,
    tld=url_tld,
    path=url_path_part
)

# Strategy for generating non-URL string content
non_url_string_content = st.text(
    st.sampled_from(string.ascii_letters + string.digits + ' -_.,!'),
    min_size=0, max_size=12
)

# Strategy for generating JSON keys
json_key_strategy = st.text(string.ascii_lowercase, min_size=1, max_size=8)

# Recursive strategy for generating JSON values that can contain URLs
@st.composite
def json_recursive_value(draw, max_depth=2):
    if max_depth <= 0:
        # At max depth, only generate simple types or a URL string
        return draw(st.one_of(
            non_url_string_content,
            st.integers(min_value=-100, max_value=100),
            st.booleans(),
            st.just(None),
            url_strategy.map(lambda u: f"{draw(non_url_string_content)} {u} {draw(non_url_string_content)}".strip())
        ))

    # Decide what type of value to generate
    value_type = draw(st.sampled_from(['string', 'int', 'bool', 'null', 'list', 'dict', 'url_embedded_string']))

    if value_type == 'string':
        return draw(non_url_string_content)
    elif value_type == 'url_embedded_string':
        url = draw(url_strategy)
        prefix = draw(non_url_string_content)
        suffix = draw(non_url_string_content)
        return f"{prefix} {url} {suffix}".strip()
    elif value_type == 'int':
        return draw(st.integers(min_value=-100, max_value=100))
    elif value_type == 'bool':
        return draw(st.booleans())
    elif value_type == 'null':
        return draw(st.just(None))
    elif value_type == 'list':
        return draw(st.lists(json_recursive_value(max_depth=max_depth - 1), min_size=0, max_size=5))
    elif value_type == 'dict':
        return draw(st.dictionaries(
            json_key_strategy,
            json_recursive_value(max_depth=max_depth - 1),
            min_size=0, max_size=5
        ))

# Strategy for generating a full JSON dictionary and then serializing it
json_dict_strategy = st.dictionaries(
    json_key_strategy,
    json_recursive_value(max_depth=2), # Limit depth to avoid overly complex JSON
    min_size=0, max_size=5 # Limit number of top-level keys
)

json_str_strategy = json_dict_strategy.map(json.dumps)

# --- Tests ---

@settings(max_examples=50, deadline=None)
@given(json_str=st.just('{"name": "John", "website": "https://www.example.com"}'))
def test_example_case(json_str):
    """
    SPEC BASIS: "Example: >>> task_func('{"name": "John", "website": "https://www.example.com"}') {'https://www.example.com': 1}"
    PROPERTY: The function returns the exact output specified in the example.
    STRATEGY: Use the exact JSON string from the problem's example.
    """
    try:
        result = task_func(json_str)
    except Exception:
        result = None
    assert result is not None
    assert result == {'https://www.example.com': 1}

@settings(max_examples=50, deadline=None)
@given(json_str=json_str_strategy, top_n=st.integers(min_value=0, max_value=12))
def test_output_size_and_top_n_limit(json_str, top_n):
    """
    SPEC BASIS: "top_n (int, Optional): The number of URLs to return. Defaults to 10."
    PROPERTY: The number of unique URLs in the output dictionary does not exceed `top_n`.
    STRATEGY: Generate diverse JSON strings with varying numbers of URLs and test with various `top_n` values, including 0, 1, and larger values.
    """
    try:
        result = task_func(json_str, top_n=top_n)
    except Exception:
        result = None
    assert result is not None
    assert isinstance(result, dict)
    assert len(result) <= top_n

@settings(max_examples=50, deadline=None)
@given(json_str=json_str_strategy)
def test_no_urls_returns_empty_dict(json_str):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict..." (implies if no URLs, none are extracted).
    PROPERTY: If the input JSON string contains no URLs matching a common pattern, the output dictionary is empty.
    STRATEGY: Generate JSON strings that are unlikely to contain URLs (by using `non_url_string_content` for values) and filter for those that definitely don't contain URLs.
    """
    # A simple regex to check for common URL patterns (http/https)
    # This is used to filter the input, not for the task_func itself.
    url_pattern_check = re.compile(r'https?://(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s"]*)?')

    # Filter out inputs that might accidentally contain URLs
    if url_pattern_check.search(json_str):
        st.assume(False) # Skip this example if it contains a URL

    try:
        result = task_func(json_str)
    except Exception:
        result = None
    assert result is not None
    assert isinstance(result, dict)
    assert len(result) == 0
    assert result == {}

@settings(max_examples=50, deadline=None)
@given(
    urls=st.lists(url_strategy, min_size=1, max_size=10),
    top_n=st.integers(min_value=1, max_value=12)
)
def test_counts_are_correct_for_all_urls_when_top_n_is_large(urls, top_n):
    """
    SPEC BASIS: "return a dict with the URLs as keys and the number of times they appear as values."
    PROPERTY: When `top_n` is sufficiently large to include all unique URLs, the counts in the output match the actual counts of URLs in the input.
    STRATEGY: Construct a JSON string with a known set of URLs (including duplicates) and compare the output counts to a manually computed Counter.
    """
    # Embed URLs into a simple JSON structure
    json_data = {"urls": []}
    for i, url in enumerate(urls):
        json_data["urls"].append(f"item_{i}: {url} and some text.")
        # Add some URLs directly as values too
        json_data[f"url_key_{i}"] = url

    json_str = json.dumps(json_data)

    # Manually extract all URLs from the generated string using the assumed pattern
    # This pattern must match the one implicitly used by task_func.
    # The problem statement says "using a specific URL pattern" but doesn't provide it.
    # We assume a common robust pattern for http(s)://...
    # This pattern is consistent with the one used in the example and the filtering above.
    url_pattern = re.compile(r'https?://(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s"]*)?')
    all_found_urls = url_pattern.findall(json_str)
    expected_counts = Counter(all_found_urls)

    # Ensure top_n is large enough to cover all unique URLs for this test's assertion
    st.assume(top_n >= len(expected_counts))

    try:
        result = task_func(json_str, top_n=top_n)
    except Exception:
        result = None
    assert result is not None
    assert isinstance(result, dict)

    # Compare the output counts with the expected counts
    assert Counter(result) == Counter(expected_counts)
    # Also check that the values (counts) are correct
    for url, count in expected_counts.items():
        assert result.get(url) == count