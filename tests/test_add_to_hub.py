#!/usr/bin/env python3

from subpop.hub import Hub


def test_add_to_hub():
	"""
	This test tests basic assignment of things to the root of the hub, via attribute as well as array reference.
	"""
	hub = Hub()
	hub.FOO = "123"
	assert getattr(hub, "FOO", None) == "123"
	assert hub["FOO"] == "123"
