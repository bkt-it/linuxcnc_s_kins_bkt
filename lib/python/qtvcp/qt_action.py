from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

import linuxcnc
import hal

# Set up logging
import logger
log = logger.getLogger(__name__)
# log.setLevel(logger.INFO) # One of DEBUG, INFO, WARNING, ERROR, CRITICAL

from qtvcp.core import Status, Info
INFO = Info()
STATUS = Status()

################################################################
# Action class
################################################################
class _Lcnc_Action(object):
    def __init__(self):
        # only initialize once for all instances
        if self.__class__._instanceNum >=1:
            return
        self.__class__._instanceNum += 1
        self.cmd = linuxcnc.command()
        self.tmp = None
        self.prefilter_path = None
        self.home_all_warning_flag = False

    def SET_ESTOP_STATE(self, state):
        if state:
            self.cmd.state(linuxcnc.STATE_ESTOP)
        else:
            self.cmd.state(linuxcnc.STATE_ESTOP_RESET)

    def SET_MACHINE_STATE(self, state):
        if state:
            self.cmd.state(linuxcnc.STATE_ON)
        else:
            self.cmd.state(linuxcnc.STATE_OFF)

    def SET_MACHINE_HOMING(self, joint):
        self.ensure_mode(linuxcnc.MODE_MANUAL)
        self.cmd.teleop_enable(False)
        if not INFO.HOME_ALL_FLAG and joint == -1:
            if not self.home_all_warning_flag == True:
                self.home_all_warning_flag = True
                STATUS.emit('error',linuxcnc.NML_ERROR,
                    ''''Home-all not available according to INI Joint Home sequence
         Set the joint sequence in the INI or
         modify the screen for individual home buttons
         to avoid this warning
         Press again to home Z axis Joint''')
            else:
                if STATUS.is_all_homed():
                    self.home_all_warning_flag = False
                    return
                # so linuxcnc is misonfigured or the Screen is built wrong (needs individual home buttons)
                # now we will fake individual home buttons by homing joints one at a time
                # but always start will Z - on a mill it's safer
                zj = INFO.GET_JOG_FROM_NAME['Z']
                if not STATUS.stat.homed[zj]:
                    log.info('Homing Joint: {}'.format(zj))
                    self.cmd.home(zj)
                    STATUS.emit('error',linuxcnc.NML_ERROR,
                        ''''Home-all not available according to INI Joint Home sequence
             Press again to home next Joint''')
                    return
                length = len(INFO.JOINT_SEQUENCE_LIST)
                for num,j in enumerate(INFO.JOINT_SEQUENCE_LIST):
                    print j, num, len(INFO.JOINT_SEQUENCE_LIST)
                    # at the end so all homed
                    if num == length -1:
                        self.home_all_warning_flag = False
                    # one from end but end is already homed
                    if num == length -2 and STATUS.stat.homed[zj]:
                        self.home_all_warning_flag = False
                    # Z joint is homed first outside this for loop
                    if j == zj : continue
                    # ok home it then stop and wait for next button push
                    if not STATUS.stat.homed[j]:
                        log.info('Homing Joint: {}'.format(j))
                        self.cmd.home(j)
                        if self.home_all_warning_flag:
                            STATUS.emit('error',linuxcnc.NML_ERROR,
                                ''''Home-all not available according to INI Joint Home sequence
                     Press again to home next Joint''')
                        break
        else:
            log.info('Homing Joint: {}'.format(joint))
            self.cmd.home(joint)

    def SET_MACHINE_UNHOMED(self, joint):
        self.ensure_mode(linuxcnc.MODE_MANUAL)
        self.cmd.teleop_enable(False)
        #self.cmd.traj_mode(linuxcnc.TRAJ_MODE_FREE)
        self.cmd.unhome(joint)

    def SET_AUTO_MODE(self):
        self.ensure_mode(linuxcnc.MODE_AUTO)

    # if called while on hard limit will set the flag and allow machine on
    # if called with flag set and now off hard limits - resets the flag
    def TOGGLE_LIMITS_OVERRIDE(self):
        if STATUS.is_limits_override_set() and STATUS.is_hard_limits_tripped():
            STATUS.emit('error',linuxcnc.OPERATOR_ERROR,'''Can Not Reset Limits Override - Still On Hard Limits''')
        elif not STATUS.is_limits_override_set() and STATUS.is_hard_limits_tripped():
            STATUS.emit('error',linuxcnc.OPERATOR_ERROR,'Hard Limits Are Overridden!')
            self.cmd.override_limits()
        else:
            # make it temparary
            STATUS.emit('error',255,'Hard Limits Are Reset To Active!')
            self.cmd.override_limits()

    def SET_MDI_MODE(self):
        self.ensure_mode(linuxcnc.MODE_MDI)

    def SET_MANUAL_MODE(self):
        self.ensure_mode(linuxcnc.MODE_MANUAL)

    def CALL_MDI(self, code):
        self.ensure_mode(linuxcnc.MODE_MDI)
        self.cmd.mdi('%s'%code)

    def CALL_MDI_WAIT(self, code, time = 5):
        log.debug('MDI_WAIT_COMMAND= {}, maxt = {}'.format(code, time))
        self.ensure_mode(linuxcnc.MODE_MDI)
        for l in code.split("\n"):
            log.debug('MDI_COMMAND: {}'.format(l))
            self.cmd.mdi( l )
            result = self.cmd.wait_complete(time)
            if result == -1:
                log.debug('MDI_COMMAND_WAIT timeout past {} sec. Error: {}'.format( time, result))
                #STATUS.emit('MDI time out error',)
                self.ABORT()
                return -1
            elif result == linuxcnc.RCS_ERROR:
                log.debug('MDI_COMMAND_WAIT RCS error: {}'.format( time, result))
                #STATUS.emit('MDI time out error',)
                return -1
            result = linuxcnc.error_channel().poll()
            if result:
                STATUS.emit('error',result[0],result[1])
                log.error('MDI_COMMAND_WAIT Error channel: {}'.format(result[1]))
                return -1
        return 0

    def CALL_INI_MDI(self, number):
        try:
            mdi = INFO.MDI_COMMAND_LIST[number]
        except:
            log.error('MDI_COMMAND= # {} Not found under [MDI_COMMAND_LIST] in INI file'.format(number))
            return
        mdi_list = mdi.split(';')
        self.ensure_mode(linuxcnc.MODE_MDI)
        for code in(mdi_list):
            self.cmd.mdi('%s'% code)

    def CALL_OWORD(self, code, time=5 ):
        log.debug('OWORD_COMMAND= {}'.format(code))
        self.ensure_mode(linuxcnc.MODE_MDI)
        self.cmd.mdi(code)
        STATUS.stat.poll()
        while STATUS.stat.exec_state == linuxcnc.EXEC_WAITING_FOR_MOTION_AND_IO or \
                        STATUS.stat.exec_state == linuxcnc.EXEC_WAITING_FOR_MOTION:
            result = self.cmd.wait_complete(time)
            if result == -1:
                log.error('Oword timeout oast () Error = # {}'.format(time, result))
                self.ABORT()
                return -1
            elif result == linuxcnc.RCS_ERROR:
                log.error('Oword RCS Error = # {}'.format(result))
                return -1
            result = linuxcnc.error_channel().poll()
            if result:
                STATUS.emit('error',result[0],result[1])
                log.error('Oword Error: {}'.format(result[1]))
                return -1
            STATUS.stat.poll()
        result = self.cmd.wait_complete(time)
        if result == -1 or result == linuxcnc.RCS_ERROR or linuxcnc.error_channel().poll():
            log.error('Oword RCS Error = # {}'.format(result))
            return -1
        result = linuxcnc.error_channel().poll()
        if result:
            STATUS.emit('error',result[0],result[1])
            log.error('Oword Error: {}'.format(result[1]))
            return -1
        log.debug('OWORD_COMMAND returns complete : {}'.format(result))
        return 0

    def UPDATE_VAR_FILE(self):
        self.ensure_mode(linuxcnc.MODE_MANUAL)
        self.ensure_mode(linuxcnc.MODE_MDI)

    def OPEN_PROGRAM(self, fname):
        self.prefilter_path = str(fname)
        self.ensure_mode(linuxcnc.MODE_AUTO)
        old = STATUS.stat.file
        flt = INFO.get_filter_program(str(fname))

        if flt:
            log.debug('get {} filtered program {}'.format(flt,fname))
            self.open_filter_program(str(fname), flt)
        else:
            log.debug( 'Load program {}'.format(fname))
            self.cmd.program_open(str(fname))

            # STATUS can't tell if we are loading the same file.
            # for instance if you edit a file then load it again.
            # so we check for it and force an update:
            if old == fname:
                STATUS.emit('file-loaded',fname)

    def SAVE_PROGRAM(self, source, fname):
        if source == '': return
        if '.' not in fname:
            fname += '.ngc'
        name, ext = fname.rsplit('.')
        try:
            outfile = open(name + '.' + ext.lower(),'w')
            outfile.write(source)
            STATUS.emit('update-machine-log', 'Saved: ' + fname, 'TIME')
        except Exception as e:
            print e
        finally:
            outfile.close()

    def SET_AXIS_ORIGIN(self,axis,value):
        if axis == '' or axis.upper() not in ("XYZABCUVW"):
            log.warning("Couldn't set orgin -axis >{}< not recognized:".format(axis))
        m = "G10 L20 P0 %s%f"%(axis,value)
        fail, premode = self.ensure_mode(linuxcnc.MODE_MDI)
        self.cmd.mdi(m)
        self.cmd.wait_complete()
        self.ensure_mode(premode)
        self.RELOAD_DISPLAY()

    # Adjust tool offsets so current position ends up the given value
    def SET_TOOL_OFFSET(self,axis,value,fixture = False):
        lnum = 10+int(fixture)
        m = "G10 L%d P%d %s%f"%(lnum, STATUS.stat.tool_in_spindle, axis, value)
        fail, premode = self.ensure_mode(linuxcnc.MODE_MDI)
        self.cmd.mdi(m)
        self.cmd.wait_complete()
        self.cmd.mdi("G43")
        self.cmd.wait_complete()
        self.ensure_mode(premode)
        self.RELOAD_DISPLAY()

    # Set actual tool offset in tool table to the given value
    def SET_DIRECT_TOOL_OFFSET(self,axis,value):
        m = "G10 L1 P%d %s%f"%( STATUS.get_current_tool(), axis, value)
        fail, premode = self.ensure_mode(linuxcnc.MODE_MDI)
        self.cmd.mdi(m)
        self.cmd.wait_complete()
        self.cmd.mdi("G43")
        self.cmd.wait_complete()
        self.ensure_mode(premode)
        self.RELOAD_DISPLAY()

    def RUN(self, line=0):
        if not STATUS.is_auto_mode():
            self.ensure_mode(linuxcnc.MODE_AUTO)
        if STATUS.is_auto_paused() and line == 0:
            self.cmd.auto(linuxcnc.AUTO_STEP)
            return
        elif not STATUS.is_auto_running():
            self.cmd.auto(linuxcnc.AUTO_RUN,line)

    def STEP(self):
        if STATUS.is_auto_running() and not STATUS.is_auto_paused():
            self.cmd.auto(linuxcnc.AUTO_PAUSE)
            return
        if STATUS.is_auto_paused():
            self.cmd.auto(linuxcnc.AUTO_STEP)
            return

    def ABORT(self):
        self.ensure_mode(linuxcnc.MODE_AUTO)
        self.cmd.abort()

    def PAUSE(self):
        if not STATUS.stat.paused:
            self.cmd.auto(linuxcnc.AUTO_PAUSE)
        else:
            log.debug('resume')
            self.cmd.auto(linuxcnc.AUTO_RESUME)

    def SET_MAX_VELOCITY_RATE(self, rate):
        self.cmd.maxvel(rate/60.0)
    def SET_RAPID_RATE(self, rate):
        self.cmd.rapidrate(rate/100.0)
    def SET_FEED_RATE(self, rate):
        self.cmd.feedrate(rate/100.0)
    def SET_SPINDLE_RATE(self, rate, number = 0):
        self.cmd.spindleoverride(rate/100.0, number)

    def SET_JOG_RATE(self, rate):
        STATUS.set_jograte(float(rate))
    def SET_JOG_RATE_ANGULAR(self, rate):
        STATUS.set_jograte_angular(float(rate))
    def SET_JOG_INCR(self, incr, text):
        STATUS.set_jog_increments(incr, text)
        # stop runaway jogging
        for jnum in range(STATUS.stat.joints):
            self.STOP_JOG(jnum)
    def SET_JOG_INCR_ANGULAR(self, incr, text):
        STATUS.set_jog_increment_angular(incr, text)
        # stop runaway joging
        for jnum in range(STATUS.stat.joints):
            self.STOP_JOG(jnum)

    def SET_SPINDLE_ROTATION(self, direction = 1, rpm = 100, number = -1):
        self.cmd.spindle(direction, rpm, number)
    def SET_SPINDLE_FASTER(self, number = 0):
        # if all spindles (-1) command , we must check each spindle
        if number == -1:
            a = 0
            b = INFO.AVAILABLE_SPINDLES
        else:
            a = number
            b = number +1
        for i in range(a,b):
            if abs(STATUS.get_spindle_speed(number)) >= INFO['MAX_SPINDLE_{}_SPEED'.format(i)]: return
            self.cmd.spindle(linuxcnc.SPINDLE_INCREASE, i)
    def SET_SPINDLE_SLOWER(self, number = 0):
        self.cmd.spindle(linuxcnc.SPINDLE_DECREASE, number)
    def SET_SPINDLE_STOP(self, number = 0):
        self.cmd.spindle(linuxcnc.SPINDLE_OFF, number)

    def SET_USER_SYSTEM(self, system):
        systemnum = str(system).strip('gG')
        if systemnum in('54', '55', '56', '57', '58', '59', '59.1', '59.2', '59.3'):
            fail, premode = self.ensure_mode(linuxcnc.MODE_MDI)
            self.cmd.mdi('G'+systemnum)
            self.cmd.wait_complete()
            self.ensure_mode(premode)
            
    def ZERO_G92_OFFSET(self):
        self.CALL_MDI("G92.1")
        self.RELOAD_DISPLAY()
    def ZERO_ROTATIONAL_OFFSET(self):
        self.CALL_MDI("G10 L2 P0 R 0")
        self.RELOAD_DISPLAY()
    def ZERO_G5X_OFFSET(self, num):
        fail, premode = self.ensure_mode(linuxcnc.MODE_MDI)
        clear_command = "G10 L2 P%d R0" % num
        for a in INFO.AVAILABLE_AXES:
            clear_command += " %c0" % a
        self.cmd.mdi('%s'% clear_command)
        self.cmd.wait_complete()
        self.ensure_mode(premode)
        self.RELOAD_DISPLAY()

    def RECORD_CURRENT_MODE(self):
        mode = STATUS.get_current_mode()
        self.last_mode = mode
        return mode

    def RESTORE_RECORDED_MODE(self):
        self.ensure_mode(self.last_mode)

    def SET_SELECTED_JOINT(self, data):
        if isinstance(data, (int, long)):
            STATUS.set_selected_joint(data)
        else:
            log.error( 'Selected joint must be an integer: {}'.format(data))

    def SET_SELECTED_AXIS(self, data):
        if isinstance(data, (str)):
            STATUS.set_selected_axis(data)
        else:
            log.error( 'Selected axis must be a string: {}'.format(data))

    # jog based on STATUS's rate and distance
    # use joint number for joint or letter for axis jogging
    def DO_JOG(self, joint_axis, direction):
        angular = False
        if isinstance(joint_axis, (int, long)):
            if STATUS.stat.joint[joint_axis]['jointType'] == linuxcnc.ANGULAR:
                angular =  True
            jointnum = joint_axis
        else:
            if joint_axis.upper() in('A','B','C'):
                angular = True
            s ='XYZABCUVW'
            jointnum = s.find(joint_axis)
        # Get jog rate
        if angular:
                distance = STATUS.get_jog_increment_angular()
                rate = STATUS.get_jograte_angular()/60
        else:
                distance = STATUS.get_jog_increment()
                rate = STATUS.get_jograte()/60
        self.JOG(jointnum, direction, rate, distance)

    # jog based on given variables
    # checks for jog joint mode first
    def JOG(self, jointnum, direction, rate, distance=0):
        jjogmode,j_or_a = self.get_jog_info(jointnum)
        if jjogmode is None or j_or_a is None:
            return
        if direction == 0:
            self.cmd.jog(linuxcnc.JOG_STOP, jjogmode, j_or_a)
        else:
            if distance == 0:
                self.cmd.jog(linuxcnc.JOG_CONTINUOUS, jjogmode, j_or_a, direction * rate)
            else:
                self.cmd.jog(linuxcnc.JOG_INCREMENT, jjogmode, j_or_a, direction * rate, distance)

    def STOP_JOG(self, jointnum):
        if STATUS.machine_is_on():
            jjogmode,j_or_a = self.get_jog_info(jointnum)
            self.cmd.jog(linuxcnc.JOG_STOP, jjogmode, j_or_a)

    def TOGGLE_FLOOD(self):
        self.cmd.flood(not(STATUS.stat.flood))
    def SET_FLOOD_ON(self):
        self.cmd.flood(1)
    def SET_FLOOD_OFF(self):
        self.cmd.flood(0)

    def TOGGLE_MIST(self):
        self.cmd.mist(not(STATUS.stat.mist))
    def SET_MIST_ON(self):
        self.cmd.mist(1)
    def SET_MIST_OFF(self):
        self.cmd.mist(0)

    def RELOAD_TOOLTABLE(self):
        self.cmd.load_tool_table()                

    def TOGGLE_OPTIONAL_STOP(self):
        self.cmd.set_optional_stop(not(STATUS.stat.optional_stop))
    def SET_OPTIONAL_STOP_ON(self):
        self.cmd.set_optional_stop(True)
    def SET_OPTIONAL_STOP_OFF(self):
        self.cmd.set_optional_stop(False)

    def TOGGLE_BLOCK_DELETE(self):
        self.cmd.set_block_delete(not(STATUS.stat.block_delete))
    def SET_BLOCK_DELETE_ON(self):
        self.cmd.set_block_delete(True)
    def SET_BLOCK_DELETE_OFF(self):
        self.cmd.set_block_delete(False)

    def RELOAD_DISPLAY(self):
        STATUS.emit('reload-display')

    def SET_GRAPHICS_VIEW(self, view):
        if view.lower() in('x', 'y', 'y2', 'z', 'z2', 'p', 'clear',
                    'zoom-in','zoom-out','pan-up','pan-down',
                    'pan-left','pan-right','rotate-up',
                'rotate-down', 'rotate-cw','rotate-ccw',
                'overlay_dro_on','overlay_dro_off',
                'overlay-offsets-on','overlay-offsets-off',
                'inhibit-selection-on','inhibit-selection-off',
                'alpha-mode-on','alpha-mode-off'):
            STATUS.emit('graphics-view-changed',view,None)

    def SET_GRAPHICS_GRID_SIZE(self, size):
            STATUS.emit('graphics-view-changed','GRID-SIZE',{'SIZE':size})

    def ADJUST_GRAPHICS_PAN(self, x, y):
        STATUS.emit('graphics-view-changed','pan-view',{'X':x,'Y':y})

    def ADJUST_GRAPHICS_ROTATE(self, x, y):
        STATUS.emit('graphics-view-changed','rotate-view',{'X':x,'Y':y})

    def SHUT_SYSTEM_DOWN_PROMPT(self):
        import subprocess
        try:
            try:
                subprocess.call('gnome-session-quit --power-off',shell=True)
            except:
                try:
                    subprocess.call('xfce4-session-logout', shell=True)
                except:
                    try:
                        subprocess.call('systemctl poweroff', shell=True)
                    except:
                        raise
        except Exception as e:
            log.warning("Couldn't shut system down: {}".format(e))

    def SHUT_SYSTEM_DOWN_NOW(self):
        import subprocess
        subprocess.call('shutdown now')

    def UPDATE_MACHINE_LOG(self, text, option=None):
        if option not in('TIME', 'DATE','DELETE',None):
            log.warning("Machine_log option not recognized: {}".format(option))
        STATUS.emit('update-machine-log', text, option)

    def CALL_DIALOG(self, command):
        try:
            a = command['NAME']
        except:
            log.warning("Call Dialog command Dict not recogzied: {}".format(option))
        STATUS.emit('dialog-request',command)

    def HIDE_POINTER(self, state):
        if state:
            QApplication.setOverrideCursor(Qt.BlankCursor)
        else:
            QApplication.restoreOverrideCursor()

    def PLAY_SOUND(self, path):
        try:
            STATUS.emit('play-sound', path)
        except AttributeError:
            log.warning("Sound request {} not recogzied".format(path))
    def PLAY_ERROR(self):
        self.PLAY_SOUND('ERROR')
    def PLAY_DONE(self):
        self.PLAY_SOUND('DONE')
    def PLAY_READY(self):
        self.PLAY_SOUND('READY')
    def PLAY_ATTENTION(self):
        self.PLAY_SOUND('ATTENTION')
    def PLAY_LOGIN(self):
        self.PLAY_SOUND('LOGIN')
    def PLAY_LOGOUT(self):
        self.PLAY_SOUND('LOGOUT')

    def SPEAK(self, speech):
        STATUS.emit('play-sound','SPEAK {}'.format(speech))

    def BEEP(self):
        self.PLAY_SOUND('BEEP')
    def BEEP_RING(self):
        self.PLAY_SOUND('BEEP_RING')
    def BEEP_START(self):
        self.PLAY_SOUND('BEEP_START')

    ######################################
    # Action Helper functions
    ######################################

    # In free (joint) mode we use the plain joint number.
    # In axis mode we convert the joint number to the equivalent
    # axis number 
    def get_jog_info (self,num):
        if STATUS.stat.motion_mode == linuxcnc.TRAJ_MODE_FREE:
            return True, self.jnum_check(num)
        return False, num

    def jnum_check(self,num):
        if STATUS.stat.kinematics_type != linuxcnc.KINEMATICS_IDENTITY:
            log.warning("Joint jogging not supported for non-identity kinematics")
            #return None
        if num > INFO.JOINT_COUNT:
            log.error("Computed joint number={} exceeds jointcount={}".format(num,INFO.JOINT_COUNT))
            # decline to jog
            return None
        if num not in INFO.AVAILABLE_JOINTS:
            log.warning("Joint {} is not in available joints {}".format(num, INFO.AVAILABLE_JOINTS))
            return None
        return num

    def ensure_mode(self, *modes):
        truth, premode = STATUS.check_for_modes(modes)
        if truth is False:
            self.cmd.mode(modes[0])
            self.cmd.wait_complete()
            return (True, premode)
        else:
            return (truth, premode)

    def open_filter_program(self,fname, flt):
        log.debug('Opening filtering program yellow<{}> for {}'.format(flt,fname))
        if not self.tmp:
            self._mktemp()
        tmp = os.path.join(self.tmp, os.path.basename(fname))
        flt = FilterProgram(flt, fname, tmp, lambda r: r or self._load_filter_result(tmp))

    def _load_filter_result(self, fname):
        old = STATUS.stat.file
        log.debug( 'Load filtered program {}'.format(fname))
        self.cmd.program_open(str(fname))

        # STATUS can't tell if we are loading the same file.
        # for instance if you edit a file then load it again.
        # so we check for it and force an update:
        if old == fname:
            STATUS.emit('file-loaded',fname)

    def _mktemp(self):
        if self.tmp:
            return
        self.tmp = tempfile.mkdtemp(prefix='emcflt-', suffix='.d')
        atexit.register(lambda: shutil.rmtree(self.tmp))


    def __getitem__(self, item):
        return getattr(self, item)
    def __setitem__(self, item, value):
        return setattr(self, item, value)

