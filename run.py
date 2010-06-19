"""
This script opens a Pyglet window, and then randomly places a number of
movable points which can be dragged up and down.  A Line is drawn between
the points, which may be either straight or curved.  UI elements like buttons
and sliders are placed which allow the curve type to be changed and the
way the curve is drawn to be varied.

Supported curve types:

  - Linear.
  - Smooth step.
  - Hermite.

This source code is in the public domain.
"""

import random, math, sys
import pyglet
from pyglet.window import key, mouse
from pyglet.gl import *


NUM_CURVE_SLIDERS = 6                   # How many draggable points there are.
NUM_SECTION_STEPS = 20                  # How many curve subdivisions between points.
SLIDER_RADIUS = 4                       # How big each draggable point is.

NORMAL_COLOUR = (1.0, 1.0, 1.0, 1.0)
BORDER_COLOUR = (0.7, 0.7, 0.7, 1.0)

NORMAL_DRAW_STYLE = GLU_FILL            # Draw style when not being dragged.
SELECTED_DRAW_STYLE = GLU_SILHOUETTE    # Draw style when being dragged.

NUM_LINE_TYPES = 3
LINES_LINEAR, LINES_SMOOTHSTEP, LINES_HERMITE = range(NUM_LINE_TYPES)

INITIAL_CURVE_TYPE = LINES_HERMITE

