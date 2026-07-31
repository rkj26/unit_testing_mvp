import random
import io

def gen_input() -> str:
    min_coord, max_coord = -10**6, 10**6
    min_coeff, max_coeff = -10**6, 10**6
    
    # Define several input generation strategies to ensure diverse coverage
    strategies = [
        "random_general",
        "min_n_max_coords",         # n=1, coords min/max
        "max_n_random_coords",      # n=300, random coords
        "home_univ_same",           # x1,y1 == x2,y2, answer must be 0
        "axis_parallel_lines",      # lines like x=k or y=k
        "lines_through_origin",     # lines like ax+by=0
        "extreme_coeff_values",     # a,b,c are near min/max
        "coords_near_zero_lines_far", # x,y small; a,b,c large
        "coords_far_lines_near_origin", # x,y large; a,b,c small
        "negative_coords_negative_coeffs", # test sign flips in negative quadrants
        "positive_coords_positive_coeffs", # test sign flips in positive quadrants
        "mixed_sign_coords_mixed_coeffs", # general mix
        "many_separating_lines", # high probability of many lines separating
        "few_separating_lines" # high probability of few lines separating
    ]
    
    strategy = random.choice(strategies)
    
    # Default values, potentially overridden by strategy
    x1, y1 = random.randint(min_coord, max_coord), random.randint(min_coord, max_coord)
    x2, y2 = random.randint(min_coord, max_coord), random.randint(min_coord, max_coord)
    n = random.randint(1, 300)

    # Apply strategy-specific adjustments
    if strategy == "min_n_max_coords":
        n = 1
        x1, y1 = min_coord, min_coord
        x2, y2 = max_coord, max_coord
    elif strategy == "max_n_random_coords":
        n = 300
    elif strategy == "home_univ_same":
        x2, y2 = x1, y1
    elif strategy == "axis_parallel_lines":
        n = random.randint(1, min(n, 10)) # Small N for focused test
        x1, y1 = random.randint(-100, 100), random.randint(-100, 100)
        x2, y2 = random.randint(-100, 100), random.randint(-100, 100)
    elif strategy == "lines_through_origin":
        n = random.randint(1, min(n, 10))
        x1, y1 = random.randint(-100, 100), random.randint(-100, 100)
        x2, y2 = random.randint(-100, 100), random.randint(-100, 100)
    elif strategy == "extreme_coeff_values":
        n = random.randint(1, min(n, 5)) # Small N
        points = [(min_coord, min_coord), (min_coord, max_coord), (max_coord, min_coord), (max_coord, max_coord),
                  (0, 0), (random.randint(-100, 100), random.randint(-100, 100))]
        x1, y1 = random.choice(points)
        x2, y2 = random.choice(points)
    elif strategy == "coords_near_zero_lines_far":
        n = random.randint(1, min(n, 10))
        x1, y1 = random.randint(-10, 10), random.randint(-10, 10)
        x2, y2 = random.randint(-10, 10), random.randint(-10, 10)
    elif strategy == "coords_far_lines_near_origin":
        n = random.randint(1, min(n, 10))
        x1, y1 = random.randint(max_coord - 100, max_coord), random.randint(max_coord - 100, max_coord)
        x2, y2 = random.randint(min_coord, min_coord + 100), random.randint(min_coord, min_coord + 100)
    elif strategy == "negative_coords_negative_coeffs":
        x1, y1 = random.randint(min_coord, -1), random.randint(min_coord, -1)
        x2, y2 = random.randint(min_coord, -1), random.randint(min_coord, -1)
    elif strategy == "positive_coords_positive_coeffs":
        x1, y1 = random.randint(1, max_coord), random.randint(1, max_coord)
        x2, y2 = random.randint(1, max_coord), random.randint(1, max_coord)
    elif strategy == "many_separating_lines":
        n = 300
        # Put points in opposite quadrants to maximize separation likelihood
        x1, y1 = random.randint(1, max_coord // 2), random.randint(1, max_coord // 2)
        x2, y2 = random.randint(min_coord // 2, -1), random.randint(min_coord // 2, -1)
    elif strategy == "few_separating_lines":
        n = 300
        # Put points close to each other, or in the same 'general' region
        x1, y1 = random.randint(-1000, 1000), random.randint(-1000, 1000)
        x2, y2 = random.randint(-1000, 1000), random.randint(-1000, 1000)

    output = io.StringIO()
    output.write(f"{x1} {y1}\n")
    output.write(f"{x2} {y2}\n")
    output.write(f"{n}\n")

    lines = set()
    for _ in range(n):
        while True:
            a, b, c = 0, 0, 0 # Initialize to 0 for default case
            
            # Generate a, b, c based on strategy or default to random
            if strategy == "axis_parallel_lines":
                if random.random() < 0.5: # Vertical line: x = -c/a
                    a = random.choice([1, -1])
                    b = 0
                else: # Horizontal line: y = -c/b
                    a = 0
                    b = random.choice([1, -1])
                c = random.randint(min_coeff, max_coeff)
            elif strategy == "lines_through_origin":
                a = random.randint(min_coeff, max_coeff)
                b = random.randint(min_coeff, max_coeff)
                c = 0
            elif strategy == "extreme_coeff_values":
                coeff_choices = [min_coeff, max_coeff, 0] + [random.randint(-1000, 1000) for _ in range(3)]
                a = random.choice(coeff_choices)
                b = random.choice(coeff_choices)
                c = random.choice(coeff_choices)
            elif strategy == "coords_near_zero_lines_far":
                # Ensure coeffs are large, so lines are far from origin
                a = random.randint(max_coeff // 2, max_coeff) * random.choice([-1, 1])
                b = random.randint(max_coeff // 2, max_coeff) * random.choice([-1, 1])
                c = random.randint(max_coeff // 2, max_coeff) * random.choice([-1, 1])
            elif strategy == "coords_far_lines_near_origin":
                # Ensure coeffs are small, so lines are near origin
                a = random.randint(-1000, 1000)
                b = random.randint(-1000, 1000)
                c = random.randint(-1000, 1000)
            elif strategy == "negative_coords_negative_coeffs":
                a = random.randint(min_coeff, -1)
                b = random.randint(min_coeff, -1)
                c = random.randint(min_coeff, -1)
            elif strategy == "positive_coords_positive_coeffs":
                a = random.randint(1, max_coeff)
                b = random.randint(1, max_coeff)
                c = random.randint(1, max_coeff)
            else: # "random_general" or strategies without specific coeff generation
                a = random.randint(min_coeff, max_coeff)
                b = random.randint(min_coeff, max_coeff)
                c = random.randint(min_coeff, max_coeff)

            # Ensure |a| + |b| > 0
            if a == 0 and b == 0:
                continue

            # Calculate base values for home and university
            # Using Python's arbitrary precision integers to avoid overflow
            val1_base = a * x1 + b * y1
            val2_base = a * x2 + b * y2

            # Potential c values that make points lie on the line
            c_forbidden_home = -val1_base
            c_forbidden_univ = -val2_base
            
            forbidden_values = set()
            # Only add to forbidden_values if they are within the coeff range
            if min_coeff <= c_forbidden_home <= max_coeff:
                forbidden_values.add(c_forbidden_home)
            if min_coeff <= c_forbidden_univ <= max_coeff:
                forbidden_values.add(c_forbidden_univ)

            # Ensure the generated c is not a forbidden value
            # If the initially generated c is forbidden, try to adjust it.
            # This handles cases where c is exactly a forbidden value.
            # Given that there are at most 2 forbidden values in a range of 2*10^6+1,
            # it's highly improbable to need more than +1/-1 adjustment.
            if c in forbidden_values:
                # Try c+1
                if c + 1 <= max_coeff and (c + 1 not in forbidden_values):
                    c += 1
                # Else try c-1
                elif c - 1 >= min_coeff and (c - 1 not in forbidden_values):
                    c -= 1
                # Else try c+2 (for cases like c=max_coeff-1, and max_coeff is forbidden)
                elif c + 2 <= max_coeff and (c + 2 not in forbidden_values):
                    c += 2
                # Else try c-2
                elif c - 2 >= min_coeff and (c - 2 not in forbidden_values):
                    c -= 2
                else:
                    # If all simple adjustments fail (very rare), regenerate the entire line (a,b,c)
                    continue 

            # Ensure unique lines (a, b, c) tuple
            if (a, b, c) in lines:
                continue
            
            lines.add((a, b, c))
            output.write(f"{a} {b} {c}\n")
            break # Valid line generated, move to next
            
    return output.getvalue()

def check(stdin: str, stdout: str) -> None:
    # Parse stdin
    input_lines = stdin.strip().split('\n')
    
    x1, y1 = map(int, input_lines[0].split())
    x2, y2 = map(int, input_lines[1].split())
    n = int(input_lines[2])
    
    roads = []
    for i in range(n):
        a, b, c = map(int, input_lines[3 + i].split())
        roads.append((a, b, c))
        
    # Calculate the expected number of separating lines
    expected_output = 0
    for a, b, c in roads:
        # Evaluate a*x + b*y + c for home and university points
        # Use Python's arbitrary precision integers to prevent overflow,
        # as a*x can be up to 10^6 * 10^6 = 10^12.
        val_home = a * x1 + b * y1 + c
        val_univ = a * x2 + b * y2 + c
        
        # A line separates two points if the values a*x+b*y+c have different signs.
        # It's guaranteed that neither point lies on a road, so val_home != 0 and val_univ != 0.
        if (val_home > 0 and val_univ < 0) or \
           (val_home < 0 and val_univ > 0):
            expected_output += 1
            
    # Parse stdout
    try:
        actual_output = int(stdout.strip())
    except ValueError:
        raise AssertionError(f"Output is not a valid integer: '{stdout}'")
    except Exception as e:
        raise AssertionError(f"Error parsing stdout: {e}, Output: '{stdout}'")
        
    # Assert that the actual output matches the expected output
    assert actual_output == expected_output, \
        f"Mismatch: Expected {expected_output}, Got {actual_output} for input:\n{stdin}"