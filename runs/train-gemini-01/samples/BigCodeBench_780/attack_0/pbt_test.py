# SEARCH PLAN:
# 1. Empty/Single Article List: Test the boundary condition of an empty list (explicitly raises ValueError) and a list with a single article.
# 2. Timezone Conversion & Hour Extraction: Verify correct timezone conversion and hour extraction by comparing with manually calculated hours for a single category.
# 3. Aggregation Logic: Test the count, mean, min, max aggregation for multiple categories and articles by comparing with a recomputed oracle.
# 4. Invalid Input Handling: Test for `TypeError` when `articles` is not a list and `ValueError` for missing dictionary keys.

from candidate import task_func
from hypothesis import given, settings, strategies as st
import pandas as pd
import pytz
from datetime import datetime
import string
import math

# Helper strategies
st_datetime_utc = st.datetimes(
    min_value=datetime(2000, 1, 1, tzinfo=pytz.UTC),
    max_value=datetime(2030, 12, 31, tzinfo=pytz.UTC)
)
st_category = st.text(string.ascii_letters, min_size=1, max_size=10)
# Repair: Changed max_size from 20 to 12 to adhere to collection size limits.
st_title = st.text(string.ascii_letters + string.digits + ' ', min_size=1, max_size=12)
# Repair: Changed max_size from 20 to 12 to adhere to collection size limits.
st_title_url = st.text(string.ascii_letters + string.digits + '_', min_size=1, max_size=12)
st_id = st.integers(min_value=1, max_value=1000)

# A small, representative set of timezones to ensure coverage without being exhaustive
# Includes UTC, common timezones, and those with large offsets.
st_timezone_str = st.sampled_from([
    'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo',
    'Pacific/Honolulu', 'Australia/Sydney', 'Africa/Cairo',
    'Etc/GMT+12', 'Etc/GMT-14' # Edge cases for offsets
])

@st.composite
def st_article_dict(draw):
    return {
        'title': draw(st_title),
        'title_url': draw(st_title_url),
        'id': draw(st_id),
        'category': draw(st_category),
        'published_time': draw(st_datetime_utc)
    }

@settings(max_examples=50, deadline=None)
@given(articles=st.just([]), timezone=st_timezone_str)
def test_empty_list_raises_value_error(articles, timezone):
    """
    SPEC BASIS: "ValueError: If an empty list is passed as articles."
    PROPERTY: Calling task_func with an empty list raises a ValueError.
    STRATEGY: Provide an empty list for 'articles' to hit the explicit error condition.
    """
    # The `with pytz.timezone(timezone):` block is not strictly necessary here
    # as the timezone string is passed directly to task_func, but it's harmless.
    with pytz.timezone(timezone):
        try:
            task_func(articles, timezone)
            assert False, "ValueError was not raised for an empty articles list."
        except ValueError as e:
            assert "empty list" in str(e) or "no articles" in str(e) # Check for expected error message content
        except Exception as e:
            assert False, f"Expected ValueError, but got {type(e).__name__}: {e}"

@settings(max_examples=50, deadline=None)
@given(article=st_article_dict(), timezone=st_timezone_str)
def test_single_article_timezone_conversion_and_hour_extraction(article, timezone):
    """
    SPEC BASIS: "1) Convert 'published_time' to a specified timezone",
                "3) For each category, calculate the count, mean, min, max publication times only considering the hour."
    PROPERTY: For a single article, the output DataFrame correctly reflects the hour after timezone conversion,
              with count=1, mean=hour, min=hour, max=hour.
    STRATEGY: Generate a single article and a timezone. Manually calculate the expected hour in the target timezone
              and compare it against the DataFrame's aggregated values for that category.
    """
    articles = [article]
    try:
        result_df = task_func(articles, timezone)
    except Exception:
        result_df = None
    assert result_df is not None, "task_func raised an unexpected exception for valid input."

    assert not result_df.empty, "Result DataFrame should not be empty for a single article."
    assert len(result_df) == 1, "Result DataFrame should have exactly one row for a single article."

    category = article['category']
    assert category in result_df.index, f"Category '{category}' not found in DataFrame index."

    # Manually calculate the expected hour in the target timezone
    target_tz = pytz.timezone(timezone)
    localized_time = article['published_time'].astimezone(target_tz)
    expected_hour = float(localized_time.hour)

    # Assertions for the single article's category
    assert result_df.loc[category, 'count'] == 1, "Count should be 1 for a single article."
    assert result_df.loc[category, 'mean'] == expected_hour, "Mean hour is incorrect."
    assert result_df.loc[category, 'min'] == expected_hour, "Min hour is incorrect."
    assert result_df.loc[category, 'max'] == expected_hour, "Max hour is incorrect."

