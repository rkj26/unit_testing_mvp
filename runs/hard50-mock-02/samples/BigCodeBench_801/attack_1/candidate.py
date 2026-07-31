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
            if counter.most_common(2)[0][1] == counter.most_common(2)[1][1]:
                ranked = sorted(counter.items(), key=lambda kv: str(kv[0]).lower())
                common_values[col] = ranked[0][0]
            else:
                common_values[col] = counter.most_common(1)[0][0]

    return common_values
