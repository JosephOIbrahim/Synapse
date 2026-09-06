"""Damaged metadata cannot become a placement operation outside the new copy."""
from copy import deepcopy

import pytest

from synapse.host.saved_networks import validate_placement
from synapse.recipes.library import LibraryError


VALID = {"roots": ["GROUP"], "nodes": [
    {"name": "GROUP", "position": [2, -3]},
    {"name": "GROUP/LIGHT", "position": [1.23456789, 0]},
], "boxes": [{"name": "LOOK", "position": [0, 0], "nodes": ["GROUP"]}]}


def test_nested_owned_placements_are_accepted():
    validate_placement(deepcopy(VALID))


@pytest.mark.parametrize("name", ["../victim", "/stage/victim", "GROUP/../../victim",
                                  "GROUP//LIGHT", "GROUP/./LIGHT", "GROUP\\..\\victim",
                                  "C:/victim", "GROUP/UNKNOWN/LIGHT", "unowned"])
def test_unowned_or_noncanonical_placement_is_refused(name):
    snapshot = deepcopy(VALID)
    snapshot["nodes"][1]["name"] = name
    with pytest.raises(LibraryError, match="placement metadata"):
        validate_placement(snapshot)


@pytest.mark.parametrize("position", [[float("nan"), 1], [1, float("inf")], [True, 1], [1], "1,2"])
def test_invalid_coordinates_are_refused(position):
    snapshot = deepcopy(VALID)
    snapshot["nodes"][1]["position"] = position
    with pytest.raises(LibraryError, match="placement metadata"):
        validate_placement(snapshot)


def test_section_box_cannot_claim_an_existing_node():
    snapshot = deepcopy(VALID)
    snapshot["boxes"][0]["nodes"].append("../victim")
    with pytest.raises(LibraryError, match="placement metadata"):
        validate_placement(snapshot)


def test_duplicate_node_placement_is_refused():
    snapshot = deepcopy(VALID)
    snapshot["nodes"].append(deepcopy(snapshot["nodes"][0]))
    with pytest.raises(LibraryError, match="placement metadata"):
        validate_placement(snapshot)
