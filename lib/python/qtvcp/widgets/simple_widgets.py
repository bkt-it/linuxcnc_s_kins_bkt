#!/usr/bin/env python
# qtVcp simple widgets
#
# Copyright (c) 2017  Chris Morley <chrisinnanaimo@hotmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

from PyQt5 import QtCore, QtGui, QtWidgets
from qtvcp.widgets.widget_baseclass import _HalWidgetBase, _HalToggleBase, _HalSensitiveBase
from qtvcp.lib.aux_program_loader import Aux_program_loader as _loader
from qtvcp.core import Action, Status
from functools import partial
import hal

AUX_PRGM = _loader()
ACTION = Action()
STATUS = Status()

# Set up logging
from qtvcp import logger
LOG = logger.getLogger(__name__)


# reacts to HAL pin changes
class LCDNumber(QtWidgets.QLCDNumber, _HalWidgetBase):
    def __init__(self, parent=None):
        super(LCDNumber, self).__init__(parent)

    def _hal_init(self):
        self.hal_pin = self.HAL_GCOMP_.newpin(self.HAL_NAME_, hal.HAL_FLOAT, hal.HAL_IN)
        self.hal_pin.value_changed.connect(lambda data: self.l_update(data))

    def l_update(self, data):
        self.display(data)


class CheckBox(QtWidgets.QCheckBox, _HalToggleBase):
    def __init__(self, parent=None):
        super(CheckBox, self).__init__(parent)


class RadioButton(QtWidgets.QRadioButton, _HalToggleBase):
    def __init__(self, parent=None):
        super(RadioButton, self).__init__(parent)


class Slider(QtWidgets.QSlider, _HalWidgetBase):
    def __init__(self, parent=None):
        super(Slider, self).__init__(parent)

    def _hal_init(self):
        self.hal_pin_s = self.HAL_GCOMP_.newpin(str(self.HAL_NAME_+'-s'), hal.HAL_S32, hal.HAL_OUT)
        self.hal_pin_f = self.HAL_GCOMP_.newpin(self.HAL_NAME_+'-f', hal.HAL_FLOAT, hal.HAL_OUT)
        self.hal_pin_scale = self.HAL_GCOMP_.newpin(self.HAL_NAME_+'-scale', hal.HAL_FLOAT, hal.HAL_IN)
        self.hal_pin_scale.set(1)
        def _f(data):
            scale = self.hal_pin_scale.get()
            self.hal_pin_s.set(data)
            self.hal_pin_f.set(data*scale)
        self.valueChanged.connect(partial(_f))

class Dial(QtWidgets.QDial, _HalWidgetBase):
    def __init__(self, parent=None):
        super(Dial, self).__init__(parent)
        self._lastRawCount = 0
        self._currentTotalCount = 0
        self._deltaScaled  = 0
        self.epiLow = int(self.maximum() * .25)
        self.epiHigh = self.maximum() - self.epiLow
        self.scale = 1

    def _hal_init(self):
        self.hal_pin_s = self.HAL_GCOMP_.newpin(str(self.HAL_NAME_+'-s'), hal.HAL_S32, hal.HAL_OUT)
        self.hal_pin_f = self.HAL_GCOMP_.newpin(self.HAL_NAME_+'-f', hal.HAL_FLOAT, hal.HAL_OUT)
        self.hal_pin_d = self.HAL_GCOMP_.newpin(self.HAL_NAME_+'-d', hal.HAL_FLOAT, hal.HAL_OUT)
        self.hal_pin_scale = self.HAL_GCOMP_.newpin(self.HAL_NAME_+'-scale', hal.HAL_FLOAT, hal.HAL_IN)
        self.hal_pin_scale.value_changed.connect(lambda data: self.updateScale(data))
        self.hal_pin_scale.set(1)
        self.valueChanged.connect(lambda data:self.updateCount(data))

    def updateScale(self, data):
        self.scale = data
        self.hal_pin_f.set(self._currentTotalCount * data)

    def updateCount(self, count):
        if count == self.maximum(): count = 0

        delta = self._lastRawCount - count
        #print 'last:',self._lastRawCount ,'raw count',count,'delta',delta,'count:',count
        if self._lastRawCount > self.epiHigh and count < self.epiLow  :
                change = self.maximum() - self._lastRawCount + count
                self._currentTotalCount += change
                self._deltaScaled += change * self.scale
        elif count > self.epiHigh and self._lastRawCount < self.epiLow  :
                change = self.maximum() - count + self._lastRawCount
                self._currentTotalCount -= change
                self._deltaScaled -= change * self.scale
        else:
                self._currentTotalCount -= delta
                self._deltaScaled -= delta * self.scale


        self._lastRawCount = count
        self.hal_pin_s.set(self._currentTotalCount)
        self.hal_pin_f.set(self._currentTotalCount * self.scale)
        self.hal_pin_d.set(self._deltaScaled)

