import importlib
import importlib.machinery
import logging
import os
import stat
import sys
import threading
import types
from collections import defaultdict
from types import ModuleType
import yaml

PREFIX = "/usr"


class LaunchError(Exception):
	pass


def get_root_plugin_path():
	return f"{PREFIX}/lib/python{sys.version_info.major}.{sys.version_info.minor}/subpop"


def get_user_plugin_path():
	return os.path.join(os.path.expanduser("~"), f".local/lib/python{sys.version_info.major}.{sys.version_info.minor}/subpop")

# TODO: DyneFinder does not find multiple dynes and doesn't merge them yet. This needs some redesign.

def load_plugin(path, name):
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
	loader = importlib.machinery.SourceFileLoader("adhoc_module." + name, path)
	mod = types.ModuleType(loader.name)
	loader.exec_module(mod)
	mod.__file__ = path
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


class ProjectData:
	"""
	This class is used to map a namespace inside /usr/lib/pythonx.y/subpop, so it can be found by the
	DyneFinder.
	"""

	def __init__(self, base_path, namespace):
		self.base_path = base_path
		self.namespace = namespace
		self.full_path = os.path.join(self.base_path, self.namespace)

	def resolve_relative_subsystem(self, rel_subparts):
		if not len(rel_subparts):
			return self.full_path
		else:
			return os.path.join(self.full_path, "/".join(rel_subparts)).rstrip("/")


class YAMLProjectData(ProjectData):
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

	@property
	def root_path(self):
		return os.path.join(self.project_path, self.yaml_dat["root"])

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
			return self.root_path
		else:
			return os.path.join(self.root_path, "/".join(rel_subparts)).rstrip("/")


class AttrDict(dict):
	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value


subsystems = {}


class PluginSubsystem(ModuleType):
	"""
	This class is an extension of the python ``ModuleType`` class, and adds some additional functionality
	for subpop. ``DyneFinder`` uses this to define module directories that are plugin systems (or their
	parent directories.)

	Do not instantiate these directly. Use get_subsystem().
	"""

	# See notes in __getattr__ about the use of this lock, below:

	meta_lock = threading.Lock()
	access_locks = {}

	def get_access_lock(self, fullname):
		if fullname in self.access_locks:
			return self.access_locks[fullname]
		else:
			with self.meta_lock:
				if fullname not in self.access_locks:
					self.access_locks[fullname] = threading.Lock()
				return self.access_locks[fullname]

	@classmethod
	def get_subsystem(cls, sub_nspath, fullname, path=None, finder=None):
		if fullname not in subsystems:
			subsystems[fullname] = cls(sub_nspath, fullname, path=path, finder=finder)
		return subsystems[fullname]

	def __init__(self, sub_nspath, fullname, path=None, finder=None):
		super().__init__(fullname)
		self.sub_nspath = sub_nspath
		self.path = self.__file__ = path
		self.finder = finder
		self.initialized = False
		self.config = {}
		self._model = AttrDict()

	# The BEGINNING of all the model stuff. Basically, when you access the model, it will auto-initialize.
	# This fully automatic functionality is kind of nice but also kind of sucks. Because you have no way
	# to interact with the initialization and this becomes problematic, with the need to attach things to
	# the hub, etc. So it should be moved to a Configuration/moons paradigm.

	"""
	@property
	def model(self):
		if not self.initialized:
			self.initialize()
		return self._model

	def initialize(self):
		if self.initialized:
			return
		init_path = os.path.join(self.path, "init.py")
		if not os.path.exists(init_path):
			self.initialized = True
			return

		mod = load_plugin(init_path, "init")
		init_func = getattr(mod, "__init__", None)
		if init_func is not None and isinstance(init_func, types.FunctionType):
			try:
				logging.warning(f"Passing {self.config} to init_func")
				# TODO: make this thread-safe so it only gets called once.
				init_func(self._model, **self.config)
			except TypeError as te:
				raise TypeError(f"Init via {init_path}: {str(te)}")
		self.initialized = True
	"""

	# The END of all the model stuff

	def __iter__(self):
		"""
		This method implements the ability for developers to iterate through plugins in a sub.

		For example::

		  import dyne.org.funtoo.powerbus.mysub as mysub
		  for plugin in mysub:
		      mysub.do_something()

		Also see``tests/test_import_iter.py`` for an example of how this can be used.
		"""
		if not self.initialized:
			raise LaunchError(f"Please launch {self.sub_nspath}.")
		if self.__file__ is not None:
			for file in os.listdir(self.path):
				if file.endswith(".py"):
					if file not in ["__init__.py", "init.py"]:
						fullname = f"{self.__name__}.{file[:-3]}"
						mod = sys.modules.get(fullname, None)
						if mod:
							yield mod
						else:
							yield self.finder.load_module(fullname)

	def __getattr__(self, key):
		"""
		This method enables the ability to automatically reference plugins from a sub. For example, you
		can import just the sub::

		  import dyne.org.funtoo.powerbus.foo as foo

		And then you can access a plugin as follows::

		  foo.myplugin.do_something()

		Behind the scenes, we leverage the DyneFinder to load the plugin dynamically using our official Dyne
		loading mechanism.

		However, you typically DON'T want to import the plugin, as this example does::

		  import dyne.org.funtoo.powerbus.foo.myplugin
		  myplugin.do_something()

		Technically, it will work. However, doing this *will* bypass subsystem initialization code in
		``init.py``, as well as mapping your config to your model, so it's strongly discouraged.

		"""

		# We use a special lock here below, because dyne code can load other dyne code -- and this can
		# even create cycles. We want to import a dyne module only once. But we have to lock per module, because
		# otherwise we can deadlock if a dyne itself grabs a dyne.

		# For a reason I haven't figured out, the debian-sources generator was triggering either the race
		# condition or the deadlock. First I fixed the race condition. Then it deadlocked. This module-specific
		# lock fixes both issues.

		fullname = f"{self.__name__}.{key}"
		access_lock = self.get_access_lock(fullname)
		with access_lock:
			if not self.initialized:
				raise LaunchError(f"Please launch {self.sub_nspath}.")
			mod = sys.modules.get(fullname, None)
			if mod:
				return mod
			else:
				return self.finder.load_module(fullname)

	async def launch(self, config_obj=None, **config_kwargs):
		if config_obj:
			self.model = config_obj()
			await self.model.start(**config_kwargs)
		self.initialized = True

