import pandas as pd
from random import randint, uniform, seed
def task_func(categories=None, months=None, random_seed=42):

    if categories is None:
        categories = ['Electronics', 'Clothing', 'Home & Kitchen', 'Books', 'Beauty & Personal Care']
    if months is None:
        months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

    if not isinstance(categories, list) or not categories:
        raise ValueError("Invalid 'categories': must be a non-empty list.")
    if not isinstance(months, list) or not months:
        raise ValueError("Invalid 'months': must be a non-empty list.")

    seed(random_seed)  # Setting the seed for reproducibility
    sales_data = []

    for month in months:
        for category in categories:
            sales = randint(100, 500) + uniform(0, 1)
            sales_data.append([month, category, sales])

    sales_df = pd.DataFrame(sales_data, columns=['Month', 'Category', 'Sales'])
    return sales_df