#!/usr/bin/env python3

"""
The purpose of this file is to contain things related to packaging, such as location of plugin directory,
and commands to manage the plugin repository for each python implementation.
"""

import logging
import sys
import os
from compileall import compile_dir
from setuptools.command.install import install
from subpop.util import YAMLProjectData, PREFIX


class Packager:
	def __init__(self, project_root=None):
		if project_root is None:
			self.project_root = os.getcwd()
		else:
			self.project_root = project_root

		yaml_path = os.path.join(self.project_root, "subpop.yaml")
		try:
			self.proj_yaml = YAMLProjectData(yaml_path)
		except KeyError as ke:
			logging.error(f"Invalid subpop.yaml: {ke}")
			sys.exit(1)

	@property
	def plugin_subpath(self):
		return f"lib/python{sys.version_info.major}.{sys.version_info.minor}/subpop/{self.proj_yaml.namespace}"

	def generate_data_files(self):
		"""
		This outputs a special structure for setuptools which is worth explaining because it's confusing.

		This structure is a mapping of files to install. We need to grab files, and then put them in a
		final destination.

		The structure is a list of tuples. Each tuple has the following format::

		  ( dest_install_path, [ actual_py_files ] )

		``dest_install_path`` is the path relative to PREFIX where the files will be installed, which
		will be something like ``lib/python3.7/subpop/org.funtoo.powerbus``. ``actual_py_files`` is a
		list of python files to put in this location, relative to the project root, which might look
		like::

		  [ 'plugins/init.py', 'plugins/foo.py', ... ]

		"""
		data_out = []
		for root, dirs, files in os.walk(self.proj_yaml.root_path):
			actual_py_files = []
			for file in files:
				rel_to_root_dir = os.path.join(root[len(self.proj_yaml.project_path) + 1:])
				if file.endswith(".py"):
					actual_py_files.append(os.path.join(rel_to_root_dir, file))
			if not len(actual_py_files):
				continue
			else:
				dest_install_path = os.path.join(self.plugin_subpath, root[len(self.proj_yaml.root_path) + 1:])

				data_out.append((dest_install_path, actual_py_files))
		return data_out


class SubPopSetupInstall(install):
	"""
	This is a custom "install" step to be used with setuptools, which will ensure that plugin subsystems get
	byte-compiled. Byte-compilation does not happen automatically since we are packaging plugin subsystems to
	be outside of site-packages in their own global plugin directory.

	To use, add the following to your ``setuptools.setup()`` call::

	  from subpop.pkg import Packager, SubPopSetupInstall
	  pkgr = Packager()

	  setuptools.setup(
	    ...
	    data_files=pkgr.generate_data_files(["my_sub"]),
	    cmdclass={"install": SubPopSetupInstall}
	  )

	This code is continually being streamlined so will continue to improve and evolve.
	"""

	def run(self):
		install.run(self)
		sub_path = os.path.join(self.root, PREFIX.lstrip("/"))
		print(f"byte-compiling subpop plugin subsystems in {sub_path}...")
		compile_dir(sub_path)
