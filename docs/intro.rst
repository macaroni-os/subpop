Introduction
============

What is Subpop?
~~~~~~~~~~~~~~~

Subpop is a framework designed to advance the paradigm of Plugin-Oriented Programming, and is designed to be an
evolution and refinement of the concepts in POP_. It currently has less functionality than POP_, but is designed to
be more elegant and easier to use. POP was developed within SaltStack and had to meet certain internal needs. As I
started to use POP for Funtoo Linux, I identified several areas where I believe POP could be improved.

Subpop is intended to be a Funtoo Linux project, as it supports active Funtoo Linux projects. It is also a project
that may be used for future POP efforts at SaltStack (now part of VMware, Inc.)

What is Plugin-Oriented Programming?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plugin-Oriented Programming is a software development methodology that is designed to encourage code maintainability and
extensibility. Subpop implements this vision by implementing an alternative Python "code loader" that is a replacement
for the traditional ``import`` statement, with enhanced functionality to support a paradigm of "pluggable" software.
When you ``import dyne.foo`` -- you are actually importing using special code that looks in a plugin directory instead
of in the traditional places that Python imports from.

The predecessor to subpop, POP_, uses something called a "hub" as a super-global that is available throughout your
application, and uses it to collect not just plugin subsystems, but also live objects your program may need (it doesn't
use regular ``import`` statements for loading plugin subsystems like subpop does.)

I have decided that this is messy and bad. So in subpop, you don't attach plugins to the hub, but you import them
using ``import dyne.x.y.z``, and you are also discouraged from using the hub as a 'catch all' for live objects --
instead a concept called a "model" is available, and each plugin subsystem has a model that can hold these objects.

Why Plugin-Oriented Programming?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OOP principles can encourage the creation of large, monolithic code bases that are highly inter-dependent and thus hard
to maintain as well as refactor. Plugin-Oriented Programming aims to address this tendency by encouraging code to be
organized in small, modular pieces called 'plugins', which are organized into 'plugin subsystems'. This approach to
organizing code this way is not particularly sophisticated, but somehow this pattern seems to be very beneficial.
When creating code in this fashion, code can be kept very 'flat' which can make it much simpler and easier to maintain.

