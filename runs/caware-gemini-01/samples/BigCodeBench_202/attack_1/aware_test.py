from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
import re
from collections import Counter

# A robust URL pattern for comparison, similar to the one in the candidate but simplified for testing purposes
# This pattern is not used to re-implement the solution, but to verify if URLs are correctly identified.
# The candidate's pattern is very specific, so we'll use a simpler one for generating valid URLs.
# The candidate's pattern: r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
# For testing, we'll use a simpler one to generate valid URLs that *should* be matched by the candidate's pattern.
# The candidate's pattern is quite strict, so we'll generate simple, common URLs.
SIMPLE_URL_PATTERN = r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'

# Strategy for generating simple, valid URLs that should be matched by the candidate's regex
# The candidate's regex is complex, so we aim for common cases it should definitely catch.
st_url = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-"),
    min_size=3, max_size=8
).map(lambda s: f"https://www.{s}.com")

# Strategy for generating non-URL strings
st_non_url = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789 "),
    min_size=1, max_size=10
).filter(lambda s: not re.match(SIMPLE_URL_PATTERN, s))

# Strategy for generating JSON keys
st_key = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz"),
    min_size=1, max_size=5
)

# Strategy for generating JSON values (can be string, dict, or list)
@st.composite
def st_json_value(draw, depth=0):
    if depth > 2: # Limit recursion depth
        return draw(st.one_of(st_url, st_non_url, st.integers(), st.booleans()))

    return draw(st.one_of(
        st_url,
        st_non_url,
        st.integers(),
        st.booleans(),
        st.lists(st_json_value(depth=depth + 1), min_size=0, max_size=3),
        st.dictionaries(st_key, st_json_value(depth=depth + 1), min_size=0, max_size=3)
    ))

# Strategy for generating JSON dictionaries
st_json_dict = st.dictionaries(st_key, st_json_value(), min_size=0, max_size=5)

