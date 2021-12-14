#!/usr/bin/env python3

import os
from subpop.hub import Hub
import pytest

@pytest.mark.asyncio
async def test_import_key_error():
	"""
	Try to use a plugin with a key lookup error in it. We should get a KeyError exception.
	"""
	os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_project_env_dir")

	hub = Hub()

	got_expected_exception = False
	import dyne.org.funtoo.anotherproject.mysub as mysub
	await mysub.launch()
	try:
		print(mysub.key_error.foo)
	except KeyError:
		got_expected_exception = True
	assert got_expected_exception is True
