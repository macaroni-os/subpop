Subpop Project Structure
========================

NOTE: THIS DOCUMENT IS A WORK-IN-PROGRESS AND THINGS ARE VERY LIKELY TO CHANGE A LOT, SOON!

This section documents all you need to know about creating a Subpop project -- what things are required, how to
organize things, etc. The goal is to help you understand *why* things should be organized this way -- not just 'the
how'.

Terms
-----

We'll use the term "project root directory" or "project root" to refer to the main directory of your software project.
This is the directory that is the root of your source code, so your root directory will contain a ``.git`` directory,
for example.

``subpop.yaml``
---------------

When you create your software project, you will need to create a ``subpop.yaml`` file in the root directory. For
now, this file should be left blank, but will be used in the future. This file is important because Subpop looks
for it to identify the root of your software project, so it must exist. To create this file, perform the following::

  # touch subpop.yaml
  # git add subpop.yaml


Creating Your First Application
-------------------------------

I will typically create a ``bin/`` folder on the project root, which will contain executable Python programs without
the ``.py`` extension. This can be done as follows::

  # mkdir bin
  # vim bin/doit (write your command)
  # chmod +x bin/doit
  # git add bin/doit

The most simple skeleton for the content of your command might look like this for a non-async program:

.. code-block:: python

  #!/usr/bin/env python3

  from subpop.hub import Hub

  def main_thread():
    return

  if __name__ == "__main__":
    hub = Hub()
    main_thread()

If you are writing a program that uses asyncio, then you will want to use this skeleton instead:

.. code-block:: python

  #!/usr/bin/env python3

  from subpop.hub import Hub

  async def main_thread():
    return

  if __name__ == "__main__":
    hub = Hub()
    hub.LOOP.run_until_complete(main_thread())

Organizing Plugin Subsystems
----------------------------

Of course, you will want to add plugin subsystems to your Hub so you can do things with it. Where should the
plugins live? Subpop gives you flexibility in defining where these live in your project root. You could create
a directory called ``subsystems``, or simply create a directory named something related to your project, such
as ``funtoo``. Inside this directory, you will create more directories which are the plugin subsystems themselves.
And inside those directories will live ``.py`` files which contain the actual plugins.

Whatever directory structure you decide upon, you will need to specify this path in your application when loading
the subsystem. So for example, if you have a plugin subsystem at ``funtoo/pkgtools`` relative to your project root,
then you will add this subsystem to the hub as per this example code:

.. code-block:: python

  #!/usr/bin/env python3

  from subpop.hub import Hub

  async def main_thread():
    await hub.pkgtools.myplugin.do_something_async()

  if __name__ == "__main__":
    hub = Hub()
    hub.add('funtoo/pkgtools')
    hub.LOOP.run_until_complete(main_thread())

As you can see, when a subsystem is added to the hub, it will be available on the hub at ``hub.<subsystem_dir_name>``.

Calling from /usr/bin
---------------------

If you are
running everything from a local git repository, this structure tends to work fine, and you will just make sure that
``<project_root>/bin`` is in your ``PATH``. However, there may be times where you will want to install your script
into a common program directory outside of your project root, such as in ``/usr/bin``. For these situations, it's
recommended that you use a *symbolic link* in ``/usr/bin`` which *points* to the program in your project root.

Using Entry Points
------------------

Python's setuptools supports the concept of "entry points", which are ``functions`` for which setuptools will create
a small executable wrapper. From a python packaging perspective, you can learn more about this functionality in the
`python packaging documentation`_. But is this functionality compatible with Subpop?

In theory, yes -- but it requires some tweaks to our project structure, because "entry points" leverage the ``import``
mechanism of Python to do their thing. And you've noticed that so far, we haven't even discussed the creation of a
Python module. For your commands to be imported, instead of locating a command at ``bin/doit``, you will want to
use a structure of ``<pymodule>/cmd/doit.py``. In this organizational structure, we are creating a python module called
``<pymodule>`` (replace with your favorite name), and we will use a slightly different command template in ``doit.py``:

.. code-block:: python

  #!/usr/bin/env python3

  from subpop.hub import Hub

  async def main_thread():
    await hub.pkgtools.myplugin.do_something_async()

  def main():
    hub = Hub()
    hub.add('funtoo/pkgtools')
    hub.LOOP.run_until_complete(main_thread())

I used the async example to point out some important things. One is that your entry point as specified in ``setup.py``
will be ``<myplugin>.cmd.doit:main`` -- in other words, the ``main()`` function. This is because we always want to
initialize the Hub in a non-async function, because it will initialize its internal asyncio loop, which we then use
to start our async code.

If you use the model above, and of course set up ``setup.py`` with this entrypoint, and add an ``__init__.py`` file to
the ``<pymodule>`` and ``<pymodule>/cmd`` directories, then setuptools should be able to properly call the entry point
to the Subpop command using this model. The "stub" command autogenerated by setuptools will execute something like
the following code:

.. code-block:: python

  #!/usr/bin/env python3

  from <myplugin>.cmd.doit import main

  if __name__ == "__main__":
    main()


.. _python packaging documentation: https://python-packaging.readthedocs.io/en/latest/command-line-scripts.html
