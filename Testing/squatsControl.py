import time as time_
# ODrive
import odrive
from odrive.enums import *
import math
# Joystick
import os, struct, array
from fcntl import ioctl
import threading
# Shell commands
from subprocess import call
import sys
import matplotlib.pyplot as plt
import numpy as np

global timeNow
global start
global array1 
global array2
global array3
array1 = []
array2 = []
array3 = []
#


#drive1 is top right driver
#drive2 is bottom right driver

print("Finding an ODrive...")
my_drive1 = odrive.find_any("usb","206237793548")
my_drive2 = odrive.find_any("usb","388937803437")

inTime = 0
print("Odrive found!")



# Joystick Code --------------------------------------

# JS state storage
axis_states = {}
button_states = {}



def enc_map(x, in_min, in_max, out_min, out_max):
    return (x-in_min) * (out_max-out_min) / (in_max-in_min) + out_min


# These constants were borrowed from linux/input.h
axis_names = {
    0x00 : 'x',
    0x01 : 'y',
    0x02 : 'z',
    0x03 : 'rx',
    0x04 : 'ry',
    0x05 : 'rz',
    0x06 : 'trottle',
    0x07 : 'rudder',
    0x08 : 'wheel',
    0x09 : 'gas',
    0x0a : 'brake',
    0x10 : 'hat0x',
    0x11 : 'hat0y',
    0x12 : 'hat1x',
    0x13 : 'hat1y',
    0x14 : 'hat2x',
    0x15 : 'hat2y',
    0x16 : 'hat3x',
    0x17 : 'hat3y',
    0x18 : 'pressure',
    0x19 : 'distance',
    0x1a : 'tilt_x',
    0x1b : 'tilt_y',
    0x1c : 'tool_width',
    0x20 : 'volume',
    0x28 : 'misc',
}

button_names = {
    0x120 : 'trigger',
    0x121 : 'thumb',
    0x122 : 'thumb2',
    0x123 : 'top',
    0x124 : 'top2',
    0x125 : 'pinkie',
    0x126 : 'base',
    0x127 : 'base2',
    0x128 : 'base3',
    0x129 : 'base4',
    0x12a : 'base5',
    0x12b : 'base6',
    0x12f : 'dead',
    0x130 : 'a',
    0x131 : 'b',
    0x132 : 'c',
    0x133 : 'x',
    0x134 : 'y',
    0x135 : 'z',
    0x136 : 'tl',
    0x137 : 'tr',
    0x138 : 'tl2',
    0x139 : 'tr2',
    0x13a : 'select',
    0x13b : 'start',
    0x13c : 'mode',
    0x13d : 'thumbl',
    0x13e : 'thumbr',

    0x220 : 'dpad_up',
    0x221 : 'dpad_down',
    0x222 : 'dpad_left',
    0x223 : 'dpad_right',

    # XBox 360 controller uses these codes.
    0x2c0 : 'dpad_left',
    0x2c1 : 'dpad_right',
    0x2c2 : 'dpad_up',
    0x2c3 : 'dpad_down',
}

axis_map = []
button_map = []

# Open the joystick device.
fn = '/dev/input/js0'
print('Opening %s...' % fn)

try:
    jsdev = open(fn, 'rb')

except IOError:
    print('No PS3 Controller connected')
    print('Please press the PS button to connect...')

    while True:
        if os.path.exists('/dev/input/js0'):
            print('Controller connected')

            jsdev = open(fn, 'rb')
            break

# Get the device name.
buf = bytearray(63)
# buf = array.array('u', ['\0'] * 64)
ioctl(jsdev, 0x80006a13 + (0x10000 * len(buf)), buf) # JSIOCGNAME(len)
# Get rid of random padding
buf = buf.rstrip(b'\0')
js_name = str(buf, encoding='utf-8')
print('Device name: %s' % js_name)

# Get number of axes and buttons.
buf = array.array('B', [0])
ioctl(jsdev, 0x80016a11, buf) # JSIOCGAXES
num_axes = buf[0]

buf = array.array('B', [0])
ioctl(jsdev, 0x80016a12, buf) # JSIOCGBUTTONS
num_buttons = buf[0]

# Get the axis map.
buf = array.array('B', [0] * 0x40)
ioctl(jsdev, 0x80406a32, buf) # JSIOCGAXMAP

for axis in buf[:num_axes]:
    axis_name = axis_names.get(axis, 'unknown(0x%02x)' % axis)
    axis_map.append(axis_name)
    axis_states[axis_name] = 0.0

# Get the button map.
buf = array.array('H', [0] * 200)
ioctl(jsdev, 0x80406a34, buf) # JSIOCGBTNMAP

for btn in buf[:num_buttons]:
    btn_name = button_names.get(btn, 'unknown(0x%03x)' % btn)
    button_map.append(btn_name)
    button_states[btn_name] = 0
    
