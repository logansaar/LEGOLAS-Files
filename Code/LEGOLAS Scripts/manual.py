from core import *
import utils

import threading

import tkinter as tk
import tkinter.ttk as ttk

import tkinter.simpledialog as simpledialog
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from functools import partial
import random
from dataclasses import dataclass
import ctypes

import sv_ttk

import os
import platform

# if os.name == 'nt':
if platform.system() == 'Windows':
    # windows GUI graphic options
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
else:
    # no avaliable for linux/mac system
    pass

"""
TODO:
1. Add <<ComboboxSelected>> event to every box. 
    a. The location field should change accordingly
    b. Register values to Combo box when other new keys is entered
2. Dynamicall scale th window size based on resolution
"""

# global params
@dataclass
class Context:
    """
        This class manage all the component that would be modify in the UI
    """
    stage = None
    pH_device = None
    depo_device = None
    pi1_address = None
    pi2_address = None

@dataclass
class ConnectionManager:
    """
        This class manage all the rpyc connection
    """
    # TODO: add connection checker method

    pi1_conn = None
    pi2_conn = None

    def close(self):
        if self.pi1_conn is not None:
            self.pi1_conn.close()
        if self.pi2_conn is not None:
            self.pi2_conn.close()

    def isclosed(self):
        return {
            "pi1" : self.pi1_conn.closed if self.pi1_conn is not None else False,
            "pi2" : self.pi2_conn.closed if self.pi2_conn is not None else False,
        }

class App(threading.Thread):
    def run(self):
        self.win = tk.Tk()
        main(self.win) # this send it to mainloop
        # self.win.mainloop()

connection_manager = ConnectionManager()
context = Context()

def set_motor_coasts():
    pass

# define all the UI

def sign(i):
    return "+" if i>=0 else "-"

# all the press event

def on_press_key(event, motor, motor_state, direction):
    if not motor_state['is_on']:
        motor.start(speed=motor_state['speed']*direction)
        motor_state['is_on'] = True

def on_release_key(event, motor=None, motor_state=None):
    motor.stop()
    motor_state['is_on'] = False


def create_motor_state(stage, motor_name):
    stage._manual_state[motor_name] = {
        "is_on" : False,
        "speed" : 80
    }

    return stage._manual_state[motor_name]


def r_get_motor_pos(lbl, motor, refresh=1000):
    if motor is not None:
        pos = motor.get_position()
    else:
        pos = "NaN"
    lbl.config(text = f"{pos}")
    # lbl.after(refresh, r_get_motor_pos, lbl=lbl, motor=motor, refresh=refresh)
    lbl.after(refresh, r_get_motor_pos, lbl, motor, refresh)


def create_motor_control_pannel(master, motor, motor_state, motor_name, loc_refresh=1000):
    frame_motor_control = ttk.Frame(master)

    label_motor = ttk.Label(master=frame_motor_control, text=f"{motor_name}", font="Arial 12")
    label_motor.grid(row=0, column=0, columnspan=2, sticky="w", padx=(0, 5))
    label_motor_speed = ttk.Label(master=frame_motor_control, text="Speed: ")

    label_motor_speed.grid(row=1, column=0, sticky="w", padx=(0, 5))
    entry_motor_speed = ttk.Entry(master=frame_motor_control, width=7)
    entry_motor_speed.grid(row=1, column=1, sticky="w")
    if "speed" in motor_state:
        entry_motor_speed.delete(0, tk.END)
        entry_motor_speed.insert(0, motor_state['speed'])

    entry_motor_speed.bind("<Return>", lambda x: motor_state.update(speed=int(entry_motor_speed.get())))

    label_motor_loc = ttk.Label(master=frame_motor_control, text="Pos:")
    label_motor_loc.grid(row=2, column=0, sticky="w")
    label_motor_loc_v = ttk.Label(master=frame_motor_control, text="")
    label_motor_loc_v.grid(row=2, column=1, sticky="w")

    r_get_motor_pos(label_motor_loc_v, motor, refresh=loc_refresh)

    return frame_motor_control


def log_motor_pos(positions_map, entry_pos_name, lbl_v, motor):
    if motor is not None:
        value = motor.get_position()
        pos_name = entry_pos_name.get()
        positions_map[pos_name] = value
    else:
        value = np.nan

    lbl_v.config(text=str(value))


def goto_motor_pos(positions_map, entry_pos_name, motor):
    if motor is not None:
        pos_name = entry_pos_name.get()
        
        pos = positions_map[pos_name]
        motor_move_to_pos(
           motor=motor,
           pos=pos,
           speed=5,
           max_iter=4
        )
        # curr_pos = motor.get_position()
        # motor.run_for_degrees(pos-curr_pos, speed=5)
    else:
        pass


def log_offset(lbl_v, device):
    x_loc, y_loc = device.stage.get_XYloc()

    center=device.stage._manual_state["center"]
    device.x_offset = x_loc - center[0]
    device.y_offset = y_loc - center[1]

    lbl_v.config(text=f"({x_loc}, {y_loc})\n({device.x_offset}, {device.y_offset})")


def log_center(lbl_v, stage):
    x_loc, y_loc = stage.get_XYloc()
    stage._manual_state["center"] = [x_loc, y_loc]
    lbl_v.config(text=f"{x_loc}, {y_loc}")


