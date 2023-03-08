import os

try:
    from autoscript_sdb_microscope_client import SdbMicroscopeClient
    from autoscript_sdb_microscope_client.structures import (AdornedImage,
                                                             GrabFrameSettings,
                                                             Rectangle,
                                                             RunAutoCbSettings,
                                                             Point,
                                                             MoveSettings,
                                                             StagePosition)
    from autoscript_sdb_microscope_client.enumerations import (
                                                        CoordinateSystem)
except:
    print('Autoscript module not found')

import numpy as np
from dataclasses import dataclass
import utils


from importlib import reload  # Python 3.4+
reload(utils)

from utils import BeamType
from utils import MicroscopeState
from utils import ImageSettings

class Microscope():
    def __init__(self, settings: dict = None, log_path: str = None,
                 ip_address: str = "192.168.0.1", demo: bool=True):
        self.settings = settings
        self.demo = demo
        self.ip_address = ip_address
        self.log_path = log_path
        self.microscope_state = MicroscopeState()

        try:
            print('initialising microscope')
            self.microscope = SdbMicroscopeClient()
        except:
            print('Autoscript not installed on the computer, using demo mode')
            self.demo = True
            self.microscope = ['no Autoscript found']


    def establish_connection(self):
        """Connect to the SEM microscope."""
        try:
            # TODO: get the port
            print('connecting to microscope...')
            #logging.info(f"Microscope client connecting to [{ip_address}]")
            self.microscope = SdbMicroscopeClient()
            self.microscope.connect(self.ip_address)
            self.microscope.specimen.stage.set_default_coordinate_system(CoordinateSystem.SPECIMEN)
            #logging.info(f"Microscope client connected to [{ip_address}]")
        except Exception as e:
            print(f"AutoLiftout is unavailable. Unable to connect to microscope: {e}")
            self.microscope = ['could not connect to microscope']

        return self.microscope


    def autocontrast(self, quadrant: int = 1) -> None:
        """Automatically adjust the microscope image contrast."""
        if not self.demo:
            self.microscope.imaging.set_active_view(quadrant)
            settings = RunAutoCbSettings(
                            method="MaxContrast",
                            resolution="768x512",  # low resolution, so as not to damage the sample
                            number_of_frames=5)
            #logging.info("automatically adjusting contrast...")
            self.microscope.auto_functions.run_auto_cb(settings)
        else:
            print('demo: automatically adjusting contrast...')


    def set_beam_point(self,
                       beam_x : int = 0,
                       beam_y : int = 0):
        """
        API requires:
        x : float,  X coordinate of the spot. The valid range of the coordinate is [0, 1].
        y : float,  Y coordinate of the spot. The valid range of the coordinate is [0, 1].
        ----------
        Parameters
        ----------
        beam_x : int coordinate in pixels
        beam_y : int coordinate in pixels
        convert to
        x, y = beam_x / pixels_in_x, beam_y / pixels_in_y

        Returns None
        -------
        """
        if not self.demo:
            """ current screen resolution """
            resolution = self.microscope.beams.electron_beam.scanning.resolution.value
            [width, height] = np.array(resolution.split("x")).astype(int)
            if beam_x > width  : beam_x = width
            if beam_y > height : beam_y = height
            x = float(beam_x) / float(width)
            y = float(beam_y) / float(height)
            self.microscope.beams.electron_beam.scanning.mode.set_spot(x, y)
        else:
            print(f'demo: setting beam spot coordinates to ({beam_x}, {beam_y})')


    def set_full_frame(self):
        if not self.demo:
            self.microscope.beams.electron_beam.scanning.mode.set_full_frame()
        elif self.demo:
            print('setting scanning mode to full frame...   ')


    def beam_blank(self):
        if not self.demo:
            _state = self.microscope.beams.electron_beam.is_blanked
            if _state == True:
                """ beam state is blanked, unblank it """
                self.microscope.beams.electron_beam.unblank()
            elif _state == False:
                """beam state is not blanked, blank it"""
                self.microscope.beams.electron_beam.blank()
            return self.microscope.beams.electron_beam.is_blanked

        elif self.demo:
            print('demo mode: beam blank/unblank function called...   ')
            return 'demo blank'


    def blank(self):
        if not self.demo:
            self.microscope.beams.electron_beam.blank()
            return self.microscope.beams.electron_beam.is_blanked

        elif self.demo:
            print('demo mode: beam blank...   ')
            return 'demo blank'

    def unblank(self):
        if not self.demo:
            self.microscope.beams.electron_beam.unblank()
            return self.microscope.beams.electron_beam.is_blanked

        elif self.demo:
            print('demo mode: beam unblank...   ')
            return 'demo blank'


    def acquire_image(self, all_settings: dict,
                      hfw = None):
        """Take new electron or ion beam image.
        Returns
        -------
        AdornedImage
            If the returned AdornedImage is named 'image', then:
            image.data = a numpy array of the image pixels
            image.metadata.binary_result.pixel_size.x = image pixel size in x
            image.metadata.binary_result.pixel_size.y = image pixel size in y
            dwell_time in microseconds! x1e-6 coversion to seconds
        """
        print('acquiring image...')
        # logging.info(f"acquiring new {beam_type.name} image.")

        if not self.demo:
            if all_settings is not None:
                settings = self.update_image_settings(all_settings)
                self.microscope.imaging.set_active_view(settings.quadrant)

                if hfw is not None:
                    hfw = hfw
                else:
                    hfw = settings.horizontal_field_width

                if hfw > self.microscope.beams.electron_beam.horizontal_field_width.limits.max:
                    hfw = self.microscope.beams.electron_beam.horizontal_field_width.limits.max
                self.microscope.beams.electron_beam.horizontal_field_width.value = hfw

                if settings.autocontrast==True:
                    self.autocontrast(quadrant=settings.quadrant)

                if settings.frame_integration <= 0:
                    settings.frame_integration = 1

                grab_frame_settings = GrabFrameSettings(resolution=settings.resolution,
                                                        dwell_time=settings.dwell_time,
                                                        bit_depth=settings.bit_depth,
                                                        drift_correctiion=settings.drift_correction,
                                                        frame_integration=settings.frame_integration)
                image = self.microscope.imaging.grab_frame(grab_frame_settings)
            else:
                image = self.microscope.imaging.grab_frame()

            return image

        else:
            print('demo mode   ')
            if all_settings is not None:
                settings = self.update_image_settings(all_settings)
                print('settings = ', settings)
                resolution = settings.resolution
                [width, height] = np.array(resolution.split("x")).astype(int)
            else:
                height, width = 768, 512
            simulated_image = np.random.randint(0, 255, [height,width])
            return simulated_image


    def last_image(self,  quadrant : int, save : bool = False):
        """Get the last previously acquired ion or electron beam image.
        Parameters
        ----------
        microscope : Autoscript microscope object.
        beam_type :

        Returns
        -------
        AdornedImage
            If the returned AdornedImage is named 'image', then:
            image.data = a numpy array of the image pixels
            image.metadata.binary_result.pixel_size.x = image pixel size in x
            image.metadata.binary_result.pixel_size.y = image pixel size in y
        """
        if not self.demo:
            self.microscope.imaging.set_active_view(quadrant)
            image = self.microscope.imaging.get_image()
            return image

        else:
            simulated_image = np.random.randint(0, 255, [512,768])
            print(simulated_image.shape)
            return simulated_image


    def update_stage_position(self):
        try:
            position = \
                self.microscope.specimen.stage.current_position
            MicroscopeState.update_stage_position(self.microscope_state,
                                                  x=position.x, y=position.y, z=position.z,
                                                  t=position.t, r=position.r)
            return (position.x, position.y, position.z,
                    position.t, position.r)

        except Exception as e:
            print(f'stage position, error {e}, simulated coordinates are:')
            #[x, y, z, t, r] = np.random.randint( 0,5, [5,1] ).astype(float)
            [x, y, z, t, r] = np.random.rand(5, 1)
            MicroscopeState.update_stage_position(self.microscope_state,
                                                  x=x[0]*1e-3, y=y[0]*1e-3, z=z[0]*1e-3,
                                                  t=t[0], r=r[0])
            print(MicroscopeState.get_stage_position(self.microscope_state))
            return (x[0]*1e-3, y[0]*1e-3, z[0]*1e-3, t[0], r[0])



    def set_scan_rotation(self, rotation_angle : float = 0, type="Absolute") -> float:
        """Set scan rotation angle
        Args:
            rotation_angle (float): angle of scan rotation in degrees,
            needs conversion to rad
        Returns
        -------
        float: system-level scan rotation angle in degrees
        """
        try:
            rot_min = self.microscope.beams.electron_beam.scanning.rotation.limits.min
            rot_max = self.microscope.beams.electron_beam.scanning.rotation.limits.max

            if type=="Relative":
                """
                    Change the current scan rotation by the specified value
                    Check that targety scan_rot does not exceed (-2pi, +2pi)
                    Otherwise divide module to stay within the (-2pi, +2pi) range
                """
                current_scan_rot = \
                    self.microscope.beams.electron_beam.scanning.rotation.value

                target_rot_angle = current_scan_rot + rotation_angle

                if target_rot_angle >=rot_max:
                    target_rot_angle = target_rot_angle % (2*np.pi)
                elif target_rot_angle <=rot_min:
                    target_rot_angle = target_rot_angle % (2*np.pi)

                print(f"setting scan rotation {type} to {np.rad2deg(target_rot_angle)}")
                # TODO backend from from frontend separation
                self.microscope.beams.electron_beam.scanning.rotation.value = target_rot_angle

            elif type=="Absolute":
                """Absolute value of the scan rotation"""
                if rotation_angle >=rot_max:
                    rotation_angle = rotation_angle % (2*np.pi)
                elif rotation_angle <=rot_min:
                    rotation_angle = rotation_angle % (2*np.pi)

                print(f"setting scan rotation {type} to {np.rad2deg(rotation_angle)}")
                # TODO backend from from frontend separation
                self.microscope.beams.electron_beam.scanning.rotation.value = rotation_angle

            self._get_current_microscope_state()
            return self.microscope.beams.electron_beam.scanning.rotation.value

        except Exception as e:
            print(f'Failed to set scan rotation {type} by {np.rad2deg(rotation_angle)} deg, error {e}')
            return rotation_angle


    def set_beam_shift(self,
                       beam_shift_x : float = 0.0,
                       beam_shift_y : float = 0.0) -> None:
        """Adjusting the beam shift
        Args:
            beam_shift_x: in metres, shift along x-axis
            beam_shift_y: in metres, shift along y-axis
        Returns
        -------
        None. Update the microscope state with the new beam shift values
        """
        # adjust beamshift
        try:
            self.microscope.beams.electron_beam.beam_shift.value = Point(beam_shift_x, beam_shift_y)
            self._get_current_microscope_state()
        except Exception as e:
            print(f"Could not apply beam shift, error {e}")


    def reset_beam_shifts(self):
        """Set the beam shift to zero for the electron beam
        Args:
            None
        """
        # logging.info(
        #     f"reseting ebeam shift to (0, 0) from: {microscope.beams.electron_beam.beam_shift.value} "
        # )
        try:
            print(f"reseting e-beam shift to (0, 0) from: {self.microscope.beams.electron_beam.beam_shift.value}")
            self.microscope.beams.electron_beam.beam_shift.value = Point(0, 0)
            print(f"reset beam shifts to zero complete")
        except Exception as e:
            print(f"Could not reset the beam shift, error {e}")
        self._get_current_microscope_state()
        # logging.info(f"reset beam shifts to zero complete")


    def _get_current_microscope_state(self) -> MicroscopeState:
        """Acquires the current microscope state to store
         if necessary it is possible to return to this stored state later
         Returns the state in MicroscopeState dataclass variable
        Args:
            None
        Returns
        -------
        MicroscopeState
        """
        try:
            (x,y,z,t,r) = self.update_stage_position()
            self.microscope_state.x = x
            self.microscope_state.y = y
            self.microscope_state.z = z
            self.microscope_state.t = t
            self.microscope_state.r = r
            self.microscope_state.working_distance = \
                self.microscope.beams.electron_beam.working_distance.value

            self.microscope_state.horizontal_field_width = \
                self.microscope.beams.electron_beam.horizontal_field_width.value
            self.microscope_state.resolution = self.microscope.beams.electron_beam.scanning.resolution.value

            self.microscope_state.hv = self.microscope.beams.electron_beam.high_voltage.value
            self.microscope_state.beam_current = self.microscope.beams.electron_beam.beam_current.value

            self.microscope_state.scan_rotation_angle = \
                self.microscope.beams.electron_beam.scanning.rotation.value
            self.microscope_state.brightness = self.microscope.detector.brightness.value
            self.microscope_state.contrast = self.microscope.detector.contrast.value

            beam_shift = self.microscope.beams.electron_beam.beam_shift.value # returns Point()
            self.microscope_state.beam_shift_x = beam_shift.x
            self.microscope_state.beam_shift_y = beam_shift.y

        except Exception as e:
            print(f"Could not get the microscope state, error {e}")
            self.microscope_state.x = 2
            self.microscope_state.y = 1
            self.microscope_state.z = 0
            self.microscope_state.t = 0
            self.microscope_state.r = 0
            self.microscope_state.scan_rotation_angle = 0

        return self.microscope_state


    def _restore_microscope_state(self, state : MicroscopeState) -> None:
        """Restores the microscope state from the stored MicroscopeState variable
        Args:
            state : MicroscopeState
            TODO basic restore (state position, imaging conditions),
            full restore (volage, beam current etc)
        Returns
        -------
        None
        """
        try:
            """move function take x,y,z in micrometres and r,t in degrees
            the stored values are straight from the microscope in metres and rad
            """
            # self.move_stage(x=state.x, y=state.y, z=state.z,
            #                 t=state.t, r=state.r,
            #                 move_type='Absolute')
            self.microscope.beams.electron_beam.horizontal_field_width.value = \
                state.horizontal_field_width
            self.microscope.beams.electron_beam.scanning.resolution = state.resolution
            self.microscope.beams.electron_beam.scanning.rotation.value =\
                state.scan_rotation_angle
            self.microscope.detector.brightness.value = state.brighness
            self.microscope.detector.contrast.value = state.contrast
            self.microscope.beams.electron_beam.beam_shift.value = Point(state.beam_shift_x,
                                                                         state.beam_shift_y)
        except:
            print('Could not restore the microscope state')


    def update_image_settings(self,
                              all_settings: dict,
                              resolution=None,
                              dwell_time=None,
                              horizontal_field_width=None,
                              autocontrast=None,
                              beam_type=None,
                              quadrant=None,
                              sample_name=None,
                              path=None,
                              bit_depth=None,
                              drift_correction=None,
                              frame_integration=None
                              ):
        """Update image settings. Uses default values if not supplied
        Args:
            settings (dict): the settings dictionary from GUI
            resolution (str, optional): image resolution. Defaults to None.
            dwell_time (float, optional): image dwell time. Defaults to None.
            hfw (float, optional): image horizontal field width. Defaults to None.
            autocontrast (bool, optional): use autocontrast. Defaults to None.
            beam_type (BeamType, optional): beam type to image with (Electron, Ion). Defaults to None.
            gamma (GammaSettings, optional): gamma correction settings. Defaults to None.
            save (bool, optional): save the image. Defaults to None.
            label (str, optional): image filename . Defaults to None.
            save_path (Path, optional): directory to save image. Defaults to None.
        """

        # new image_settings
        if resolution:
            self.resolution = resolution
        else:
            self.resolution = all_settings["imaging"]["resolution"]

        if dwell_time:
            self.dwell_time = dwell_time
        else:
            self.dwell_time = all_settings["imaging"]["dwell_time"]

        if horizontal_field_width:
            self.horizontal_field_width = horizontal_field_width
        else:
            self.horizontal_field_width = all_settings["imaging"]["horizontal_field_width"]

        if autocontrast:
            self.__autocontrast = autocontrast
        else:
            self.__autocontrast = all_settings["imaging"]["autocontrast"]

        if beam_type:
            self.beam_type = beam_type
        else:
            self.beam_type = all_settings["imaging"]["beam_type"]

        if quadrant:
            self.quadrant = quadrant
        else:
            self.quadrant = all_settings["imaging"]["quadrant"]

        if path:
            self.path = path
        else:
            self.path = all_settings["imaging"]["path"]

        if bit_depth:
            self.bit_depth = bit_depth
        else:
            self.bit_depth = all_settings["imaging"]["bit_depth"]

        if sample_name:
            self.sample_name = sample_name
        else:
            self.sample_name = all_settings["imaging"]["sample_name"]

        if drift_correction:
            self.drift_correction = drift_correction
        else:
            self.drift_correction = all_settings["imaging"]["drift_correction"]

        if frame_integration:
            self.frame_integration = frame_integration
        else:
            self.frame_integration = all_settings["imaging"]["frame_integration"]

        self.image_settings = ImageSettings(
            resolution=self.resolution,
            dwell_time=self.dwell_time,
            horizontal_field_width=self.horizontal_field_width,
            quadrant=self.quadrant,
            autocontrast=self.__autocontrast,
            beam_type=BeamType.ELECTRON if beam_type is None else beam_type,
            path=self.path,
            sample_name=self.sample_name,
            bit_depth=self.bit_depth,
            drift_correction=self.drift_correction,
            frame_integration=self.frame_integration
        )

        return self.image_settings


    def disconnect(self):
        try:
            self.microscope.disconnect()
        except:
            pass # probably demo mode, no microscope connected, continue shutting down





if __name__ == '__main__':
    pass



