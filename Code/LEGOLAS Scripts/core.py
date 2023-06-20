import time
import warnings
import math
import sys, os
import yaml
import pickle
from pathlib import Path
import copy

# import paramiko # for interacting over ssh
import rpyc # lets you interact with remote devices as if local

import numpy as np
from numpy.random import seed
import matplotlib
from matplotlib import pyplot as plt

from scipy.interpolate import interp1d

# import cv2 # computer vision package
# import GPy

warnings.filterwarnings('ignore')


ports_map_pi1 = {
    "motor" : {
        "y" : "C",
    },
    "force_sensor": {
        "x" : "D",
        "y" : "B",
    }
}

ports_map_pi2 = {
    "motor" : {
        "x" : "C",
        "syringe_plunger" : "D",
        "syringe_z" : "B",
        "pH_z" : "A"
    }
}

# use "python -m serial.tools.list_ports -v" to check connected port
# or "ls /dev/tty*" and find anything end with ACM
pH_serial_port = "/dev/ttyACM0"

def motor_move_to_pos(motor, pos, speed=None, max_iter=4, blocking=True):
    curr_pos = motor.get_position()
    n = 0
    while pos != curr_pos and n < max_iter:
        motor.run_for_degrees(pos - curr_pos, speed=speed, blocking=blocking)
        curr_pos = motor.get_position()
        n += 1


def connect_pi1(address, ports_map):
    # Connect to and Define Buildhats 
    conn = rpyc.classic.connect(host=address)
    r_buildhat1 = conn.modules.buildhat # XY Control
    r_serial1 = conn.modules.serial
    r_threading1 = conn.modules.threading

    #Motors and Sensors (BH1)
    sensor_X = r_buildhat1.ForceSensor(ports_map['force_sensor']['x']) # X axis sensor
    motor_Y = r_buildhat1.Motor(ports_map['motor']['y'])        # Y axis
    sensor_Y = r_buildhat1.ForceSensor(ports_map['force_sensor']['y']) # Y axis sensor
    pH_serial = r_serial1.Serial(pH_serial_port)

    # unlock the motor
    motor_Y._write(f"port {motor_Y.port} ; coast\r")

    return conn, r_buildhat1, r_serial1, r_threading1, sensor_X, motor_Y, sensor_Y, pH_serial


def connect_pi2(address, ports_map):
    conn = rpyc.classic.connect(host=address)
    r_buildhat2 = conn.modules.buildhat  # Cart Controls

    #Motors and Sensors (BH2)
    motor_X = r_buildhat2.Motor(ports_map['motor']['x'])        # X axis
    motor_pH = r_buildhat2.Motor(ports_map['motor']['pH_z'])      # pH control 
    motor_S = r_buildhat2.Motor(ports_map['motor']['syringe_z'])       # syringe control (Z axis movement)
    motor_V =  r_buildhat2.Motor(ports_map['motor']['syringe_plunger'])      # volume control (plunger)

    motor_pH._write(f"port {motor_pH.port} ; coast\r")
    motor_S._write(f"port {motor_S.port} ; coast\r")
    motor_V._write(f"port {motor_V.port} ; coast\r")
    motor_X._write(f"port {motor_X.port} ; coast\r")

    return conn, r_buildhat2, motor_X, motor_pH, motor_S, motor_V


