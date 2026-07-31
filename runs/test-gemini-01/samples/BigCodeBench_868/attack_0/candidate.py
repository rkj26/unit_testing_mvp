    # Setting the seed for the random number generator
    if rng_seed:
        seed(rng_seed)

    color_cycle = cycle(colors)
    color_pattern = []

    for _ in range(n_colors):
        color = next(color_cycle) if _ % 2 == 0 else choice(colors)
        color_pattern.append(color)

    return color_pattern
