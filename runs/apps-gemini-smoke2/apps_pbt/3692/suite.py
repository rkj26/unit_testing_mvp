from hypothesis import given, strategies as st, settings
from harness import run_candidate   # run_candidate(stdin: str) -> stdout: str

# Helper to format circles into a string
def format_circles(n, circles):
    lines = [str(n)]
    for x, y, r in circles:
        lines.append(f"{x} {y} {r}")
    return "\n".join(lines) + "\n"

# Strategy for generating a valid input string
@st.composite
def make_input(draw):
    n = draw(st.integers(min_value=1, max_value=3))

    # Generate n unique circles
    circles = draw(st.lists(
        st.tuples(
            st.integers(min_value=-10, max_value=10), # x
            st.integers(min_value=-10, max_value=10), # y
            st.integers(min_value=1, max_value=10)    # r
        ),
        min_size=n,
        max_size=n,
        unique_by=lambda c: (c[0], c[1], c[2]) # Ensures no two circles have the same x,y,r
    ))

    return format_circles(n, circles)

@given(make_input())
@settings(max_examples=50, deadline=None)
def test_output_format_and_bounds(stdin):
    """
    Verifies that the output is a single integer and falls within the provable
    minimum and maximum number of regions for a given N.
    """
    stdout = run_candidate(stdin)
    
    # Assert output is a single integer
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output '{stdout.strip()}' is not a single integer.")

    # Extract N from the input for bounds checking
    lines = stdin.strip().split('\n')
    n = int(lines[0])

    # Assert bounds based on N
    if n == 1:
        # One circle always divides the plane into 2 regions.
        assert result == 2, f"Expected 2 regions for n=1, got {result} for input:\n{stdin}"
    elif n == 2:
        # Two circles:
        # Min: 3 regions (e.g., disjoint or tangent, or one contains another).
        # Max: 4 regions (e.g., two intersecting circles).
        assert 3 <= result <= 4, f"Expected 3 or 4 regions for n=2, got {result} for input:\n{stdin}"
    elif n == 3:
        # Three circles:
        # Min: 4 regions (e.g., three disjoint circles, or three nested).
        # Max: 8 regions (e.g., three circles mutually intersecting, no three points concurrent).
        assert 4 <= result <= 8, f"Expected 4 to 8 regions for n=3, got {result} for input:\n{stdin}"
    else:
        # This case should not be reached due to make_input constraints
        raise AssertionError(f"Invalid n value encountered: {n}")


@st.composite
def make_translated_input_pair(draw):
    """
    Generates an original input and a translated version of it, ensuring both
    remain within the problem's coordinate bounds.
    """
    n = draw(st.integers(min_value=1, max_value=3))
    
    original_circles = draw(st.lists(
        st.tuples(
            st.integers(min_value=-10, max_value=10),
            st.integers(min_value=-10, max_value=10),
            st.integers(min_value=1, max_value=10)
        ),
        min_size=n,
        max_size=n,
        unique_by=lambda c: (c[0], c[1], c[2])
    ))

    # Determine safe translation ranges for dx, dy to keep all (x+dx, y+dy) within [-10, 10]
    min_x = min(c[0] for c in original_circles)
    max_x = max(c[0] for c in original_circles)
    min_y = min(c[1] for c in original_circles)
    max_y = max(c[1] for c in original_circles)

    dx_lower_bound = -10 - min_x
    dx_upper_bound = 10 - max_x
    dy_lower_bound = -10 - min_y
    dy_upper_bound = 10 - max_y

    # Intersect with a smaller fixed range like [-5, 5] to encourage non-zero shifts
    # but also not to produce too wide spread coordinates in case original circles are compact
    dx_valid_range = st.integers(max(dx_lower_bound, -5), min(dx_upper_bound, 5))
    dy_valid_range = st.integers(max(dy_lower_bound, -5), min(dy_upper_bound, 5))

    # Handle cases where no valid integer translation exists for the intersection
    # (e.g., dx_lower_bound > dx_upper_bound after intersecting with [-5,5])
    # In such cases, default to a zero shift.
    try:
        dx = draw(dx_valid_range)
    except Exception: # Catch specific error from Hypothesis if range is empty
        dx = 0
    
    try:
        dy = draw(dy_valid_range)
    except Exception: # Catch specific error from Hypothesis if range is empty
        dy = 0

    # Apply translation
    translated_circles = []
    for x, y, r in original_circles:
        translated_circles.append((x + dx, y + dy, r))
    
    stdin_original = format_circles(n, original_circles)
    stdin_translated = format_circles(n, translated_circles)

    return stdin_original, stdin_translated