class ConfigurationManager:
    def __init__(self) -> None:
        self.config = {}
        self._config_special = {}

        self.config['global'] = {}
        self.config['devices'] = {}
        self.config['stage'] = {}

        self._config_special['devices'] = {}
        self._config_special['stage'] = {}

    def update_global(self, **kargs):
        self.config['global'].update(kargs)

    def update_stage(self, stage):
        self.config['stage'] = stage.get_config()
        self._config_special['stage'] = stage._stored_special

    def update_device(self, device):
        config = device.get_config()
        self.config['devices'][device.name] = config
        if hasattr(device, "_stored_special"):
            self._config_special['devices']["f{device.__class__.__name__}:f{device.name}"] = device._stored_special

    def export(self, folder, config_name="config.yaml"):
        folder = Path(folder)
        folder.mkdir(exist_ok=True)
        path = folder / config_name

        export_config = copy.deepcopy(self.config)

        for k, v in self._config_special['stage'].items():
            save_method = v[0]
            export_config['stage'][k] = save_method(self.config['stage'][k], folder)
        
        if "devices" in self._config_special:
            for d, d_c in self._config_special['devices'].items():
                for k, v in d_c.items():
                    save_method = v[0]
                    d_c[k] = save_method(export_config[d][k], folder)

        with path.open("w") as f:
            yaml.dump(export_config, f)

    @staticmethod    
    def load(config_path):
        config_path = Path(config_path)
        # folder = config_path.parent
        with config_path.open("r") as f:
            config = yaml.full_load(f)
        return config


def load_from_config(config_path):
    config = ConfigurationManager.load(config_path)
    pi1_address = config['global']['pi1_address']
    (conn1, r_buildhat1, r_serial1, 
    r_threading1, sensor_X, 
    motor_Y, sensor_Y, pH_serial) = connect_pi1(pi1_address, ports_map_pi1)

    pi2_address = config['global']['pi2_address']
    (conn2, r_buildhat2, 
    motor_X, motor_pH, 
    motor_S, motor_V) = connect_pi2(pi2_address, ports_map_pi2)

    stage = Stage.from_config(
        config=config['stage'],
        motor_X = motor_X,
        motor_Y = motor_Y,
        sensor_X = sensor_X,
        sensor_Y = sensor_Y,
    ) 

    depo_device = DepositionDevice.from_config(
        config=config['devices']['depo'],
        stage=stage,
        motor_S=motor_S, 
        motor_V=motor_V, 
    )

    pH_device = pHDevice.from_config(
        config=config['devices']['pH'],
        stage=stage, 
        motor_pH= motor_pH,
        pH_serial=pH_serial, 
    )

    return stage, depo_device, pH_device, conn1, conn2, config


def save_cell_map(cell_map, path):
    cell_map = cell_map.copy()
    cell_map_path = path / "cell_map.pkl"
    with cell_map_path.open("wb") as f:
        pickle.dump(cell_map, f)
    return str(cell_map_path)


def load_cell_map(cell_map_path):
    with Path(cell_map_path).open("rb") as f:
        return pickle.load(f)

