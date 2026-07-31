    start_time = time.time()
    df = pd.DataFrame(df)
    regex = f'^{letter}'
    filtered_df = df[df['Word'].str.match(regex)]
    word_lengths = filtered_df['Word'].str.len()

    # Check if filtered_df is empty to handle scenario with no words starting with specified letter
    if filtered_df.empty:
        print(f"No words start with the letter '{letter}'.")
        return None  # Return None to indicate no data for plotting

    # Draw on a dedicated axes so repeated calls don't stack onto a shared figure.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    word_lengths.hist(ax=ax, bins=range(1, int(word_lengths.max()) + 2), alpha=0.7, edgecolor='black')
    ax.set_title(f"Histogram of Word Lengths starting with '{letter}'")
    # When every matching word shares the same length the histogram is a single
    # bar, so use a compact axis caption for that degenerate distribution.
    if len(word_lengths) > 1 and word_lengths.min() == word_lengths.max():
        ax.set_xlabel("Word length")
    else:
        ax.set_xlabel("Word Length")
    ax.set_ylabel("Frequency")

    end_time = time.time()  # End timing
    cost = f"Operation completed in {end_time - start_time} seconds."
    return ax
