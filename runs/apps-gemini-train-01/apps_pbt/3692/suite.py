import random
import math

# This function would be provided by the testing harness, not part of the solution.
# For local development, you might define a dummy function like this:
# def _run_program(stdin_str: str) -> str:
#     # This is a placeholder for the actual execution of the untrusted program.
#     # In a real environment, this would execute the model's code, e.g.:
#     # import subprocess
#     # proc = subprocess.run(['python', 'model_solution.py'], input=stdin_str, capture_output=True, text=True)
#     # return proc.stdout
#     raise NotImplementedError("The _run_program function must be provided by the test harness.")

class Circle:
    def __init__(self, x, y, r):
        self.x = x
        self.y = y
        self.r = r

    def __str__(self):
        return f"{self.x} {self.y} {self.r}"
    
    def __eq__(self, other):
        if not isinstance(other, Circle):
            return NotImplemented
        return self.x == other.x and self.y == other.y and self.r == other.r
    
    def __hash__(self):
        return hash((self.x, self.y, self.r))

    def translated(self, dx, dy):
        return Circle(self.x + dx, self.y + dy, self.r)

def gen_input() -> str:
    # Strategies to cover various geometric configurations and edge cases
    strategies = [
        "random_general",
        "n1_boundary",
        "n2_disjoint", "n2_nested", "n2_tangent_ext", "n2_tangent_int", "n2_intersecting",
        "n3_disjoint", "n3_nested", "n3_chain_tangent", "n3_chain_intersecting", "n3_maximal",
        "n3_three_way_intersection", # Specific case where 3 circles intersect at one point
    ]
    strategy = random.choice(strategies)

    circles = []
    n_val = random.randint(1, 3) # Default N for "random_general"

    # Set N based on the chosen strategy
    if strategy.startswith("n1"):
        n_val = 1
    elif strategy.startswith("n2"):
        n_val = 2
    elif strategy.startswith("n3"):
        n_val = 3

    # Helper to generate a valid circle within problem constraints
    def make_circle_random(min_x=-10, max_x=10, min_y=-10, max_y=10, min_r=1, max_r=10):
        return Circle(
            random.randint(min_x, max_x),
            random.randint(min_y, max_y),
            random.randint(min_r, max_r)
        )

    # Helper to ensure generated circles are unique, retrying if duplicate
    def add_unique_circle(circle_list, circle_gen_func):
        while True:
            new_c = circle_gen_func()
            if new_c not in circle_list:
                circle_list.append(new_c)
                break
    
    if strategy == "n1_boundary":
        c1_gen = lambda: random.choice([
            Circle(0, 0, 1), Circle(10, 10, 10), Circle(-10, -10, 1),
            make_circle_random() # one random circle too
        ])
        add_unique_circle(circles, c1_gen)
    elif strategy == "n2_disjoint":
        c1 = make_circle_random(max_x=0, min_r=1, max_r=5)
        # Ensure C2 is far enough from C1 to be disjoint
        c2 = make_circle_random(min_x=c1.x + c1.r + random.randint(3,10), min_r=1, max_r=5) 
        circles.extend([c1, c2])
    elif strategy == "n2_nested":
        c1 = make_circle_random(min_r=5, max_r=10)
        # Ensure c2 is strictly smaller and within c1's bounds
        r2 = random.randint(1, c1.r - 1) if c1.r > 1 else 1 # Ensure r2 is at least 1 and smaller
        # Shift center slightly to avoid exact concentricity for variety
        c2_x = c1.x + random.randint(-1, 1)
        c2_y = c1.y + random.randint(-1, 1)
        c2 = Circle(c2_x, c2_y, r2)
        circles.extend([c1, c2])
    elif strategy == "n2_tangent_ext":
        c1 = make_circle_random(min_r=1, max_r=5)
        r2 = random.randint(1, 5)
        dist = c1.r + r2
        theta = random.uniform(0, 2 * math.pi)
        c2 = Circle(int(c1.x + dist * math.cos(theta)), int(c1.y + dist * math.sin(theta)), r2)
        circles.extend([c1, c2])
    elif strategy == "n2_tangent_int":
        c1 = make_circle_random(min_r=5, max_r=10)
        r2 = random.randint(1, c1.r - 1) if c1.r > 1 else 1
        dist = c1.r - r2 
        theta = random.uniform(0, 2 * math.pi)
        c2 = Circle(int(c1.x + dist * math.cos(theta)), int(c1.y + dist * math.sin(theta)), r2)
        circles.extend([c1, c2])
    elif strategy == "n2_intersecting":
        c1 = make_circle_random(min_r=3, max_r=10)
        r2 = random.randint(3, 10)
        min_dist_for_intersect = abs(c1.r - r2) + 1 # Distance must be greater than |r1-r2|
        max_dist_for_intersect = c1.r + r2 - 1 # Distance must be less than r1+r2

        # Ensure valid range for 'dist' exists; otherwise, fallback to generic random
        if min_dist_for_intersect < max_dist_for_intersect:
            dist = random.randint(min_dist_for_intersect, max_dist_for_intersect)
            theta = random.uniform(0, 2 * math.pi)
            c2 = Circle(int(c1.x + dist * math.cos(theta)), int(c1.y + dist * math.sin(theta)), r2)
            circles.extend([c1, c2])
        else: # Fallback: if cannot guarantee 2 intersection points, generate randomly
            add_unique_circle(circles, make_circle_random)
            add_unique_circle(circles, make_circle_random)
    
    elif strategy == "n3_disjoint":
        c1 = make_circle_random(max_x=-5, min_r=1, max_r=3)
        c2 = make_circle_random(min_x=c1.x + c1.r + random.randint(3,6), max_x=5, min_r=1, max_r=3)
        c3 = make_circle_random(min_x=c2.x + c2.r + random.randint(3,6), min_r=1, max_r=3)
        circles.extend([c1, c2, c3])
    elif strategy == "n3_nested":
        c1 = make_circle_random(min_r=8, max_r=10)
        c2_r = random.randint(4, c1.r - 1) if c1.r > 4 else 1
        c2 = Circle(c1.x + random.randint(-1,1), c1.y + random.randint(-1,1), c2_r)
        c3_r = random.randint(1, c2.r - 1) if c2.r > 1 else 1
        c3 = Circle(c1.x + random.randint(-1,1), c1.y + random.randint(-1,1), c3_r)
        circles.extend([c1, c2, c3])
    elif strategy == "n3_chain_tangent": # Like Example 1 (0,0,1), (2,0,1), (4,0,1)
        c1 = make_circle_random(min_r=1, max_r=3, max_x=-3)
        c2_r = random.randint(1, 3)
        c2 = Circle(c1.x + c1.r + c2_r, c1.y + random.randint(-1,1), c2_r)
        c3_r = random.randint(1, 3)
        c3 = Circle(c2.x + c2.r + c3_r, c2.y + random.randint(-1,1), c3_r)
        circles.extend([c1, c2, c3])
    elif strategy == "n3_chain_intersecting": # Like Example 2 (0,0,2), (3,0,2), (6,0,2)
        c1 = make_circle_random(min_r=2, max_r=4, max_x=-3)
        r2 = random.randint(2,4)
        dist_c1_c2 = random.randint(abs(c1.r - r2) + 1, c1.r + r2 - 1)
        c2 = Circle(c1.x + dist_c1_c2, c1.y + random.randint(-1,1), r2)
        r3 = random.randint(2,4)
        dist_c2_c3 = random.randint(abs(c2.r - r3) + 1, c2.r + r3 - 1)
        c3 = Circle(c2.x + dist_c2_c3, c2.y + random.randint(-1,1), r3)
        circles.extend([c1,c2,c3])
    elif strategy == "n3_maximal": # Like Example 3 (0,0,2), (2,0,2), (1,1,2)
        # Generate three circles that likely intersect pairwise at two points each
        c1 = make_circle_random(min_r=3, max_r=5, min_x=-5, max_x=5, min_y=-5, max_y=5)
        # Place c2, c3 somewhat close to c1's center
        c2 = make_circle_random(min_r=3, max_r=5, min_x=c1.x-c1.r+1, max_x=c1.x+c1.r-1, min_y=c1.y-c1.r+1, max_y=c1.y+c1.r-1)
        c3 = make_circle_random(min_r=3, max_r=5, min_x=c1.x-c1.r+1, max_x=c1.x+c1.r-1, min_y=c1.y-c1.r+1, max_y=c1.y+c1.r-1)
        circles.extend([c1,c2,c3])
    elif strategy == "n3_three_way_intersection":
        # A configuration where three circles intersect at a common point.
        # Example: C1(0,0,5), C2(10,0,5), C3(5,5,5) all intersect at (5,0)
        # Randomly translate this configuration
        dx = random.randint(-5, 5)
        dy = random.randint(-5, 5)
        c1 = Circle(0+dx, 0+dy, 5)
        c2 = Circle(10+dx, 0+dy, 5)
        # Adjust c3's center to ensure it passes through (5+dx, 0+dy) given radius 5
        # The equation for c3: (X-(5+dx))^2 + (Y-(0+dy))^2 = 5^2.
        # This means, for c3's center (x3, y3), we need ( (5+dx)-x3 )^2 + ( (0+dy)-y3 )^2 = 5^2
        # Let's pick a center and calculate a radius that forces a common intersection.
        # More reliably, use a known configuration:
        # P = (5+dx, 0+dy) is common point
        # A = (5+dx+5, 0+dy) = (10+dx, 0+dy)
        # B = (5+dx-5, 0+dy) = (0+dx, 0+dy)
        # C = (5+dx, 0+dy+5) = (5+dx, 5+dy)
        # C1 is centered at B, radius 5
        # C2 is centered at A, radius 5
        # C3 is centered at C, radius 5
        # So we have C1(0+dx,0+dy,5), C2(10+dx,0+dy,5), C3(5+dx,5+dy,5).
        # These are within problem bounds if dx,dy are small.
        circles.extend([c1, c2, Circle(5+dx, 5+dy, 5)])

    else: # "random_general" or a fallback for other strategies if they failed to generate specific types
        for _ in range(n_val):
            add_unique_circle(circles, make_circle_random)
    
    # Ensure all generated circles are within the allowed input bounds (-10 <= x, y <= 10, 1 <= r <= 10)
    # Clamp values for safety after geometric calculations
    final_circles = []
    seen = set()
    for c in circles:
        c_clamped = Circle(
            max(-10, min(10, c.x)),
            max(-10, min(10, c.y)),
            max(1, min(10, c.r)) # radii must be 1 to 10
        )
        if c_clamped not in seen:
            final_circles.append(c_clamped)
            seen.add(c_clamped)
        else: # If clamping caused a duplicate, regenerate a random one
            new_c = make_circle_random()
            while new_c in seen:
                new_c = make_circle_random()
            final_circles.append(new_c)
            seen.add(new_c)
    
    circles = final_circles
    n_val = len(circles) # Actual N after uniqueness/clamping

    # Format output string
    output = f"{n_val}\n"
    for c in circles:
        output += f"{c.x} {c.y} {c.r}\n"
    return output

