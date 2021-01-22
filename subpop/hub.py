#!/usr/bin/env python3

import asyncio
import os
import importlib.util
import threading
import types


class PluginDirectory:
	"""
	A ``PluginDirectory`` is the object that is put on the Hub when you use ``hub.add()``. So for example, if you
	do ``hub.add("path/to/foo")``, then ``hub.foo`` will be a ``PluginDirectory`` object. This object handles references
	to plugins that you want to access, such as ``hub.foo.bar``. By default, a Hub will run in "lazy" mode, which means
	that except for the speciail ``init.py`` file, all plugins will only be loaded *on first reference* rather than
	when your run ``hub.add()``. However, if you create your Hub with the ``lazy=False`` keyword argument, it will
	call the ``PluginDirectory.load()`` method when adding a subsystem, which will automatically load all plugins
	at startup. This is slower and not normally necessary so is not recommended.

	The ``PluginDirectory.__getattr__`` method is what implements the 'hook' to dynamically load plugins as they are
	referenced.
	"""

	def __init__(self, hub, path, init_kwargs=None):
		self.path = path
		self.hub = hub
		self.init_done = False  # This means that we tried to run init.py if one existed.
		self.loaded = False  # This means the plugin directory has been fully loaded and initialized.
		self.plugins = {}
		self.init_kwargs = init_kwargs
		self.do_dir_init()

	def ensure_plugin(self, plugin_name):
		"""
		This allows a plugin to be explicitly loaded, which is handy if you are using lazy loading (load on first
		reference to something in a plugin) but your first interaction with it.
		"""
		self.do_dir_init()
		if self.loaded:
			if plugin_name not in self.plugins:
				raise IndexError(f"Unable to find plugin {plugin_name}.")
		else:
			self.plugins[plugin_name] = self.hub.load_plugin(os.path.join(self.path, plugin_name + ".py"), plugin_name)

	def do_dir_init(self):
		"""
		This method performs the initialization of the subsystem -- the loading of ``init.py`` -- if it exists.
		This *always* happens first, even if the subsystem is being lazy-loaded.
		"""
		if self.init_done:
			return
		init_path = os.path.join(self.path, "init.py")
		if os.path.exists(init_path):
			print(f"Loading init from {init_path}")
			# Load "init.py" plugin and also pass init_kwargs which will get passed to the __init__() method.
			self.plugins["init"] = self.hub.load_plugin(init_path, "init", init_kwargs=self.init_kwargs)
		self.init_done = True

	def load(self):
		"""
		The Hub will call this to force-load all of the plugins when running in non-lazy mode.
		"""
		self.do_dir_init()
		for item in os.listdir(self.path):
			if item in ["__init__.py", "init.py"]:
				continue
			if item.endswith(".py"):
				plugin_name = item[:-3]
				if plugin_name not in self.plugins:
					self.plugins[plugin_name] = self.hub.load_plugin(os.path.join(self.path, item), plugin_name)
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


