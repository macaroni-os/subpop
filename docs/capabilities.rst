Plugin-Oriented Programming Capabilities
========================================

This document is intended to exhaustively list the functional current and future capabilities of Subpop, with examples
if possible, along with their status.

Traditional 'Plugin' Model
--------------------------

By 'traditional', we mean the concept of something like a GIMP plugin. For this pattern to be supported, one needs
to be able to iterate over all plugins::

 .. code-block:: python

  for plugin in hub.pkgtools:
    (do something)

This has not yet been added to the code, I don't think.

Recursive Loading
-----------------

POP has the ability to add a sub and all subs underneath it recursively, so that adding ``pkgtools`` might also add
``hub.pkgtools.foo`` as a sub, and ``hub.pkgtools.foo.bar`` as a plugin. This is not yet supported.

