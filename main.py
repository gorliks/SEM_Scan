import qtdesigner_files.main_gui as gui_main
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QObject, QThread, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtWidgets import QFileDialog
import qimage2ndarray

from importlib import reload  # Python 3.4+
from dataclasses import dataclass

import sys, time, os, glob
import numpy as np
import SEM


import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as _FigureCanvas
from matplotlib.backends.backend_qt5agg import (
    NavigationToolbar2QT as _NavigationToolbar,
)

import utils
from utils import BeamType


class GUIMainWindow(gui_main.Ui_MainWindow, QtWidgets.QMainWindow):
    def __init__(self, demo):
        super(GUIMainWindow, self).__init__()
        self.setupUi(self)
        self.demo = demo
        self.time_counter = 0
        print('mode demo is ', demo)
        self.setStyleSheet("""QPushButton {
        border: 1px solid lightgray;
        border-radius: 5px;
        background-color: #e3e3e3;
        }""")

        self.DIR = os.getcwd()

        self.setup_connections()
        self.initialise_image_frames()
        self.initialise_hardware()

        self._abort_clicked_status = False
        self._blanked = False

        self.image = None
        self.image_mod = None
        self.current_image = None

        self._get_all_the_HFW_to_use()

        try:
            self.initialise_hardware()
        except Exception as e:
            print(f'Could not initialise the microscope, Error {e}')
            self.label_messages.setText('Could not initialise the microscope: ' + str(e))


    def setup_connections(self):
        self.pushButton_acquire.clicked.connect(lambda: self.acquire_image())
        self.pushButton_select_directory.clicked.connect(lambda: self.select_directory())
        self.pushButton_initialise_microscope.clicked.connect(lambda: self.initialise_hardware())
        self.pushButton_last_image.clicked.connect(lambda: self.last_image())
        self.pushButton_update_stage_position.clicked.connect(lambda: self.update_stage_position())
        self.pushButton_move_stage.clicked.connect(lambda: self.move_stage())
        self.pushButton_abort_stack_collection.clicked.connect(lambda: self._abort_clicked())
        self.pushButton_collect_stack.clicked.connect(lambda: self.collect_stack())
        self.pushButton_update_SEM_state.clicked.connect(lambda: self.update_SEM_state())
        #
        self.pushButton_save_file.clicked.connect(lambda: self._save_SEM_image())
        #
        self.pushButton_open_file.clicked.connect(lambda: self._open_file())
        self.pushButton_apply_clahe.clicked.connect(lambda: self._apply_clahe())
        self.pushButton_restore.clicked.connect(lambda: self._restore_image())




    def create_settings_dict(self) -> dict:
        resolution = self.comboBox_resolution.currentText()
        dwell_time = self.spinBox_dwell_time.value() * 1e-6
        horizontal_field_width = self.spinBox_horizontal_field_width.value() * 1e-6
        autocontrast = self.checkBox_autocontrast.isChecked()
        beam_type = self.comboBox_beam_type.currentText()
        if beam_type == "ELECTRON":
            beam_type = BeamType.ELECTRON
        elif beam_type == "ION":
            beam_type = BeamType.ION
        else:
            beam_type = BeamType.ELECTRON

        quadrant = int(self.comboBox_quadrant.currentText())
        q1 = self.checkBox_q1.isChecked()
        q2 = self.checkBox_q2.isChecked()

        path = self.DIR
        sample_name = self.plainTextEdit_sample_name.toPlainText()
        bit_depth = int(self.comboBox_bit_depth.currentText())
        drift_correction = self.checkBox_drift_correction.isChecked()
        frame_integration = self.spinBox_frame_integration.value()

        self.all_settings = {
            "imaging": {
                "resolution": resolution,
                "horizontal_field_width": horizontal_field_width,
                "dwell_time": dwell_time,
                "autocontrast": autocontrast,
                "beam_type": beam_type,
                "quadrant": quadrant,
                "path": path,
                "sample_name": sample_name,
                "bit_depth": bit_depth,
                "drift_correction" : drift_correction,
                'frame_integration' : frame_integration,
                'q1' : q1,
                'q2' : q2
            }
        }
        return self.all_settings

    ##############################################  HARDWARE ###########################################################

    def initialise_hardware(self):
        all_settings = self.create_settings_dict()
        self.microscope = SEM.Microscope(settings=all_settings, log_path=None, demo=self.demo)
        self.microscope.establish_connection()
        self.label_messages.setText(str(self.microscope.microscope_state))



    def acquire_image(self,
                      hfw = None):
        all_settings = self.create_settings_dict()
        if hfw is not None:
            all_settings["imaging"]["horizontal_field_width"] = hfw

        self.image = \
            self.microscope.acquire_image(all_settings=all_settings,
                                          hfw=hfw)
        try:
            self.pixelsize_x = self.image.metadata.binary_result.pixel_size.x
        except Exception as e:
            self.pixelsize_x = 1
            print(f'Cannot extract pixel size from the image metadata, error {e}')

        self.doubleSpinBox_pixel_size.setValue(self.pixelsize_x / 1e-9)
        self.update_display(image=self.image)
        return self.image


    def acquire_multiple_frames(self,
                                hfw = None):
        all_settings = self.create_settings_dict()
        if hfw is not None:
            all_settings["imaging"]["horizontal_field_width"] = hfw

        self.images = \
            self.microscope.acquire_multiple_frames(all_settings=all_settings,
                                                    hfw=hfw)
        try:
            self.pixelsize_x = self.images[0].metadata.binary_result.pixel_size.x
        except Exception as e:
            self.pixelsize_x = 1
            print(f'Cannot extract pixel size from the image metadata, error {e}')

        self.doubleSpinBox_pixel_size.setValue(self.pixelsize_x / 1e-9)
        self.update_display(image=self.images[0])
        return self.images


    def last_image(self):
        quadrant = int(self.comboBox_quadrant.currentText())
        self.image = \
            self.microscope.last_image(quadrant=quadrant)
        try:
            image = self.image.data
        except:
            image = self.image
        self.update_display(image=image)


    def update_stage_position(self):
        self.comboBox_move_type.setCurrentText("Absolute")
        self.microscope.update_stage_position()
        self.doubleSpinBox_stage_x.setValue(self.microscope.microscope_state.x / 1e-6)
        self.doubleSpinBox_stage_y.setValue(self.microscope.microscope_state.y / 1e-6)
        self.doubleSpinBox_stage_z.setValue(self.microscope.microscope_state.z / 1e-6)
        r = np.rad2deg(self.microscope.microscope_state.r)
        self.doubleSpinBox_stage_r.setValue(r)
        t = np.rad2deg(self.microscope.microscope_state.t)
        self.doubleSpinBox_stage_t.setValue(t)


    def update_SEM_state(self):
        self.microscope._get_current_microscope_state()
        self.update_stage_position()
        self.doubleSpinBox_working_distance.setValue(self.microscope.microscope_state.working_distance / 1e-3)

        self.doubleSpinBox_high_voltage.setValue(self.microscope.microscope_state.hv)
        self.doubleSpinBox_beam_current.setValue(self.microscope.microscope_state.beam_current / 1e-9)
        self.doubleSpinBox_brightness.setValue(self.microscope.microscope_state.brightness)
        self.doubleSpinBox_contrast.setValue(self.microscope.microscope_state.contrast)

        self.spinBox_horizontal_field_width.setValue(
            self.microscope.microscope_state.horizontal_field_width / 1e-6 )
        self.doubleSpinBox_scan_rotation.setValue(
            np.rad2deg(self.microscope.microscope_state.scan_rotation_angle)
        )
        self.doubleSpinBox_beam_shift_x.setValue(self.microscope.microscope_state.beam_shift_x / 1e-6)
        self.doubleSpinBox_beam_shift_y.setValue(self.microscope.microscope_state.beam_shift_y / 1e-6)



    def set_scan_rotation(self):
        rotation_angle = self.doubleSpinBox_scan_rotation.value()
        rotation_angle = np.deg2rad(rotation_angle)
        self.microscope.set_scan_rotation(rotation_angle=rotation_angle)


    def set_beam_shift(self):
        beam_shift_x = self.doubleSpinBox_beam_shift_x.value() * 1e-6
        beam_shift_y = self.doubleSpinBox_beam_shift_y.value() * 1e-6
        self.microscope.set_beam_shift(beam_shift_x=beam_shift_x,
                                       beam_shift_y=beam_shift_y)

    def reset_beam_shift(self):
        self.microscope.reset_beam_shifts()

    ##########################################################################################

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, caption='Select a folder')
        print(directory)
        self.label_messages.setText(directory)
        self.DIR = directory

    # def update_image(self, quadrant, image, update_current_image=True):
    #     if update_current_image:
    #         self.data_in_quadrant[quadrant] = image
    #     image_to_display = qimage2ndarray.array2qimage(image.copy())
    #     if quadrant in range(0, 4):
    #         self.label_image_frames[quadrant].setPixmap(QtGui.QPixmap(image_to_display))


    # TODO fix pop-up plot bugs
    def initialise_image_frames(self):
        self.figure_SEM = plt.figure(10)
        plt.axis("off")
        plt.tight_layout()
        plt.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.01)
        self.canvas_SEM = _FigureCanvas(self.figure_SEM)
        self.toolbar_SEM = _NavigationToolbar(self.canvas_SEM, self)
        #
        self.label_image_frame1.setLayout(QtWidgets.QVBoxLayout())
        self.label_image_frame1.layout().addWidget(self.toolbar_SEM)
        self.label_image_frame1.layout().addWidget(self.canvas_SEM)


    """TODO fix bugs with plotting data and using pop-up plots"""
    def update_display(self, image):
        self.current_image = image
        try:
            image = image.data
        except:
            image = image

        self.figure_SEM.clear()
        self.figure_SEM.patch.set_facecolor(
            (240 / 255, 240 / 255, 240 / 255))
        self.ax = self.figure_SEM.add_subplot(111)
        # ax.set_title("test")

        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        self.ax.imshow(image, cmap='gray')
        self.canvas_SEM.draw()



    def collect_stack(self):
        """ Update all the settings, store the current microscope state and
            particularly the current position. After the stack acquisition
            it is possible to return to the original position using move_absolute
            stored state: self.microscope.stored_state : MicroscopeState
            stack setting are stored in self.stack_settings : StackSettings
        """
        all_settings = self.create_settings_dict()
        timestamp = utils.current_timestamp()
        sample_name = self.plainTextEdit_sample_name.toPlainText()

        HFW_and_selections = self._get_all_the_HFW_to_use()
        print(HFW_and_selections)

        self.pushButton_acquire.setEnabled(False)
        self.pushButton_collect_stack.setEnabled(False)
        self.pushButton_abort_stack_collection.setEnabled(True)

        """Store the current microscope state, including the current position"""
        stored_microscope_state = self.microscope._get_current_microscope_state()
        # x0 = stored_microscope_state.x

        """Create directory for saving the stack"""
        if self.DIR is not None:
            self.stack_dir = self.DIR
        else:
            self.stack_dir = os.getcwd()
        # if self.DIR:
        #     self.stack_dir = os.path.join(self.DIR, 'stack_' + sample_name + '_' + timestamp)
        # else:
        #     self.stack_dir = os.path.join(os.getcwd(), 'stack_' + sample_name + '_' + timestamp)
        # if not os.path.isdir(self.stack_dir):
        #     os.mkdir(self.stack_dir)

        self.label_messages.setText(f"stack save dir {self.stack_dir}")

        keys = ('x', 'y', 'z', 't', 'r',
                'horizontal_field_width', 'scan_rotation_angle',
                'brightness', 'contrast',
                'beam_shift_x', 'beam_shift_y')
        self.experiment_data = {element: [] for element in keys}
        """add other data keys"""
        self.experiment_data['file_name'] = []
        self.experiment_data['timestamp'] = []


        def _run_loop(all_settings):
            counter = 0
            for hfw_and_status in HFW_and_selections:
                hfw = hfw_and_status[0]
                status = hfw_and_status[1]
                magnification = hfw_and_status[2]
                print(hfw_and_status, hfw, status, magnification)

                if status==True:

                    self.microscope._get_current_microscope_state()

                    # if not both q1 and q2 selected, then grab image only from a SIGNLE selected quadrant
                    if not (self.checkBox_q1.isChecked() and self.checkBox_q2.isChecked()):
                        timestamp = utils.current_timestamp()
                        self.spinBox_horizontal_field_width.setValue(hfw)

                        file_name = '%06d_' % counter + sample_name + '_' + \
                                    str(hfw) + '_' +  timestamp + '.tif'

                        """ This is a high-level procedure to acquire an image using the settings from the GUI """
                        image = self.acquire_image(hfw=hfw*1e-6)

                        utils.save_image(image, path=self.stack_dir, file_name=file_name)

                        self.experiment_data = utils.populate_experiment_data_frame(
                            data_frame=self.experiment_data,
                            microscope_state=self.microscope.microscope_state,
                            file_name=file_name,
                            timestamp=utils.current_timestamp(),
                            keys=keys)

                    # if  both q1 and q2 ARE selected, then grab multiframe image
                    elif  (self.checkBox_q1.isChecked() and self.checkBox_q2.isChecked()):
                        timestamp = utils.current_timestamp()
                        self.spinBox_horizontal_field_width.setValue(hfw)

                        """ This is a high-level procedure to acquire an image using the settings from the GUI """
                        images = self.acquire_multiple_frames(hfw=hfw * 1e-6)

                        for ii in range(len(images)):
                            file_name = '%06d_' % counter + sample_name + '_' + \
                                           str(hfw) + '_' + str(ii) + '_' + timestamp + '.tif'
                            utils.save_image(images[ii], path=self.stack_dir, file_name=file_name)

                            self.experiment_data = utils.populate_experiment_data_frame(
                                data_frame=self.experiment_data,
                                microscope_state=self.microscope.microscope_state,
                                file_name=file_name,
                                timestamp=utils.current_timestamp(),
                                keys=keys)

                    counter += 1

                self.repaint()  # update the GUI to show the progress
                QtWidgets.QApplication.processEvents()

                if self._abort_clicked_status == True:
                    print('Abort clicked')
                    self._abort_clicked_status = False  # reinitialise back to False
                    return

        _run_loop(all_settings)
        self.pushButton_acquire.setEnabled(True)
        self.pushButton_collect_stack.setEnabled(True)
        self.pushButton_abort_stack_collection.setEnabled(False)

        print('End of long scan, returning to the stored microscope state', stored_microscope_state)
        utils.save_data_frame(data_frame=self.experiment_data,
                              path=self.stack_dir,
                              file_name='summary')
        #self.microscope._restore_microscope_state(state=stored_microscope_state)


    def _abort_clicked(self):
        print('------------ abort clicked --------------')
        self.pushButton_abort_stack_collection.setEnabled(False)
        self._abort_clicked_status = True


    def _open_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(self,
                                                   "QFileDialog.getOpenFileName()",
                                                   "", "TIF files (*.tif);;TIFF files (*.tiff);;All Files (*)",
                                                   options=options)
        if file_name:
            print(file_name)
            if file_name.lower().endswith('.tif') or file_name.lower().endswith('.tiff'):
                self.image = utils.load_image(file_name)
                self.update_display(image=self.image)

            # other file format, not tiff, for example numpy array data, or txt format
            else:
                try:
                    self.image = np.loadtxt(file_name)
                    self.update_image(image=self.image)
                except:
                    self.label_messages.setText('File or mode not supported')


    def _save_SEM_image(self):
        if self.current_image is not None:
            utils.save_image(self.current_image)


    def _apply_clahe(self):
        if self.image is not None:
            clipLimit = int(self.spinBox_clip_limit.value())
            tileGridSize = int(self.spinBox_tile_grid_size.value())
            self.image_mod = utils.enhance_contrast(self.image,
                                                    clipLimit=clipLimit,
                                                    tileGridSize=tileGridSize)
            self.update_display(self.image_mod)


    def _restore_image(self):
        if self.image is not None:
            self.update_display(self.image)


    def _get_all_the_HFW_to_use(self):
        selected_hfw = []
        ##################################################################################################
        field_widths = [attr for attr in dir(self) if not callable(getattr(self, attr)) and attr.startswith("doubleSpinBox_hfw")]
        self.field_widths = ['self.'+ii for ii in field_widths]
        print(self.field_widths)
        ##################################################################################################
        clicked = [attr for attr in dir(self) if not callable(getattr(self, attr)) and attr.startswith("checkBox_hfw")]
        self.clicked = ['self.'+ii for ii in clicked]
        print(self.clicked)
        ##################################################################################################
        magnifications = [attr for attr in dir(self) if
                          not callable(getattr(self, attr)) and attr.startswith("label_hfw")]
        self.magnifications = ['self.' + ii for ii in magnifications]
        ##################################################################################################
        for ii in range(len(self.field_widths)):
            print( eval( self.field_widths[ii] + '.value()' ),
                   ' - ',
                   eval( self.clicked[ii] + '.isChecked()' ),
                   ' - ',
                   eval( self.magnifications[ii] + '.text()' ) )
            selected_hfw.append( [eval(self.field_widths[ii] + '.value()'),
                                  eval(self.clicked[ii] + '.isChecked()'),
                                  eval(self.magnifications[ii] + '.text()')
                                 ]
                                )
        return selected_hfw

    def disconnect(self):
        # logging.info("Running cleanup/teardown")
        # logging.debug("Running cleanup/teardown")
        print('closing down, cleaning...')
        if self.microscope:
            self.microscope.disconnect()





def main(demo):
    app = QtWidgets.QApplication([])
    qt_app = GUIMainWindow(demo)
    app.aboutToQuit.connect(qt_app.disconnect)  # cleanup & teardown
    qt_app.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main(demo=False)

