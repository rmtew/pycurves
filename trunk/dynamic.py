"""
Link: http://code.google.com/p/pycurves/
Author: Richard Tew <richard.m.tew@gmail.com>

Description
-----------

This script opens a Pyglet window, and then draws a curve with
accompanying controls that allow it to be manipulated.  The
curve can be scrolled left or right (points in either direction are
not deterministic), at varying speeds and more.

Supported curve types:

  - Linear.
  - Smooth step.
  - Hermite.

Dependencies
------------

Pyglet

Testing
-------

It was written using Python 2.6 on Windows and has not been tested on other
platforms.
"""

import random, math, sys
import pyglet
from pyglet.window import key, mouse
from pyglet.gl import *


CURVE_DISPLAY_SECTIONS = 6
CURVE_MARGIN_SECTIONS = 2
CURVE_SECTIONS = CURVE_MARGIN_SECTIONS + CURVE_DISPLAY_SECTIONS + CURVE_MARGIN_SECTIONS
CURVE_SECTION_SUBDIVISIONS = 20
CURVE_POINTS = CURVE_SECTIONS + 1
CURVE_SUBDIVISION_FRACTION = 1.0 / CURVE_SECTION_SUBDIVISIONS

INITIAL_CURVE_SCROLL_PERIOD = 3.0
INITIAL_CURVE_SCROLL_DIRECTION = 1.0

CURVE_HEIGHT = 40
CURVE_X_MARGIN = 60
CURVE_Y_MARGIN = 80
CURVE_Y0 = CURVE_Y_MARGIN
CURVE_Y1 = CURVE_Y0 + CURVE_HEIGHT

SLIDER_RADIUS = 4

NORMAL_COLOUR = (1.0, 1.0, 1.0, 1.0)
BORDER_COLOUR = (0.7, 0.7, 0.7, 1.0)

NORMAL_DRAW_STYLE = GLU_FILL            # Draw style when not being dragged.
SELECTED_DRAW_STYLE = GLU_SILHOUETTE    # Draw style when being dragged.

NUM_LINE_TYPES = 3
LINES_LINEAR, LINES_SMOOTHSTEP, LINES_HERMITE = range(NUM_LINE_TYPES)

INITIAL_CURVE_TYPE = LINES_LINEAR

line_labels = {
    LINES_LINEAR:       "Linear",
    LINES_SMOOTHSTEP:   "Smooth Step",
    LINES_HERMITE:      "Hermite",
}


class Vector2D:
    def __init__(self, *args):
        if len(args) == 1 and type(args[0]) is type(self):
            self.x = args[0].x
            self.y = args[0].y
        else:
            self.x = args[0]
            self.y = args[1]

    def __str__(self):
        return "(%0.2f, %0.2f)" % (self.x, self.y)

    def __iter__(self):
        yield self.x
        yield self.y

    def __mul__(self, other):
        v = Vector2D(self.x, self.y)
        if type(other) in (float, int):
            v.x *= other
            v.y *= other
        else:
            raise Exception("unhandled operation", self, other)
        return v

    def __div__(self, other):
        v = Vector2D(self.x, self.y)
        if type(other) in (float, int):
            v.x /= other
            v.y /= other
        else:
            raise Exception("unhandled operation", self, other)
        return v
        
    def __add__(self, other):
        v = Vector2D(self.x, self.y)
        v.x += other.x
        v.y += other.y
        return v

    def __sub__(self, other):
        v = Vector2D(self.x, self.y)
        v.x -= other.x
        v.y -= other.y
        return v    

    def length2(self):
        return self.x * self.x + self.y * self.y

    def length(self):
        return math.sqrt(self.length2())

    def normalise(self):
        length = self.length()
        return Vector2D(self.x/length, self.y/length)

    def dot_product(self, other):
        return self.x * other.x + self.y * other.y

    def angle_between(self, other):
        return math.acos(self.dot_product(other) / (self.length2() + other.length2()))

## Interpolation.

def smooth_step_interpolation(v):
    return (v * v * (3.0 - 2.0 * v))

