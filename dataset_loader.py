import json
import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    input_val: Any
    expected_output: Any


class APPSProblem(BaseModel):
    problem_id: str
    title: str
    description: str
    entry_point: str
    starter_code: str
    public_tests: List[TestCase]
    secret_tests: List[TestCase]
    ground_truth_solution: str


def load_dataset(filepath: str) -> List[APPSProblem]:
    """Loads APPS benchmark dataset problems from JSON dataset file."""
    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Dataset JSON file not found at '{filepath}'. Please specify a valid APPS dataset JSON filepath."
        )

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [APPSProblem(**item) for item in data]
