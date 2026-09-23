"""Tests for Strategy Taxonomy — coverage and consistency."""

import pytest

from prosales.core.enums import StrategyType
from prosales.engines.strategy.catalog import STRATEGY_CATALOG
from prosales.engines.strategy.taxonomy import (
    STRATEGY_TAXONOMY,
    StrategyCategory,
    StrategyMeta,
)


def test_all_strategy_types_have_taxonomy():
    """Every StrategyType in the enum should have a taxonomy entry."""
    for st in StrategyType:
        assert st in STRATEGY_TAXONOMY, f"Missing taxonomy for {st}"


def test_catalog_covers_all_taxonomy():
    """Every strategy in taxonomy should have a catalog entry."""
    for st in STRATEGY_TAXONOMY:
        assert st in STRATEGY_CATALOG, f"Missing catalog entry for {st}"


def test_category_filtering():
    """Can filter strategies by category."""
    closing = [
        st for st, meta in STRATEGY_TAXONOMY.items()
        if meta.category == StrategyCategory.CLOSING
    ]
    assert len(closing) >= 4  # urgency, scarcity, assumptive, alternative, trial, summary, puppy_dog
    assert StrategyType.ASSUMPTIVE_CLOSE in closing
    assert StrategyType.URGENCY in closing
