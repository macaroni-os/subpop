#!/usr/bin/env python3

import asyncio
import os
import importlib.util
import threading
import types


class PluginDirectory:
	def __init__(self, hub, path, init_kwargs=None):
		self.path = path
		self.hub = hub
		self.init_done = False  # This means that we tried to run init.py if one existed.
		self.loaded = False  # This means the plugin directory has been fully loaded and initialized.
		self.plugins = {}
		self.init_kwargs = init_kwargs
		# I'm testing this -- it's probably best to make sure we do all init at the very beginning.
		self.do_dir_init()

	def load_plugin(self, plugin_name):
		"""
		This allows a plugin to be explicitly loaded, which is handy if you are using lazy loading (load on first
		reference to something in a plugin) but your first interaction with it
		"""
		self.do_dir_init()
		if self.loaded:
			if plugin_name not in self.plugins:
				raise IndexError(f"Unable to find plugin {plugin_name}.")
		else:
			self.plugins[plugin_name] = self.hub.load_plugin(os.path.join(self.path, plugin_name + ".py"), plugin_name)

	def do_dir_init(self):
		if self.init_done:
			return
		init_path = os.path.join(self.path, "init.py")
		if os.path.exists(init_path):
			print(f"Loading init from {init_path}")
			# Load "init.py" plugin and also pass init_kwargs which will get passed to the __init__() method.
			self.plugins["init"] = self.hub.load_plugin(init_path, "init", init_kwargs=self.init_kwargs)
		self.init_done = True

	def load(self):
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
		if not self.loaded:
			self.load()
		if plugin_name not in self.plugins:
			raise AttributeError(f"Plugin {plugin_name} not found.")
		return self.plugins[plugin_name]


class Hub:
	"""
	The Hub is a super-global and a core paradigm of Plugin-Oriented Programming. It is designed to always be available
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
		if name is None:
			name = os.path.basename(path)
		pdir = os.path.join(self.root_dir, path)
		if not os.path.isdir(pdir):
			raise FileNotFoundError(f"Plugin directory {pdir} not found or not a directory.")
		self.paths[name] = PluginDirectory(self, pdir, init_kwargs=init_kwargs)
		if not self.lazy:
			self.paths[name].load()

	def load_plugin(self, path, name, init_kwargs=None):
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
