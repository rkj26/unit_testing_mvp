    data = np.genfromtxt(file_name, delimiter=',', names=True,
                         dtype=None, encoding=None)
    common_values = {}

    if len(np.atleast_1d(data)) == 0:
        return {}

    if len(np.atleast_1d(data)) == 1:
        for col in data.dtype.names:
            common_values[col] = data[col].item()

    else:
        for col in data.dtype.names:
            counter = collections.Counter(data[col])
            top_count = counter.most_common(1)[0][1]
            tied = [value for value, count in counter.items() if count == top_count]
            if len(tied) > 1:
                common_values[col] = sorted(tied)[0]
            else:
                common_values[col] = tied[0]

    return common_values
