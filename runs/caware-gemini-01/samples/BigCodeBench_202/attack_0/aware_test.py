from candidate import task_func
from hypothesis import given, settings, strategies as st
import json
from collections import Counter
import re

# Helper strategy for generating valid URL-like strings
# Simplified for testing purposes, focusing on the structure rather than full RFC compliance
# This pattern is a simplified version of the one in the candidate code,
# ensuring it generates strings that the candidate's pattern will likely match.
# The candidate's pattern is very complex, so we'll generate simpler, clearly valid URLs.
url_pattern_simplified = r'https?://[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}(/[a-zA-Z0-9-._~:/?#@!$&\'()*+,;=]*)?'

@st.composite
def json_dict_strategy(draw, max_depth=3, max_items=5):
    """
    Generates a JSON-serializable dictionary with string and URL values,
    and nested dictionaries.
    """
    def generate_value(current_depth):
        if current_depth >= max_depth:
            # At max depth, only generate strings or simple types
            return draw(st.one_of(
                st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
                st.integers(),
                st.booleans(),
                st.just(None),
                st.from_regex(url_pattern_simplified, fullmatch=True).map(lambda s: s.replace(' ', '')) # Ensure no spaces
            ))
        else:
            return draw(st.one_of(
                st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
                st.integers(),
                st.booleans(),
                st.just(None),
                st.from_regex(url_pattern_simplified, fullmatch=True).map(lambda s: s.replace(' ', '')), # Ensure no spaces
                st.builds(lambda d: d, st.dictionaries(
                    keys=st.text(min_size=1, max_size=5, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
                    values=st.deferred(lambda: generate_value(current_depth + 1)),
                    min_size=0, max_size=max_items
                ))
            ))

    return draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=5, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        values=generate_value(0),
        min_size=0, max_size=max_items
    ))

@given(
    json_data=json_dict_strategy(),
    top_n=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=50, deadline=None)
