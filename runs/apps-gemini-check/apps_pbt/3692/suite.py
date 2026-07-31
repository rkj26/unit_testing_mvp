from hypothesis import given, strategies as st, settings
from harness import run_candidate
import math

# Helper function to calculate distance between two points
def dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

# Build ONE valid STDIN string in this problem's exact input format (include newlines the problem expects).
@st.composite
def make_input(draw):
    n = draw(st.integers(min_value=1, max_value=3))
    circles = []
    used_configs = set()

    for _ in range(n):
        while True:
            x = draw(st.integers(min_value=-10, max_value=10))
            y = draw(st.integers(min_value=-10, max_value=10))
            r = draw(st.integers(min_value=1, max_value=10))
            config = (x, y, r)
            if config not in used_configs:
                circles.append(config)
                used_configs.add(config)
                break

    input_str = f"{n}\n"
    for x, y, r in circles:
        input_str += f"{x} {y} {r}\n"
    return input_str.strip()

@given(make_input())
@settings(max_examples=500, deadline=None)
def test_output_is_single_integer(stdin):
    stdout = run_candidate(stdin)
    try:
        value = int(stdout.strip())
        assert value >= 1, "Number of regions must be at least 1 (the infinite region)"
    except ValueError:
        raise AssertionError(f"Output '{stdout.strip()}' is not a single integer.")

@given(make_input())
@settings(max_examples=500, deadline=None)
def test_regions_upper_bound(stdin):
    # Euler's formula for planar graphs: V - E + F = 1 + C (for connected graphs, C=1)
    # For circles, the maximum number of regions is given by N^2 - N + 2, where N is the number of circles.
    # This occurs when every pair of circles intersects at two distinct points, and no three circles intersect at a single point.
    # For N=1, max regions = 1^2 - 1 + 2 = 2
    # For N=2, max regions = 2^2 - 2 + 2 = 4
    # For N=3, max regions = 3^2 - 3 + 2 = 8
    # The formula is actually N^2 - N + 2 for N circles, if all circles intersect each other at two distinct points.
    # A more general formula is 1 + E + F_c, where E is the number of intersection points and F_c is the number of circle arcs.
    # A simpler upper bound is 1 + N + N(N-1) = N^2 + 1.
    # For N=1, max regions = 2
    # For N=2, max regions = 4
    # For N=3, max regions = 8
    # The actual formula for maximum regions is N^2 - N + 2.
    # Let's use the known maximums for N=1, 2, 3.
    # N=1: max 2 regions (inside, outside)
    # N=2: max 4 regions (two circles intersect at two points)
    # N=3: max 8 regions (three circles intersect pairwise at two points, no three-way intersection)

    lines = stdin.strip().split('\n')
    n = int(lines[0])
    stdout = run_candidate(stdin)
    num_regions = int(stdout.strip())

    if n == 1:
        assert num_regions <= 2, f"For N=1, regions should be at most 2, got {num_regions}"
    elif n == 2:
        assert num_regions <= 4, f"For N=2, regions should be at most 4, got {num_regions}"
    elif n == 3:
        assert num_regions <= 8, f"For N=3, regions should be at most 8, got {num_regions}"

    # Also, the number of regions must be at least 1 (the infinite region).
    # If there are N circles, there are at least N+1 regions if no circles overlap or intersect.
    # If circles are nested, it's still N+1.
    # The minimum number of regions is N+1 (e.g., N concentric circles).
    assert num_regions >= n + 1, f"For N={n}, regions should be at least {n+1}, got {num_regions}"


@given(make_input())
@settings(max_examples=500, deadline=None)
def test_regions_monotonicity_with_non_intersecting_circles(stdin):
    # If we have N circles and add a new circle that does not intersect any existing circles,
    # the number of regions should increase by 1.
    # This is a metamorphic property.

    lines = stdin.strip().split('\n')
    n_original = int(lines[0])

    if n_original < 3: # We can only add a circle if n < 3
        original_stdout = run_candidate(stdin)
        original_regions = int(original_stdout.strip())

        # Create a new circle far away from all existing circles
        # Find max_r and max_abs_coord to place the new circle far enough
        max_r = 0
        max_abs_coord = 0
        circles_data = []
        for i in range(1, n_original + 1):
            x, y, r = map(int, lines[i].split())
            circles_data.append((x, y, r))
            max_r = max(max_r, r)
            max_abs_coord = max(max_abs_coord, abs(x) + r, abs(y) + r)

        new_x = max_abs_coord + max_r + 100 # Ensure it's far enough
        new_y = max_abs_coord + max_r + 100
        new_r = 1

        # Check if this new circle configuration already exists
        new_circle_config = (new_x, new_y, new_r)
        existing_configs = set((c[0], c[1], c[2]) for c in circles_data)
        if new_circle_config in existing_configs:
            # If by chance the new circle config is identical to an existing one,
            # we can't use it as the problem states "No two circles have the same x, y and r at the same time."
            # This is highly unlikely given the large coordinates, but for robustness.
            return

        # Construct new stdin with the added circle
        new_n = n_original + 1
        new_stdin = f"{new_n}\n"
        for x, y, r in circles_data:
            new_stdin += f"{x} {y} {r}\n"
        new_stdin += f"{new_x} {new_y} {new_r}\n"

        new_stdout = run_candidate(new_stdin.strip())
        new_regions = int(new_stdout.strip())

        # Verify that the new circle indeed does not intersect any existing circles
        # A circle (x1, y1, r1) and (x2, y2, r2) do not intersect if dist((x1,y1), (x2,y2)) > r1 + r2
        for cx, cy, cr in circles_data:
            distance = dist(cx, cy, new_x, new_y)
            assert distance > cr + new_r, \
                f"New circle ({new_x},{new_y},{new_r}) unexpectedly intersects existing circle ({cx},{cy},{cr}). Distance: {distance}, Sum of radii: {cr+new_r}"

        assert new_regions == original_regions + 1, \
            f"Adding a non-intersecting circle should increase regions by 1. Original: {original_regions}, New: {new_regions}"

@given(make_input())
@settings(max_examples=500, deadline=None)
def test_regions_with_concentric_circles(stdin):
    # If all circles are concentric, the number of regions should be N+1.
    # This is a specific edge case.

    lines = stdin.strip().split('\n')
    n = int(lines[0])

    if n > 0:
        # Extract the first circle's center
        x0, y0, r0 = map(int, lines[1].split())

        # Create a new input where all circles are concentric at (x0, y0)
        # and have distinct radii to avoid identical circles.
        # Radii must be distinct and positive.
        concentric_circles = []
        radii = set()
        for i in range(n):
            # Use a strategy to generate distinct radii
            # We need to ensure radii are distinct and positive.
            # Let's use a simple increasing sequence for radii.
            r_val = 1 + i * 2 # Ensure distinct and positive
            concentric_circles.append((x0, y0, r_val))

        # Construct the new stdin
        concentric_stdin = f"{n}\n"
        for cx, cy, cr in concentric_circles:
            concentric_stdin += f"{cx} {cy} {cr}\n"

        stdout = run_candidate(concentric_stdin.strip())
        num_regions = int(stdout.strip())

        assert num_regions == n + 1, \
            f"For {n} concentric circles, expected {n+1} regions, got {num_regions}. Input: {concentric_stdin.strip()}"