#############################
###########################################
# Filter Class
########################################################################
import os, sys, time, select, re
import tempfile, atexit, shutil

# slightly reworked code from gladevcp
# loads a filter program and collects the result
progress_re = re.compile("^FILTER_PROGRESS=(\\d*)$")
class FilterProgram:
    def __init__(self, program_filter, infilename, outfilename, callback=None):
        import subprocess
        outfile = open(outfilename, "w")
        infilename_q = infilename.replace("'", "'\\''")
        env = dict(os.environ)
        env['AXIS_PROGRESS_BAR'] = '1'
        p = subprocess.Popen(["sh", "-c", "%s '%s'" % (program_filter, infilename_q)],
                              stdin=subprocess.PIPE,
                              stdout=outfile,
                              stderr=subprocess.PIPE,
                              env=env)
        p.stdin.close()  # No input for you
        self.p = p
        self.stderr_text = []
        self.program_filter = program_filter
        self.callback = callback
        self.gid = STATUS.connect('periodic', self.update)
        #progress = Progress(1, 100)
        #progress.set_text(_("Filtering..."))

    def update(self, w):
        if self.p.poll() is not None:
            self.finish()
            STATUS.disconnect(self.gid)
            return False

        r,w,x = select.select([self.p.stderr], [], [], 0)
        if not r:
            return True
        stderr_line = self.p.stderr.readline()
        m = progress_re.match(stderr_line)
        if m:
            pass #progress.update(int(m.group(1)), 1)
        else:
            self.stderr_text.append(stderr_line)
            sys.stderr.write(stderr_line)
        return True

    def finish(self):
        # .. might be something left on stderr
        for line in self.p.stderr:
            m = progress_re.match(line)
            if not m:
                self.stderr_text.append(line)
                sys.stderr.write(line)
        r = self.p.returncode
        if r:
            self.error(r, "".join(self.stderr_text))
        if self.callback:
            self.callback(r)

    # pop a (probable) dialog box
    def error(self, exitcode, stderr):
        message = _('The filter program %(program)r exited with an error')% {'program': self.program_filter}
        more = _("Any error messages it produced are shown below:")
        mess = {'NAME':'MESSAGE','ID':'ACTION_ERROR__',
            'MESSAGE':message,
            'MORE': more,
            'DETAILS':stderr,
            'ICON':'CRITICAL',
            'FOCUS_TEXT': _('Filter program Error'),
            'TITLE':'Program Filter Error'}
        STATUS.emit('dialog-request', mess)
        log.error('Filter Program Error:{}'.format (stderr))