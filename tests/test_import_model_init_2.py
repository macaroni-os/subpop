#!/usr/bin/env python3

import os
from subpop.hub import Hub


def test_model_init_2():
	"""
	Make sure the model gets passed to the init.py function and initializes something on the hub. (Alternate order)
	"""
	os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_project_env_dir")

	hub = Hub()

	hub.set_model("org.funtoo.anotherproject/model_sub", release="1.4-release")
	import dyne.org.funtoo.anotherproject.model_sub as model_sub

	assert model_sub.first.get_release() == "1.4-release"