@given(make_translated_input_pair())
@settings(max_examples=50, deadline=None)
def test_translation_invariance(input_pair):
    """
    Tests that translating all circles by a (dx, dy) vector does not change
    the total number of regions. This is a fundamental geometric property.
    """
    stdin_original, stdin_translated = input_pair
    
    stdout_original = run_candidate(stdin_original)
    stdout_translated = run_candidate(stdin_translated)
    
    result_original = int(stdout_original.strip())
    result_translated = int(stdout_translated.strip())
    
    assert result_original == result_translated, \
        f"Translation changed region count.\nOriginal input:\n{stdin_original} -> {result_original}\n" \
        f"Translated input:\n{stdin_translated} -> {result_translated}"


@st.composite
def make_permuted_input_pair(draw):
    """
    Generates an original input and a permuted version of the circle order.
    """
    n = draw(st.integers(min_value=1, max_value=3))
    
    circles = draw(st.lists(
        st.tuples(
            st.integers(min_value=-10, max_value=10),
            st.integers(min_value=-10, max_value=10),
            st.integers(min_value=1, max_value=10)
        ),
        min_size=n,
        max_size=n,
        unique_by=lambda c: (c[0], c[1], c[2])
    ))

    # Create a permuted copy
    permuted_circles = list(circles) # Make a copy
    draw(st.permutations(permuted_circles)) # This mutates permuted_circles in place
    
    stdin_original = format_circles(n, circles)
    stdin_permuted = format_circles(n, permuted_circles)

    return stdin_original, stdin_permuted

@given(make_permuted_input_pair())
@settings(max_examples=50, deadline=None)
def test_permutation_invariance(input_pair):
    """
    Tests that permuting the order of circles in the input does not change
    the total number of regions. The order of input should not matter.
    """
    stdin_original, stdin_permuted = input_pair
    
    stdout_original = run_candidate(stdin_original)
    stdout_permuted = run_candidate(stdin_permuted)
    
    result_original = int(stdout_original.strip())
    result_permuted = int(stdout_permuted.strip())
    
    assert result_original == result_permuted, \
        f"Permutation changed region count.\nOriginal input:\n{stdin_original} -> {result_original}\n" \
        f"Permuted input:\n{stdin_permuted} -> {result_permuted}"


