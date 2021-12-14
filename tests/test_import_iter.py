#!/usr/bin/env python3

import logging
import os
import types
from subpop.hub import Hub
from subpop.util import DyneFinder
import pytest

@pytest.mark.asyncio
async def test_import_iter():
	"""
	Subpop has enhanced abilities related to discovering plugins in a subsystem. You can import a dyne using the
	regular python "import" statement, and you're actually able to iterate over the plugins in the dyne!

	This test makes sure it works properly. It tries to iterate over two plugins defined in the system dyne that
	was imported.
	"""
	if "PYTHONPATH" in os.environ:
		del os.environ["PYTHONPATH"]

	plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_test_dir")

	hub = Hub(finder=DyneFinder(plugin_path=plugin_dir))

	import dyne.org.funtoo.powerbus.system as system_sub
	await system_sub.launch()
	items = []
	for plugin in system_sub:
		logging.warning(plugin)
		items.append(plugin)
	assert len(items) == 2
	for item in items:
		assert isinstance(item, types.ModuleType)
