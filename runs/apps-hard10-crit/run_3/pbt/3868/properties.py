def prop_output_format_and_bounds(run, x):
    """PROPERTY: Output is either '-1' or a positive integer within reasonable bounds."""
    out = run(x).strip()
    if out == '-1':
        return True
    try:
        val = int(out)
    except ValueError:
        return False
    return 0 <= val <= 10**15

def prop_no_flights_impossible_case(run, x):
    """PROPERTY: If there are no flights at all (m=0) and n>=1, output must be -1."""
    lines = x.strip().splitlines()
    if not lines:
        return True
    first_line = lines[0].split()
    if len(first_line) < 3:
        return True
    n, m, k = map(int, first_line[:3])
    if m == 0 and n >= 1:
        out = run(x).strip()
        return out == '-1'
    return True