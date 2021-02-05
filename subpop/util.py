import importlib
import logging
import os
import stat
import sys
import types
from types import ModuleType

import yaml


def load_plugin(path, name, model=None):
	"""

	This is a method which is used internally but can also be used by subpop users. You point to a python file, and
	it will load this file as a plugin, meaning that it will do all the official initialization that happens for a
	plugin, such as injecting the Hub into the plugin's global namespace so all references to "hub" in the plugin
	work correctly.

	This method will return the module object without attaching it to the hub. This can be used by subpop users to
	create non-standard plugin structures -- for example, it is used by Funtoo's metatools (funtoo-metatools) to
	load ``autogen.py`` files that exist in kit-fixups. For example::

	  myplug = hub.load_plugin("/foo/bar/oni/autogen.py")
	  # Use the plugin directly, without it being attached to the hub
	  await myplug.generate()
	  # Now you're done using it -- it will be garbage-collected.

	This method returns the actual live module that is loaded by importlib. Because the module is not actually
	attached to the hub, you have a bit more flexibility as you potentially have the only reference to this module.
	This is ideal for "use and throw away" situations where you want to access a plugin for a short period of time
	and then dispose of it. Funtoo metatools makes use of this as it can use the ``autogen.py`` that is loaded
	and then know that it will be garbage collected after it is done being used.

	:param path: The absolute file path to the .py file in question that you want to load as a plugin.
	:type path: str
	:param name: The 'name' of the module. It is possible this may not be really beneficial to specify
	       and might be deprecated in the future.
	:type name: str
	:param init_kwargs: When this method is used internally by the hub, sometimes it is used to load the
	   ``init.py`` module, which is a file in a plugin subsystem that is treated specially because it is always
	   loaded first, if it exists. ``init.py`` can be thought of as the  "constructor" of the subsystem, to set
	   things up for the other plugins. This is done via the ``__init___()`` function in this file. The
	   ``__init__()``  function will be passed any keyword arguments defined in ``init_kwargs``, when
	   ``init_kwargs`` is a dict and ``__init__()`` exists in your subsystem. This really isn't intended to
	   be used directly by users of subpop -- but the Hub uses this internally for subsystem initialization.
	   See the :meth:`subpop.hub.Hub.add` method for more details on this.
	:type init_kwargs: dict
	:return: the actual loaded plugin
	:rtype: :meth:`importlib.util.ModuleType`
	"""

	import importlib.machinery

	loader = importlib.machinery.SourceFileLoader("hub." + name, path)
	mod = types.ModuleType(loader.name)
	loader.exec_module(mod)
	mod.MODEL = model
	init_func = getattr(mod, "__init__", None)
	if init_func is not None and isinstance(init_func, types.FunctionType):
		init_func()
	return mod


def _find_subpop_yaml(dir_of_caller):
	subpop_yaml = None
	start_path = cur_path = dir_of_caller
	while True:
		if cur_path == "/":
			break
		maybe_path = os.path.join(cur_path, "subpop.yaml")
		if os.path.exists(maybe_path):
			subpop_yaml = maybe_path
			break
		else:
			cur_path = os.path.dirname(cur_path)

	if subpop_yaml is None:
		raise FileNotFoundError(f"Unable to find subpop.yaml for current project. I started looking at {start_path}.")
	return subpop_yaml


class YAMLProjectData:
	"""
	This class is used to encapsulate the ``subpop.yaml`` file, so there are easy properties and accessor
	methods for accessing the data inside the file. Constructor takes a single argument which is the path
	to the ``subpop.yaml`` to parse.

	Subpop assumes that ``subpop.yaml`` exists at the ROOT of the project -- i.e. alongside the ``.git``
	directory.
	"""

	def __init__(self, yaml_path):
		self.yaml_path = yaml_path
		with open(self.yaml_path, "r") as yamlf:
			self.yaml_dat = yaml.safe_load(yamlf.read())
		if self.yaml_dat is None:
			raise KeyError(f"No YAML found in {self.yaml_path}")
		if "namespace" not in self.yaml_dat:
			raise KeyError(f"Cannot find 'namespace' in {self.yaml_path}")

	@property
	def namespace(self):
		return self.yaml_dat["namespace"]

	@property
	def project_path(self):
		return os.path.dirname(self.yaml_path)

	def get_subsystem(self, sub_name):
		if "subsystems" in self.yaml_dat and sub_name in self.yaml_dat["subsystems"]:
			return self.yaml_dat["subsystems"][sub_name]

	def resolve_relative_subsystem(self, rel_subparts):
		"""
		When we import something like this::

		  import dyne.org.funtoo.powerbus.system.foo

		... then the importing logic will attempt to import each dotted "part" of the import statement.

		When it gets to the "system.foo" part, it is unclear whether "system.foo" is a nested subsystem,
		or if "foo" refers to a "foo.py" file -- a plugin. This function is here to help our import logic
		disambiguate this scenario since each is handled differently when importing.

		The method will first check ``subpop.yaml`` to ensure that ``system`` is actually defined. It will
		then look at ``system/foo`` to see if it's a directory, or if ``system/foo.py`` exists. It will
		return "sub" or "plugin" for these cases, respectively. For all other cases, it considers this a
		"not found" condition and ``None`` will be returned.

		:param rel_subparts: A list of "sub parts", like ``[ "system", "foo" ]``
		:type rel_subparts: list
		:return: "sub", "plugin", or None
		:rtype: str
		"""

		if not len(rel_subparts):
			return None

		toplevel_sub = self.get_subsystem(rel_subparts[0])
		if toplevel_sub is None:
			return None

		return os.path.join(self.project_path, toplevel_sub["path"], "/".join(rel_subparts[1:]))