class GridLayout(QtWidgets.QWidget, _HalSensitiveBase):
    def __init__(self, parent=None):
        super(GridLayout, self).__init__(parent)


class RichButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super(RichButton, self).__init__(parent)
        self._text = self.text()

        self._label = QtWidgets.QLabel(self._text, self)
        self._label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents )
        self._label.setAlignment(QtCore.Qt.AlignCenter|QtCore.Qt.AlignVCenter)
        self._label.show()

    def setText(self, text):
        self._label.setText(text)

    def text(self):
        try:
            return self._label.text()
        except:
            pass

    def event(self, event):
        if event.type() ==  QtCore.QEvent.Resize:
            w = QtGui.QResizeEvent.size(event)
            try:
                self._label.resize(w.width(), w.height())
                self.resize(w.width(), w.height())
            except:
                pass
            return True
        else:
            return super(RichButton, self).event( event)

    def set_richText(self, data):
        self.setText(data)
    def get_richText(self):
        return self.text()
    def reset_richText(self):
        self.setText('Button')
    richtext_string = QtCore.pyqtProperty(str, get_richText, set_richText, reset_richText)

# LED indicator on the right corner
class Indicated_PushButton(QtWidgets.QPushButton, _HalWidgetBase):
    def __init__(self, parent=None):
        super(Indicated_PushButton, self).__init__(parent)
        self._indicator_state = False # Current State

        # changing text data
        self._state_text = False # use text
        self._true_string = 'True'
        self._false_string = 'False'

        # python commands data
        self._python_command = False # use commands
        self.true_python_command = '''print"true command"'''
        self.false_python_command = '''print"false command"'''

        # indicator LED data
        self.draw_indicator = False # Show LED
        self._HAL_pin = False # control by HAL
        self._shape = 0 # 0 triangle, 1 circle
        self._size = .3 # triangle
        self._diameter = 10 # circle
        self._corner_radius = 5
        self._h_fraction = .3
        self._w_fraction = .9
        self._right_edge_offset = 0
        self._top_edge_offset = 0
        self._on_color = QtGui.QColor("red")
        self._off_color = QtGui.QColor("black")

        # indicator linuxcnc's status options
        self._ind_status = False # control by status
        self._is_estopped = False
        self._is_on = False
        self._is_homed = False
        self._is_idle = False
        self._is_paused = False
        self._invert_status = False
        self._is_flood = False
        self._is_mist = False
        self._is_block_delete = False
        self._is_optional_stop = False
        self._is_joint_homed = False
        self._is_limits_overridden = False
        self._is_manual = False
        self._is_mdi = False
        self._is_auto = False
        self._is_spindle_stopped = False
        self._is_spindle_fwd = False
        self._is_spindle_rev = False
        self._joint_number = 0

    # Override setText function so we can toggle displayed text
    def setText(self, text):
        if not self._state_text:
            super(Indicated_PushButton, self).setText(text)
            return
        if self.isCheckable():
            if self.isChecked():
                super(Indicated_PushButton, self).setText(self._true_string)
            else:
                super(Indicated_PushButton, self).setText(self._false_string)
        elif self._indicator_state:
            super(Indicated_PushButton, self).setText(self._true_string)
        else:
            super(Indicated_PushButton, self).setText(self._false_string)

    def _hal_init(self):
        if self._HAL_pin:
            self.hal_pin_led = self.HAL_GCOMP_.newpin(self.HAL_NAME_ + '-led', hal.HAL_BIT, hal.HAL_IN)
            self.hal_pin_led.value_changed.connect(lambda data: self.indicator_update(data))
        elif self._ind_status:
            self._init_state_change()
        self._globalParameter = {'__builtins__' : None, 'INSTANCE':self.QTVCP_INSTANCE_,
                                 'PROGRAM_LOADER':AUX_PRGM, 'ACTION':ACTION}
        self._localsParameter = {'dir': dir}

    def _init_state_change(self):
        def only_false(data):
            if data:
                return
            self._flip_state(False)

        if self._is_estopped:
            STATUS.connect('state-estop', lambda w: self._flip_state(True))
            STATUS.connect('state-estop-reset', lambda w: self._flip_state(False))
        elif self._is_on:
            STATUS.connect('state-on', lambda w: self._flip_state(True))
            STATUS.connect('state-off', lambda w: self._flip_state(False))
        elif self._is_homed:
            STATUS.connect('all-homed', lambda w: self._flip_state(True))
            STATUS.connect('not-all-homed', lambda w, axis: self._flip_state(False))
        elif self._is_idle:
            STATUS.connect('interp-idle', lambda w: self._flip_state(True))
            STATUS.connect('interp-run', lambda w: self._flip_state(False))
        elif self._is_paused:
            STATUS.connect('program-pause-changed', lambda w, data: self._flip_state(data))
        elif self._is_flood:
            STATUS.connect('flood-changed', lambda w, data: self._flip_state(data))
        elif self._is_mist:
            STATUS.connect('mist-changed', lambda w, data: self._flip_state(data))
        elif self._is_block_delete:
            STATUS.connect('block-delete-changed', lambda w, data: self._flip_state(data))
        elif self._is_optional_stop:
            STATUS.connect('optional-stop-changed', lambda w, data: self._flip_state(data))
        elif self._is_joint_homed:
            STATUS.connect('homed', lambda w, data: self._j_homed(data))
            STATUS.connect('not-all-homed', lambda w, data: self._j_unhomed(data))
        elif self._is_limits_overridden:
            STATUS.connect('override-limits-changed', self._check_override_limits)
            STATUS.connect('hard-limits-tripped', lambda w, data: only_false(data))
        elif self._is_manual or self._is_mdi or self._is_auto:
            STATUS.connect('mode-manual', lambda w: self._mode_changed(0))
            STATUS.connect('mode-mdi', lambda w: self._mode_changed(1))
            STATUS.connect('mode-auto', lambda w: self._mode_changed(2))
        elif self._is_spindle_stopped or self._is_spindle_fwd or self._is_spindle_rev:
            STATUS.connect('spindle-control-changed',  lambda w, state, speed: self._spindle_changed(speed))

    def _flip_state(self, data):
            if self._invert_status:
                data = not data
            self.indicator_update(data)

    def _j_homed(self, joint):
        if int(joint) == self._joint_number:
            self._flip_state(True)

    def _j_unhomed(self, jlist):
        if str(self._joint_number) in jlist:
            self._flip_state(False)

    def _check_override_limits(self, w, state, data):
        for i in data:
            if i == 1:
                self._flip_state(True)
                return
        self._flip_state(False)

    def _mode_changed(self, mode):
        if self._is_manual and mode == 0:
            self._flip_state(True)
        elif self._is_mdi and mode == 1:
            self._flip_state(True)
        elif self._is_auto and mode == 2:
            self._flip_state(True)
        else:
            self._flip_state(False)

    def _spindle_changed(self, state):
        if self._is_spindle_stopped and state == 0:
            self._flip_state(True)
        elif self._is_spindle_rev and state < 0:
            self._flip_state(True)
        elif self._is_spindle_fwd and state > 0:
            self._flip_state(True)
        else:
            self._flip_state(False)

    # arbitraray python commands are possible using 'INSTANCE' in the string
    # gives acess to widgets and handler functions 
    def python_command(self, state = None):
        if self._python_command:
            if state:
                exec(self.true_python_command, self._globalParameter, self._localsParameter)
            else:
                exec(self.false_python_command, self._globalParameter, self._localsParameter)

    # callback to toggle text when button is toggled
    def toggle_text(self, state=None):
        if not self._state_text:
            return
        else:
            self.setText(None)

    def indicator_update(self, data):
        self._indicator_state = data
        self.update()

    # override paint function to first paint the stock button
    # then our indicator paint routine
    def paintEvent(self, event):
        super(Indicated_PushButton, self).paintEvent(event)
        if self.draw_indicator:
            self.paintIndicator()

    # Paint specified size a triangle at the top right
    def paintIndicator(self):
            p = QtGui.QPainter(self)

            if self._indicator_state:
                color = self._on_color
            else:
                color = self._off_color

            # triangle
            if self._shape == 0:
                rect = p.window()
                top_right = rect.topRight() - QtCore.QPoint(self._right_edge_offset,-self._top_edge_offset)
                if self.width() < self.height():
                    size = self.width() * self._size
                else:
                    size = self.height() * self._size

                gradient = QtGui.QLinearGradient(top_right- QtCore.QPoint(size, 0), top_right)
                gradient.setColorAt(0, QtCore.Qt.white)
                gradient.setColorAt(1, color)
                p.setBrush(QtGui.QBrush(gradient))
                p.setPen(color)

                triangle = QtGui.QPolygon([top_right, top_right - QtCore.QPoint(size, 0),
                                       top_right + QtCore.QPoint(0, size)])
                p.drawLine(triangle.point(1), triangle.point(2))
                p.drawPolygon(triangle)

            # circle
            elif self._shape == 1:
                x = self.width() - self._diameter - self._right_edge_offset
                y = 0 + self._top_edge_offset
                gradient = QtGui.QRadialGradient(x + self._diameter / 2, y + self._diameter / 2,
                                   self._diameter * 0.4, self._diameter * 0.4, self._diameter * 0.4)
                gradient.setColorAt(0, QtCore.Qt.white)
                gradient.setColorAt(1, color)
                p.setBrush(QtGui.QBrush(gradient))
                p.setPen(color)
                p.setRenderHint(QtGui.QPainter.Antialiasing, True)
                p.drawEllipse(x, y, self._diameter - 1, self._diameter - 1)

            # top bar
            elif self._shape == 2:
                rect = p.window()
                topLeft = rect.topLeft()
                #p.setPen(color)
                #p.setBrush(QtGui.QBrush(color, QtCore.Qt.SolidPattern))
                grad = QtGui.QLinearGradient()
                grad.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
                grad.setStart(0,0)
                grad.setFinalStop(0,.8)
                grad.setColorAt(0, color)
                grad.setColorAt(.5, QtCore.Qt.white)
                grad.setColorAt(.8, color)
                p.setBrush(QtGui.QBrush(grad))
                p.drawRoundedRect(topLeft.x()+(self.width()*((1-self._w_fraction)/2)) + self._top_edge_offset,
                                    topLeft.y()+self._right_edge_offset,
                                    self.width()*self._w_fraction+2,
                                    self.height()*self._h_fraction,
                                    self._corner_radius, self._corner_radius)


            # side bar
            elif self._shape == 3:
                rect = p.window()
                topRight = rect.topRight()
                #p.setPen(color)
                #p.setBrush(QtGui.QBrush(color, QtCore.Qt.SolidPattern))
                grad = QtGui.QLinearGradient()
                grad.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
                grad.setStart(0,0)
                grad.setFinalStop(0,.8)
                grad.setColorAt(0, color)
                grad.setColorAt(.5, QtCore.Qt.white)
                grad.setColorAt(.8, color)
                p.setBrush(QtGui.QBrush(grad))
                p.drawRoundedRect(topRight.x()- self.width()*self._w_fraction-self._right_edge_offset,
                                    topRight.y()+(self.height()*((1-self._h_fraction)/2)) + self._top_edge_offset,
                                    self.width()*self._w_fraction,
                                    self.height()*self._h_fraction,
                                    self._corner_radius, self._corner_radius)

    def set_indicator(self, data):
        self.draw_indicator = data
        self.update()
    def get_indicator(self):
        return self.draw_indicator
    def reset_indicator(self):
        self.draw_indicator = False

    def set_shape(self, data):
        self._shape = data
        self.update()
    def get_shape(self):
        return self._shape
    def reset_shape(self):
        self._shape = 0

    def set_HAL_pin(self, data):
        self._HAL_pin = data
        if data:
            self._ind_status = False
    def get_HAL_pin(self):
        return self._HAL_pin
    def reset_HAL_pin(self):
        self._HAL_pin = False

    def set_ind_status(self, data):
        self._ind_status = data
        if data:
            self._HAL_pin = False
    def get_ind_status(self):
        return self._ind_status
    def reset_ind_status(self):
        self._ind_status = False

    def set_state_text(self, data):
        self._state_text = data
        if data:
            self.setText(None)
    def get_state_text(self):
        return self._state_text
    def reset_state_text(self):
        self._state_text = False

    def set_python_command(self, data):
        self._python_command = data
    def get_python_command(self):
        return self._python_command
    def reset_python_command(self):
        self._python_command = False

    def get_on_color(self):
        return self._on_color
    def set_on_color(self, value):
        self._on_color = value
        self.update()
    def get_off_color(self):
        return self._off_color
    def set_off_color(self, value):
        self._off_color = value
        self.update()

    def set_indicator_size(self, data):
        self._size = data
        self.update()
    def get_indicator_size(self):
        return self._size
    def reset_indicator_size(self):
        self._size = 0.3
        self.update()

    def set_circle_diameter(self, data):
        self._diameter = data
        self.update()
    def get_circle_diameter(self):
        return self._diameter
    def reset_circle_diameter(self):
        self._diameter = 10
        self.update()

    def set_corner_radius(self, data):
        self._corner_radius = data
        self.update()
    def get_corner_radius(self):
        return self._corner_radius
    def reset_corner_radius(self):
        self._corner_radius = 5
        self.update()

    def set_h_fraction(self, data):
        self._h_fraction = data
        self.update()
    def get_h_fraction(self):
        return self._h_fraction
    def reset_h_fraction(self):
        self._h_fraction = .5
        self.update()

    def set_w_fraction(self, data):
        self._w_fraction = data
        self.update()
    def get_w_fraction(self):
        return self._w_fraction
    def reset_w_fraction(self):
        self._w_fraction = .5
        self.update()

    def set_right_edge_offset(self, data):
        self._right_edge_offset = data
        self.update()
    def get_right_edge_offset(self):
        return self._right_edge_offset
    def reset_right_edge_offset(self):
        self._right_edge_offset = 0
        self.update()

    def set_top_edge_offset(self, data):
        self._top_edge_offset = data
        self.update()
    def get_top_edge_offset(self):
        return self._top_edge_offset
    def reset_top_edge_offset(self):
        self._top_edge_offset = 0
        self.update()

    def set_true_string(self, data):
        data = data.replace('\\n' , '\n')
        self._true_string = data
        if self._state_text:
            self.setText(None)
    def get_true_string(self):
        return self._true_string
    def reset_true_string(self):
        self._true_string = 'False'

    def set_false_string(self, data):
        data = data.replace('\\n' , '\n')
        self._false_string = data
        if self._state_text:
            self.setText(None)
    def get_false_string(self):
        return self._false_string
    def reset_false_string(self):
        self._false_string = 'False'

    def set_true_python_command(self, data):
        self.true_python_command = data
    def get_true_python_command(self):
        return self.true_python_command
    def reset_true_python_command(self):
        self.true_python_command = ''

    def set_false_python_command(self, data):
        self.false_python_command = data
    def get_false_python_command(self):
        return self.false_python_command
    def reset_false_python_command(self):
        self.false_python_command = ''

    indicator_option = QtCore.pyqtProperty(bool, get_indicator, set_indicator, reset_indicator)
    indicator_HAL_pin_option = QtCore.pyqtProperty(bool, get_HAL_pin, set_HAL_pin, reset_HAL_pin)
    indicator_status_option = QtCore.pyqtProperty(bool, get_ind_status, set_ind_status, reset_ind_status)
    checked_state_text_option = QtCore.pyqtProperty(bool, get_state_text, set_state_text, reset_state_text)
    python_command_option = QtCore.pyqtProperty(bool, get_python_command, set_python_command, reset_python_command)
    on_color = QtCore.pyqtProperty(QtGui.QColor, get_on_color, set_on_color)
    shape_option = QtCore.pyqtProperty(int, get_shape, set_shape, reset_shape)
    off_color = QtCore.pyqtProperty(QtGui.QColor, get_off_color, set_off_color)
    indicator_size = QtCore.pyqtProperty(float, get_indicator_size, set_indicator_size, reset_indicator_size)
    circle_diameter = QtCore.pyqtProperty(float, get_circle_diameter, set_circle_diameter, reset_circle_diameter)
    right_edge_offset = QtCore.pyqtProperty(float, get_right_edge_offset, set_right_edge_offset, reset_right_edge_offset)
    top_edge_offset = QtCore.pyqtProperty(float, get_top_edge_offset, set_top_edge_offset, reset_top_edge_offset)
    corner_radius = QtCore.pyqtProperty(float, get_corner_radius, set_corner_radius, reset_corner_radius)
    height_fraction = QtCore.pyqtProperty(float, get_h_fraction, set_h_fraction, reset_h_fraction)
    width_fraction = QtCore.pyqtProperty(float, get_w_fraction, set_w_fraction, reset_w_fraction)
    true_state_string = QtCore.pyqtProperty(str, get_true_string, set_true_string, reset_true_string)
    false_state_string = QtCore.pyqtProperty(str, get_false_string, set_false_string, reset_false_string)
    true_python_cmd_string = QtCore.pyqtProperty(str, get_true_python_command, set_true_python_command, reset_true_python_command)
    false_python_cmd_string = QtCore.pyqtProperty(str, get_false_python_command, set_false_python_command, reset_false_python_command)


    #########################################################################
    # This is how designer can interact with our widget properties.
    # designer will show the QtCore.pyqtProperty properties in the editor
    # it will use the get set and reset calls to do those actions
    #
    # _toggle_status_properties makes it so we can only select one option
    ########################################################################

    def _toggle_status_properties(self, picked):
        data = ('is_paused', 'is_estopped', 'is_on', 'is_idle', 'is_homed',
                'is_flood', 'is_mist', 'is_block_delete', 'is_optional_stop',
                'is_joint_homed', 'is_limits_overridden','is_manual',
                'is_mdi', 'is_auto', 'is_spindle_stopped', 'is_spindle_fwd',
                'is_spindle_rev')

        for i in data:
            if not i == picked:
                self[i+'_status'] = False