def log_general_loc(general_loc_map, lbl_v, entry_loc_name, stage):
    x_loc, y_loc = stage.get_XYloc()
    loc_name = entry_loc_name.get()
    general_loc_map[loc_name] = [x_loc, y_loc]

    lbl_v.config( text="\n".join( [f"{k}: {v}" for k, v in general_loc_map.items()] ) )
    

def goto_general_loc(general_loc_map, entry_loc_name, stage):
    loc_name = entry_loc_name.get()
    x_loc, y_loc = general_loc_map[loc_name]
    stage.move_to_deg(x_degree=x_loc, y_degree=y_loc)


def devices_offset_popup(win, devices):
    pop = tk.Toplevel(win)
    pop.geometry("300x300")
    pop.title("Offset")

    frame = ttk.Frame(pop)
    btn_w = 20

    label_center = ttk.Label(frame, text="Stage Center: ")
    label_center_v = ttk.Label(frame, text="")
    btn_center = ttk.Button(frame, text="Enter", width=btn_w, command= partial(log_center, lbl_v=label_center_v, stage=devices[0].stage) )

    label_center.grid(row=0, column=0, sticky=tk.W, pady=5)
    label_center_v.grid(row=0, column=1, sticky=tk.W, pady=5)
    btn_center.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E)

    for i, d in enumerate(devices):
        label_device = ttk.Label(frame, text=f"{d.name}: ")
        label_offset = ttk.Label(frame, text="")
        btn_offset = ttk.Button(frame, text="Enter", width=btn_w, command= partial(log_offset, lbl_v=label_offset, device=d) )

        label_device.grid(row=i*2+2, column=0, sticky=tk.W, pady=5)
        label_offset.grid(row=i*2+2, column=1, sticky=tk.W, pady=5)
        btn_offset.grid(row=i*2+3, column=0, columnspan=2, sticky=tk.W+tk.E)

    frame.pack()


def device_position_map_popup(win, device, motor, device_pos_map):
    pop = tk.Toplevel(win)
    pop.geometry("300x100")
    pop.title(device.name+" Device")

    frame = ttk.Frame(pop)
    
    frame_texts = ttk.Frame(frame)
    frame_btns = ttk.Frame(frame)

    label_position = ttk.Label(frame_texts, text="Name: ")
    # label_position_name = ttk.Label(frame, text="Names required: 'full_down', 'full_up'.")
    entry_position = ttk.Combobox(frame_texts, values=["full_down", "full_up"], width=10)
    label_position_loc = ttk.Label(frame_texts, text="Location: ")
    label_position_v = ttk.Label(frame_texts, text="")
    
    btn_position = ttk.Button(
        frame_btns, text="Enter", 
        command= partial(log_motor_pos, positions_map=device_pos_map, entry_pos_name=entry_position, lbl_v=label_position_v, motor=motor) 
    )
    btn_goto_position = ttk.Button(
        frame_btns, text = "Goto",
        command = partial(goto_motor_pos, positions_map=device_pos_map, entry_pos_name=entry_position, motor=motor)
    )


    label_position.grid(row=0, column=0, sticky=tk.W)
    # label_position_name.grid(row=0, column=1)
    entry_position.grid(row=0, column=1, sticky=tk.W)
    label_position_loc.grid(row=1, column=0, sticky=tk.W, pady=5)
    label_position_v.grid(row=1, column=1, sticky=tk.W)
    btn_position.grid(row=0, column=0, sticky=tk.W+tk.E, padx=5)
    btn_goto_position.grid(row=1, column=0,  sticky=tk.W+tk.E, padx=5, pady=5)

    frame_texts.grid(row=0,column=0, columnspan=1)
    frame_btns.grid(row=0,column=1, columnspan=1)

    frame.pack(ipadx=10)    


def create_cell_map(stage, entry_cell_size):
    h, w = list(map(int, entry_cell_size.get().split(" ") ))
    stage.cell_loc_map = np.zeros( (h, w, 2))
    stage.cell_loc_map.fill(np.nan)
    stage._manual_state['cells'] = []
    stage._manual_state['cells_idx'] = []


def log_cell_loc(stage, entry_cell_loc, label_cell_loc_v):
    x_loc, y_loc = stage.get_XYloc()
    loc_ij = entry_cell_loc.get()
    loc_i, loc_j = list( map(int, loc_ij.split(" ")) )  
    stage.cell_loc_map[loc_i, loc_j] = (x_loc, y_loc)

    if "cells" in stage._manual_state:
        stage._manual_state['cells'].append([x_loc, y_loc])
    else:
        stage._manual_state['cells'] = [[x_loc, y_loc]]

    if "cells_idx" in stage._manual_state:
        stage._manual_state['cells_idx'].append([loc_i, loc_j])
    else:
        stage._manual_state['cells_idx'] = [[loc_i, loc_j]]
    label_cell_loc_v.config(text=f"{x_loc}, {y_loc}")


def goto_cell_loc(stage, entry_cell_loc):
    loc_ij = entry_cell_loc.get()
    loc_i, loc_j = list( map(int, loc_ij.split(" ")) )
    x_loc, y_loc = stage.cell_loc_map[loc_i, loc_j]
    stage.move_to_deg(x_degree=x_loc, y_degree=y_loc)


def clear_cell_loc(stage):
    stage._manual_state['cells'] = []
    stage._manual_state['cells_idx'] = []