OOP and POP can be used together. OOP is an excellent paradigm for encapsulating functionality. But sometimes, another
tool is needed to organize code which is less focused on encapsulation and more focused on collecting related
functionality into logical chunks, without having to encapsulate them in a class. This is where POP comes in. When you
use POP principles, you can encapsulate functionality in a class using OOP when it makes sense -- but if it isn't
helpful to do so (and it often isn't), then you do not need to 'default' to OOP methods for organizing your code.
This tendency to 'default to OOP' is what we have found tends to create complex, monolithic code bases. Because too
many internals are encapsulated in classes, complex object coupling must occur, with arguments being passed between
object methods, and this results in a mess over time.

In a Nutshell, How Do You Use Subpop?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's assume your Python project will create plugins, as well as have a program that uses these plugins.

In the root of your Python project, you will want to create a ``subpop.yaml`` file. This file specifies the fully-
qualified namespace of your plugins, as well as their location relative to the root of your project. Something like
this would suffice:

.. code-block:: yaml

  namespace: org.funtoo.powerbus
  root: plugins

For this program, our namespace is "org.funtoo.powerbus", and it is customary to use this "reverse domain" format.
And our plugins and plugin subsystems will live in a directory called "plugins".

You might create a plugin called "plugins/session.py" that looks like this:

.. code-block:: python

  #!/usr/bin/env python3

  from subpop.hub import Hub

  if __name__ == "__main__":
    hub = Hub()

This main program has just created a "hub". Think of a hub as a super-global variable, that is automatically accessible
as a global variable in every plugin you add to your code. The hub is designed to give your code a central point of
reference for both calling other plugins, and also accessing important shared data. This reduces the need to pass this
data between functions as arguments.

So, what is a plugin? A "plugin" is just Python code that is designed to be loaded by the hub using subpop's code
loader, rather than the traditional method using an ``import`` statement. Plugins are organized into *plugin subsystems*
-- which we call "subs". So you will typically define a name for your sub, and then each plugin in the sub will also
have a name.

In its simplest form, a "sub" is just a directory of plugins. Let's say you have a sub in your Python code called
``pkgtools``, and it has the plugins ``foobar.py`` and ``oni.py``. In this case, the plugin structure in your code
might look like this::

  subs/
    pkgtools/
      foobar.py
      oni.py

You would add the sub to the Hub as follows:

.. code-block:: python

  #!/usr/bin/env python3

  from subpop.hub import Hub

  if __name__ == "__main__":
    hub = Hub()
    hub.add("subs/pkgtools")


Above, we specified ``subs/pkgtools``, which references a directory that is relative to the root of your Python project,
and the subsystem will now be available at ``hub.pkgtools`` by default (you can use the ``name=`` keyword argument if
you would like to change this name.)  By calling ``hub.add``, we have added the plugin subsystem to the hub, and now the
contents of ``foobar.py`` and ``oni.py`` can be used by extending our code as follows:

.. code-block:: python

  if __name__ == "__main__":
    hub = Hub()
    hub.add("subs/pkgtools")
    hub.pkgtools.foobar.my_function()
    hub.pkgtools.oni.MY_GLOBAL_VARIABLE

The code for ``subs/pkgtools/foobar.py`` might look something like this:

.. code-block:: python

  #!/usr/bin/env python3

  hub = None

  def my_function():
    print("Hello, there!")
    print(f"Oni's global variable is {hub.pkgtools.oni.MY_GLOBAL_VARIABLE}.")

The code for ``subs/pkgtools/oni.py`` might look like this:

.. code-block:: python

  #!/usr/bin/env python3

  hub = None

  MY_GLOBAL_VARIABLE="I am plugin oni!"

This is an extremely basic example of a Subpop application, sub, and plugins but hopefully it conveys the basic
organizational structure.

You will notice a couple of things about our very basic example plugins. First, we set ``hub`` to a value of ``None``.
This is done primarily just as a short-hand to indicate that this code is a plugin. The suppop code loader will replace
it with your main thread’s Hub object by the time your plugin’s functions or methods are called. So when subpop loads
this plugin, the the actual ``hub`` defined in your main application will be "injected" into the plugin, making it
available to your plugin's methods and functions. This also includes the possibility of accessing the hub from
class constructors (``def __init__(self):`` functions) in classes. You might be thinking -- "Ooh! this might come
in handy for sharing important things throughout my code!" If you thought this, then you are starting to see some
of the possible benefits of POP paradigms in cleaning up some old, crufty and overly complex code you might have
lying around.

You can also see that our main application can access both plugins, and you can also see that the ``foobar.py`` is
able to access the ``MY_GLOBAL_VARIABLE`` defined in ``oni.py`` as well. You may want to choose to have neighbor
plugins to access one another as in this example, or discourage or disallow it to have more of a microservices-style
model in your plugin subsystem, where all the code to handle a specific domain of your application is self-contained
in an individual plugin, with no or minimal external dependencies on neighboring plugins.

It's OK to Import
-----------------

You may be wondering -- how does my main application or plugin use existing Python modules? Simply import them as
you normally would. If your plugin needs a module, do the import at the top of the plugin.

However, you don't want to import your subpop plugins using the ``import`` statement. Instead, you always want to
add them to your hub using ``hub.add(path_to_subsystem)``, and then access them via the hub as
``hub.subsystem.plugin_name.function``.

Subs as Libraries
-----------------

As you continue to write your program, you are encouraged to define subs and plugins to organize your code. Sometimes,
you will want to create a sub that is used like a library, where each plugin takes care of a separate part of your
program. You can then use the hub to allow these various parts of your program to work together. Using this design,
you can have each plugin be somewhat or completely independent from other plugins, which is more of a "microservice"
model, as in the following example sub::

  business_logic/
    billing.py
    customer.py
    container.py
    backup.py


By using the hub to tie your program together, it's possible to create complex programs while keeping the design of your
code very 'flat' and simple, because you don't have to rely on passing arguments between functions as methods nearly as
much as in a traditional OOP design. This makes refactoring your code a lot easier. If you play with this approach a
bit, you'll start to see some of the potential of Plugin-Oriented Programming.

Subs as Collections of Plugins
------------------------------

It's also possible to use subs to organize a collection of what most people commonly associate with the word "plugin" --
that is, each Python file containing some new capability that gets "plugged in" using the same interface. For example,
you can imagine a graphics program that supports filters, and each plugin adds a new kind of filter that shows up in
a menu. Using this design, each plugin file will contain some common interface that can be leveraged by the application
in a consistent way.

.. _POP: https://pypi.org/project/pop/