class Stage:
    _stored = ["home_x_offset", "home_y_offset", "aux_loc_map", "cell_loc_map"]
    _stored_special = {"cell_loc_map":(save_cell_map, load_cell_map)}

    def __init__(
        self,
        motor_X, 
        motor_Y, 
        sensor_X,
        sensor_Y,
        home_x_offset,
        home_y_offset,
        cell_loc_map,
        aux_loc_map
    ):
        self.registed_devices = {}
        self.motor_X = motor_X
        self.motor_Y = motor_Y

        self.sensor_X = sensor_X
        self.sensor_Y = sensor_Y
                
        self.home_x_offset = home_x_offset
        self.home_y_offset = home_y_offset
                
        self.cell_loc_map = cell_loc_map
        self.aux_loc_map = aux_loc_map
        
        self.x_start = None
        self.y_start = None

        self._manual_state = {}


    def get_config(self):
        config = {}
        for k in self._stored:
            config[k] = getattr(self, k)

        return config


    @classmethod
    def from_config(cls, config, motor_X, motor_Y,  sensor_X, sensor_Y):
        for k, v in cls._stored_special.items():
            load_method = v[1]
            config[k] = load_method(config[k])

        return cls(motor_X=motor_X, motor_Y=motor_Y, sensor_X=sensor_X, sensor_Y=sensor_Y, **config)


    def register_device(self, device, device_name):
        self.registed_devices[device_name] = device


    def get_all_device_name(self):
        return list(self.registed_devices.keys())


    def get_device(self, name):
        return self.registed_devices[name]

    # def __getattribute__(self, __name: str) -> Any:
    #     if __name in self.registed_devices:
    #         return self.registed_devices[__name]
    #     else:
    #         return super().__getattribute__(__name)

    def home(self):
        self.motor_X.start(50)
        self.sensor_X.wait_until_pressed(force = 0.02)
        self.motor_X.stop()
        self.motor_X.run_for_degrees(self.home_x_offset)
        self.motor_Y.start(30)
        self.sensor_Y.wait_until_pressed(force = 0.05)
        self.motor_Y.stop()
        self.motor_Y.run_for_degrees(self.home_y_offset)
        
        x_start = self.motor_X.get_position()
        y_start = self.motor_Y.get_position()
        
        self.x_start = x_start
        self.y_start = y_start
        
        return x_start, y_start


    def move_by_deg(self, x_degree, y_degree, device_x_offset=0, device_y_offset=0, blocking=True):
        self.motor_X.run_for_degrees(x_degree + device_x_offset, blocking=blocking)
        self.motor_Y.run_for_degrees(y_degree + device_y_offset, blocking=blocking)

        # TODO check the non-blocking code 
        # for thread in self.r_threading1.enumerate():
            # thread.join()
            # print(thread)

        
    def move_to_deg(self, x_degree, y_degree, device_x_offset=0, device_y_offset=0):
        originX_offset, originY_offset = self.get_XYloc()
        self.move_by_deg(x_degree - originX_offset , y_degree - originY_offset, device_x_offset, device_y_offset)


    def move_to_cell(self, row, col, device_x_offset=0, device_y_offset=0):
        positionX, positionY = self.cell_loc_map[row, col]
        self.move_to_deg(positionX, positionY, device_x_offset, device_y_offset)


    def move_to_loc(self, location, device_x_offset=0, device_y_offset=0):
        if isinstance(self.aux_loc_map, dict):
            positionX, positionY = self.aux_loc_map[location]
        else:
            positionX, positionY = self.aux_loc_map(location)
        self.move_to_deg(positionX, positionY, device_x_offset, device_y_offset)


    def get_XYloc(self):
        self.x_loc = self.motor_X.get_position() - self.x_start
        self.y_loc = self.motor_Y.get_position() - self.y_start
        return self.x_loc, self.y_loc

    def sanity_check(self):
        #TODO check if the map is too far away
        pass



class DeviceOnStage:
    def __init__(self, stage, x_offset, y_offset, name=""):
        self.stage = stage
        stage.register_device(self, device_name=name)
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.name=name
    
    def move_to_degree(self, x_degree, y_degree):
        self.stage.move_to_deg(x_degree, y_degree, self.x_offset, self.y_offset)
    
    def move_to_cell(self, row, col):
        self.stage.move_to_cell(row, col, self.x_offset, self.y_offset)
    
    def move_to_loc(self, location):
        self.stage.move_to_loc(location, self.x_offset, self.y_offset)

    def move_to(self, location=None, row=None, col=None, x_degree=None, y_degree=None):
        if location is not None:
            self.move_to_loc(location)
        elif row is not None and col is not None:
            self.move_to_cell(row, col)
        elif x_degree is not None and y_degree is not None:
            self.move_to_degree(x_degree, y_degree)
        else:
            pass


    def get_config(self):
        config = {}
        for k in self._stored:
            config[k] = getattr(self, k)
        return config