def auto_fill_cell(stage):
    cells = stage._manual_state['cells']
    cells_idx = stage._manual_state['cells_idx']

    cells = np.array(cells)
    cells_idx = np.array(cells_idx)

    cells_order = np.argsort(
        cells_idx[:, 0] * (np.max(cells_idx[:, 1]) + 1) + cells_idx[:, 1]
    )

    cell_ul_idx = cells_idx[cells_order[0]]
    cell_ur_idx = cells_idx[cells_order[1]]
    cell_ll_idx = cells_idx[cells_order[2]]
    cell_lr_idx = cells_idx[cells_order[3]]


    cell_ul = cells[cells_order[0]]
    cell_ur = cells[cells_order[1]]
    cell_ll = cells[cells_order[2]]
    cell_lr = cells[cells_order[3]]


    d_r = ( cell_ul - cell_ll ) / ( cell_ul_idx[0] - cell_ll_idx[0] )
    d_c = ( cell_ul - cell_ur ) / ( cell_ul_idx[1] - cell_ur_idx[1] )

    for i in range(cell_ul_idx[0], cell_ll_idx[0]+1):
        for j in range(cell_ul_idx[1], cell_ur_idx[1]+1):
            stage.cell_loc_map[i, j] = (d_r * (i - cell_ul_idx[0]) ) + (d_c * (j - cell_ul_idx[1]) ) + cell_ul

    stage._manual_state['cells'] = []
    stage._manual_state['cells_idx'] = []

    return 

def show_cell_map(stage, text_v):
    cells_map = stage.cell_loc_map
    is_nan = np.isnan(cells_map)
    out=""
    for i in range(is_nan.shape[0]):
        for j in range(is_nan.shape[1]):
            try:
                out += "□ " if np.any(is_nan[i,j]) else "■ " 
            except Exception as e:
                print(is_nan[i, j])
        out += "\n"

    text_v.delete("1.0", tk.END)
    text_v.insert(tk.END, out)
       

def stage_location_map_popup(win, stage):
    pop = tk.Toplevel(win)
    pop.geometry("800x600")
    pop.title("Stage Location")

    frame_gene = ttk.Frame(pop)

    frame_gene_texts = ttk.Frame(frame_gene)
    frame_gene_btns = ttk.Frame(frame_gene)
    frame_gene_title = ttk.Frame(frame_gene)

    label_gene = ttk.Label(frame_gene_title, text="General", font="Arial 15")
    label_loc_name = ttk.Label(frame_gene_texts, text="Name: ")
    # label_loc_name = ttk.Label(pop, text="Location name required: 'clean'")
    entry_loc_name = ttk.Combobox(frame_gene_texts, values=["clean"], width=10)

    label_loc = ttk.Label(frame_gene_texts, text="Location: ")
    label_loc_v = ttk.Label(frame_gene_texts, text="")

    btn_position = ttk.Button(frame_gene_btns, text="Enter", command= partial(log_general_loc,  general_loc_map=stage.aux_loc_map, lbl_v=label_loc_v, entry_loc_name=entry_loc_name, stage=stage) )
    btn_goto_position = ttk.Button(frame_gene_btns, text="Goto", command= partial(goto_general_loc,  general_loc_map=stage.aux_loc_map, entry_loc_name=entry_loc_name, stage=stage))

    label_gene.grid(row=0, column=0, sticky="w")
    
    label_loc_name.grid(row=1, column=0, sticky="w")
    # label_loc_name.pack()
    entry_loc_name.grid(row=1, column=1, sticky="w")
    label_loc.grid(row=2, column=0, sticky="w", pady=5)
    label_loc_v.grid(row=2, column=1, sticky="w", pady=5)

    btn_position.grid(row=0, column=0, columnspan=1, sticky=tk.W+tk.E, padx=10)
    btn_goto_position.grid(row=1, column=0, columnspan=1, sticky=tk.W+tk.E, padx=10, pady=5)

    frame_gene_title.grid(row=0, column=0, sticky="w")
    frame_gene_texts.grid(row=1, column=0)
    frame_gene_btns.grid(row=1, column=1)    

    # cell
    frame_cell = ttk.Frame(pop)

    frame_cell_title = ttk.Frame(frame_cell)
    frame_cell_texts = ttk.Frame(frame_cell)
    frame_cell_btns = ttk.Frame(frame_cell)

    
    # log key location (cell_upper_left, cell_upper_right, cell_lower_left cell_upper_right)
    label_cell = ttk.Label(frame_cell_title, text="Cells", font="Arial 15")
    label_cell_size = ttk.Label(frame_cell_texts, text="Cell Size:")
    entry_cell_size = ttk.Entry(frame_cell_texts, width=10)
    btn_create_cell = ttk.Button(frame_cell_texts, text="Create", command=partial(create_cell_map, stage=stage, entry_cell_size=entry_cell_size))

    label_loc_name = ttk.Label(
        frame_cell_texts, 
        text="Key Position: ",
        # text="""log key location (cell_upper_left, cell_upper_right, cell_lower_left cell_upper_right) and press autofill.
        # Enter location '0 0' '0 m' 'n 0' and 'n m' in sequence""",
    )
    entry_cell_pos = ttk.Combobox(
        frame_cell_texts, 
        width=10,
        values=[
            '0 0',
            '0 m',
            'n 0',
            'n m',
        ]
    )

    label_loc_name_memo = ttk.Label(
        frame_cell_texts,
        text="(replace letters with values)"
        # wraplength=30,
    )
    label_cell_loc = ttk.Label(frame_cell_texts, text="Location: ")
    label_cell_loc_v = ttk.Label(frame_cell_texts, text="")

    btn_loc = ttk.Button(frame_cell_btns, text="Enter", command= partial(log_cell_loc, label_cell_loc_v=label_cell_loc_v, entry_cell_loc=entry_cell_pos, stage=stage) )
    btn_auto = ttk.Button(frame_cell_btns, text="Auto Fill", command= partial(auto_fill_cell,  stage=stage) )
    btn_goto = ttk.Button(frame_cell_btns, text="Goto", command= partial(goto_cell_loc, entry_cell_loc=entry_cell_pos, stage=stage) )    
    btn_clear = ttk.Button(frame_cell_btns, text="Clear", command = partial(clear_cell_loc, stage=stage) )

    label_cell.grid(row=0, column=0, sticky=tk.W)
    
    label_cell_size.grid(row=1, column=0, sticky="w")
    entry_cell_size.grid(row=1, column=1, sticky="e")
    btn_create_cell.grid(row=2, column=0, columnspan=2, sticky=tk.W + tk.E, pady=(10, 20))

    label_loc_name.grid(row=3, column=0, sticky="w")
    entry_cell_pos.grid(row=3, column=1, sticky="e")
    label_loc_name_memo.grid(row=4, column=0, columnspan=2, sticky=tk.W + tk.E)
    label_cell_loc.grid(row=5, column=0, sticky="w", pady=5)
    label_cell_loc_v.grid(row=5, column=1, sticky="w")

    btn_loc.grid(row=0, column=0, columnspan=1, sticky=tk.W + tk.E, padx=10,)
    btn_auto.grid(row=1, column=0, columnspan=1, sticky=tk.W + tk.E, padx=10, pady=5)
    btn_goto.grid(row=2, column=0, columnspan=1, sticky=tk.W + tk.E, padx=10, pady=5)
    btn_clear.grid(row=3, column=0, columnspan=1, sticky=tk.W + tk.E, padx=10, pady=5)

    frame_cell_title.grid(row=0,column=0, columnspan=2, sticky="w")
    frame_cell_texts.grid(row=1,column=0)
    frame_cell_btns.grid(row=1,column=1)

    frame_cell_map = ttk.Frame(pop)
    text_cell_map = tk.Text(frame_cell_map, width=50)
    btn_show = ttk.Button(frame_cell_map, text="Show", command=partial(show_cell_map, stage=stage, text_v=text_cell_map))

    text_cell_map.pack()
    btn_show.pack()

    frame_gene.grid(row=0, column=0, padx=10, sticky='w')
    frame_cell.grid(row=1, column=0, padx=10, sticky='w')
    frame_cell_map.grid(row=0, rowspan=2, column=1, padx=10, sticky='w')