def extract_urls_from_dict_standard(data):
    """Helper to extract URLs using standard Python JSON parsing behavior."""
    urls = []
    pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'

    def _extract(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                _extract(value)
        elif isinstance(obj, list):
            for item in obj:
                _extract(item)
        elif isinstance(obj, str) and re.match(pattern, obj):
            urls.append(obj)
    _extract(data)
    return urls

@given(data=st_json_dict, top_n=st.integers(min_value=1, max_value=10))
@settings(max_examples=50, deadline=None)
def test_extracted_urls_subset_of_all_possible(data, top_n):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict"
    PROPERTY: All URLs returned by task_func must be valid URLs and must be present in the original JSON structure.
              The count of URLs returned should not exceed top_n, unless fewer than top_n URLs are found.
    STRATEGY: General property test.
    """
    json_str = json.dumps(data)
    
    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, "task_func raised an unexpected exception"
    assert isinstance(result, dict), "task_func should return a dictionary"

    # Check if all returned keys are valid URLs according to the candidate's pattern
    candidate_pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
    for url in result.keys():
        assert re.match(candidate_pattern, url), f"Returned key '{url}' is not a valid URL according to the candidate's pattern."

    # Check top_n constraint
    if len(result) > top_n:
        assert False, f"Returned more than top_n URLs: {len(result)} > {top_n}"

    # Check that counts are positive
    for count in result.values():
        assert count > 0, "URL counts must be positive."

@given(
    key=st_key,
    url1=st_url,
    url2=st_url.filter(lambda u: u != st.just(url1)), # Ensure url2 is different from url1
    non_url_str=st_non_url
)
@settings(max_examples=50, deadline=None)
def test_duplicate_keys_last_url_is_missed(key, url1, url2, non_url_str):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict"
    PROPERTY: If a JSON string contains an object with duplicate keys, and a URL is associated with a *later*
              occurrence of a duplicate key, that URL should still be extracted. The candidate's `merge_pairs`
              hook will cause this URL to be missed.
    STRATEGY: Targets the `object_pairs_hook=merge_pairs` behavior. Constructs JSON with duplicate keys where
              the later key holds a URL that should be extracted.
    """
    # Case 1: URL is the second value for a duplicate key
    json_str_url_second = json.dumps({key: non_url_str, "dummy": "value"})[:-1] + f', "{key}": "{url1}"}}'
    
    # Case 2: URL is the first value for a duplicate key (should be found)
    json_str_url_first = json.dumps({key: url1, "dummy": "value"})[:-1] + f', "{key}": "{non_url_str}"}}'

    # Case 3: Two different URLs for the same key, second one should be found by standard parsing
    json_str_two_urls_second = json.dumps({key: url1, "dummy": "value"})[:-1] + f', "{key}": "{url2}"}}'

    # Test Case 1: URL is the second value for a duplicate key
    try:
        result_second = task_func(json_str_url_second)
    except Exception:
        result_second = None
    
    assert result_second is not None, "task_func raised an unexpected exception for URL as second value"
    # The candidate's code with merge_pairs will keep the first value (non_url_str) and miss url1.
    assert url1 not in result_second, f"Suspicion confirmed: URL '{url1}' was found when it should have been missed due to duplicate key '{key}' and merge_pairs hook. Input: {json_str_url_second}"

    # Test Case 2: URL is the first value for a duplicate key
    try:
        result_first = task_func(json_str_url_first)
    except Exception:
        result_first = None

    assert result_first is not None, "task_func raised an unexpected exception for URL as first value"
    # The candidate's code with merge_pairs will keep the first value (url1) and find it.
    assert url1 in result_first, f"URL '{url1}' should have been found as it was the first value for duplicate key '{key}'. Input: {json_str_url_first}"

    # Test Case 3: Two different URLs for the same key, second one should be found by standard parsing
    try:
        result_two_urls_second = task_func(json_str_two_urls_second)
    except Exception:
        result_two_urls_second = None

    assert result_two_urls_second is not None, "task_func raised an unexpected exception for two different URLs"
    # The candidate's code with merge_pairs will keep the first value (url1) and miss url2.
    assert url2 not in result_two_urls_second, f"Suspicion confirmed: URL '{url2}' was found when it should have been missed due to duplicate key '{key}' and merge_pairs hook. Input: {json_str_two_urls_second}"
    assert url1 in result_two_urls_second, f"URL '{url1}' should have been found as it was the first value for duplicate key '{key}'. Input: {json_str_two_urls_second}"


@given(data=st_json_dict)
@settings(max_examples=50, deadline=None)
def test_no_urls_returns_empty_dict(data):
    """
    SPEC BASIS: Example: `task_func('{"name": "John", "website": "https://www.example.com"}')` returns `{'https://www.example.com': 1}`.
                Implies that if no URLs are found, an empty dict should be returned.
    PROPERTY: If the input JSON contains no strings matching the URL pattern, the function should return an empty dictionary.
    STRATEGY: General property test.
    """
    # Filter out any URLs from the generated data to ensure no URLs are present
    def remove_urls(obj):
        if isinstance(obj, dict):
            return {k: remove_urls(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [remove_urls(item) for item in obj]
        elif isinstance(obj, str) and re.match(SIMPLE_URL_PATTERN, obj):
            return "not_a_url_string"
        return obj

    data_no_urls = remove_urls(data)
    json_str = json.dumps(data_no_urls)

    # Verify that the filtered JSON string indeed contains no URLs according to a simple pattern
    # This is a sanity check for the test strategy itself.
    assert not re.search(SIMPLE_URL_PATTERN, json_str), "Test setup failed: JSON string still contains a simple URL."

    try:
        result = task_func(json_str)
    except Exception:
        result = None

    assert result is not None, "task_func raised an unexpected exception"
    assert result == {}, f"Expected an empty dictionary when no URLs are present, but got {result}"

@given(
    urls_list=st.lists(st_url, min_size=1, max_size=10),
    top_n=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=50, deadline=None)
def test_top_n_limit_and_counts(urls_list, top_n):
    """
    SPEC BASIS: "top_n (int, Optional): The number of URLs to return. Defaults to 10."
                "Returns: dict: A dict with URLs as keys and the number of times they appear as values."
    PROPERTY: The returned dictionary should contain at most `top_n` unique URLs.
              The counts for each URL should be accurate.
              If `len(unique_urls) <= top_n`, all unique URLs should be returned with correct counts.
    STRATEGY: General property test focusing on `top_n` and `Counter` logic.
    """
    # Create a JSON string where all URLs are directly accessible
    json_data = {"urls": urls_list}
    json_str = json.dumps(json_data)

    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, "task_func raised an unexpected exception"
    assert isinstance(result, dict), "task_func should return a dictionary"

    # Calculate expected counts using standard Counter
    all_found_urls = extract_urls_from_dict_standard(json.loads(json_str))
    expected_counts = Counter(all_found_urls)

    if len(expected_counts) <= top_n:
        # If fewer or equal unique URLs than top_n, all should be returned
        assert len(result) == len(expected_counts), \
            f"Expected {len(expected_counts)} URLs, got {len(result)} when all should be returned. Input: {json_str}, top_n: {top_n}"
        assert result == dict(expected_counts), \
            f"Counts mismatch when all URLs should be returned. Expected: {dict(expected_counts)}, Got: {result}. Input: {json_str}, top_n: {top_n}"
    else:
        # If more unique URLs than top_n, only top_n most common should be returned
        assert len(result) == top_n, \
            f"Expected {top_n} URLs, got {len(result)} when limiting by top_n. Input: {json_str}, top_n: {top_n}"
        
        # Convert result to Counter for easier comparison of counts
        result_counter = Counter(result)
        
        # Check that the returned URLs are indeed among the most common
        most_common_expected = expected_counts.most_common(top_n)
        
        # The order of items with the same count is not guaranteed by most_common,
        # so we compare sets of (url, count) pairs.
        assert set(result.items()) == set(most_common_expected), \
            f"Top_n URLs or their counts mismatch. Expected: {set(most_common_expected)}, Got: {set(result.items())}. Input: {json_str}, top_n: {top_n}"