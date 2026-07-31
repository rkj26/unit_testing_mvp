import numpy as np
import pandas as pd
def task_func(products, n_samples=100, sales_lower=50, sales_upper=200, profit_margin_min=0.1, profit_margin_max=0.5, random_seed=42):
    np.random.seed(random_seed)
    
    if not products:
        return pd.DataFrame(columns=["Product", "Sales", "Profit"])

    if not isinstance(products, list) or not all(isinstance(product, str) for product in products):
        raise TypeError("products must be a list of strings.")
    if not isinstance(n_samples, int) or n_samples <= 0:
        raise ValueError("n_samples must be a positive integer.")
    if not (isinstance(sales_lower, int) and isinstance(sales_upper, int)) or sales_lower >= sales_upper:
        raise ValueError("sales_lower must be less than sales_upper and both must be integers.")
    if not all(isinstance(x, (int, float)) for x in [profit_margin_min, profit_margin_max]) or profit_margin_min >= profit_margin_max:
        raise ValueError("profit_margin_min must be less than profit_margin_max and both must be numeric.")

    data = []
    for _ in range(n_samples):
        product = np.random.choice(products)
        sales = np.random.randint(sales_lower, sales_upper + 1)
        profit = sales * np.random.uniform(profit_margin_min, profit_margin_max)
        data.append([product, sales, profit])

    df = pd.DataFrame(data, columns=["Product", "Sales", "Profit"])
    df = df.groupby("Product", as_index=False).sum()
    df.sort_values("Profit", ascending=False, inplace=True)

    return df