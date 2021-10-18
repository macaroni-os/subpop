#!/usr/bin/env python3

import asyncio
import inspect
import os
import sys
import threading

from subpop.util import DyneFinder


class Hub(dict):
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

	def __init__(self, finder=None):
		super().__init__()
		self._thread_ctx = threading.local()
		try:
			self._thread_ctx._loop = asyncio.get_running_loop()
		except RuntimeError:
			self._thread_ctx._loop = asyncio.new_event_loop()
			asyncio.set_event_loop(self._thread_ctx._loop)

		# Initialize meta-loader
		if finder is None:
			finder = DyneFinder(hub=self)
		if not hasattr(sys, "frozen"):
			if len(sys.meta_path) and not isinstance(sys.meta_path[-1], DyneFinder):
				sys.meta_path.append(finder)

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

	def run_async_adapter(self, corofn, *args, **kwargs):
		"""
		Use this method to run an asynchronous worker within a ThreadPoolExecutor.
		Without this special wrapper, this normally doesn't work, and the
		ThreadPoolExecutor will not allow async calls.  But with this wrapper, our
		worker and its subsequent calls can be async.
		"""
		return self.LOOP.run_until_complete(corofn(*args, **kwargs))

	def __getattr__(self, name):
		if name not in self:
			frame = inspect.stack()[1]
			filename_of_caller = os.path.realpath(frame[0].f_code.co_filename)
			raise AttributeError(f"{filename_of_caller}, in {frame[3]}(): hub.{name} is not defined.")
		return self[name]

	def __setattr__(self, key, val):
		self[key] = val


# vim: ts=4 sw=4 noet
