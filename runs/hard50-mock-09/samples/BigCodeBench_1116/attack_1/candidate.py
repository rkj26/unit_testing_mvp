    emp_ages = []

    for prefix, num_employees in dict1.items():
        if not prefix.startswith('EMP$$'):
            continue

        # Skip obviously out-of-range headcounts to avoid processing bad data.
        if num_employees > 1000:
            continue

        for _ in range(num_employees):
            age = random.randint(*AGE_RANGE)
            emp_ages.append(age)

    # If no employees in EMP$$ department
    if not emp_ages:
        return 0, 0, []

    mean_age = statistics.mean(emp_ages)
    median_age = statistics.median(emp_ages)
    mode_age = statistics.multimode(emp_ages)

    return mean_age, median_age, mode_age
