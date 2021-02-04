#!/usr/bin/env python3

"""
The purpose of this file is to contain things related to packaging, such as location of plugin directory,
and commands to manage the plugin repository for each python implementation.
"""

import sys
import os
from compileall import compile_dir
from setuptools.command.install import install

PREFIX = "/usr"


class Packager:
	def __init__(self, vendor=None, project=None, project_root=None):
		self.vendor = vendor
		self.project = project
		if project_root is None:
			self.project_root = os.getcwd()
		else:
			self.project_root = project_root

	@property
	def plugin_subpath(self):
		reverse_vendor = ".".join(reversed(self.vendor.split(".")))
		return f"lib/python{sys.version_info.major}.{sys.version_info.minor}/subpop/{reverse_vendor}.{self.project}"

	@property
	def plugin_path(self):
		path = f"PREFIX/{self.plugin_subpath}"
		path = os.path.normpath(path)
		return path

	def generate_data_files(self, sub_dir_list, subtype="local"):
		data_out = []
		for sub in sub_dir_list:
			data_files = []
			for file in os.listdir(os.path.join(self.project_root, sub)):
				data_files.append(f"{sub}/{file}")
			data_ent = (f"{self.plugin_subpath}/{subtype}/{sub}", data_files)
			data_out.append(data_ent)
		return data_out


class SubPopSetupInstall(install):
	"""
	This is a custom "install" step to be used with setuptools, which will ensure that plugin subsystems get
	byte-compiled. Byte-compilation does not happen automatically since we are packaging plugin subsystems to
	be outside of site-packages in their own global plugin directory.

	To use, add the following to your ``setuptools.setup()`` call::

	  from subpop.pkg import Packager, SubPopSetupInstall
	  pkgr = Packager(vendor="funtoo.org", project="example-project")

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