def readJS():
    global armed
    global setpt_on
    global angle_cnt
    global calibrating
    global my_drive
    global pid
    global jsdev
    global inTime
    global varTime
    global trigValue
    global gain
    global curCtrl
    global pos_0
    global pos_1
    global strt
    global walkPath
    global start
    global mapPos0
    global mapPos1
    mapPos0 = 3150
    mapPos1 = -680
    start = 0
    gain = 20
    strt = 0
    walkPath = 0
    pos_0 = -1000
    pos_1 = -1000
    trigValue = 0
    curCtrl = 0
    armed = False
    calibrating = False
    while True:

        # Read the joystick
        try:
            evbuf = jsdev.read(8)

        # If the controller disconnects during operation, turn off motors and wait for reconnect
        except IOError:
            my_drive1.axis0.requested_state = AXIS_STATE_IDLE
            my_drive1.axis1.requested_state = AXIS_STATE_IDLE
            my_drive2.axis0.requested_state = AXIS_STATE_IDLE
            my_drive2.axis1.requested_state = AXIS_STATE_IDLE
            print('No PS3 Controller connected')
            print('Please press the PS button to connect...')

            while True:
                if os.path.exists('/dev/input/js0'):
                    print('Controller connected')

                    evbuf = jsdev.read(8)
                    break

        if evbuf:
            time, value, type, number = struct.unpack('IhBB', evbuf)

            # Determine if evbuf is the initial value
            if type & 0x80:
                # print((initial)),
                continue

            # Determine if evbuf is a button
            if type & 0x01:
                button = button_map[number]
                if button:
                   button_states[button] = value

            if button_states['select'] and (armed == True):
                my_drive1.axis0.requested_state = AXIS_STATE_IDLE
                my_drive1.axis1.requested_state = AXIS_STATE_IDLE
                my_drive2.axis0.requested_state = AXIS_STATE_IDLE
                my_drive2.axis1.requested_state = AXIS_STATE_IDLE
                armed = False
                walkPath = 0
                print("Motors Unarmed!")
                      
            if button_states['dpad_up']:   
                gain += 10
                print(gain)

            
            if button_states['dpad_down']:
                gain -= 10
                print(gain)                     
                    
            if button_states['b']:
                walkPath = 0

                
            if button_states['a']:
                walkPath = 1

            if button_states['start'] and (armed == False):

                my_drive1.axis0.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
                my_drive1.axis1.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
                my_drive1.axis0.controller.config.control_mode = CTRL_MODE_POSITION_CONTROL
                my_drive1.axis1.controller.config.control_mode = CTRL_MODE_POSITION_CONTROL
                
                my_drive2.axis0.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
                my_drive2.axis1.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
                my_drive2.axis0.controller.config.control_mode = CTRL_MODE_POSITION_CONTROL
                my_drive2.axis1.controller.config.control_mode = CTRL_MODE_POSITION_CONTROL
                
                armed = True

                print("Motors Armed!")
                continue
            
                
            # Determine if evbuf is an axis
            if type & 0x02:
                fvalue = value / 32767.0
                axis = axis_map[number]
                if(axis == 'ry'):
                    fvalue = (value / 32767.0) + 1
                    mapPos0 = enc_map(fvalue,2,0,2180,2650)
                    mapPos1 = enc_map(fvalue,2,0,-1585,-1180)
                    trigValue = fvalue           
                    axis_states[axis] = fvalue
              #      print(trigValue," ",mapPos)

               
# Start the readJS thread. Reads joystick in the "background"
readJSThrd = threading.Thread(target=readJS)
readJSThrd.daemon = True
readJSThrd.start()

    

while True:
    # Allows ctrl-C to exit the program, should keep the IMU stable
    try:


        if(walkPath == 1 and armed == True):
            my_drive1.axis0.controller.pos_setpoint = mapPos0+200
            my_drive1.axis1.controller.pos_setpoint = mapPos1
            my_drive1.axis0.controller.config.pos_gain = gain
            my_drive1.axis1.controller.config.pos_gain = gain
        
        
            my_drive2.axis0.controller.pos_setpoint = mapPos0
            my_drive2.axis1.controller.pos_setpoint = mapPos1
            my_drive2.axis0.controller.config.pos_gain = gain
            my_drive2.axis1.controller.config.pos_gain = gain
            
           # print("[", my_drive1.axis0.encoder.pos_estimate, ", ", my_drive1.axis1.encoder.pos_estimate,"]", "[", my_drive2.axis0.encoder.pos_estimate, ", ", my_drive2.axis1.encoder.pos_estimate,"], Temp1: [ ",my_drive1.axis0.get_temp(),", ", my_drive1.axis1.get_temp(),"] . Temp2: [",my_drive2.axis0.get_temp()," , ", my_drive2.axis1.get_temp(),"]")
           
            print("[", my_drive1.axis0.motor.current_control.Iq_measured, ", ", my_drive1.axis1.motor.current_control.Iq_measured,"]", "[", my_drive2.axis0.motor.current_control.Iq_measured, ", ", my_drive2.axis1.motor.current_control.Iq_measured,"], Temp1: [ ",my_drive1.axis0.get_temp(),", ", my_drive1.axis1.get_temp(),"] . Temp2: [",my_drive2.axis0.get_temp()," , ", my_drive2.axis1.get_temp(),"]")

           
            time_.sleep(0.05)

  
    except (KeyboardInterrupt):
        # Turn off the motors
        armed = False
        my_drive1.axis0.requested_state = AXIS_STATE_IDLE
        my_drive1.axis1.requested_state = AXIS_STATE_IDLE
        my_drive2.axis0.requested_state = AXIS_STATE_IDLE
        my_drive2.axis1.requested_state = AXIS_STATE_IDLE
        # Close the data file
        testdata.close()
        sys.exit()


