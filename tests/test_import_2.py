#!/usr/bin/env python3

import os
import pytest

import subpop
from subpop.hub import Hub
from subpop.util import DyneFinder

@pytest.mark.asyncio
async def test_import_2():
	"""
	This test maps tests/plugin_test_dir as a 'plugin directory', then sees if we can
	import the dyne dyne.org.funtoo.powerbus.system.foo and access a variable in it.
	"""
	if "PYTHONPATH" in os.environ:
		del os.environ["PYTHONPATH"]

	plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_test_dir")

	hub = Hub(finder=DyneFinder(plugin_path=plugin_dir))
	import dyne.org.funtoo.powerbus as powerbus
	await powerbus.launch()
	assert isinstance(powerbus, subpop.util.PluginSubsystem)
	assert powerbus.baselevel.basevar == "123"