@st.composite
def make_specific_cases_input(draw):
    """
    Generates specific, commonly tricky geometric configurations for N=1, 2, 3
    that have known region counts. This helps cover edge cases like disjoint,
    nested, tangent, or fully intersecting circles.
    """
    n = draw(st.integers(min_value=1, max_value=3))
    circles = []
    expected_regions = 0

    if n == 1:
        # A single circle (always 2 regions)
        x = draw(st.integers(min_value=-10, max_value=10))
        y = draw(st.integers(min_value=-10, max_value=10))
        r = draw(st.integers(min_value=1, max_value=10))
        circles = [(x, y, r)]
        expected_regions = 2
    elif n == 2:
        choice = draw(st.sampled_from(["disjoint", "concentric", "tangent", "intersecting"]))
        
        if choice == "disjoint":
            # Two widely separated circles (3 regions)
            r1 = draw(st.integers(1, 2))
            r2 = draw(st.integers(1, 2))
            c1 = (draw(st.integers(-10, -5)), draw(st.integers(-10, 10)), r1)
            c2 = (draw(st.integers(5, 10)), draw(st.integers(-10, 10)), r2)
            st.assume(c1 != c2) # Ensure distinct. Distant by design, but good to be explicit.
            circles = [c1, c2]
            expected_regions = 3
        elif choice == "concentric":
            # One circle strictly inside another (3 regions)
            x, y = draw(st.integers(-5, 5)), draw(st.integers(-5, 5))
            r1 = draw(st.integers(5, 10))
            r2 = draw(st.integers(1, r1 - 1)) # r2 must be smaller and positive
            circles = [(x, y, r1), (x, y, r2)]
            expected_regions = 3
        elif choice == "tangent":
            # Two circles touching at exactly one point (3 regions)
            r_val = draw(st.integers(1, 4)) # Keep radius small for coordinate range
            x_base, y_base = draw(st.integers(-10 + r_val, 10 - 3*r_val)), draw(st.integers(-10, 10))
            c1 = (x_base, y_base, r_val)
            c2 = (x_base + 2 * r_val, y_base, r_val) # Tangent horizontally
            st.assume(-10 <= c2[0] <= 10 and -10 <= c2[1] <= 10) # Ensure C2 is in bounds
            circles = [c1, c2]
            expected_regions = 3
        elif choice == "intersecting":
            # Two circles intersecting at two points (4 regions)
            r_val = draw(st.integers(2, 5)) # Radius large enough to allow intersection
            x_base, y_base = draw(st.integers(-10 + r_val, 10 - 2*r_val)), draw(st.integers(-10, 10))
            c1 = (x_base, y_base, r_val)
            # Center of C2 is at distance d from C1, where 0 < d < 2*r_val (for intersection)
            d = draw(st.integers(1, 2 * r_val - 1))
            c2 = (x_base + d, y_base, r_val) # Intersecting horizontally
            st.assume(-10 <= c2[0] <= 10 and -10 <= c2[1] <= 10) # Ensure C2 is in bounds
            circles = [c1, c2]
            expected_regions = 4
    elif n == 3:
        choice = draw(st.sampled_from(["three_disjoint", "three_nested", "example_max_regions"]))
        
        if choice == "three_disjoint":
            # Three widely separated circles (4 regions)
            r_val = draw(st.integers(1, 2))
            c1 = (draw(st.integers(-10, -5)), draw(st.integers(-10, 10)), r_val)
            c2 = (draw(st.integers(-2, 2)), draw(st.integers(-10, 10)), r_val)
            c3 = (draw(st.integers(5, 10)), draw(st.integers(-10, 10)), r_val)
            # Ensure all three are distinct
            st.assume(len(set([c1, c2, c3])) == 3)
            circles = [c1, c2, c3]
            expected_regions = 4
        elif choice == "three_nested":
            # Three concentric circles (4 regions)
            x, y = draw(st.integers(-5, 5)), draw(st.integers(-5, 5))
            r1 = draw(st.integers(8, 10))
            r2 = draw(st.integers(4, r1 - 1))
            r3 = draw(st.integers(1, r2 - 1))
            circles = [(x, y, r1), (x, y, r2), (x, y, r3)]
            st.assume(r1 > r2 and r2 > r3 and r3 >= 1) # Ensure distinct radii and valid
            expected_regions = 4
        elif choice == "example_max_regions":
            # The example input from the problem that produces 8 regions
            circles = [(0, 0, 2), (2, 0, 2), (1, 1, 2)]
            expected_regions = 8

    stdin_str = format_circles(n, circles)
    return stdin_str, expected_regions

@given(make_specific_cases_input())
@settings(max_examples=50, deadline=None)
def test_specific_degenerate_cases(input_pair):
    """
    Tests specific configurations of circles where the expected number of regions
    is known, including minimum, maximum, and common interaction types.
    """
    stdin, expected_regions = input_pair
    
    stdout = run_candidate(stdin)
    result = int(stdout.strip())
    
    assert result == expected_regions, \
        f"Specific case yielded wrong regions.\nInput:\n{stdin} -> Expected {expected_regions}, Got {result}"