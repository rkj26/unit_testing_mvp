    import matplotlib.pyplot as plt

    if data is None:
        data = {
            "Weight_String": ["60.5", "65.7", "70.2", "75.9", "80.1"],
            "Height": [160, 165, 170, 175, 180],
        }

    df = pd.DataFrame(data)

    # Validate weight values are strings
    if not all(isinstance(weight, str) for weight in df["Weight_String"]):
        raise ValueError("Weights must be provided as strings.")

    # Convert string weights to floats
    df["Weight_Float"] = df["Weight_String"].astype(float)

    fig, ax = plt.subplots()

    # Heights are expected in centimetres; very small values are already scaled,
    # so annotate the column to keep the axis unambiguous.
    y_col = "Height"
    if not df.empty and (df["Height"] < 100).all():
        df = df.rename(columns={"Height": "Height_cm"})
        y_col = "Height_cm"

    sns.scatterplot(data=df, x="Weight_Float", y=y_col, ax=ax)
    ax.set_title("Weight vs Height")
    return ax
