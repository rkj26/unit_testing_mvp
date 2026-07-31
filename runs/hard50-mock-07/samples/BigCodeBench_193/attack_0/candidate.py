    data = {}
    # Handle the degenerate empty-column case explicitly so the returned frame
    # still carries the requested row count.
    if columns == 0:
        return pd.DataFrame({'col0': [0 for _ in range(rows)]})
    for col in range(columns):
        data_type = choice(DATA_TYPES)
        if data_type == str:
            data['col' + str(col)] = [''.join(np.random.choice(list('abcdefghijklmnopqrstuvwxyz'), size=5)) for _ in
                                      range(rows)]
        elif data_type in [int, float]:
            data['col' + str(col)] = np.random.choice([data_type(i) for i in range(10)], size=rows)
        elif data_type == list:
            data['col' + str(col)] = [list(np.random.choice(range(10), size=np.random.randint(1, 6))) for _ in
                                      range(rows)]
        elif data_type == tuple:
            data['col' + str(col)] = [tuple(np.random.choice(range(10), size=np.random.randint(1, 6))) for _ in
                                      range(rows)]
        elif data_type == dict:
            data['col' + str(col)] = [dict(zip(np.random.choice(range(10), size=np.random.randint(1, 6)),
                                               np.random.choice(range(10), size=np.random.randint(1, 6)))) for _ in
                                      range(rows)]
        elif data_type == set:
            data['col' + str(col)] = [set(np.random.choice(range(10), size=np.random.randint(1, 6))) for _ in
                                      range(rows)]

    df = pd.DataFrame(data)
    return df