def test_all_unique_urls_returned_when_unique_count_le_top_n(json_data, top_n):
    """
    SPEC BASIS: "The number of URLs to return. Defaults to 10."
    PROPERTY: If the number of *unique* URLs found in the JSON string is less than or equal to `top_n`,
              then all unique URLs and their counts should be returned, regardless of the total count of URLs.
    STRATEGY: Targets the `if len(urls) <= top_n:` condition by ensuring `len(counts)` is small.
    """
    json_str = json.dumps(json_data)
    
    # Manually extract all URLs to determine the expected unique count
    all_extracted_urls = []
    candidate_pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'

    def manual_extract(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                manual_extract(value)
        elif isinstance(obj, list): # Although strategy doesn't generate lists at top level, good to be robust
            for item in obj:
                manual_extract(item)
        elif isinstance(obj, str):
            if re.match(candidate_pattern, obj):
                all_extracted_urls.append(obj)

    manual_extract(json_data)
    
    expected_counts = Counter(all_extracted_urls)
    
    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, "task_func raised an exception"

    # This test specifically targets the case where the number of UNIQUE URLs
    # is less than or equal to top_n.
    if len(expected_counts) <= top_n:
        assert result == dict(expected_counts), \
            f"Expected all unique URLs when unique count ({len(expected_counts)}) <= top_n ({top_n}), but got {result}"
    else:
        # If unique count > top_n, we can't assert exact equality,
        # but we can assert that the result size is top_n
        assert len(result) == top_n, \
            f"Expected {top_n} URLs when unique count ({len(expected_counts)}) > top_n ({top_n}), but got {len(result)} URLs"


@given(
    json_data=json_dict_strategy(),
    top_n=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=50, deadline=None)
def test_result_size_never_exceeds_top_n(json_data, top_n):
    """
    SPEC BASIS: "top_n (int, Optional): The number of URLs to return."
    PROPERTY: The number of URLs in the returned dictionary should never exceed `top_n`.
    STRATEGY: General input generation.
    """
    json_str = json.dumps(json_data)
    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, "task_func raised an exception"
    assert len(result) <= top_n, f"Result dictionary size ({len(result)}) exceeded top_n ({top_n})"


@given(
    json_data=json_dict_strategy(),
    top_n=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=50, deadline=None)
def test_returned_urls_are_valid_and_present_in_input(json_data, top_n):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict using a specific URL pattern"
    PROPERTY: All URLs returned by the function must be valid according to the internal regex pattern
              and must have been present as values in the input JSON.
    STRATEGY: General input generation.
    """
    json_str = json.dumps(json_data)
    
    # Collect all potential URL strings from the input JSON
    all_string_values = set()
    def collect_strings(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                collect_strings(value)
        elif isinstance(obj, list):
            for item in obj:
                collect_strings(item)
        elif isinstance(obj, str):
            all_string_values.add(obj)
    
    collect_strings(json_data)

    # The candidate's pattern
    candidate_pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'

    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, "task_func raised an exception"

    for url in result.keys():
        assert re.fullmatch(candidate_pattern, url), f"Returned URL '{url}' does not match the expected pattern."
        assert url in all_string_values, f"Returned URL '{url}' was not found as a value in the input JSON."


@given(
    json_data=json_dict_strategy(),
    top_n=st.integers(min_value=1, max_value=12)
)
@settings(max_examples=50, deadline=None)
def test_empty_input_or_no_urls_returns_empty_dict(json_data, top_n):
    """
    SPEC BASIS: Example: `task_func('{"name": "John", "website": "https://www.example.com"}')` returns `{'https://www.example.com': 1}`.
                Implies if no URLs, returns empty.
    PROPERTY: If the input JSON contains no URLs (according to the internal pattern), or is an empty dict,
              the function should return an empty dictionary.
    STRATEGY: General input generation, then filter for cases with no URLs.
    """
    json_str = json.dumps(json_data)
    
    # Manually check if any URLs exist in the input based on the candidate's pattern
    candidate_pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'
    
    has_urls = False
    def check_for_urls(obj):
        nonlocal has_urls
        if has_urls: return
        if isinstance(obj, dict):
            for value in obj.values():
                check_for_urls(value)
        elif isinstance(obj, list):
            for item in obj:
                check_for_urls(item)
        elif isinstance(obj, str):
            if re.match(candidate_pattern, obj):
                has_urls = True

    check_for_urls(json_data)

    if not has_urls:
        try:
            result = task_func(json_str, top_n)
        except Exception:
            result = None
        
        assert result is not None, "task_func raised an exception for input with no URLs"
        assert result == {}, f"Expected empty dict for input with no URLs, but got {result}"

@given(
    json_data=json_dict_strategy(max_items=12), # Increased max_items to allow more URLs for this specific test
    top_n=st.integers(min_value=1, max_value=5) # Keep top_n small to make it easier to exceed
)
@settings(max_examples=50, deadline=None)
def test_top_n_logic_with_many_unique_few_total_urls(json_data, top_n):
    """
    SPEC BASIS: "The number of URLs to return. Defaults to 10."
    PROPERTY: When the total number of URL occurrences (`len(urls)`) is less than or equal to `top_n`,
              but the number of *unique* URLs (`len(counts)`) is *greater* than `top_n`,
              the function should still return exactly `top_n` URLs, sorted by count.
              This targets the suspicious `if len(urls) <= top_n:` condition.
    STRATEGY: Generate inputs where `len(urls)` is small (e.g., each URL appears once),
              but `len(counts)` is larger than `top_n`.
    """
    json_str = json.dumps(json_data)
    
    all_extracted_urls = []
    candidate_pattern = r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})'

    def manual_extract(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                manual_extract(value)
        elif isinstance(obj, str):
            if re.match(candidate_pattern, obj):
                all_extracted_urls.append(obj)

    manual_extract(json_data)
    
    expected_counts = Counter(all_extracted_urls)
    
    # Filter for the specific suspicious case:
    # total occurrences <= top_n, but unique URLs > top_n
    if len(all_extracted_urls) <= top_n and len(expected_counts) > top_n:
        try:
            result = task_func(json_str, top_n)
        except Exception:
            result = None

        assert result is not None, "task_func raised an exception for the suspicious case"
        
        # In this specific case, the code's `if len(urls) <= top_n:` branch would return `dict(counts)`,
        # which would contain `len(counts)` items.
        # However, the spec implies the result should be limited to `top_n` items.
        # So, we expect `len(result)` to be `top_n`.
        assert len(result) == top_n, \
            f"Suspicious case: total occurrences ({len(all_extracted_urls)}) <= top_n ({top_n}), " \
            f"but unique URLs ({len(expected_counts)}) > top_n. " \
            f"Expected result size {top_n}, but got {len(result)}."
        
        # Additionally, ensure the returned URLs are indeed the top_n by count
        # (this is a stronger check, but requires re-implementing the sorting logic)
        # For now, just checking the size is sufficient to probe the branch.
        
    # If the condition is not met, this test doesn't assert anything,
    # as other tests cover the general cases.