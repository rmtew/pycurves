Python code to allow display and visualisation of curves.

This script opens a Pyglet window, and then randomly places a number of
movable points which can be dragged up and down.  A Line is drawn between
the points, which may be either straight or curved.  UI elements like buttons
and sliders are placed which allow the curve type to be changed and the
way the curve is drawn to be varied.

Supported curve types:

  * Linear.
  * Smooth step.
  * Hermite.

# Dependencies #

[Pyglet](http://www.pyglet.org/).

# Compatibility #

It was written using Python 2.6 on Windows and has not been tested on other
platforms.

# Screenshots #

Linear curve (static.py):

![http://pycurves.googlecode.com/files/curve-linear.png](http://pycurves.googlecode.com/files/curve-linear.png)

Smooth step curve (static.py):

![http://pycurves.googlecode.com/files/curve-smoothstep.png](http://pycurves.googlecode.com/files/curve-smoothstep.png)

Hermite curve (static.py):

![http://pycurves.googlecode.com/files/curve-hermite.png](http://pycurves.googlecode.com/files/curve-hermite.png)

Hermite curve scrolling (dynamic.py):

![http://pycurves.googlecode.com/files/dynamic-20100621-01-hermite.png](http://pycurves.googlecode.com/files/dynamic-20100621-01-hermite.png)