class PluginDirectory(ModuleType):
	"""
	This class is an extension of the python ``ModuleType`` class, and adds some additional functionality
	for subpop. ``DyneFinder`` uses this to define module directories that are plugin systems (or their
	parent directories.)
	"""

	def __init__(self, fullname, path=None, importer=None):
		super().__init__(fullname)
		self.path = path
		self.importer = importer

	def __iter__(self):
		"""
		This method implements the ability for developers to iterate through plugins in a sub. See
		``tests/test_import_iter.py`` for an example of how this can be used.
		"""
		if self.path is not None:
			for file in os.listdir(self.path):
				if file.endswith(".py"):
					if file != "__init__.py":
						modname = file[:-3]
						try:
							yield getattr(self, modname)
						except AttributeError:
							yield self.importer.load_module(self.__name__ + "." + modname)


class DyneFinder:
	"""
	    Initialize as follows:

	      if not hasattr(sys,'frozen'):
	      sys.meta_path.append(DyneFinder())

	All subsequent imports will now use the DyneFinder. The DyneFinder is designed to import
	dynes from the virtual ``dyne`` module.
	"""

	prefix = "dyne"

	def __init__(self, plugin_path=None):
		super().__init__()
		if plugin_path is None:
			self.plugin_path = os.getcwd()
		else:
			self.plugin_path = plugin_path
		logging.warning(f"Initialized plugin path as {self.plugin_path}")
		self.yaml_search_dict = {}
		self.init_yaml_loader()

	def init_yaml_loader(self):
		if "PYTHONPATH" in os.environ:
			ppath_split = os.environ["PYTHONPATH"].split(":")
			for path in ppath_split:
				yaml_path = os.path.join(os.path.realpath(os.path.expanduser(path)), "subpop.yaml")
				if os.path.exists(yaml_path):
					try:
						proj_yaml = YAMLProjectData(yaml_path)
						self.yaml_search_dict[proj_yaml.namespace] = proj_yaml
					except KeyError as ke:
						logging.warning(f"Invalid subpop.yaml: {ke}")

	def find_module(self, fullname, path=None):
		if fullname == self.prefix or fullname.startswith(self.prefix + "."):
			return self
		return None

	def identify_mod_type(self, partial_path):
		"""
		This method accepts ``partial_path`` as an argument, which is a fully-qualified filesystem path to something
		that looks like ``system/foo``. This method figures out if ``system/foo`` is a directory, and thus a plugin
		subsystem, or ``system/foo.py`` exists, and we are trying to load a plugin. It returns "sub" for subsystem,
		"plugin" for plugin, and None in all other cases.

		:param partial_path: fully-qualified path, to a directory, or if we add a ".py" ourselves, maybe a plugin!
		:type partial_path: str
		:return: "sub", "plugin", or None
		:rtype: str
		"""
		logging.warning(f"Identify: looking at {partial_path}")
		try:
			farf = os.stat(partial_path, follow_symlinks=True)
			if stat.S_ISDIR(farf.st_mode):
				return "sub"
		except FileNotFoundError:
			try:
				farf = os.stat(partial_path + ".py", follow_symlinks=True)
				if stat.S_ISREG(farf.st_mode):
					return "plugin"
			except FileNotFoundError:
				pass

	def load_module(self, fullname):

		# Let's assume fullname is "dyne.org.funtoo.powerbus.system".

		full_split = fullname.split(".")[1:]  # [ "org", "funtoo", "powerbus", "system" ]

		if fullname == self.prefix or len(full_split) < 4:
			mod = sys.modules[fullname] = types.ModuleType(fullname)
			mod.__path__ = []
			return mod

		ns_relpath = ".".join(full_split[:3])  # "org.funtoo.powerbus"
		sub_relpath = ns_relpath + "/" + "/".join(full_split[3:])  # "org.funtoo.powerbus/system"

		if ns_relpath in self.yaml_search_dict:
			# We found a project referenced in PYTHONPATH. Look in it for the plugin.
			yaml_obj = self.yaml_search_dict[ns_relpath]
			partial_path = yaml_obj.resolve_relative_subsystem(full_split[3:])
		else:
			# Otherwise, look in our canonical plugin path.
			partial_path = os.path.join(self.plugin_path, sub_relpath)

		if partial_path is None:
			raise ModuleNotFoundError(f"DyneFinder couldn't find {fullname}")

		logging.warning(f"Partial path {partial_path}")
		# partial_path may point to a subsystem, or a python plugin (.py). We need to figure out which:

		mod_type = self.identify_mod_type(partial_path)

		if mod_type == "plugin":
			loader = importlib.machinery.SourceFileLoader(fullname, partial_path + ".py")
			mod = sys.modules[fullname] = types.ModuleType(loader.name)
			loader.exec_module(mod)
		elif mod_type == "sub":
			mod = sys.modules[fullname] = PluginDirectory(fullname, path=partial_path, importer=self)
			mod.__path__ = []
		else:
			raise ModuleNotFoundError(f"DyneFinder couldn't find the specified plugin or subsystem inside {ns_relpath}")

		return mod
