# SEARCH PLAN:
# 1. URL Pattern & Counting: Generate diverse JSON with URLs (unique, duplicates, various structures) and non-URLs to verify correct extraction and counting against an oracle regex.
# 2. `top_n` Boundary: Test `top_n` values at boundaries (0, 1), around the default (10), and larger than total unique URLs to ensure correct truncation and selection.
# 3. Empty/No URLs: Provide JSON strings with no URLs to ensure an empty dictionary is returned.
# 4. JSON Structure Robustness: Embed URLs in deeply nested objects and arrays to ensure comprehensive traversal and extraction.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import re
import json
from collections import Counter

# A robust URL regex for generating and validating URLs.
# This pattern is designed to cover common URL structures including schemes, domains, paths, queries, and fragments.
# It's a common pattern, but not exhaustive for all possible URLs, focusing on typical web URLs.
URL_REGEX = r'https?://(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}(?:/?|[/?]\S+)'

# Strategy for generating valid URL components
st_scheme = st.sampled_from(['http', 'https'])
st_domain_part = st.text(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789-'), min_size=1, max_size=5).map(lambda s: s.strip('-'))
st_tld = st.sampled_from(['com', 'org', 'net', 'io', 'co.uk', 'info'])
st_path_segment = st.text(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789-_/'), min_size=0, max_size=5)
st_query_param = st.text(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789-_='), min_size=1, max_size=5)
st_fragment = st.text(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789-_'), min_size=1, max_size=5)

@st.composite
def st_url(draw):
    scheme = draw(st_scheme)
    subdomains = draw(st.lists(st_domain_part, min_size=0, max_size=1)) # Reduced max_size for smaller domains
    domain = ".".join(subdomains + [draw(st_domain_part)]) if subdomains else draw(st_domain_part)
    tld = draw(st_tld)
    path = draw(st.lists(st_path_segment, min_size=0, max_size=1)).map(lambda segments: "/" + "/".join(segments) if segments else "")
    query = draw(st.one_of(st.just(""), st.builds(lambda p: "?" + p, st_query_param)))
    fragment = draw(st.one_of(st.just(""), st.builds(lambda f: "#" + f, st_fragment)))
    
    # Ensure domain is not empty and ends with a valid TLD
    full_domain = f"{domain}.{tld}"
    # Simplified domain validation for generation to avoid complex filtering
    if not re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}$', full_domain):
        full_domain = f"example-{draw(st.text(st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=3))}.com"

    url = f"{scheme}://{full_domain}{path}{query}{fragment}"
    # Filter to ensure the generated URL matches the oracle regex.
    # This is crucial to ensure the oracle itself can find the URLs it generates.
    return draw(st.just(url)).filter(lambda u: re.fullmatch(URL_REGEX, u))


# Strategy for generating non-URL strings
st_non_url_text = st.text(st.characters(blacklist_categories=('Cs',), min_codepoint=32, max_codepoint=126), min_size=0, max_size=12).filter(lambda s: not re.search(URL_REGEX, s))

# Strategy for generating JSON values that can contain URLs or non-URLs
@st.composite
def st_json_value(draw, max_depth=2):
    if max_depth <= 0:
        return draw(st.one_of(st_url(), st_non_url_text, st.integers(), st.booleans(), st.just(None)))

    return draw(st.one_of(
        st_url(),
        st_non_url_text,
        st.integers(),
        st.booleans(),
        st.just(None),
        st.lists(st_json_value(max_depth=max_depth - 1), min_size=0, max_size=3),
        st.dictionaries(st.text(st.sampled_from('abc'), min_size=1, max_size=3), st_json_value(max_depth=max_depth - 1), min_size=0, max_size=3)
    ))

# Strategy for generating the full JSON string
st_json_str = st.dictionaries(
    st.text(st.sampled_from('abc'), min_size=1, max_size=3),
    st_json_value(),
    min_size=0, max_size=5
).map(json.dumps)

# Strategy for top_n, including boundary values
st_top_n = st.one_of(
    st.just(0),
    st.just(1),
    st.just(10), # Default value
    st.integers(min_value=2, max_value=15) # Values around default and slightly larger
)


@settings(max_examples=50, deadline=None)
@given(json_str=st_json_str, top_n=st_top_n)
def test_output_contains_top_n_urls_by_count(json_str, top_n):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict using a specific URL pattern and return a dict
                with the URLs as keys and the number of times they appear as values."
                "top_n (int, Optional): The number of URLs to return. Defaults to 10."
    PROPERTY: The output dictionary should contain at most `top_n` entries. If there are more unique URLs than `top_n`,
              the returned URLs must be the ones with the highest counts.
    STRATEGY: Generate JSON strings with varying numbers of URLs and duplicates. Test `top_n` values including 0, 1,
              and values larger than the number of unique URLs to ensure the limit is respected and correct URLs are chosen.
    """
    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: {json_str}, top_n={top_n}"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    # Oracle: Extract all URLs and count them
    all_extracted_urls = re.findall(URL_REGEX, json_str)
    oracle_counts = Counter(all_extracted_urls)

    # Sort oracle counts to determine expected top_n.
    # Tie-breaking: sort by count (descending), then URL (ascending) for consistent results.
    sorted_oracle_urls = sorted(oracle_counts.items(), key=lambda item: (-item[1], item[0]))

    # Expected result based on top_n
    expected_top_urls = dict(sorted_oracle_urls[:top_n])

    assert len(result) <= top_n, f"Output has {len(result)} URLs, expected at most {top_n}. Input: {json_str}, top_n={top_n}"

    # Check if all URLs in the result are present in the oracle's top_n and have correct counts.
    for url, count in result.items():
        assert url in expected_top_urls, f"URL '{url}' in result but not in expected top {top_n} URLs. Input: {json_str}, top_n={top_n}"
        assert expected_top_urls[url] == count, f"Count for URL '{url}' is {count}, expected {expected_top_urls[url]}. Input: {json_str}, top_n={top_n}"

    # If the number of unique URLs is less than or equal to top_n, the result should match the oracle exactly.
    if len(oracle_counts) <= top_n:
        assert Counter(result) == Counter(oracle_counts), f"Result does not match oracle counts when unique URLs <= top_n. Input: {json_str}, top_n={top_n}"
    else:
        # If more unique URLs than top_n, ensure the result contains exactly the top_n highest-counted URLs.
        for url, count in expected_top_urls.items():
            assert url in result, f"Expected URL '{url}' (count {count}) not found in result. Input: {json_str}"
            assert result[url] == count, f"Count mismatch for URL '{url}'. Expected {count}, got {result[url]}. Input: {json_str}"


@settings(max_examples=50, deadline=None)
@given(json_str=st_json_str)
def test_sum_of_counts_equals_total_extracted_urls(json_str):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict using a specific URL pattern and return a dict
                with the URLs as keys and the number of times they appear as values."
    PROPERTY: The sum of counts in the output dictionary (when `top_n` is large enough to include all URLs)
              should equal the total number of URLs *actually present* in the input JSON string, as identified
              by a robust oracle regex. This tests the correctness of the counting mechanism.
    STRATEGY: Generate JSON strings with various URLs, including duplicates. Independently extract all URLs from
              the raw string using a known-good regex and compare the sum of counts.
    """
    try:
        # Call with a very large top_n to ensure all URLs are returned for counting
        result = task_func(json_str, top_n=1000)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: {json_str}"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    # Oracle: Extract all URLs from the raw string using the same regex
    oracle_all_urls = re.findall(URL_REGEX, json_str)
    
    # Sum of counts from task_func
    task_func_total_count = sum(result.values())

    # Total count from oracle
    oracle_total_count = len(oracle_all_urls)

    assert task_func_total_count == oracle_total_count, \
        f"Sum of counts ({task_func_total_count}) does not match total URLs found by oracle ({oracle_total_count}). Input: {json_str}"
    
    # Additionally, ensure all URLs in the result are valid according to the oracle regex
    for url in result.keys():
        assert re.fullmatch(URL_REGEX, url), f"Result contains an invalid URL: '{url}'. Input: {json_str}"


@settings(max_examples=50, deadline=None)
@given(json_str=st.one_of(
    st.just('{}'),
    st.just('{"key": "no url here"}'),
    st.just('{"data": [1, 2, "plain text", {"nested": false}]}')
), top_n=st_top_n)
def test_no_urls_returns_empty_dict(json_str, top_n):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict..." (implies if no URLs, dict is empty).
    PROPERTY: If the JSON string is valid but contains no URLs matching the pattern, the function should return an empty dictionary.
    STRATEGY: Generate JSON strings that are valid but explicitly contain no URLs, including empty objects/arrays.
              This targets the boundary case where no matches are found.
    """
    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: {json_str}, top_n={top_n}"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result == {}, f"Expected empty dict for JSON with no URLs, got {result}. Input: {json_str}, top_n={top_n}"


@settings(max_examples=50, deadline=None)
@given(json_str=st_json_str, top_n=st_top_n)
def test_all_extracted_urls_are_valid(json_str, top_n):
    """
    SPEC BASIS: "Extract all URLs from a string-serialized JSON dict using a specific URL pattern"
    PROPERTY: Every key (URL) in the returned dictionary must conform to the specified URL pattern.
    STRATEGY: Generate diverse JSON strings. This test ensures that the function does not extract
              or return malformed strings that are not actual URLs according to the oracle regex.
    """
    try:
        result = task_func(json_str, top_n)
    except Exception:
        result = None

    assert result is not None, f"task_func raised an exception for input: {json_str}, top_n={top_n}"
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    for url in result.keys():
        assert re.fullmatch(URL_REGEX, url), f"Result contains an invalid URL: '{url}'. Input: {json_str}"