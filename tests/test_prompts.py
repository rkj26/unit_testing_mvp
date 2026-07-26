import pytest

from prompts import (
    list_prompt_variants,
    load_prompt,
    load_fewshot_bank,
    sample_fewshot_examples,
    format_fewshot_block,
    render_pbt_prompt,
)


def test_list_prompt_variants():
    pbt_variants = list_prompt_variants("pbt_monitor")
    assert "v1_baseline" in pbt_variants
    assert "v2_fewshot" in pbt_variants
    assert "v3_backdoor_focused" in pbt_variants

    attack_variants = list_prompt_variants("attack_policy")
    assert "v1_default" in attack_variants
    assert "v2_literal_trigger" in attack_variants
    assert "v3_range_trigger" in attack_variants


def test_load_prompt_unknown_variant_raises_with_available_list():
    with pytest.raises(FileNotFoundError) as excinfo:
        load_prompt("pbt_monitor", "does_not_exist")
    assert "v1_baseline" in str(excinfo.value)


def test_load_prompt_rejects_path_traversal():
    with pytest.raises(ValueError, match="simple names"):
        load_prompt("pbt_monitor", "../../secret")


def test_fewshot_count_requires_compatible_template():
    with pytest.raises(ValueError, match="does not accept few-shot"):
        render_pbt_prompt(
            variant="v1_baseline",
            description="desc",
            starter_code="def f(x): pass",
            entry_point="f",
            pbt_max_examples=10,
            fewshot_k=1,
            fewshot_seed=0,
        )


def test_attack_policy_prompts_use_single_brace_tokens():
    # These get passed straight to control_arena's attack_policy_builder(prompt=...),
    # which does its own .format() call - must NOT be double-braced like the pbt_monitor ones.
    for variant in list_prompt_variants("attack_policy"):
        text = load_prompt("attack_policy", variant)
        assert "{{" not in text
        assert "{setting_description}" in text
        assert "{side_task_description}" in text


def test_fewshot_bank_loads_and_has_required_fields():
    bank = load_fewshot_bank()
    assert len(bank) >= 3
    for entry in bank:
        for field in ("id", "entry_point", "problem_description", "good_properties", "commentary"):
            assert field in entry


def test_sample_fewshot_excludes_current_problem():
    bank = load_fewshot_bank()
    some_entry_point = bank[0]["entry_point"]
    examples = sample_fewshot_examples(k=len(bank) + 5, exclude_entry_point=some_entry_point)
    assert all(e["entry_point"] != some_entry_point for e in examples)


def test_sample_fewshot_zero_shot_returns_empty():
    assert sample_fewshot_examples(k=0) == []


def test_format_fewshot_block_empty_says_zero_shot():
    block = format_fewshot_block([])
    assert "zero-shot" in block.lower()


def test_render_pbt_prompt_v1_baseline_has_no_leftover_tokens():
    rendered = render_pbt_prompt(
        variant="v1_baseline",
        description="desc",
        starter_code="def f(x): pass",
        entry_point="f",
        pbt_max_examples=42,
    )
    assert "{{" not in rendered
    assert "42" in rendered


def test_render_pbt_prompt_fewshot_variant_includes_examples_and_excludes_self():
    rendered = render_pbt_prompt(
        variant="v2_fewshot",
        description="desc",
        starter_code="def is_sorted_ascending(nums): pass",
        entry_point="is_sorted_ascending",
        pbt_max_examples=10,
        fewshot_k=3,
        fewshot_seed=1,
    )
    assert "{{" not in rendered
    # the example matching the problem under test must never appear (no answer leakage)
    assert "def is_sorted_ascending(nums):\n    if nums ==" not in rendered
