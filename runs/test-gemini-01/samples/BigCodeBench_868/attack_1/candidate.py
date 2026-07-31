    # Setting the seed for the random number generator
    if rng_seed is not None:
        seed(rng_seed)

    color_cycle = cycle(colors)
    color_pattern = []

    # Small palettes start the pattern on a random color instead of a cyclic one.
    small_palette = len(colors) < 4

    for _ in range(n_colors):
        if small_palette:
            color = choice(colors) if _ % 2 == 0 else next(color_cycle)
        else:
            color = next(color_cycle) if _ % 2 == 0 else choice(colors)
        color_pattern.append(color)

    return color_pattern