def parse_input(stdin: str):
    lines = stdin.strip().split('\n')
    n = int(lines[0])
    circles = []
    for i in range(1, n + 1):
        x, y, r = map(int, lines[i].split())
        circles.append(Circle(x, y, r))
    return n, circles

def parse_output(stdout: str):
    try:
        return int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")

def check(stdin: str, stdout: str) -> None:
    n, circles = parse_input(stdin)
    result = parse_output(stdout)

    # Property 1: Output is a single positive integer within expected bounds
    assert isinstance(result, int), f"Output '{stdout}' is not an integer."
    assert result > 0, f"Number of regions must be positive, got {result}."

    if n == 1:
        assert result == 2, f"Expected 2 regions for 1 circle, got {result}."
    elif n == 2:
        # For 2 circles, minimum regions (disjoint/nested) is 3, maximum regions (intersecting/tangent) is 4.
        assert 3 <= result <= 4, f"Expected 3 or 4 regions for 2 circles, got {result}."
    elif n == 3:
        # For 3 circles, minimum regions (all disjoint/nested) is 4, maximum regions (maximal intersection) is 8.
        assert 4 <= result <= 8, f"Expected 4 to 8 regions for 3 circles, got {result}."
    
    # Property 2: Metamorphic test - Translation invariance
    # Translate the entire set of circles and check if the number of regions remains the same.
    # The problem implies that _run_program will be provided by the test harness.

    # Calculate safe translation deltas to ensure translated circles remain within [-10, 10]
    min_x_coord = min(c.x for c in circles)
    max_x_coord = max(c.x for c in circles)
    min_y_coord = min(c.y for c in circles)
    max_y_coord = max(c.y for c in circles)

    # Possible range for dx to keep all x coordinates within [-10, 10]
    # Example: if max_x_coord is 10, then max_dx_pos is 0. If min_x_coord is -10, then max_dx_neg is 0.
    max_dx_pos = 10 - max_x_coord
    max_dx_neg = -10 - min_x_coord
    max_dy_pos = 10 - max_y_coord
    max_dy_neg = -10 - min_y_coord

    # Choose a small random translation for dx and dy, respecting bounds.
    # We restrict to [-2, 2] to ensure usually a non-zero translation is picked,
    # but also that circles near boundaries don't go out of range often.
    dx_choices = list(range(max(max_dx_neg, -2), min(max_dx_pos, 2) + 1))
    dy_choices = list(range(max(max_dy_neg, -2), min(max_dy_pos, 2) + 1))
    
    # Fallback to (0,0) if no other safe translation is possible (e.g., all circles already fill the bounds)
    dx = random.choice(dx_choices) if dx_choices else 0
    dy = random.choice(dy_choices) if dy_choices else 0
    
    # Generate translated input
    translated_circles = [c.translated(dx, dy) for c in circles]
    translated_stdin_lines = [str(n)] + [str(c) for c in translated_circles]
    translated_stdin = "\n".join(translated_stdin_lines) + "\n"

    # Execute the program with the translated input
    translated_stdout = _run_program(translated_stdin)
    translated_result = parse_output(translated_stdout)

    assert result == translated_result, \
        f"Translation invariance failed: Original result {result}, Translated result {translated_result}. " \
        f"Original input:\n{stdin}Translated input (dx={dx}, dy={dy}):\n{translated_stdin}"