There are two kinds of libraries in Linux: static (`.a`) and dynamic (`.so`) libraries. The `a` in static libraries stand for archive, and they are created with the `ar` program which takes a collection of object files (`.o`) and puts them together into a single file (the archive or static library).

The contents of the archive can be extracted and the individual files examined. Doing so can reveal dependency relationships among the objects comprising the archive. In particular, we can do this for `libc.a`, the static c library.

Now, there's an object file in `libc.a`, called `libc-start.o`, that contains the function `__libc_start_main`. This function is called by the `_start` function, which is where program execution begins (Yes, it's not `main`, since much has to be initialized before main can begin. A good article on this is [Linux x86 Program Start Up](http://dbp-consulting.com/tutorials/debugging/linuxProgramStartup.html). It's also why main can get away with not calling `_exit`, since it can return to whoever called it, and finally someone can call `_exit` with the return value of main.) The `_start` function is defined in `/usr/lib/crt1.o`, and it's linked to your program by gcc (as can be seen by passing the `-v` option to gcc).

So, since we're pulling in `libc-start.o` from `libc.a`, we have to also pull in the objects that it depends on, and the objects they depend on in turn, and so on. My goal was to see how much of libc you have to link just to use `_start`.

Of course, you can also supply your own `_start` function. But as soon as you call any libc function at all, you are likely to pull in a large portion of it since it's highly connected. This program can also be used to explore this dependency graph for other starting points like `printf` or `malloc`.

And finally, this situation is specific to glibc. For other libc implementations, it'll be different. For musl, the dependency from `libc-start.o` (actually it's called `libc-start.lo`) is extremely simple, in line with its emphasis on simplicity.