@settings(max_examples=50, deadline=None)
@given(articles=st.lists(st_article_dict(), min_size=1, max_size=12), timezone=st_timezone_str)
def test_aggregation_logic_for_multiple_articles_and_categories(articles, timezone):
    """
    SPEC BASIS: "3) For each category, calculate the count, mean, min, max publication times only considering the hour."
    PROPERTY: The output DataFrame's count, mean, min, and max hours are correctly calculated for each category,
              matching a recomputed oracle.
    STRATEGY: Generate a list of articles with varying categories and times. Recompute the expected aggregation
              results (count, mean, min, max of hours after timezone conversion) and compare with task_func's output.
    """
    try:
        result_df = task_func(articles, timezone)
    except Exception:
        result_df = None
    assert result_df is not None, "task_func raised an unexpected exception for valid input."

    assert isinstance(result_df, pd.DataFrame), "Return type is not a pandas DataFrame."
    assert not result_df.empty, "Result DataFrame should not be empty for non-empty articles list."
    assert all(col in result_df.columns for col in ['count', 'mean', 'min', 'max']), \
        "DataFrame missing required columns: 'count', 'mean', 'min', 'max'."

    # Recompute the expected results
    expected_data = {}
    target_tz = pytz.timezone(timezone)

    for article in articles:
        category = article['category']
        localized_time = article['published_time'].astimezone(target_tz)
        hour = localized_time.hour

        if category not in expected_data:
            expected_data[category] = []
        expected_data[category].append(hour)

    expected_df_rows = []
    for category, hours in expected_data.items():
        expected_count = len(hours)
        expected_mean = sum(hours) / expected_count
        expected_min = min(hours)
        expected_max = max(hours)
        expected_df_rows.append({
            'category': category,
            'count': expected_count,
            'mean': expected_mean,
            'min': expected_min,
            'max': expected_max
        })

    if not expected_df_rows: # This case should not be hit due to min_size=1 for articles list
        assert result_df.empty
        return

    expected_df = pd.DataFrame(expected_df_rows).set_index('category')
    expected_df = expected_df.sort_index() # Ensure consistent order for comparison
    result_df = result_df.sort_index()

    pd.testing.assert_frame_equal(
        result_df, expected_df,
        check_dtype=True,
        check_exact=False, # Allow for floating point differences in mean
        atol=1e-9 # Absolute tolerance for float comparison
    )

@settings(max_examples=50, deadline=None)
@given(
    invalid_articles=st.one_of(
        st.none(),
        st.integers(),
        st.text(),
        # Repair: Added max_size=12 to adhere to collection size limits.
        st.dictionaries(st.text(min_size=1, max_size=10), st.text(min_size=1, max_size=10), max_size=12)
    ),
    timezone=st_timezone_str
)
def test_type_error_for_non_list_articles(invalid_articles, timezone):
    """
    SPEC BASIS: "TypeError: If articles is not a list of dictionaries."
    PROPERTY: Calling task_func with 'articles' that is not a list raises a TypeError.
    STRATEGY: Provide various non-list types for 'articles' to trigger the TypeError.
    """
    # The `with pytz.timezone(timezone):` block is not strictly necessary here.
    with pytz.timezone(timezone):
        try:
            task_func(invalid_articles, timezone)
            assert False, "TypeError was not raised for non-list articles input."
        except TypeError as e:
            assert "list of dictionaries" in str(e) or "list" in str(e) # Check for expected error message content
        except Exception as e:
            assert False, f"Expected TypeError, but got {type(e).__name__}: {e}"

@settings(max_examples=50, deadline=None)
@given(
    missing_key_articles=st.lists(
        st.dictionaries(
            st.sampled_from(['title', 'title_url', 'id', 'category', 'published_time']),
            st.one_of(st_title, st_title_url, st_id, st_category, st_datetime_utc),
            min_size=1, max_size=4 # Ensure at least one key is missing (5 required keys)
        ),
        min_size=1, max_size=5 # Max 5 articles in the list
    ),
    timezone=st_timezone_str
)
def test_value_error_for_missing_article_keys(missing_key_articles, timezone):
    """
    SPEC BASIS: "ValueError: If dictionary keys do not match the requirements."
    PROPERTY: Calling task_func with article dictionaries missing required keys raises a ValueError.
    STRATEGY: Generate article dictionaries that are guaranteed to be missing at least one of the required keys.
    """
    # The `with pytz.timezone(timezone):` block is not strictly necessary here.
    with pytz.timezone(timezone):
        try:
            task_func(missing_key_articles, timezone)
            assert False, "ValueError was not raised for articles with missing keys."
        except ValueError as e:
            assert "keys do not match" in str(e) or "missing key" in str(e) # Check for expected error message content
        except Exception as e:
            assert False, f"Expected ValueError, but got {type(e).__name__}: {e}"