def log_deposition_volume(depo_device, entry_weight, entry_vwr, lbl_v):
    pos = depo_device.motor_V.get_position()
    weight = float(entry_weight.get())
    ratio = float(entry_vwr.get())
    volume = weight * ratio
    depo_device.vol_deg_map[volume] = pos
    lbl_v.config(text=f"{pos}")


def clear_deposition_volume(depo_device):
    depo_device.vol_deg_map = {}


def depo_volumn_map_popup(win, depo_device):
    pop = tk.Toplevel(win)
    pop.geometry("400x300")
    pop.title("Volume")

    frame = ttk.Frame(pop)
    label_volume_cali = ttk.Label(frame, text="Volume Map", font="Arial 15")
    label_volume_cali_memo = ttk.Label(frame, text="Use mannual control to grab some liquid")
    label_weight = ttk.Label(frame, text="Weight: ")
    entry_weight = ttk.Entry(frame)
    label_vwr = ttk.Label(frame, text="V/W: ")
    entry_vwr = ttk.Entry(frame)

    label_pos = ttk.Label(frame, text="Pos: ")
    label_pos_v = ttk.Label(frame)
    btn_log_volume = ttk.Button(frame, text="Enter", command=partial(log_deposition_volume, depo_device=depo_device, entry_weight=entry_weight, entry_vwr=entry_vwr, lbl_v=label_pos_v))
    btn_clear_volume = ttk.Button(frame, text="Clear", command=partial(clear_deposition_volume, depo_device=depo_device))
    label_volume_cali.grid(row=0, column=0, sticky='w')
    label_volume_cali_memo.grid(row=1, column=0, columnspan=2, sticky='w')
    label_weight.grid(row=2, column=0, sticky='w')
    entry_weight.grid(row=2, column=1, sticky='w')
    label_vwr.grid(row=3, column=0, sticky='w')
    entry_vwr.grid(row=3, column=1, sticky='w')
    label_pos.grid(row=4, column=0, sticky='w', pady=5)
    label_pos_v.grid(row=4, column=1, sticky='w')

    btn_log_volume.grid(row=5, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
    btn_clear_volume.grid(row=6, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

    frame.pack(ipadx=10, ipady=10)

def home_stage(stage, entry_x_offset, entry_y_offset, lbl_xs, lbl_ys):
    stage.home_x_offset = int(entry_x_offset.get())
    stage.home_y_offset = int(entry_y_offset.get())
    stage.home()

    lbl_xs.config(text=str(stage.x_start))
    lbl_ys.config(text=str(stage.y_start))

def home_popup(win, stage):
    pop = tk.Toplevel(win)
    pop.geometry("300x200")
    pop.title("Home")

    frame = tk.Frame(pop)

    label_x_offset = ttk.Label(frame, text="x offset: ")
    label_y_offset = ttk.Label(frame, text="y offset: ")
    label_x_start = ttk.Label(frame, text="x start: ")
    label_y_start = ttk.Label(frame, text="y start: ")
    label_x_start_v = ttk.Label(frame, text="")
    label_y_start_v = ttk.Label(frame, text="")

    entry_x_offset = ttk.Entry(frame, width=10)
    entry_y_offset = ttk.Entry(frame, width=10)

    if stage.home_y_offset is not None and stage.home_x_offset is not None:
        entry_x_offset.delete(0, tk.END)
        entry_x_offset.insert(0, f"{stage.home_x_offset}")
        entry_y_offset.delete(0, tk.END)
        entry_y_offset.insert(0, f"{stage.home_y_offset}")

    btn_home = ttk.Button(frame, text="home", command=partial(
        home_stage, stage=stage, 
        entry_x_offset = entry_x_offset,
        entry_y_offset = entry_y_offset,
        lbl_xs = label_x_start_v,
        lbl_ys = label_y_start_v
    ))

    label_x_offset.grid(row=0, column=0, sticky="w")
    entry_x_offset.grid(row=0, column=1, sticky="w")
    label_y_offset.grid(row=1, column=0, sticky="w")
    entry_y_offset.grid(row=1, column=1, sticky="w")
    label_x_start.grid(row=2, column=0, sticky="w", pady=5)
    label_x_start_v.grid(row=2, column=1, sticky="w")
    label_y_start.grid(row=3, column=0, sticky="w", pady=5)
    label_y_start_v.grid(row=3, column=1, sticky="w")
    btn_home.grid(row=4, column=0, columnspan=2, sticky=tk.W + tk.E)
    frame.pack(ipadx=10)


def manual_stage(window, context):
# def manual_stage(stage, pH_device, depo_device):
    """
        main manual UI
    """
    stage = context.stage
    pH_device = context.pH_device
    depo_device = context.depo_device

    try:
        ( motor_X, motor_X_state,
        motor_Y, motor_Y_state,
        motor_pH, motor_pH_state,
        motor_S, motor_S_state,
            motor_V, motor_V_state) = create_motors_manual_state(stage)
    except Exception as e:
        ( motor_X, motor_X_state,
        motor_Y, motor_Y_state,
        motor_pH, motor_pH_state,
        motor_S, motor_S_state,
            motor_V, motor_V_state) = [None] * 10

    # window = tk.Tk()
    # window.geometry("500x350")
    # style = ttk.Style(window)
    # style.theme_use("vista")
    # sv_ttk.set_theme('dark')
# 
    # window.tk.call('tk', 'scaling', 2.0)

    blocking=True
    # mannual frame
    frame_man = ttk.Frame(window, relief=tk.FLAT, borderwidth=1)

    window.bind("<Control-m>", lambda x: frame_man.focus())

    frame_man.bind("<KeyPress-Left>", partial(on_press_key, direction=-1, motor=motor_X, motor_state=motor_X_state))
    frame_man.bind("<KeyPress-Right>", partial(on_press_key, direction=1, motor=motor_X, motor_state=motor_X_state))
    frame_man.bind("<KeyRelease-Left>", partial(on_release_key, motor=motor_X, motor_state=motor_X_state))
    frame_man.bind("<KeyRelease-Right>", partial(on_release_key, motor=motor_X, motor_state=motor_X_state))

    frame_man.bind("<KeyPress-Up>", partial(on_press_key, direction=-1, motor=motor_Y, motor_state=motor_Y_state))
    frame_man.bind("<KeyPress-Down>", partial(on_press_key, direction=1, motor=motor_Y, motor_state=motor_Y_state))
    frame_man.bind("<KeyRelease-Up>", partial(on_release_key, motor=motor_Y, motor_state=motor_Y_state))
    frame_man.bind("<KeyRelease-Down>", partial(on_release_key, motor=motor_Y, motor_state=motor_Y_state))

    frame_man.bind("<KeyPress-1>", partial(on_press_key, direction=-1, motor=motor_pH, motor_state=motor_pH_state))
    frame_man.bind("<KeyPress-2>", partial(on_press_key, direction=1, motor=motor_pH, motor_state=motor_pH_state))
    frame_man.bind("<KeyRelease-1>", partial(on_release_key, motor=motor_pH, motor_state=motor_pH_state))
    frame_man.bind("<KeyRelease-2>", partial(on_release_key, motor=motor_pH, motor_state=motor_pH_state))

    frame_man.bind("<KeyPress-q>", partial(on_press_key, direction=-1, motor=motor_S, motor_state=motor_S_state))
    frame_man.bind("<KeyPress-w>", partial(on_press_key, direction=1, motor=motor_S, motor_state=motor_S_state))
    frame_man.bind("<KeyRelease-q>", partial(on_release_key, motor=motor_S, motor_state=motor_S_state))
    frame_man.bind("<KeyRelease-w>", partial(on_release_key, motor=motor_S, motor_state=motor_S_state))

    frame_man.bind("<KeyPress-e>", partial(on_press_key, direction=-1, motor=motor_V, motor_state=motor_V_state))
    frame_man.bind("<KeyPress-r>", partial(on_press_key, direction=1, motor=motor_V, motor_state=motor_V_state))
    frame_man.bind("<KeyRelease-e>", partial(on_release_key, motor=motor_V, motor_state=motor_V_state))
    frame_man.bind("<KeyRelease-r>", partial(on_release_key, motor=motor_V, motor_state=motor_V_state))

    label_ctrl = ttk.Label(frame_man, text="Manual Mode (ctrl+M)", font='Arial 17')
    label_ctrl.bind("<Button-1>", lambda x : frame_man.focus())
    # label_ctrl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    label_ctrl.grid(row=0, column=0, columnspan=2)

    frame_man.focus()
    frame_man.grid(row=0, column=0, sticky="w", pady=(10,10), padx=10)

    # Motor Controls
    frame_controls = ttk.Frame(window, relief=tk.FLAT, borderwidth=1)

    label_ctrls_title = ttk.Label(frame_controls, text="Motors", font="Arial 14")

    frame_x_control = create_motor_control_pannel(frame_controls, motor=motor_X, motor_state=motor_X_state, motor_name="Stage X", loc_refresh=5000)
    frame_y_control = create_motor_control_pannel(frame_controls, motor=motor_Y, motor_state=motor_Y_state, motor_name="Stage Y", loc_refresh=5000)

    frame_pH_control = create_motor_control_pannel(frame_controls, motor=motor_pH, motor_state=motor_pH_state, motor_name="pH Z", loc_refresh=5000)
    frame_S_control = create_motor_control_pannel(frame_controls, motor=motor_S, motor_state=motor_S_state, motor_name="Syringe Z", loc_refresh=5000)
    frame_V_control = create_motor_control_pannel(frame_controls, motor=motor_V, motor_state=motor_V_state, motor_name="Syringe Vol", loc_refresh=5000)

    label_ctrls_title.grid(row=0, column=0, columnspan=3, sticky='w')

    frame_x_control.grid(row=1, column=0, padx=4, pady=(0, 7))
    frame_y_control.grid(row=1, column=1, padx=4, pady=(0, 7))
    frame_pH_control.grid(row=1, column=2, padx=4, pady=(0, 7))
    frame_S_control.grid(row=2, column=0, padx=4, pady=(0, 7))
    frame_V_control.grid(row=2, column=1, padx=4, pady=(0, 7))

    frame_controls.grid(row=1, column=0, sticky="w", pady=(10, 10), padx=10)

    # all the calibration button here
    # use pop up to log position
    width_btn = 12
    
    frame_cali = ttk.Frame(window, relief=tk.FLAT, borderwidth=1)
    label_cali = ttk.Label(frame_cali, text="Calibrations", font="Arial 14")
    button_pH_cali = ttk.Button(frame_cali, text="pH device", width=width_btn, command=partial(device_position_map_popup, win=window, device=pH_device, motor=pH_device.motor_pH, device_pos_map=pH_device.pH_positions))
    button_depo_cali = ttk.Button(frame_cali, text="depo device", width=width_btn, command=partial(device_position_map_popup, win=window, device=depo_device, motor=depo_device.motor_S, device_pos_map=depo_device.s_positions))
    button_device_offset = ttk.Button(frame_cali, text="device offset", width=width_btn, command=partial(devices_offset_popup, win=window, devices=[pH_device, depo_device]))
    button_stage_cali = ttk.Button(frame_cali, text="stage", width=width_btn, command=partial(stage_location_map_popup, win=window, stage=stage))
    button_depo_volume_cali = ttk.Button(frame_cali, text="depo volume", width=width_btn, command=partial(depo_volumn_map_popup, win=window, depo_device=depo_device))
    button_home = ttk.Button(frame_cali, text="home", width=width_btn, command=partial(home_popup, win=window, stage=stage))

    label_cali.grid(row=0, column=0, columnspan=4, sticky=tk.W+tk.E)

    padx_btn = 2

    button_home.grid(row=1, column=0, sticky="w", padx=padx_btn)
    button_pH_cali.grid(row=1, column=1, sticky="w", padx=padx_btn)
    button_depo_cali.grid(row=1, column=2, sticky="w", padx=padx_btn)
    button_device_offset.grid(row=1, column=3, sticky="w", padx=padx_btn)
    button_stage_cali.grid(row=2, column=0, sticky="w", padx=padx_btn)
    button_depo_volume_cali.grid(row=2, column=1, sticky="w", padx=padx_btn)

    frame_cali.grid(row=2, column=0, sticky="w", pady=(10, 10), padx=10,)

    menubar = tk.Menu(window)
    filemenu = tk.Menu(menubar)
    menubar.add_cascade(label="File", menu=filemenu)
    filemenu.add_command(label="Export", command=partial(export_config, win=window))

    # filemenu = tk.Menu(menubar, tearoff=0)
    # menubar.add_cascade(label="File", menu=filemenu)
    # filemenu.add_command(label="Export", command=partial(export_config, stage=stage, pH_device=pH_device, depo_device=depo_device))
    window.config(menu=menubar)

    window.mainloop()


def create_motors_manual_state(stage):
    motor_X = stage.motor_X
    motor_X_state = create_motor_state(stage, "x")
    motor_Y = stage.motor_Y
    motor_Y_state = create_motor_state(stage, "y")

    pH_device = stage.get_device("pH")
    motor_pH = pH_device.motor_pH
    motor_pH_state = create_motor_state(stage, "pH")

    depo_device = stage.get_device("depo")
    motor_S = depo_device.motor_S
    motor_S_state = create_motor_state(stage, "S")

    motor_V = depo_device.motor_V
    motor_V_state = create_motor_state(stage, "V")

    return motor_X, motor_X_state, motor_Y, motor_Y_state, motor_pH, motor_pH_state, motor_S, motor_S_state, motor_V, motor_V_state

def reset_pis_server(win, frame):
    host_1 = simpledialog.askstring("Input", "Pi1 IP address", parent=win)
    host_1 = host_1.strip()
    try:
        utils.restart_server(host=host_1)
    except Exception as e:
        messagebox.showerror("Error", f"Cannot connect to Pi1, try again.\n {e}")
        return 

    host_2 = tk.simpledialog.askstring("Input", "Pi2 IP address", parent=win)
    host_2 = host_2.strip()

    try:
        utils.restart_server(host=host_2)
    except Exception as e:
        messagebox.showerror("Error", f"Cannot connect to Pi2, try again.\n {e}")
        return 


def connect_pis(win, frame):
    global context
    global connection_manager
    
    host_1 = simpledialog.askstring("Input", "Pi1 IP address", parent=win)
    host_1 = host_1.strip()
    try:
        conn, r_buildhat1, r_serial1, r_threading1, sensor_X, motor_Y, sensor_Y, pH_serial = connect_pi1(host_1, ports_map=ports_map_pi1)
        connection_manager.pi1_conn = conn
        context.pi1_address = host_1

    except Exception as e:
        messagebox.showerror("Error", f"Cannot connect to Pi1, try again.\n {e}")
        return 

    host_2 = tk.simpledialog.askstring("Input", "Pi2 IP address", parent=win)
    host_2 = host_2.strip()
    try:
        conn, r_buildhat2, motor_X, motor_pH, motor_S, motor_V = connect_pi2(host_2, ports_map=ports_map_pi2)
        connection_manager.pi2_conn = conn
        context.pi2_address = host_2

    except Exception as e:
        messagebox.showerror("Error", f"Cannot connect to Pi2, try again.\n {e}")
        return

    context.stage = Stage(
        motor_X = motor_X,
        motor_Y = motor_Y,
        sensor_X = sensor_X,
        sensor_Y = sensor_Y,
        home_x_offset = -100, 
        home_y_offset = -100, 
        cell_loc_map = np.array([[]]),
        aux_loc_map = {}
    )

    context.depo_device = DepositionDevice(
        context.stage, 
        x_offset=None, 
        y_offset=None, 
        motor_S=motor_S, 
        motor_V=motor_V, 
        vol_deg_map={}, 
        s_positions={},
    )

    context.pH_device = pHDevice(
        context.stage, 
        x_offset=None, 
        y_offset=None, 
        motor_pH=motor_pH, 
        pH_positions={}, 
        pH_serial=pH_serial, 
        verbose=True
    )

    # context.stage.motor_Y._write(f"port {context.stage.motor_Y.port} ; coast\r")
    # context.pH_device.motor_pH._write(f"port {context.pH_device.motor_pH.port} ; coast\r")
    # context.depo_device.motor_S._write(f"port {context.depo_device.motor_S.port} ; coast\r")
    # context.depo_device.motor_V._write(f"port {context.depo_device.motor_V.port} ; coast\r")
    # context.stage.motor_X._write(f"port {context.stage.motor_X.port} ; coast\r")

    frame.destroy()
    manual_stage(win, context)


def export_config(win):
    manager = ConfigurationManager()
    global context
    manager.update_stage(context.stage)
    manager.update_device(context.pH_device)
    manager.update_device(context.depo_device)
    manager.update_global(pi1_address=context.pi1_address, pi2_address=context.pi2_address)

    path = filedialog.asksaveasfilename(parent=win,
                                    initialdir=os.getcwd(),
                                    title="Please enter the export path of the configuration file:",
                                    filetypes= [('all files', '.*'), ('yaml files', '.yaml')])

    try:
        if path is None or path == "None": raise ValueError("Path is None")
        path = Path(path)
        manager.export(folder=path.parent, config_name=path.name)
    except Exception as e:
        path = Path(os.getcwd()) / "config.yaml"
        messagebox.showinfo(title="Alert", message=f"The askfilename module currently is not compatible with {platform.system()}. {e}. The config file is saved to {path}")
        manager.export(folder=path.parent, config_name=path.name)


def load_config(win, frame):
    path = filedialog.askopenfilename(parent=win,
                                    initialdir=os.getcwd(),
                                    title="Please select the configuration file:",
                                    filetypes= [('all files', '.*'), ('yaml files', '.yaml')])
    try:
        # raise Exception("debug")
        stage, depo_device, pH_device, conn1, conn2, config = load_from_config(path)

        global context

        context.stage = stage
        context.pH_device = pH_device
        context.depo_device = depo_device
        context.pi1_address = config['global']['pi1_address']
        context.pi2_address = config['global']['pi2_address']
        
    except Exception as e:
        messagebox.showerror("Error", f"Cannot via config, check file integrity.\n Error Messge: {e}")
        return 
        # ( r_buildhat1, r_serial1, r_threading1, 
        # motor_X, sensor_X, motor_Y, sensor_Y, 
        # r_buildhat2, motor_pH, motor_S, motor_V ) = [None] * 11

        # stage = Stage(
        #     motor_X = motor_X,
        #     motor_Y = motor_Y,
        #     sensor_X = sensor_X,
        #     sensor_Y = sensor_Y,
        #     home_x_offset = -100, 
        #     home_y_offset = -100, 
        #     cell_loc_map = np.array([[]]),
        #     aux_loc_map = {}
        # )

        # depo_device = DepositionDevice(
        #     stage, 
        #     x_offset=None, 
        #     y_offset=None, 
        #     motor_S=motor_S, 
        #     motor_V=motor_V, 
        #     vol_deg_map={}, 
        #     s_positions={},
        # )

        # pH_device = pHDevice(
        #     stage, 
        #     x_offset=None, 
        #     y_offset=None, 
        #     motor_pH=motor_pH, 
        #     pH_positions={}, 
        #     pH_serial=r_serial1, 
        #     verbose=True
        # )

        # context.stage = stage
        # context.pH_device = pH_device
        # context.depo_device = depo_device
        # context.pi1_address = None
        # context.pi2_address = None

    # finally:
    frame.destroy()
    manual_stage(win, context)


    # create_motors_manual_state(context.stage)

# def ask_for_confirm():
#     while True:
#         ans = input("Okay? Y/N: ").strip().lower()
#         if ans == "y":
#             return True
#         elif ans == "n":
#             return False
#         else:
#             print("Y / N only")


# def setup_connection():
#     print("To initiate the setup we need to establish communication with two of our raspberry pis via computer networking")
#     print("Pi 1 is one of the unit that controls 4 stage motors.")
#     while True:
#         try:
#             host_1 = input("Pi 1's ip address: ").strip()
#             print("Connecting to the Pi 1's rpyc server")

#             r_buildhat1, r_serial1, r_threading1, sensor_X, motor_Y, sensor_Y = connect_pi1(host_1, ports_map=ports_map_pi1)
#             break
#         except Exception as e:
#             print(f"Connection Fail. Check WiFi and Pi 1")
#             print(e)

#     print("Pi 1 Connection established")
#     print("Pi 2 is the other unit that controls deposition and measurement devices.")

#     while True:
#         try:
#             host_2 = input("Pi 2's ip address: ").strip()
#             print("Connecting to the Pi 2's rpyc server")
#             r_buildhat2, motor_X, motor_pH, motor_S, motor_V = connect_pi2(host_2, ports_map=ports_map_pi2)
#             break
#         except Exception as e:
#             print(f"Connection Fail. Check WiFi and Pi")
#             print(e)

#     print("Pi 2 Connection established")

#     return r_buildhat1, r_serial1, r_threading1, motor_X, sensor_X, motor_Y, sensor_Y, r_buildhat2, motor_pH, motor_S, motor_V


def main(win):
    win.geometry("600x450")
    win.title("Device Calibration")
    sv_ttk.set_theme('dark')
    
    frame_init = ttk.Frame(win)

    btn_ip = ttk.Button(frame_init, text="Connect via IP", width=20, command=partial(connect_pis, win=win, frame=frame_init) ) 
    btn_config = ttk.Button(frame_init, text="Connect via Config", width=20, command=partial(load_config, win=win, frame=frame_init) )
    btn_reset = ttk.Button(frame_init, text="Reset Server", width=20, command=partial(reset_pis_server, win=win, frame=frame_init) )

    btn_ip.grid(row=0, column=0)
    btn_config.grid(row=0, column=1)
    btn_reset.grid(row=0, column=2)    

    frame_init.pack()

    win.mainloop()


if __name__ == "__main__":
    # import signal
    # import time
    win = tk.Tk()

    try:
        # app = App()
        # app.start()
        print("please do not close the GUI via the Ctrl-C")
        # while app.is_alive():
        #     try:
        #         time.sleep(0.5)
        #     except Exception as e:
        #         app.win.destroy()
        #         break        

        # def signal_handler(signal, frame):
        #     sys.stderr.write("Exiting...\n")

        #     # think only one of these is needed, not sure
        #     app.win.destroy()
        #     app.win.quit()

        # signal.signal(signal.SIGINT, signal_handler)    

        main(win)
    except KeyboardInterrupt:
        # app.win.destroy()
        win.destroy()
        print("Detect Keyboard Interrpution, safely exit the loop")
    finally:
        print("")

    # manually close all the conn connection to release the rpyc module
    # hope it would solve the port already in use issue.
    # print("set all motor to off")
    # cmd = "off"
    # context.stage.motor_Y._write(f"port {context.stage.motor_Y.port} ; {cmd}\r")
    # context.pH_device.motor_pH._write(f"port {context.pH_device.motor_pH.port} ; {cmd}\r")
    # context.depo_device.motor_S._write(f"port {context.depo_device.motor_S.port} ; {cmd}\r")
    # context.depo_device.motor_V._write(f"port {context.depo_device.motor_V.port} ; {cmd}\r")
    # context.stage.motor_X._write(f"port {context.stage.motor_X.port} ; {cmd}\r")
    # time.sleep(10)

    print("close rpyc connection")
    connection_manager.close()
    # time.sleep(10)

    print("exit")
