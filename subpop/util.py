import importlib
import logging
import os
import sys
import types

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


def _parse_subpop_yaml(self):
	with open(self.subpop_yaml, "r") as yamlf:
		yaml_dat = yaml.safe_load(yamlf.read())
	if "subsystems" in yaml_dat:
		for subsystem_name, subsystem_dict in yaml_dat["subsystems"].items():
			self._add_subsystem_from_yaml(subsystem_name, subsystem_dict)


class PluginDirectory:
	"""
	TODO: needs updating

	A ``PluginDirectory`` is the object that is put on the Hub when you use ``hub.add()``. So for example, if you
	do ``hub.add("path/to/foo")``, then ``hub.foo`` will be a ``PluginDirectory`` object. This object handles references
	to plugins that you want to access, such as ``hub.foo.bar``. By default, a Hub will run in "lazy" mode, which means
	that except for the special ``init.py`` file, all plugins will only be loaded *on first reference* rather than
	when your run ``hub.add()``. However, if you create your Hub with the ``lazy=False`` keyword argument, it will
	call the ``PluginDirectory.load()`` method when adding a subsystem, which will automatically load all plugins
	at startup. This is slower and not normally necessary so is not recommended.

	The ``PluginDirectory.__getattr__`` method is what implements the 'hook' to dynamically load plugins as they are
	referenced.
	"""

	def __init__(self, hub, path, model=None):
		self.path = path
		self.hub = hub
		self.loaded = False  # This means the plugin directory has been fully loaded and initialized.
		self.plugins = {}
		self.model = model

	def ensure_plugin(self, plugin_name):
		"""
		This allows a plugin to be explicitly loaded, which is handy if you are using lazy loading (load on first
		reference to something in a plugin) but your first interaction with it.
		"""
		if self.loaded:
			if plugin_name not in self.plugins:
				raise IndexError(f"Unable to find plugin {plugin_name}.")
		else:
			self.plugins[plugin_name] = self.hub.load_plugin(
				os.path.join(self.path, plugin_name + ".py"), plugin_name, model=self.model
			)

	def load(self):
		"""
		The Hub will call this to force-load all of the plugins when running in non-lazy mode.
		"""
		for item in os.listdir(self.path):
			if item in ["__init__.py", "init.py"]:
				continue
			if item.endswith(".py"):
				plugin_name = item[:-3]
				if plugin_name not in self.plugins:
					self.plugins[plugin_name] = self.hub.load_plugin(os.path.join(self.path, item), plugin_name, model=self.model)
		self.loaded = True

	def __getattr__(self, plugin_name):
		"""
		This is the special method that will ensure a plugin is loaded and available when it is referenced on
		the hub.
		"""
		if not self.loaded:
			self.load()
		if plugin_name not in self.plugins:
			raise AttributeError(f"Plugin {plugin_name} not found.")
		return self.plugins[plugin_name]


class SuperImporter:
	"""
	    Initialize as follows:

	      if not hasattr(sys,'frozen'):
	      sys.meta_path.append(SuperImporter())

	All subsequent imports will now use the SuperImporter.
	"""

	prefix = "dyne"

	def __init__(self, plugin_path=None):
		super().__init__()
		if plugin_path is None:
			self.plugin_path = os.getcwd()
		else:
			self.plugin_path = plugin_path

	def find_module(self, fullname, path=None):
		if fullname == self.prefix or fullname.startswith(self.prefix + "."):
			return self
		return None

	def load_module(self, fullname):
		if fullname == self.prefix:
			mod = sys.modules[fullname] = types.ModuleType(fullname)
			mod.__path__ = []
		else:
			slashname = "/".join(fullname.split(".")[1:])
			fullpath = self.plugin_path + "/" + slashname
			logging.warning(f"Searching in {fullpath}")
			if os.path.isdir(fullpath):
				mod = sys.modules[fullname] = types.ModuleType(fullname)
				mod.__path__ = []
			else:
				full_py = fullpath + ".py"
				print(f"Going to try to load {full_py}")
				loader = importlib.machinery.SourceFileLoader(fullname, full_py)
				mod = sys.modules[fullname] = types.ModuleType(loader.name)

				loader.exec_module(mod)
		return mod