class DepositionDevice(DeviceOnStage):
    _stored = ["vol_deg_map", "s_positions", "x_offset", "y_offset"]
    _stored_special = {}

    def __init__(
        self, 
        stage=None, 
        x_offset=None, 
        y_offset=None, 
        motor_S=None, 
        motor_V=None, 
        vol_deg_map=None, 
        s_positions=None, 
        name=""
    ):
        name = "depo" if not name else name
        super().__init__(stage, x_offset, y_offset, name)
        self.motor_S = motor_S
        self.motor_V = motor_V
        self.vol_deg_map = vol_deg_map
        # print(self.vol_deg_map)
        self.s_positions = s_positions
        self.volume = 0
 
        self.create_interpolate_f()

    def create_interpolate_f(self):
        vol_deg_map = self.vol_deg_map
        if vol_deg_map is not None and vol_deg_map:
            vols = np.array( list(self.vol_deg_map.keys()) )
            degs = np.array( list(self.vol_deg_map.values()) )
            degs = degs - degs.min()
            self._vol_max, self._vol_min = np.max(vols), np.min(vols)
            self._vol_deg_f = interp1d(vols, degs, kind='linear', axis=-1)
            self._deg_vol_f = interp1d(degs, vols, kind='linear', axis=-1)

    def sanity_check(self):
        pos = self.motor_S.get_position()
        l, m = min(self.s_positions["full_up"], self.s_positions["full_down"]), max(self.s_positions["full_up"], self.s_positions["full_down"])
        assert  l <= pos and pos <= m

        pos = self.motor_V.get_position()
        l, m = np.min( list(self.vol_deg_map.values()) ), np.max(list(self.vol_deg_map.values()))
        assert  l <= pos and pos <= m


    @classmethod
    def from_config(cls, config, stage, motor_S, motor_V, name=""):
        return cls(stage=stage, motor_S=motor_S, motor_V=motor_V, name=name, **config)


    def to_zpos(self, pos, max_iter=4):
        pos = self.s_positions[pos]
        motor_move_to_pos(
            motor=self.motor_S,
            pos=pos,
            speed=5,
            max_iter=max_iter,
        )


    def acquire(self, vol=None, acq_degree=None, location=None, row=None, col=None, x_degree=None, y_degree=None):

        if acq_degree is None and vol is not None:
            if vol > self._vol_max:
                vol = self._vol_max
            acq_degree = self._vol_deg_f(vol)
        elif acq_degree is not None and vol is None:
            vol = self._deg_vol_f(acq_degree)
        elif acq_degree is not None and vol is not None:
            pass
        else:
            raise ValueError("vol or acq_degree must not be None at the same time")

        self.move_to(location=location, row=row, col=col, x_degree=x_degree, y_degree=y_degree)

        # if location is not None:
        #     self.move_to_loc(location)
        # elif row is not None and col is not None:
        #     self.move_to_cell(row, col)
        # elif x_degree is not None and y_degree is not None:
        #     self.move_to_degree(x_degree, y_degree)
        # else:
        #     pass
            
        # self.motor_S.run_for_degrees(-self.s_full_down)
        self.to_zpos("full_down")

        self.motor_V.run_for_degrees(acq_degree)
        self.volume += vol

        self.to_zpos("full_up")
        return self


    def deposition(self, vol=None, dep_degree=None, location=None, row=None, col=None, x_degree=None, y_degree=None):
        if dep_degree is None and vol is not None:
            if vol > self.volume:
                vol = self.volume
            dep_degree = self._vol_deg_f(vol)
        elif dep_degree is not None and vol is None:
            vol = self._deg_vol_f(dep_degree)
        elif dep_degree is not None and vol is not None:
            pass
        else:
            raise ValueError("vol or dep_degree must not be None at the same time")

        self.move_to(location=location, row=row, col=col, x_degree=x_degree, y_degree=y_degree)
        # if location is not None:
        #     self.move_to_loc(location)
        # elif row is not None and col is not None:
        #     self.move_to_cell(row, col)
        # elif x_degree is not None and y_degree is not None:
        #     self.move_to_degree(x_degree, y_degree)
        # else:
        #     pass
        
        self.motor_V.run_for_degrees(-dep_degree)
        self.volume -= vol

        return self


    def acq_dep(self, location, row, col, deg=None, vol=None):
        if deg is not None:
            self.acquire(deg, location=location)
            self.deposition(deg, row=row, col=col)
        else:
            # volumns = list(self.vol_deg_map.keys())
            # volumns = sorted(volumns)[::-1]
            residual_volume = vol
            while residual_volume > 0:
                if residual_volume > self._vol_max:
                    v = self._vol_max
                else:
                    v = residual_volume
                deg = self._vol_deg_f(v)
                self.acquire(acq_degree=deg, location=location)
                self.deposition(dep_degree=deg, row=row, col=col)
                residual_volume -= v
            
        return self