def hermite_interpolation(p0, p1, p2, p3, mu, tension, bias):
    """
    Taken from:
      http://local.wasp.uwa.edu.au/~pbourke/miscellaneous/interpolation/
    """
    mu2 = mu * mu
    mu3 = mu2 * mu

    m0  = (p1-p0)*(1.0+bias)*(1.0-tension)/2.0
    m0 += (p2-p1)*(1.0-bias)*(1.0-tension)/2.0
    m1  = (p2-p1)*(1.0+bias)*(1.0-tension)/2.0
    m1 += (p3-p2)*(1.0-bias)*(1.0-tension)/2.0
    a0 =  2.0*mu3 - 3.0*mu2 + 1.0
    a1 =      mu3 - 2.0*mu2 + mu
    a2 =      mu3 -     mu2
    a3 = -2.0*mu3 + 3.0*mu2

    return p1*a0 + m0*a1 + m1*a2 + p2*a3

def xclip_far(p0, p1, x1):
    dv = p1 - p0
    m = dv.y / dv.x
    c = p1.y - m * p1.x
    return Vector2D(x1, m * x1 + c)


## UI.

class UIElement:
    x = 0
    y = 0
    width = 0
    height = 0

    def within(self, x, y):
        return x > self.x and x < self.x + self.width and \
               y > self.y and y < self.y + self.height

    def drawable(self):
        return True

    def event_press(self, x, y):
        pass

    def event_release(self, x, y):
        pass
        
    def event_drag(self, x, y):
        pass
        
    def event_drag_child(self, child, x, y):
        pass


class Label(UIElement):
    def __init__(self, x, y, label="Label"):
        self.x = x
        self.y = y
        self.label = label

        self.label_element = pyglet.text.Label(self.label,
            x=self.x,
            y=self.y,
            font_size=8,
            anchor_x="center")

    def set_text(self, text):
        self.label_element.text = text

    def draw(self):
        self.label_element.draw()


class Circle(UIElement):
    def __init__(self, x, y, radius=10.0, colour=NORMAL_COLOUR, parent=None):
        self.x = x
        self.y = y
        self.radius = radius
        self.colour = colour
        self.quadric = gluNewQuadric()
        self.resolution = 60
        self.draw_style = NORMAL_DRAW_STYLE
        
        self.parent = parent
        self.bounds = None

    def within(self, x, y):
        return math.sqrt((x - self.x) ** 2.0 + (y - self.y) ** 2.0) < self.radius

    def drawable(self):
        if self.parent:
            return self.parent.drawable()
        return UIElement.drawable(self)
        
    def event_press(self, x, y):
        self.draw_style = SELECTED_DRAW_STYLE

    def event_release(self, x, y):
        self.draw_style = NORMAL_DRAW_STYLE

    def event_drag(self, x, y):
        if self.parent:
            self.parent.event_drag_child(self, x, y)
            return

        min_y, max_y = CURVE_Y0, CURVE_Y1

        if y < min_y:
            y = min_y
        elif y > max_y:
            y = max_y

        self.y = y

    def draw(self):
        glColor4f(*self.colour)

        glPushMatrix()
        glTranslatef(self.x, self.y, 0.0)
        gluQuadricDrawStyle(self.quadric, self.draw_style)
        gluDisk(self.quadric, 0, self.radius, self.resolution, 1)
        glPopMatrix()


