import random

def _gen_unique_circle(existing_circles, x_range=(-10, 10), y_range=(-10, 10), r_range=(1, 10)):
    """Generates a unique circle (x, y, r) within specified ranges."""
    while True:
        x = random.randint(x_range[0], x_range[1])
        y = random.randint(y_range[0], y_range[1])
        r = random.randint(r_range[0], r_range[1])
        circle_tuple = (x, y, r)
        if circle_tuple not in existing_circles:
            existing_circles.add(circle_tuple)
            return circle_tuple

def gen_input() -> str:
    """
    Generates a single STDIN string for the problem.
    Covers N=1, N=2, N=3, with specific configurations for each N
    to thoroughly test edge cases and common scenarios.
    """
    # Bias towards N=3 as it's the most complex case.
    n_choice = random.choice([1]*2 + [2]*3 + [3]*8)
    n = n_choice

    circles = set()
    input_lines = [str(n)]

    # Handle N=1 explicitly
    if n == 1:
        circles.add(_gen_unique_circle(circles))
    # Handle N=2 with various geometric relationships
    elif n == 2:
        choice = random.choice(["disjoint_sep", "disjoint_nested", "tangent_ext", "tangent_int",
                               "intersecting_small_d", "intersecting_large_d", "random"])
        if choice == "disjoint_sep":
            r1 = random.randint(1, 4)
            r2 = random.randint(1, 4)
            c1_center_x, c1_center_y = random.randint(-5, 5), random.randint(-5, 5)
            # Ensure separation
            c2_center_x = c1_center_x + r1 + r2 + random.randint(1, 5)
            circles.add((c1_center_x, c1_center_y, r1))
            circles.add((c2_center_x, c1_center_y, r2))
        elif choice == "disjoint_nested":
            r_outer = random.randint(5, 10)
            r_inner = random.randint(1, r_outer - 1)
            c_center_x, c_center_y = random.randint(-5, 5), random.randint(-5, 5)
            circles.add((c_center_x, c_center_y, r_outer))
            circles.add((c_center_x, c_center_y, r_inner))
        elif choice == "tangent_ext":
            r1 = random.randint(1, 5)
            r2 = random.randint(1, 5)
            c_center_x, c_center_y = random.randint(-5, 5), random.randint(-5, 5)
            circles.add((c_center_x, c_center_y, r1))
            circles.add((c_center_x + r1 + r2, c_center_y, r2))
        elif choice == "tangent_int":
            r_outer = random.randint(5, 10)
            r_inner = random.randint(1, r_outer - 1)
            dx = r_outer - r_inner
            c_center_x, c_center_y = random.randint(-5, 5), random.randint(-5, 5)
            circles.add((c_center_x, c_center_y, r_outer))
            circles.add((c_center_x + dx, c_center_y, r_inner))
        elif choice == "intersecting_small_d": # circles barely intersect
            r1 = random.randint(4, 7)
            r2 = random.randint(4, 7)
            d = abs(r1 - r2) + 1 # minimal distance for intersection
            c_center_x, c_center_y = random.randint(-5, 5), random.randint(-5, 5)
            circles.add((c_center_x, c_center_y, r1))
            circles.add((c_center_x + d, c_center_y, r2))
        elif choice == "intersecting_large_d": # circles intersect deeply
            r1 = random.randint(4, 7)
            r2 = random.randint(4, 7)
            d = r1 + r2 - 1 # maximal distance for intersection
            c_center_x, c_center_y = random.randint(-5, 5), random.randint(-5, 5)
            circles.add((c_center_x, c_center_y, r1))
            circles.add((c_center_x + d, c_center_y, r2))
        else: # "random" N=2 case
            circles.add(_gen_unique_circle(circles))
            circles.add(_gen_unique_circle(circles))
    # Handle N=3 with specific configurations, including examples
    elif n == 3:
        choice = random.choice(["ex1", "ex2", "ex3", "nested_concentric", "nested_non_concentric",
                               "all_disjoint_tight", "all_tangent_collinear", "collinear_overlap",
                               "random_dense", "random_sparse", "random"])
        
        # Helper to add circles from a specific configuration
        def add_circles_config(config_circles_list):
            for c in config_circles_list:
                circles.add(c)
        
        # Use problem examples
        if choice == "ex1": add_circles_config([(0,0,1), (2,0,1), (4,0,1)])
        elif choice == "ex2": add_circles_config([(0,0,2), (3,0,2), (6,0,2)])
        elif choice == "ex3": add_circles_config([(0,0,2), (2,0,2), (1,1,2)])
        # Nested configurations
        elif choice == "nested_concentric":
            c_center_x, c_center_y = random.randint(-5, 5), random.randint(-5, 5)
            r1 = random.randint(1, 3)
            r2 = random.randint(r1+1, 6)
            r3 = random.randint(r2+1, 10)
            add_circles_config([(c_center_x, c_center_y, r1), (c_center_x, c_center_y, r2), (c_center_x, c_center_y, r3)])
        elif choice == "nested_non_concentric":
            c_offset_x, c_offset_y = random.randint(-2, 2), random.randint(-2, 2)
            r1 = random.randint(1, 2)
            r2 = random.randint(r1+2, 5)
            r3 = random.randint(r2+2, 9)
            add_circles_config([(0,0,r3), (c_offset_x, c_offset_y, r2), (2*c_offset_x, 2*c_offset_y, r1)])
        # Disjoint/tangent/overlapping configurations
        elif choice == "all_disjoint_tight": # Disjoint but close
            add_circles_config([(0,0,2), (5,0,2), (-5,0,2)])
        elif choice == "all_tangent_collinear": # Three circles tangent on a line
            add_circles_config([(0,0,2), (4,0,2), (8,0,2)])
        elif choice == "collinear_overlap": # Three circles overlapping significantly on a line
            add_circles_config([(0,0,5), (2,0,5), (4,0,5)])
        # Random configurations
        elif choice == "random_dense": # Circles clustered
            center_x, center_y = random.randint(-5, 5), random.randint(-5, 5)
            for _ in range(n):
                x = random.randint(max(-10, center_x-2), min(10, center_x+2))
                y = random.randint(max(-10, center_y-2), min(10, center_y+2))
                r = random.randint(3, 7)
                circles.add(_gen_unique_circle(circles) if random.random() < 0.2 else (x,y,r))
        elif choice == "random_sparse": # Circles spread out with small radii
            for _ in range(n):
                x = random.randint(-10, 10)
                y = random.randint(-10, 10)
                r = random.randint(1, 2)
                circles.add(_gen_unique_circle(circles) if random.random() < 0.2 else (x,y,r))
        else: # Default "random" case
            for _ in range(n):
                circles.add(_gen_unique_circle(circles))
    
    # Ensure exactly N unique circles are generated for the input
    while len(circles) < n:
        circles.add(_gen_unique_circle(circles))

    # Format the circles into the STDIN string
    for c_x, c_y, c_r in list(circles)[:n]: # Take only N circles
        input_lines.append(f"{c_x} {c_y} {c_r}")

    return "\n".join(input_lines) + "\n"

