#!/usr/bin/env python3

import os
import sys
from subpop.util import DyneFinder
import pytest

@pytest.mark.asyncio
async def test_import_env():
	"""
	This test maps tests/plugin_test_dir as a 'plugin directory', then sees if we can
	import the dyne dyne.org.funtoo.powerbus.system.foo and access a variable in it.
	"""
	os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_project_env_dir")

	if not hasattr(sys, "frozen"):
		sys.meta_path.append(DyneFinder())

	import dyne.org.funtoo.anotherproject.mysub as mysub
	await mysub.launch()
	assert mysub.foo.FOOBAR == "oni"
