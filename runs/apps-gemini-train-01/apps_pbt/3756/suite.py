import random
import string
from decimal import Decimal, ROUND_HALF_UP

def gen_input() -> str:
    n_val = random.choice([
        3, 4, 5, 10, 20, 50, 100, 500, 1000, 200000,
        random.randint(3, 200000)
    ])
    t_val = random.choice([
        1, 2, 3, 5, 10, 100, 1000, 10**5, 10**9,
        random.randint(1, 10**9)
    ])

    # Ensure at least one digit before and after the decimal point
    dot_idx = random.randint(1, n_val - 2) 
    int_part_len = dot_idx
    dec_part_len = n_val - 1 - dot_idx

    int_part = []
    # First digit of integer part must not be '0'
    int_part.append(random.choice('123456789'))
    int_part.extend(random.choices(string.digits, k=int_part_len - 1))

    dec_part = []
    # Generate decimal part with various patterns to test different rounding scenarios
    pattern_choice = random.random()

    if pattern_choice < 0.2: # Case: No digits >= '5' in decimal part
        dec_part.extend(random.choices('1234', k=dec_part_len - 1))
        dec_part.append(random.choice('1234')) # Last digit not '0'
    elif pattern_choice < 0.4: # Case: First roundable digit (>= '5') is relatively early
        round_pos = random.randint(0, min(dec_part_len - 1, 3)) # Position for the first '>=5' digit
        dec_part.extend(random.choices('1234', k=round_pos))
        dec_part.append(random.choice('56789'))
        if dec_part_len - 1 - round_pos > 0:
            dec_part.extend(random.choices(string.digits, k=dec_part_len - 1 - round_pos))
        if dec_part[-1] == '0': dec_part[-1] = random.choice('123456789') # Ensure last digit is not '0'
    elif pattern_choice < 0.6: # Case: First roundable digit (>= '5') is relatively late
        round_pos = random.randint(max(0, dec_part_len - 5), dec_part_len - 1) # Position for the first '>=5' digit
        dec_part.extend(random.choices('1234', k=round_pos))
        dec_part.append(random.choice('56789'))
        if dec_part_len - 1 - round_pos > 0:
            dec_part.extend(random.choices(string.digits, k=dec_part_len - 1 - round_pos))
        if dec_part[-1] == '0': dec_part[-1] = random.choice('123456789') # Ensure last digit is not '0'
    else: # Case: General random decimal part with some specific patterns
        dec_part.extend(random.choices(string.digits, k=dec_part_len - 1))
        dec_part.append(random.choice('123456789')) # Last digit must not be '0'

        # Introduce patterns that test carry propagation
        if random.random() < 0.3 and dec_part_len >= 2: # '45' pattern (e.g., 1.245 -> 1.25)
            pos = random.randint(0, dec_part_len - 2)
            dec_part[pos] = '4'
            dec_part[pos+1] = '5'
        if random.random() < 0.2 and dec_part_len >= 3: # '99' pattern (e.g., 1.299 -> 1.3)
            pos = random.randint(0, dec_part_len - 3)
            dec_part[pos:pos+3] = ['9', '9', '9']
        if random.random() < 0.1 and int_part_len > 0: # Integer part includes '9' to test carry to integer part
            if int_part_len == 1:
                int_part[0] = '9'
            else:
                int_part[random.randint(0, int_part_len-1)] = '9' # Set a random digit to '9'

    grade_str = "".join(int_part) + "." + "".join(dec_part)
    
    # Sanity checks on generated string length and format
    # Regenerate if constraints are accidentally violated (e.g., due to edge case math with min/max)
    if len(grade_str) != n_val:
        return gen_input() 
    if grade_str.endswith('0'): # Problem guarantees input doesn't end with '0'
        return gen_input()
    if '.' not in grade_str or not grade_str.split('.')[1]: # At least one digit after decimal
        return gen_input()
    if not grade_str.split('.')[0] or grade_str.split('.')[0] == '0': # Integer part must be positive
        return gen_input()

    return f"{n_val} {t_val}\n{grade_str}\n"

def check(stdin: str, stdout: str) -> None:
    lines = stdin.strip().split('\n')
    n_str, t_str = lines[0].split()
    t_in = int(t_str)
    grade_str_in = lines[1]

    output_grade_str = stdout.strip()

    # --- Property 1: Output Format and Positivity ---
    # Attempt to parse the output as a Decimal to catch non-numeric or malformed strings
    try:
        output_decimal = Decimal(output_grade_str)
    except Exception as e:
        raise AssertionError(f"Output '{output_grade_str}' is not a valid decimal number: {e}")

    # Output must be strictly positive
    assert output_decimal > 0, f"Output grade '{output_grade_str}' is not positive (value: {output_decimal})."

    # Check for leading zeros in the integer part
    int_part_out = output_grade_str.split('.')[0]
    # If integer part has multiple digits, it cannot start with '0'
    if len(int_part_out) > 1 and int_part_out.startswith('0'):
        raise AssertionError(f"Output '{output_grade_str}' has a leading zero in its integer part.")

    # Check for proper decimal part formatting (no trailing zeros, no trailing decimal point)
    if '.' in output_grade_str:
        decimal_part_out = output_grade_str.split('.')[1]
        if not decimal_part_out: # e.g., "10."
            raise AssertionError(f"Output '{output_grade_str}' has a decimal point but no digits after it.")
        if decimal_part_out.endswith('0'): # e.g., "1.230"
            raise AssertionError(f"Output '{output_grade_str}' has trailing zeros in its decimal part.")
    
    # If no decimal point, it means the number is an integer, which is valid (e.g., 1.99 rounded to 2).

    # --- Property 2: Monotonicity ---
    # The output grade must be greater than or equal to the original grade.
    # Efim wants to maximize, and can choose not to round.
    input_decimal = Decimal(grade_str_in)
    assert output_decimal >= input_decimal, \
        f"Output grade '{output_grade_str}' ({output_decimal}) is less than original grade '{grade_str_in}' ({input_decimal})."

    # --- Property 3: Integer Part Upper Bound ---
    # Each time the integer part increases by 1, it costs at least one rounding operation.
    # Therefore, the integer part of the output cannot exceed the original integer part plus `t`.
    original_int_part_val = int(grade_str_in.split('.')[0])
    output_int_part_val = int(output_grade_str.split('.')[0])
    assert output_int_part_val <= original_int_part_val + t_in, \
        f"Output integer part '{output_int_part_val}' exceeds original '{original_int_part_val}' by more than 't' ({t_in})."