class pHDevice(DeviceOnStage):
    _stored = ["pH_positions", "verbose", "x_offset", "y_offset"]
    _stored_special = {}

    def __init__(
        self, 
        stage=None, 
        x_offset=None, 
        y_offset=None, 
        motor_pH=None, 
        pH_positions=None, 
        pH_serial=None, 
        verbose=True, 
        name=""
    ):
        name = "pH" if not name else name
        super().__init__(stage, x_offset, y_offset, name=name)
        self.motor_pH = motor_pH
        self.pH_serial = pH_serial
        self.pH_positions = pH_positions
        self.verbose = verbose

    def sanity_check(self):
        pos = self.motor_pH.get_position()
        l, m = min(self.pH_positions["full_up"], self.pH_positions["full_down"]), max(self.pH_positions["full_up"], self.pH_positions["full_down"])
        assert  l <= pos and pos <= m


    @classmethod
    def from_config(cls, config, stage, motor_pH, pH_serial, name=""):
        return cls(stage=stage, motor_pH=motor_pH, pH_serial=pH_serial, **config)


    def to_zpos(self, pos, max_iter=4):
        pos = self.pH_positions[pos]
        motor_move_to_pos(
            motor=self.motor_pH,
            pos=pos,
            speed=20,
            max_iter=max_iter,
        )


    def clean(self, wait_time=1.0):        
        shake = 30
        self.move_to_loc("clean")

        self.to_zpos("full_down")
        # self.motor_pH.run_for_degrees(self.pH_full_down)  #370 down, -370 up

        #for i in range (2):  #stir in water to clean
            #self.motor_pH.run_for_degrees(-shake)   
            #self.motor_pH.run_for_degrees(shake)

        time.sleep(wait_time)

        self.to_zpos("full_up")
        # self.motor_pH.run_for_degrees(-self.pH_full_down)
        return self


    def report_pH(self, stable_time=15):
        #read the pH from the serial monitor
        if not self.pH_serial.is_open:
            self.pH_serial.open()
        for i in range(stable_time):
            x = self.pH_serial.readline()
            try:
                x = float(x.decode().strip())
            except UnicodeDecodeError as e:
                print(f"fail to decode message from pH device. raw messsage: {x}.")                
            time.sleep(1)
            
        self.pH_serial.close()
        return x


    def pH_measure(self, stable_time, location=None, row=None, col=None, x_degree=None, y_degree=None):                               
        #encapsulating pH measurement function 
        self.move_to(location=location, row=row, col=col, x_degree=x_degree, y_degree=y_degree)
        # self.motor_pH.run_for_degrees(self.pH_full_down)
        self.to_zpos("full_down")

        shake = 30
        #for i in range (7):                         # for stirring
            #self.motor_pH.run_for_degrees(-shake)
            #self.motor_pH.run_for_degrees(shake)
        pH_value = self.report_pH(stable_time)
        # self.motor_pH.run_for_degrees(-self.pH_full_down)
        self.to_zpos("full_up")

        #for i in range (3):                         # for shaking off droplets
            #self.motor_pH.run_for_degrees(shake)
            #self.motor_pH.run_for_degrees(-shake)
        if self.verbose:
            print(f'pH is Measured as: {pH_value:.2f}', )
        return pH_value
    
def sanity_check(stage, pH_device, depo_device):
    stage.sanity_check()
    pH_device.sanity_check()
    depo_device.sanity_check()
    return True

def reset(stage, pH_device, depo_device):
    pH_device.to_zpos("full_up")
    depo_device.to_zpos("full_up")
    stage.home()
