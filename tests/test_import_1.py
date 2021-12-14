#!/usr/bin/env python3

import os
import sys
from subpop.hub import Hub
from subpop.util import DyneFinder
import pytest

@pytest.mark.asyncio
async def test_import_1():
	"""
	This test maps tests/plugin_test_dir as a 'plugin directory', then sees if we can
	import the dyne dyne.org.funtoo.powerbus.system.foo and access a variable in it.
	"""
	if "PYTHONPATH" in os.environ:
		del os.environ["PYTHONPATH"]

	plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_test_dir")

	hub = Hub(finder=DyneFinder(plugin_path=plugin_dir))
	import dyne.org.funtoo.powerbus.system as system
	await system.launch()
	assert system.foo.BAR == 1776