class DyneFinder:
	"""
	    Initialize as follows:

	      if not hasattr(sys,'frozen'):
	      sys.meta_path.append(DyneFinder())

	All subsequent imports will now use the DyneFinder. The DyneFinder is designed to import
	dynes from the virtual ``dyne`` module.
	"""

	prefix = "dyne"

	def __init__(self, hub=None, plugin_path=None):
		super().__init__()
		self.hub = hub
		# self.plugin_path is a means to override self.path_search_dict for tests -- it allows us to say "look here for subs" instead
		# of looking in /usr/lib/pythonx.y and ~/.local/lib/pythonx.y.
		self.plugin_path = plugin_path
		self.yaml_search_dict = {}
		self.path_search_dict = {}
		self.init_yaml_loader()
		self.thread_id = threading.get_ident()
		self.mod_path_lock = defaultdict(lambda: threading.Lock())
		self.lock = threading.Lock()

	def init_yaml_loader(self):

		# This adds all plugins that are in /usr/lib/pythonx.y/subpop:

		if self.plugin_path:
			scan_paths = [ self.plugin_path ]
		else:
			scan_paths = [ get_root_plugin_path(), get_user_plugin_path() ]

		for scan_path in scan_paths:
			try:
				for namespace in os.listdir(scan_path):
					if namespace in self.path_search_dict:
						logging.warning(f"Subpop namespace {namespace} at {self.path_search_dict.full_path} overridden by subsystem at {scan_path}")
					self.path_search_dict[namespace] = ProjectData(scan_path, namespace)
			except FileNotFoundError:
				pass
			except PermissionError:
				logging.warning(f"Unable to read {scan_path} due to insufficient permissions.")

		# This adds all plugins mapped via PYTHONPATH. PYTHONPATH is 'special' in that we assume these
		# are development sources; therefore, we look for a subpop.yaml file and parse it directly to
		# identify our namespace and location of subsystems, rather than looking for our official
		# directory structure.

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
		"plugin" for plugin, and will return None if neither is found.

		:param partial_path: fully-qualified path, to a directory, or if we add a ".py" ourselves, maybe a plugin!
		:type partial_path: str
		:return: "sub", "plugin", or None
		:rtype: str
		"""
		try:
			farf = os.stat(partial_path, follow_symlinks=True)
			if stat.S_ISDIR(farf.st_mode):
				return "sub"
		except FileNotFoundError:
			# This will raise FileNotFound exception if this file doesn't exist.
			try:
				farf = os.stat(partial_path + ".py", follow_symlinks=True)
				if stat.S_ISREG(farf.st_mode):
					return "plugin"
			except FileNotFoundError as fnfe:
				return

	def load_module(self, fullname):
		# do a lock before using our mod_path_lock to acquire a lock!
		self.lock.acquire()
		with self.mod_path_lock[fullname]:
			self.lock.release()
			result = self.really_load_module(fullname)
		return result

	@property
	def thread_str(self):
		cur_thread_id = threading.get_ident()
		if cur_thread_id == self.thread_id:
			return ""
		else:
			return f"(thread id {cur_thread_id})"

	def really_load_module(self, fullname):
		# Let's see if the module has already been loaded:

		mod = getattr(sys.modules, fullname, None)
		if mod is not None:
			return mod

		# Let's assume fullname is "dyne.org.funtoo.powerbus.system".

		full_split = fullname.split(".")[1:]  # [ "org", "funtoo", "powerbus", "system" ]

		# "org.funtoo.powerbus" is allowed to be imported as well -- as a root subsystem.

		if fullname == self.prefix or len(full_split) < 3:
			mod = sys.modules[fullname] = types.ModuleType(fullname)
			mod.__path__ = []
			return mod

		ns_relpath = ".".join(full_split[:3])  # "org.funtoo.powerbus"
		plugin_parts =full_split[3:]  # ["system"]
		sub_nspath = ns_relpath
		if len(full_split) > 3:
			sub_nspath = sub_nspath + "/" + "/".join(plugin_parts)  # "org.funtoo.powerbus/system"

		partial_path = None
		if ns_relpath in self.yaml_search_dict:
			# We found a project referenced in PYTHONPATH. Look in it for the plugin.
			yaml_obj = self.yaml_search_dict[ns_relpath]
			partial_path = yaml_obj.resolve_relative_subsystem(plugin_parts)
		elif ns_relpath in self.path_search_dict:
			# We found the subsystem in our path structure
			path_obj: ProjectData = self.path_search_dict[ns_relpath]
			partial_path = path_obj.resolve_relative_subsystem(plugin_parts)

		if partial_path is None:
			raise ModuleNotFoundError(f"DyneFinder couldn't find {fullname}")

		# partial_path may point to a subsystem, or a python plugin (.py). We need to figure out which:

		mod_type = self.identify_mod_type(partial_path)
		if mod_type is None:
			raise ModuleNotFoundError(
				f'DyneFinder couldn\'t find the specified plugin or subsystem "{fullname}" -- looked for {partial_path}(.py)'
			)

		if mod_type == "plugin":
			loader = importlib.machinery.SourceFileLoader(fullname, partial_path + ".py")
			mod = sys.modules[fullname] = types.ModuleType(loader.name)
			try:
				loader.exec_module(mod)
			except BaseException as be:
				try:
					del sys.modules[fullname]
				except KeyError:
					pass
				raise be
			my_sub_path = f"{self.prefix}.{ns_relpath}.{'.'.join(plugin_parts[:-1])}".rstrip('.')
			if not sys.modules[my_sub_path].initialized:
				raise LaunchError(f"Please launch {my_sub_path} before using {partial_path}.py.")
			# do hub/model injection -- as long as we find a hub/model defined (typically set to None)
			mod.__sub__ = ns_relpath
			mod.__file__ = partial_path + ".py"
			# *ALWAYS* inject the hub.
			mod.hub = self.hub
		elif mod_type == "sub":
			mod = sys.modules[fullname] = PluginSubsystem.get_subsystem(sub_nspath, fullname, path=partial_path, finder=self)
			mod.__path__ = []
			mod.__launched__ = False

		return mod