def check(stdin: str, stdout: str) -> None:
    """
    Verifies the program's output based on problem constraints and metamorphic relations.
    """
    # 1. Parse stdin to get the original circles and N
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    original_circles = []
    for i in range(1, n + 1):
        x, y, r = map(int, lines[i].split())
        original_circles.append((x, y, r))

    # 2. Parse stdout and validate it's a single integer
    try:
        result = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout.strip()}'")

    # 3. Basic Format and Range Checks (Soundness is non-negotiable)
    assert result > 0, f"Number of regions must be positive, got {result} for N={n}"
    if n == 1:
        assert result == 2, f"For N=1, expected 2 regions, got {result}"
    elif n == 2:
        assert 3 <= result <= 4, f"For N=2, expected 3-4 regions, got {result}"
    elif n == 3:
        assert 4 <= result <= 8, f"For N=3, expected 4-8 regions, got {result}"
    
    # --- Metamorphic Relations ---
    
    # Helper to check if a transformed list of circles remains within input constraints
    def is_valid_circles_list(circles_list):
        for x, y, r in circles_list:
            if not (-10 <= x <= 10 and -10 <= y <= 10 and 1 <= r <= 10):
                return False
        return True

    # Helper to format a list of circles into the STDIN string format
    def format_circles_to_stdin(n_val, circles_list):
        lines = [str(n_val)]
        for c_x, c_y, c_r in circles_list:
            lines.append(f"{c_x} {c_y} {c_r}")
        return "\n".join(lines) + "\n"

    # Define various geometric transformations.
    # These transformations should preserve the number of regions.
    transformations = []

    # 1. Translation: Shift all circles by (dx, dy). dx/dy are kept small to stay within bounds.
    dx = random.randint(-2, 2)
    dy = random.randint(-2, 2)
    if dx != 0 or dy != 0: # Only add if it's an actual shift
        transformations.append(
            (f"Translation by ({dx},{dy})",
             lambda x, y, r: (x + dx, y + dy, r))
        )

    # 2. Reflection across x-axis: (x, y, r) -> (x, -y, r)
    transformations.append(
        ("Reflection across x-axis",
         lambda x, y, r: (x, -y, r))
    )

    # 3. Reflection across y-axis: (x, y, r) -> (-x, y, r)
    transformations.append(
        ("Reflection across y-axis",
         lambda x, y, r: (-x, y, r))
    )
    
    # 4. Reflection across origin: (x, y, r) -> (-x, -y, r)
    transformations.append(
        ("Reflection across origin",
         lambda x, y, r: (-x, -y, r))
    )

    # 5. Reflection across y=x line: (x, y, r) -> (y, x, r)
    transformations.append(
        ("Reflection across y=x",
         lambda x, y, r: (y, x, r))
    )
    
    # 6. Reflection across y=-x line: (x, y, r) -> (-y, -x, r)
    transformations.append(
        ("Reflection across y=-x",
         lambda x, y, r: (-y, -x, r))
    )

    # Execute metamorphic tests by re-running the program with transformed inputs.
    # `rerun_program` is assumed to be provided by the testing harness.
    if 'rerun_program' in globals():
        for desc, transform_func in transformations:
            transformed_circles = []
            for c_x, c_y, c_r in original_circles:
                new_x, new_y, new_r = transform_func(c_x, c_y, c_r)
                transformed_circles.append((new_x, new_y, new_r))
            
            # Crucially, only run the test if the transformed input is still valid
            # and the number of distinct circles remains N.
            if is_valid_circles_list(transformed_circles) and len(set(transformed_circles)) == n:
                stdin_transformed = format_circles_to_stdin(n, transformed_circles)
                
                try:
                    stdout_transformed = rerun_program(stdin_transformed)
                    result_transformed = int(stdout_transformed.strip())
                    assert result_transformed == result, \
                        f"Metamorphic test failed for '{desc}': " \
                        f"Original output was {result}, transformed output was {result_transformed}.\n" \
                        f"Original stdin:\n{stdin.strip()}\n" \
                        f"Transformed stdin:\n{stdin_transformed.strip()}"
                except Exception as e:
                    raise AssertionError(f"Program crashed or produced invalid output on transformed input ({desc}): {e}\n"
                                         f"Transformed stdin:\n{stdin_transformed.strip()}") from e