class Hub:
	"""
	The Hub is a superglobal and a core paradigm of Plugin-Oriented Programming. It is designed to always be available
	as a global in your plugins. The Subpop code loader automatically injects the hub into each plugin's global
	namespace. This means that any class method or function in your plugin can reference the hub as a global variable.
	It will be transformed into your main thread's Hub object by the time your plugin's functions or methods are called.

	One important note, however -- you won't be able to reference the hub in your plugin's global namespace, since it
	won't be available yet. So always reference the hub inside a function or method. In other words, here's an example
	plugin::

	        def my_plugin_function():
	                # hub will be 'live' and work:
	                hub.foo()

	        # hub is not initialized yet, and this will not work:
	        hub.foo()

	Also note: You will want to create a hub in your application's main thread, *before* you start any asyncio loop.
	See ``LOOP`` below for the right way to start your program's asyncio loop.

	:param lazy: By default, the hub will load plugins when they are first referenced. When ``lazy`` is set to ``False``,
	        all plugins in the sub will be loaded when the sub is added to the hub via ``hub.add(path_to_sub)``.
	        It's recommended to use the default setting of ``True`` -- loading each plugin on first reference.
	:type lazy: bool
	"""

	def __init__(self, lazy: bool = True):

		self.root_dir = os.path.normpath(os.path.join(os.path.realpath(__file__), "../../"))
		self.paths = {}
		self.lazy = lazy
		self._thread_ctx = threading.local()

		try:
			self._thread_ctx.loop = asyncio.get_running_loop()
		except RuntimeError:
			self._thread_ctx.loop = asyncio.new_event_loop()
			asyncio.set_event_loop(self._thread_ctx.loop)

	@property
	def THREAD_CTX(self):
		"""
		In Python, threads and asyncio event loops are connected. Python asyncio has the concept of the
		"current asyncio loop", and this current event loop is bound to the *current thread*. If you are
		using non-threaded code, your Python code still runs in a thread -- the 'main thread' (process)
		of your application.

		If you *do* happen to use multi-threaded code, don't worry -- the ``hub.LOOP`` is thread-aware.
		It uses thread-local storage -- ``THREAD_CTX`` -- behind-the-scenes to store local copies of each
		ioloop for each thread in your application. The ioloop is stored internally at ``THREAD_CTX._loop``.

		``hub.THREAD_CTX`` can also be used by developers to store other thread-local state. You just need
		to assign something to ``hub.THREAD_CTX.foo`` and its value will be local to the currently-running
		thread.
		"""
		return self._thread_ctx

	@property
	def LOOP(self):
		"""
		This is the official way to use the asyncio ioloop using subpop. To start the ioloop in your
		code, you will want to use the following pattern in your main thread, prior to starting any
		asyncio loop::

		        async def main_thread():
		                ...

		        if __name__ == "__main__":
		                hub = Hub()
		                hub.LOOP.run_until_complete(main_thread())

		Once you are in async code, you can reference ``hub.LOOP`` to get the current running ioloop::

		        async def main_thread():
		                fut = hub.LOOP.create_future()

		If you are using threads, here is how you can run async code inside your new thread::

		        def my_thread_function(my_arg, kwarg_foo=None):
		                do_cpu_intensive_things()

		        def run_async_adapter(corofn, *args, **kwargs):
		                # This function runs INSIDE a threadpool. By default, Python
		                # does not start an ioloop in a child thread. The hub.LOOP
		                # code magically takes care of instantiating a new ioloop
		                # for the current thread, so we just need to start the ioloop
		                # in this child thread as follows:
		                return hub.LOOP.run_until_complete(corofn(*args, **kwargs))

		        # The thread pool executor will return futures for our ioloop
		        # that are bound to the completion of the child thread. But the
		        # child thread is started without an ioloop in Python by default.

		        futures = []
		        with ThreadPoolExecutor(max_workers=cpu_count()) as tpexec:
		                for thing_to_do in list_of_things:
		                        # This hub.LOOP references the ioloop in the main thread:
		                        future = hub.LOOP.run_in_executor(
		                                tpexec, run_async_adapter, my_arg, kwarg_foo="bar"
		                        )
		                        futures.append(future)
		                # wait on *this thread's IO
		                await asyncio.gather(*futures)

		"""
		loop = getattr(self._thread_ctx, "_loop", None)
		if loop is None:
			loop = self._thread_ctx._loop = asyncio.new_event_loop()
		return loop

	def add(self, path, name=None, **init_kwargs):
		"""
		This function is the official way to add a plugin subsystem to the Hub.

		:param path: A path to a plugin subsystem directory, relative to the root of your Python project.
		:type path: str
		:param name: The name that will be used to map the subsystem to the Hub. Defaults to last portion of
		   path -- the directory name of the subsystem -- but you can use this to override it.
		:type name: str
		:param init_kwargs: Any additional keyword arguments passed to this method will be passed to the
		   ``__init__()`` function of the ``init.py`` in the subsystem, if the subsystem has these things.
		   This is the official way to pass things in to the intialization of a subsystem. Often, the
		   ``__init__()`` function will add certain objects to the Hub. It's recommended that if you do
		   this, that these objects are in UPPERCASE. See :meth:`subpop.hub.Hub.load_plugin` for more details
		   on the internals of how this works.
		:type init_kwargs: dict
		:return: None
		"""
		if name is None:
			name = os.path.basename(path)
		pdir = os.path.join(self.root_dir, path)
		if not os.path.isdir(pdir):
			raise FileNotFoundError(f"Plugin directory {pdir} not found or not a directory.")
		self.paths[name] = PluginDirectory(self, pdir, init_kwargs=init_kwargs)
		if not self.lazy:
			self.paths[name].load()

	def load_plugin(self, path, name, init_kwargs=None):
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
		spec = importlib.util.spec_from_file_location(name, path)
		if spec is None:
			raise FileNotFoundError(f"Could not find plugin: {path}")
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		# inject hub into plugin so it's available:
		mod.hub = self
		init_func = getattr(mod, "__init__", None)
		if init_func is not None and isinstance(init_func, types.FunctionType):
			if init_kwargs is None:
				init_func()
			else:
				# pass what was sent to hub.add("foo", blah=...) as kwargs to __init__() in the init.py.
				init_func(**init_kwargs)
		return mod

	def __getattr__(self, name):
		if name not in self.paths:
			raise AttributeError(f"{name} not found on hub.")
		return self.paths[name]