line_labels = {
    LINES_LINEAR: "Linear",
    LINES_SMOOTHSTEP: "Smooth Step",
    LINES_HERMITE: "Hermite",
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


class UIElement:
    x = 0
    y = 0
    width = 0
    height = 0

    def within(self, x, y):
        return x > self.x and x < self.x + self.width and y > self.y and y < self.y + self.height

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

        self.labelElement = pyglet.text.Label(self.label,
            x=self.x,
            y=self.y,
            font_size=8,
            anchor_x="center")

    def set_text(self, text):
        self.labelElement.text = text

    def draw(self):
        self.labelElement.draw()


class Circle(UIElement):
    def __init__(self, x, y, radius=10.0, colour=NORMAL_COLOUR, parent=None):
        self.x = x
        self.y = y
        self.radius = radius
        self.colour = colour
        self.quadric = gluNewQuadric()
        self.circleresolution = 60
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

        min_y, max_y = window_y_border, window_y_display + window_y_border

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
        gluDisk(self.quadric, 0, self.radius, self.circleresolution, 1)
        glPopMatrix()


class Button(UIElement):
    def __init__(self, x, y, width=80, height=20, label="Click", callback=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label

        self.labelElement = pyglet.text.Label(self.label,
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

        self.labelElement.draw()


class SliderBox(UIElement):
    def __init__(self, x, y, width=40, height=100, label="Slider", min_value=0.0, max_value=1.0, step_value=0.1, value=0.0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.min_value = min_value
        self.max_value = max_value
        self.step_value = step_value
        
        self.y_margin = 20.0
        self.x_track = self.x + self.width/2.0
        self.y1_track = self.y + self.height - self.y_margin
        self.y0_track = self.y + self.y_margin
        self.track_height = self.y1_track - self.y0_track
        self.circle_y_offset = 0.0
        
        self.labelElement = pyglet.text.Label(self.label,
            x=self.x + self.width/2.0,
            y=self.y + self.height + self.y_margin/2.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.maxLabelElement = pyglet.text.Label(str(self.max_value),
            x=self.x + self.width/2.0,
            y=self.y + self.height - self.y_margin/2.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.minLabelElement = pyglet.text.Label(str(self.min_value),
            x=self.x + self.width/2.0,
            y=self.y + self.y_margin/2.0,
            font_size=8, anchor_x="center", anchor_y="center")

        self.circleElement = Circle(self.x_track + self.circle_y_offset, self.y0_track, radius=4.0, parent=self)
        objects.append(self.circleElement)

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
                
        self.update_slider_position()

    def get_value(self):
        return self.min_value + self.fraction * (self.max_value - self.min_value)

    def get_y_position(self, fraction):
        return self.y0_track + fraction * self.track_height

    def update_slider_position(self):
        self.circleElement.y = self.get_y_position(self.fraction) + self.circle_y_offset

    def event_drag_child(self, child, x, y):
        min_y, max_y = self.y0_track + self.circle_y_offset, self.y1_track + self.circle_y_offset

        if y < min_y:
            y = min_y
        elif y > max_y:
            y = max_y
                
        self.set_value_fraction((y - min_y) / (max_y - min_y))

    def drawable(self):
        return curve_type == LINES_HERMITE

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
        self.labelElement.draw()
        self.minLabelElement.draw()
        self.maxLabelElement.draw()
        self.circleElement.draw()

    
objects = []
curve_sliders = []
window_width = None
window_height = None
window_y_border = 60.0
window_y_display = None
selected_ui_element = None
hermite_tension = 0
hermite_bias = 0


def create_label(x, y, **kwargs):
    ob = Label(x, y, **kwargs)
    objects.append(ob)
    return ob

def create_curve_sliders():
    curve_sliderOffset = window_width / (NUM_CURVE_SLIDERS + 1)

    for i in range(NUM_CURVE_SLIDERS):
        x = (i+1) * curve_sliderOffset
        y = window_height - window_y_border - random.random() * window_y_display
        circle = Circle(x, y, SLIDER_RADIUS)
        curve_sliders.append(circle)

    objects.extend(curve_sliders)

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

def draw_line(startPosition, endPosition):
    glBegin(GL_LINES)
    glVertex2f(*startPosition)
    glVertex2f(*endPosition)
    glEnd()



def draw_lines(lineType):
    glColor4f(*NORMAL_COLOUR)

    if lineType == LINES_LINEAR:
        last_curve_slider = curve_sliders[0]
        for i in range(NUM_CURVE_SLIDERS):
            curve_slider = curve_sliders[i]
            if curve_slider is last_curve_slider:
                continue
            draw_line((last_curve_slider.x, last_curve_slider.y), (curve_slider.x, curve_slider.y))
            last_curve_slider = curve_slider

    elif lineType in (LINES_SMOOTHSTEP, LINES_HERMITE):
        last_curve_slider = curve_sliders[0]
        y0 = last_curve_slider.y
        p0 = Vector2D(last_curve_slider)
        stepFraction = 1.0 / NUM_SECTION_STEPS
        
        tension_value = tension_slider_box.get_value()
        bias_value = bias_slider_box.get_value()
        
        for i in range(1, NUM_CURVE_SLIDERS):
            curve_slider = curve_sliders[i]
            xStart = last_curve_slider.x
            xEnd = curve_slider.x
            xWidth = xEnd - xStart
            for j in range(NUM_SECTION_STEPS):
                xFraction = j * stepFraction
                x0 = xStart + xFraction * xWidth
                x1 = x0 + (stepFraction * xWidth)
                if lineType == LINES_SMOOTHSTEP:
                    mu = xFraction + stepFraction
                    yScalar = smooth_step_interpolation(mu)
                    y1 = (curve_slider.y * yScalar) + (last_curve_slider.y * (1 - yScalar))
                    draw_line((x0, y0), (x1, y1))
                    y0 = y1
                elif lineType == LINES_HERMITE:
                    mu = xFraction + stepFraction
                    p1 = hermite_interpolation(
                        Vector2D(curve_sliders[max(i-2, 0)]),
                        Vector2D(curve_sliders[max(i-1, 0)]),
                        Vector2D(curve_sliders[i]),
                        Vector2D(curve_sliders[min(i+1, NUM_CURVE_SLIDERS-1)]),
                        mu,
                        tension_value,
                        bias_value)
                    draw_line((p0.x, p0.y), (p1.x, p1.y))
                    p0 = p1
            last_curve_slider = curve_slider


def on_reset_button_press(button):
    for curve_slider in curve_sliders:
        curve_slider.y = window_height - window_y_border - random.random() * window_y_display

def on_next_curve_type_button_press(button):
    global curve_type
    curve_type = (curve_type + 1) % NUM_LINE_TYPES
    set_curve_type(curve_type)

def set_curve_type(new_curve_type):
    curve_label.set_text("Curve: "+ line_labels[new_curve_type])



def run():
    global window_width, window_height
    global tension_slider_box, bias_slider_box, curve_label
    global curve_type

    curve_type = INITIAL_CURVE_TYPE

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
        global window_width, window_height, window_y_display
        
        window_width = width
        window_height = height
        
        window_y_display = window_height - (window_y_border * 2.0)

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
    
    create_curve_sliders()
    curve_label = create_label(window_width / 2.0, window_height - 10 - 5)
    button1 = create_button(window_width - 100 - 5, 5, width=100, height=20, label="Randomise", callback=on_reset_button_press)
    button2 = create_button(button1.x - 120 - 5, 5, width=120, height=20, label="Change Curve Type", callback=on_next_curve_type_button_press)
    tension_slider_box = create_slider_box(5, 5, label="Tension", min_value=-1.0, max_value=1.0, value=0.0, step_value=0.1)
    bias_slider_box = create_slider_box(5, 135, label="Bias", min_value=-1.0, max_value=1.0, value=0.0, step_value=0.1)
    set_curve_type(curve_type)

    def tick(dt):
        pass

    pyglet.clock.schedule_interval(tick, 1/60.0)  
    pyglet.app.run()

if __name__ == "__main__":
    run()
