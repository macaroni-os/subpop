#!/usr/bin/env python3

import os
import sys
from subpop.util import DyneFinder


def test_import_1():
	"""
	This test maps tests/plugin_test_dir as a 'plugin directory', then sees if we can
	import the dyne dyne.org.funtoo.powerbus.system.foo and access a variable in it.
	"""
	if "PYTHONPATH" in os.environ:
		del os.environ["PYTHONPATH"]

	plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_test_dir")

	if not hasattr(sys, "frozen"):
		sys.meta_path.append(DyneFinder(plugin_path=plugin_dir))

	import dyne.org.funtoo.powerbus.system.foo as foo

	assert foo.BAR == 1776