# property getter/setters

    # invert status
    def set_invert_status(self, data):
        self._invert_status = data
    def get_invert_status(self):
        return self._invert_status
    def reset_invert_status(self):
        self._invert_status = False

    # machine is paused status
    def set_is_paused(self, data):
        self._is_paused = data
        if data:
            self._toggle_status_properties('is_paused')
    def get_is_paused(self):
        return self._is_paused
    def reset_is_paused(self):
        self._is_paused = False

    # machine is estopped status
    def set_is_estopped(self, data):
        self._is_estopped = data
        if data:
            self._toggle_status_properties('is_estopped')
    def get_is_estopped(self):
        return self._is_estopped
    def reset_is_estopped(self):
        self._is_estopped = False

    # machine is on status
    def set_is_on(self, data):
        self._is_on = data
        if data:
            self._toggle_status_properties('is_on')
    def get_is_on(self):
        return self._is_on
    def reset_is_on(self):
        self._is_on = False

    # machine is idle status
    def set_is_idle(self, data):
        self._is_idle = data
        if data:
            self._toggle_status_properties('is_idle')
    def get_is_idle(self):
        return self._is_idle
    def reset_is_idle(self):
        self._is_idle = False

    # machine_is_homed status
    def set_is_homed(self, data):
        self._is_homed = data
        if data:
            self._toggle_status_properties('is_homed')
    def get_is_homed(self):
        return self._is_homed
    def reset_is_homed(self):
        self._is_homed = False

    # machine is_flood status
    def set_is_flood(self, data):
        self._is_flood = data
        if data:
            self._toggle_status_properties('is_flood')
    def get_is_flood(self):
        return self._is_flood
    def reset_is_flood(self):
        self._is_flood = False

    # machine is_mist status
    def set_is_mist(self, data):
        self._is_mist = data
        if data:
            self._toggle_status_properties('is_mist')
    def get_is_mist(self):
        return self._is_mist
    def reset_is_mist(self):
        self._is_mist = False

    # machine_is_block_delete status
    def set_is_block_delete(self, data):
        self._is_block_delete = data
        if data:
            self._toggle_status_properties('is_block_delete')
    def get_is_block_delete(self):
        return self._is_block_delete
    def reset_is_block_delete(self):
        self._is_block_delete = False

    # machine_is_optional_stop status
    def set_is_optional_stop(self, data):
        self._is_optional_stop = data
        if data:
            self._toggle_status_properties('is_optional_stop')
    def get_is_optional_stop(self):
        return self._is_optional_stop
    def reset_is_optional_stop(self):
        self._is_optional_stop = False

    # machine_is_joint_homed status
    def set_is_joint_homed(self, data):
        self._is_joint_homed = data
        if data:
            self._toggle_status_properties('is_joint_homed')
    def get_is_joint_homed(self):
        return self._is_joint_homed
    def reset_is_joint_homed(self):
        self._is_joint_homed = False

    # machine_is_limits_overridden status
    def set_is_limits_overridden(self, data):
        self._is_limits_overridden = data
        if data:
            self._toggle_status_properties('is_limits_overridden')
    def get_is_limits_overridden(self):
        return self._is_limits_overridden
    def reset_is_limits_overridden(self):
        self._is_limits_overridden = False

    # machine is manual status
    def set_is_manual(self, data):
        self._is_manual = data
        if data:
            self._toggle_status_properties('is_manual')
    def get_is_manual(self):
        return self._is_manual
    def reset_is_manual(self):
        self._is_manual = False

    # machine is mdi status
    def set_is_mdi(self, data):
        self._is_mdi = data
        if data:
            self._toggle_status_properties('is_mdi')
    def get_is_mdi(self):
        return self._is_mdi
    def reset_is_mdi(self):
        self._is_mdi = False

    # machine is auto status
    def set_is_auto(self, data):
        self._is_auto = data
        if data:
            self._toggle_status_properties('is_auto')
    def get_is_auto(self):
        return self._is_auto
    def reset_is_auto(self):
        self._is_auto = False

    # machine is spindle_stopped status
    def set_is_spindle_stopped(self, data):
        self._is_spindle_stopped = data
        if data:
            self._toggle_status_properties('is_spindle_stopped')
    def get_is_spindle_stopped(self):
        return self._is_spindle_stopped
    def reset_is_spindle_stopped(self):
        self._is_spindle_stopped = False

    # machine is spindle_fwd status
    def set_is_spindle_fwd(self, data):
        self._is_spindle_fwd = data
        if data:
            self._toggle_status_properties('is_spindle_fwd')
    def get_is_spindle_fwd(self):
        return self._is_spindle_fwd
    def reset_is_spindle_fwd(self):
        self._is_spindle_fwd = False

    # machine is spindle_rev status
    def set_is_spindle_rev(self, data):
        self._is_spindle_rev = data
        if data:
            self._toggle_status_properties('is_spindle_rev')
    def get_is_spindle_rev(self):
        return self._is_spindle_rev
    def reset_is_spindle_rev(self):
        self._is_spindle_rev = False

    # Non bool

    # machine_joint_number status
    def set_joint_number(self, data):
        self._joint_number = data
    def get_joint_number(self):
        return self._joint_number
    def reset_joint_number(self):
        self._joint_number = 0

    # designer will show these properties in this order:
    # BOOL
    invert_the_status = QtCore.pyqtProperty(bool, get_invert_status, set_invert_status, reset_invert_status)
    is_paused_status = QtCore.pyqtProperty(bool, get_is_paused, set_is_paused, reset_is_paused)
    is_estopped_status = QtCore.pyqtProperty(bool, get_is_estopped, set_is_estopped, reset_is_estopped)
    is_on_status = QtCore.pyqtProperty(bool, get_is_on, set_is_on, reset_is_on)
    is_idle_status = QtCore.pyqtProperty(bool, get_is_idle, set_is_idle, reset_is_idle)
    is_homed_status = QtCore.pyqtProperty(bool, get_is_homed, set_is_homed, reset_is_homed)
    is_flood_status = QtCore.pyqtProperty(bool, get_is_flood, set_is_flood, reset_is_flood)
    is_mist_status = QtCore.pyqtProperty(bool, get_is_mist, set_is_mist, reset_is_mist)
    is_block_delete_status = QtCore.pyqtProperty(bool, get_is_block_delete, set_is_block_delete, reset_is_block_delete)
    is_optional_stop_status = QtCore.pyqtProperty(bool, get_is_optional_stop, set_is_optional_stop, reset_is_optional_stop)
    is_joint_homed_status = QtCore.pyqtProperty(bool, get_is_joint_homed, set_is_joint_homed, reset_is_joint_homed)
    is_limits_overridden_status = QtCore.pyqtProperty(bool, get_is_limits_overridden, set_is_limits_overridden,
                                               reset_is_limits_overridden)
    is_manual_status = QtCore.pyqtProperty(bool, get_is_manual, set_is_manual, reset_is_manual)
    is_mdi_status = QtCore.pyqtProperty(bool, get_is_mdi, set_is_mdi, reset_is_mdi)
    is_auto_status = QtCore.pyqtProperty(bool, get_is_auto, set_is_auto, reset_is_auto)
    is_spindle_stopped_status = QtCore.pyqtProperty(bool, get_is_spindle_stopped, set_is_spindle_stopped, reset_is_spindle_stopped)
    is_spindle_fwd_status = QtCore.pyqtProperty(bool, get_is_spindle_fwd, set_is_spindle_fwd, reset_is_spindle_fwd)
    is_spindle_rev_status = QtCore.pyqtProperty(bool, get_is_spindle_rev, set_is_spindle_rev, reset_is_spindle_rev)

    # NON BOOL
    joint_number_status = QtCore.pyqtProperty(int, get_joint_number, set_joint_number, reset_joint_number)

    # boilder code
    def __getitem__(self, item):
        return getattr(self, item)
    def __setitem__(self, item, value):
        return setattr(self, item, value)


