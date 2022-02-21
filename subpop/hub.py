#!/usr/bin/env python3

import asyncio
import inspect
import os
import sys
import threading

from subpop.util import DyneFinder


class Hub(dict):
	"""

	The Purpose of Subpop
	=====================

	You're a person who knows Python.

	Consider a 'python snippet' or function that you want to write, and you want it to perform a
	variety of useful things and be embedded in a powerful framework rather than be a full
	standalone python program. You just want to write a few lines of code but have it do a lot
	of powerful things.

	Now, imagine you're the developer of a sophisticated and powerful framework. You want to make
	this framework available to be used by others by having them write very simple standalone
	'snippets' of Python code without requiring the complex boilerplate of instantiating your
	entire framework and importing a lot of third-party modules. You have a command or daemon
	that instantiates the framework already, and this isn't the role of those who will be
	leveraging your framework. All you need is a snippet of code from them, maybe a single
	function -- or a bunch of snippets -- that provide processing instructions for your
	framework. You have a standard function that users of your  framework need to provide --
	and your framework runs this function. Let's not make their task too difficult. The functions
	and methods are all ready to be called -- you just need the code to call them.

	We are talking about the new world of "code as a service", or "function as a service" --
	where people can simply write Python can you can load it into your framework. This is
	different from a traditional model of Python software development where all you can provide
	are modules and then others are left to write full standalone programs.

	For hosting as well as for community-oriented projects, the "code as a service" model is one
	that is more natural and powerful, because it makes it easier to get work done. Just write
	code, and you're done. Your code runs within a larger thing. But your code doesn't need to
	be part of this larger thing's code base. The larger thing can grab your code from the
	filesystem, a git repo, using HTTPS -- whatever.

	Subpop is my personal space for exploring these concepts and facilitating their use inside
	Funtoo's metatools framework.


	Subpop Origins
	==============

	Working with Thomas Hatch (creator of Salt) on his R&D Team, I was excited to learn of his
	POP ("Plugin Oriented Programming") framework. It, I suppose, was his personal framework
	where he was exploring various concepts. It looked promising. I started porting my Funtoo
	projects over to POP, including Funtoo's internal infrastructure and our tooling projects.
	I found various limitations in the framework. The largest problems were conceptual --
	what *specific* problems was the framework trying to solve, and why? -- this was unclear,
	as well as its lack of a functioning internal API and model for POP program structure that
	almost guaranteed any non-trivial software project would turn into an incoherent mess
	as it leveraged POP more and more.

	This made it unsuitable for my continued work -- but I had already ported quite a bit of
	Funtoo internal code over to POP! So now I was stuck having to create its successor, simply
	because of my current dependence on it for Funtoo code. I liked the idea of properly
	architecting the concepts that in POP were left to subsist as odd anti-patterns. Even if
	I didn't like the idea, I was kind of obligated to try to properly architect these concepts
	to beat a path in the wilderness and try to make these concepts start to work better for
	my code, since as I was likely the world's most prolific open source POP-using developer,
	I was starting to see some pretty big problems.

	This involved a complete from-scratch creation called 'subpop', which is this thing,
	which has evolved alongside Funtoo code that I have tried to get to a better place. I had
	to take some partially-developed ideas and try to complete the thought -- all while keeping my
	code running. A bit tricky!

	The Hub -- And What's Wrong With It, Exactly?
	=============================================

	POP has the concept of a hub, which is used pervasively throughout POP and POP projects. So
	this paradigm also exists in subpop. However, in subpop, I've put some thought into the
	appropriate use of the hub and what problem it actually solves. In POP, the hub is
	everywhere. You can't get away from it. There is only one world, and this world has a hub
	in it. This raised many questions in my mind:

	1. What parts of code should be 'in POP' and what should be implemented as traditional
	   Python modules? How do they get along?

	2. What is this hub needed for, again?

	When it's just there, all the time, then the hub doesn't really serve a purpose other
	than being a "new and awesome way to write the same thing in a brand new and confusing
	way!" This was exacerbated by POP being designed to discourage the use of object-oriented
	programming paradigms in your codebase, due to Tom's personal dislike of OOP! This was a
	very bold -- and probably very incorrect -- position to take. Subpop has been designed
	to be OOP-friendly because OOP is the best model we have for encapsulating and organizing
	complex functionality within our code.

	For subpop, I've tried to apply some standards to those weird and wonderful new paradigms,
	namely:

	Anything that deviates from standard Python software development practices should
	have a clear intention and a specific problem it is trying to solve. This means that by
	definition, any such deviation should not be presented as 'the one way' to write software.
	(POP made this mistake. Everything revolves around the hub. You can't escape it in POP code.
	And if you write POP code, it's very hard to write OOP code. I'm not interested in supporting
	this kind of "my way or the highway" approach.)

	For subpop, the hub fits into a paradigm of  two worlds -- that of the framework creator and
	that of the framework user.

	Subpop's hub is really meant to exist only in the world of the framework user. The framework
	creator should create a "walled garden" with a hub in it for the framework user to leverage.
	The hub is utilized in this garden. Your framework internals themselves do not need a hub or
	hubs. They are for your framework users.

	For this purpose, a hub can make a lot of sense.


	Dynes -- Their Evolution
	========================

	POP had a model of auto-attaching functions to the hub hierarchically called "dyne", and
	grabbing these functions from potentially other code bases. This happened magically, behind
	the scenes, and in a way that was not compatible with standard module imports.

	Subpop re-implements the dyne model with a loader that is compatible with the regular
	"import" statement. Any import beginning with ``dyne.org.funtoo``, for example, is imported
	from the ``org.funtoo`` namespace. Subpop manages its own tree of dynes that get installed
	in parallel to site-packages. So, subpop dynes are very different from POP dynes, but serve
	a similar purpose of "providing access to, and loading of a subsystem". This subsystem is
	just mapped into the current code's namespace via a regular import statement. These
	subsystems are managed differently from regular imports because subpop subsystems are different
	from standard Python modules (and also from POP subsystems.)

	Every subsystem in subpop, after being imported, must be launched with a model. This model
	is designed to provide the subsystem with configuration it needs to properly initialize.
	The model is implemented as a Python class, so it can have a lot of useful well-organized
	and encapsulated functionality. This was something added to subpop due to a lack of a
	coherent way to launch a subsystem in POP.

	Once launched, the subsystem is ready for use. Then the intention is for the subsystem
	to be attached to a Hub by the framework creator, which can really be any class (it doesn't
	have to be this one, although this will likely evolve into the superclass to derive your
	Hubs from).

	Now your framework is ready to load some external Python code, call a function in it, and
	pass it the hub as an argument. The hub mediates access to subsystems, and automatically
	passes itself as context to these subsystems.

	Ta da! That's what a hub is for. We've found its purpose.
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