class Button(UIElement):
    DEFAULT_WIDTH = 80
    DEFAULT_HEIGHT = 20

    def __init__(self, x, y, width=None, height=None, label="Click", callback=None):
        self.x = x
        self.y = y
        self.width = Button.DEFAULT_WIDTH if width is None else width
        self.height = Button.DEFAULT_HEIGHT if height is None else height
        self.label = label

        self.label_element = pyglet.text.Label(self.label,
            x=self.x + self.width/2.0,
            y=self.y + self.height/2.0 + 1.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.callback = callback
        self.pressed = False

    def event_press(self, x, y):
        self.pressed = True

    def event_release(self, x, y):
        if self.pressed:
            self.pressed = False
            if self.within(x, y):
                self.callback(self)
            return True
        return False

    def draw(self):
        if self.pressed:
            glColor4f(*BORDER_COLOUR)
        else:
            glColor4f(*NORMAL_COLOUR)

        glPushMatrix()
        glTranslatef(self.x, self.y, 0.0)
        glBegin(GL_LINES)
        glVertex2f(0, 0)
        glVertex2f(0, self.height)
        glVertex2f(0, self.height)
        glVertex2f(self.width, self.height)
        glVertex2f(self.width, self.height)
        glVertex2f(self.width, 0)
        glVertex2f(self.width, 0)
        glVertex2f(0, 0)
        glEnd()
        glPopMatrix()

        self.label_element.draw()


class SliderBox(UIElement):
    DEFAULT_WIDTH = 40
    DEFAULT_HEIGHT = 100

    def __init__(self, x, y, width=None, height=None, label="Slider", min_value=0.0, max_value=1.0, step_value=0.1, value=0.0, curve_types=None, callback=None):
        self.x = x
        self.y = y
        self.width = SliderBox.DEFAULT_WIDTH if width is None else width
        self.height = SliderBox.DEFAULT_HEIGHT if height is None else height
        self.label = label
        self.min_value = min_value
        self.max_value = max_value
        self.step_value = step_value
        self.curve_types = curve_types
        self.callback = callback
        
        self.y_margin = 20.0
        self.x_track = self.x + self.width/2.0
        self.y1_track = self.y + self.height - self.y_margin
        self.y0_track = self.y + self.y_margin
        self.track_height = self.y1_track - self.y0_track
        self.circle_y_offset = 0.0
        
        self.label_element = pyglet.text.Label(self.label,
            x=self.x + self.width/2.0,
            y=self.y + self.height + self.y_margin/2.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.max_label_element = pyglet.text.Label(str(self.max_value),
            x=self.x + self.width/2.0,
            y=self.y + self.height - self.y_margin/2.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.min_label_element = pyglet.text.Label(str(self.min_value),
            x=self.x + self.width/2.0,
            y=self.y + self.y_margin/2.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.circle_element = Circle(self.x_track + self.circle_y_offset, self.y0_track, radius=4.0, parent=self)
        objects.append(self.circle_element)

        self.set_value(value)

    def set_value(self, value):
        value = max(self.min_value, min(value, self.max_value))
        fraction = (value - self.min_value) / (self.max_value - self.min_value)

        self.set_value_fraction(fraction)

    def set_value_fraction(self, fraction):        
        step_fraction = self.step_value / (self.max_value - self.min_value)
        fraction_divisor = fraction // step_fraction
        fraction_modulo = fraction % step_fraction        

        fraction = step_fraction * fraction_divisor
        if fraction_modulo >= step_fraction / 2.0:
            fraction += step_fraction

        self.fraction = fraction

        if self.callback:
            self.callback(self.get_value())
                
        self.update_slider_position()

    def get_value(self):
        return self.min_value + self.fraction * (self.max_value - self.min_value)

    def get_y_position(self, fraction):
        return self.y0_track + fraction * self.track_height

    def update_slider_position(self):
        self.circle_element.y = self.get_y_position(self.fraction) + self.circle_y_offset

    def event_drag_child(self, child, x, y):
        min_y, max_y = self.y0_track + self.circle_y_offset, self.y1_track + self.circle_y_offset

        if y < min_y:
            y = min_y
        elif y > max_y:
            y = max_y
                
        self.set_value_fraction((y - min_y) / (max_y - min_y))

    def drawable(self):
        return self.curve_types is None or curve_type in self.curve_types

    def draw(self):        
        glPushMatrix()
        glTranslatef(0.0, 0.0, 0.0)
        glColor4f(*NORMAL_COLOUR)
        glBegin(GL_LINES)
        # The border.
        glVertex2f(self.x, self.y)
        glVertex2f(self.x + self.width, self.y)
        glVertex2f(self.x + self.width, self.y)
        glVertex2f(self.x + self.width, self.y + self.height)
        glVertex2f(self.x + self.width, self.y + self.height)
        glVertex2f(self.x, self.y + self.height)
        glVertex2f(self.x, self.y + self.height)
        glVertex2f(self.x, self.y)        
        glEnd()        
        glColor4f(*BORDER_COLOUR)
        glBegin(GL_LINES)
        # The length of the track.
        glVertex2f(self.x_track, self.y0_track)
        glVertex2f(self.x_track, self.y1_track)
        # The slider notches.
        fraction = 0.0
        step_fraction = self.step_value / (self.max_value - self.min_value)
        while 1.0 - fraction > -1e-5:
            y = self.get_y_position(fraction)
            glVertex2f(self.x_track - 1.0, y)
            glVertex2f(self.x_track + 2.0, y)
            fraction += step_fraction
        glEnd()
        glPopMatrix()

        # Now draw the contained UI elements.
        self.label_element.draw()
        self.min_label_element.draw()
        self.max_label_element.draw()
        self.circle_element.draw()

    
objects = []
curve_points = []

window_width = None
window_height = None
window_display_x0 = None
window_display_x1 = None
window_point_distance = None
selected_ui_element = None
hermite_tension = 0
hermite_bias = 0


def create_label(x, y, **kwargs):
    ob = Label(x, y, **kwargs)
    objects.append(ob)
    return ob


def create_curve():
    # Create four outer points for the purpose of interpolation.
    for i in range(CURVE_POINTS):
        add_curve_point()

def add_curve_point(direction=1):
    y = CURVE_Y0 + random.random() * CURVE_HEIGHT
    point = Vector2D(0, y)
    if direction > 0:
        curve_points.append(point)
        if len(curve_points) > CURVE_POINTS:
            del curve_points[0]
    elif direction < 0:
        curve_points.insert(0, point)
        if len(curve_points) > CURVE_POINTS:
            del curve_points[-1]

def create_slider_box(x, y, **kwargs):
    ob = SliderBox(x, y, **kwargs) 
    objects.append(ob)
    return ob

def create_button(x, y, **kwargs):
    ob = Button(x, y, **kwargs)
    objects.append(ob)
    return ob

def find_ui_element(x, y):
    for ob in objects:
        if ob.within(x, y):
            return ob


def draw_line(pos0, pos1, colour=None):
    global colours_printed
    x0, y0 = pos0
    x1, y1 = pos1

    x0_after = x0 >= window_display_x0
    x1_after = x1 >= window_display_x0
    x0_before = x0 <= window_display_x1
    x1_before = x1 <= window_display_x1

    if not x1_after or not x0_before:
        return

    if abs(x1 - x0) > 1e-3:
        # Skip lines that are not within the display area.
        if not (x0_after or x1_before):
            return

        # Clip lines that cross out of the display area.        
        if not (x0_after and x1_before):
            if not x0_after:
                pos0 = xclip_far(pos1, pos0, window_display_x0)
            elif not x1_before:
                pos1 = xclip_far(pos0, pos1, window_display_x1)
                # print curve_type, Vector2D(x0, y0), Vector2D(x1, y1), "=>", pos0, pos1

    if colour:
        glColor4f(*colour)

    glBegin(GL_LINES)
    glVertex2f(*pos0)
    glVertex2f(*pos1)
    glEnd()


curve_scroll_seconds = INITIAL_CURVE_SCROLL_PERIOD
curve_scroll_direction = INITIAL_CURVE_SCROLL_DIRECTION
tick_ms = 0.0
tick_ps = 0
section_ms = 0.0
section_dt = 0.0
current_step = 0.0


def draw_lines(line_type):
    """
    TODO: Determine which points to interpolate between.

    There are X many points.
    Only Y of X points are wholly or partially displayed.

    global window_display_x0, window_display_x1
    """

    if len(curve_points) == 0:
        return

    step_fraction = current_step * CURVE_SUBDIVISION_FRACTION

    glColor4f(*NORMAL_COLOUR)

    if line_type == LINES_LINEAR:
        x_start = window_display_x0 - 1.0 * curve_section_width
        x_start -= curve_section_width * step_fraction
        for i in range(CURVE_SECTIONS):
            if i > 0:
                point0 = curve_points[i-1]
                point0.x = x_start
                point1 = curve_points[i-0]
                point1.x = x_start + curve_section_width
                draw_line(point0, point1)

                x_start += curve_section_width

    elif line_type in (LINES_SMOOTHSTEP, LINES_HERMITE):
        tension_value = tension_slider_box.get_value()
        bias_value = bias_slider_box.get_value()

        x_start = window_display_x0 - 1.0 * curve_section_width
        x_start -= curve_section_width * step_fraction
        for i in range(CURVE_SECTIONS):
            if i > 0:
                point0 = curve_points[i-1]
                point0.x = x_start
                y0 = point0.y
                p0 = point0
                point1 = curve_points[i-0]
                point1.x = x_start + curve_section_width
                x_start += curve_section_width
                
                if point1.x < window_display_x0 or point0.x > window_display_x1:
                    continue

                for j in range(CURVE_SECTION_SUBDIVISIONS):
                    x_fraction = j * CURVE_SUBDIVISION_FRACTION

                    x0 = point0.x + x_fraction * curve_section_width
                    x1 = x0 + CURVE_SUBDIVISION_FRACTION * curve_section_width

                    if line_type == LINES_SMOOTHSTEP:
                        y_fraction = smooth_step_interpolation(x_fraction + CURVE_SUBDIVISION_FRACTION)
                        y1 = (point1.y * y_fraction) + (point0.y * (1 - y_fraction))
                        draw_line(Vector2D(x0, y0), Vector2D(x1, y1))
                        y0 = y1
                    elif line_type == LINES_HERMITE:
                        mu = x_fraction + CURVE_SUBDIVISION_FRACTION
                        p1 = hermite_interpolation(
                            Vector2D(curve_points[i-2]),
                            Vector2D(curve_points[i-1]),
                            Vector2D(curve_points[i-0]),
                            Vector2D(curve_points[i+1]),
                            mu,
                            tension_value,
                            bias_value)
                        draw_line(p0, p1)
                        p0 = p1
        

def on_randomise_button_press(button):
    for curve_point in curve_points:
        curve_point.y = CURVE_Y0 + random.random() * CURVE_HEIGHT

def on_next_curve_type_button_press(button):
    global curve_type
    curve_type = (curve_type + 1) % NUM_LINE_TYPES
    set_curve_type(curve_type)

def set_curve_type(new_curve_type):
    curve_label.set_text("Curve: "+ line_labels[new_curve_type])

def set_curve_scroll_seconds(seconds):
    global section_ms, curve_scroll_seconds
    curve_scroll_seconds = seconds
    section_ms = seconds / (CURVE_SECTION_SUBDIVISIONS * CURVE_DISPLAY_SECTIONS)

def set_curve_scroll_direction(direction):
    global curve_scroll_direction
    curve_scroll_direction = direction

def set_tick_rate(value):
    global tick_ms, tick_ps
    tick_ps = 30
    tick_ms = 0.0 if value == 0 else 1.0 / value

    pyglet.clock.unschedule(tick)
    if abs(value) > 1e-5:
        pyglet.clock.schedule_interval(tick, tick_ms)


def tick(dt):
    global section_dt, current_step
    section_dt += dt * curve_scroll_direction
    current_step = math.floor(section_dt / section_ms)
    if current_step >= CURVE_SECTION_SUBDIVISIONS:
        current_step = 0.0
        section_dt = 0.0
        add_curve_point( 1)
    elif current_step < 0:
        current_step = CURVE_SECTION_SUBDIVISIONS
        section_dt = current_step * section_ms
        add_curve_point(-1)


def run():
    global window_width, window_height
    global tension_slider_box, bias_slider_box, curve_label
    global curve_type

    curve_type = INITIAL_CURVE_TYPE
    set_tick_rate(30)
    set_curve_scroll_seconds(INITIAL_CURVE_SCROLL_PERIOD)

    window = pyglet.window.Window()

    @window.event
    def on_draw():
        window.clear()
        
        draw_lines(curve_type)

        for ob in objects:
            if ob.drawable():
                ob.draw()

    @window.event
    def on_key_press(symbol, modifiers):
        if symbol == key.ESCAPE:
            pyglet.app.exit()

    @window.event
    def on_resize(width, height):
        global window_width, window_height, curve_section_width
        global window_display_x0, window_display_x1, window_display_width

        window_width = width
        window_height = height
        
        window_display_width = window_width - 2.0 * CURVE_X_MARGIN
        window_display_x0 = CURVE_X_MARGIN
        window_display_x1 = window_display_x0 + window_display_width
        curve_section_width = window_display_width / CURVE_DISPLAY_SECTIONS

    @window.event
    def on_mouse_press(x, y, button, modifiers):
        global selected_ui_element
        if button == mouse.LEFT:
            selected_ui_element = find_ui_element(x, y)
            if selected_ui_element:
                selected_ui_element.event_press(x, y)

    @window.event
    def on_mouse_release(x, y, button, modifiers):
        global selected_ui_element
        if button == mouse.LEFT:
            if selected_ui_element:
                selected_ui_element.event_release(x, y)
                selected_ui_element = None

    @window.event
    def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
        if selected_ui_element:
            selected_ui_element.event_drag(x, y)

    # on_resize() has not be called yet, so get the size manually.
    window_width, window_height = window.get_size()
    on_resize(window_width, window_height)
    
    create_curve()

    curve_label = create_label(
        window_width / 2.0,
        window_height - 10 - 5)

    BUTTON_WIDTH1 = Button.DEFAULT_WIDTH + 20
    BUTTON_WIDTH2 = Button.DEFAULT_WIDTH + 40
    button1_x = math.floor((window_width - (BUTTON_WIDTH1 + BUTTON_WIDTH2 + 5.0)) / 2.0)

    button1 = create_button(
        button1_x,
        5,
        width=BUTTON_WIDTH1,
        height=Button.DEFAULT_HEIGHT,
        label="Randomise",
        callback=on_randomise_button_press)

    button2 = create_button(
        button1.x + button1.width + 5.0,
        5,
        width=BUTTON_WIDTH2,
        height=Button.DEFAULT_HEIGHT,
        label="Change Curve Type",
        callback=on_next_curve_type_button_press)

    tension_slider_box = create_slider_box(
        5,
        5,
        label="Tension",
        min_value=-1.0, max_value=1.0, value=0.0, step_value=0.1,
        curve_types=(LINES_HERMITE,))

    bias_slider_box = create_slider_box(
        tension_slider_box.x,
        tension_slider_box.y + tension_slider_box.height + 25,
        label="Bias",
        min_value=-1.0, max_value=1.0, value=0.0, step_value=0.1,
        curve_types=(LINES_HERMITE,))

    curve_speed_slider_box = create_slider_box(
        window_width - SliderBox.DEFAULT_WIDTH - 5,
        5,
        label="Speed",
        min_value=1.0, max_value=5.0, value=3.0, step_value=0.25,
        callback=set_curve_scroll_seconds)

    curve_direction_slider_box = create_slider_box(
        window_width - SliderBox.DEFAULT_WIDTH - 5,
        curve_speed_slider_box.y + curve_speed_slider_box.height + 25,
        label="Direction",
        min_value=-1.0, max_value=1.0, value=1.0, step_value=1.0,
        callback=set_curve_scroll_direction)

    tick_ms_slider_box = create_slider_box(
        window_width - SliderBox.DEFAULT_WIDTH - 5,
        curve_direction_slider_box.y + curve_direction_slider_box.height + 25,
        label="Updates",
        min_value=0.0, max_value=60.0, value=tick_ps, step_value=5.0,
        callback=set_tick_rate)

    set_curve_type(curve_type)

    pyglet.clock.schedule_interval(tick, tick_ms)
    pyglet.app.run()

if __name__ == "__main__":
    run()