class PushButton(Indicated_PushButton, _HalWidgetBase):
    def __init__(self, parent=None):
        super(PushButton, self).__init__(parent)

    # make the super class (pushbutton) HAL pins
    # then the button pins
    def _hal_init(self):
        super(PushButton, self)._hal_init()
        self.hal_pin = self.HAL_GCOMP_.newpin(str(self.HAL_NAME_), hal.HAL_BIT, hal.HAL_OUT)

        def _update(state):
            self.hal_pin.set(state)
            self.setChecked(state)
            if self._HAL_pin is False:
                self.indicator_update(state)
            # if using state labels option update the labels
            if self._state_text:
                self.setText(None)
            # if python commands call them 
            if self._python_command:
                if state == None:
                    state = self._indicator_state
                self.python_command(state)

        if self.isCheckable():
            self.toggled[bool].connect(_update)
        else:
            self.pressed.connect(partial(_update, True))
            self.released.connect(partial(_update, False))

class ScaledLabel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super(ScaledLabel, self).__init__(parent)

    def _hal_init(self):
        if self.textFormat() == 0:
            self.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                             QtWidgets.QSizePolicy.Ignored))
            self.setMinSize(14)

    def setMinSize(self, minfs):        
        f = self.font()
        f.setPixelSize(minfs)
        br = QtGui.QFontMetrics(f).boundingRect(self.text())
        self.setMinimumSize(br.width(), br.height())

    def resizeEvent(self, event):
        super(ScaledLabel, self).resizeEvent(event)        

        if not self.text() or self.textFormat() in(1, 2):
            return

        #--- fetch current parameters ----
        f = self.font()
        cr = self.contentsRect()

        #--- iterate to find the font size that fits the contentsRect ---
        dw = event.size().width() - event.oldSize().width()   # width change
        dh = event.size().height() - event.oldSize().height() # height change
        fs = max(f.pixelSize(), 1)
        while True:
            f.setPixelSize(fs)
            br =  QtGui.QFontMetrics(f).boundingRect(self.text())

            if dw >= 0 and dh >= 0: # label is expanding
                if br.height() <= cr.height() and br.width() <= cr.width():
                    fs += 1
                else:
                    f.setPixelSize(max(fs - 1, 1)) # backtrack
                    break

            else: # label is shrinking
                if br.height() > cr.height() or br.width() > cr.width():
                    fs -= 1
                else:
                    break

            if fs < 1: break

        #--- update font size ---
        self.setFont(f)
