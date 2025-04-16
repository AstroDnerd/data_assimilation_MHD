#import modules
import yt
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import warnings
import random
import sys
import time
import imageio
from IPython.display import Image
warnings.filterwarnings("ignore")
import json

from tempfile import mkstemp
from shutil import move, copymode
from os import fdopen, remove

from mpl_toolkits.axes_grid1 import AxesGrid


def make_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def animator(path_to_plots,name_of_gif):
    images = []
    filenames = list(sorted(os.listdir(path_to_plots)))
    for filename in filenames:
        images.append(imageio.imread(path_to_plots+'/'+filename))
        imageio.mimsave(path_to_plots+'/../'+name_of_gif+'.gif', images)

def run_simulation(path_to_simulation_output, restart_datadump = None, path_to_initial_conditions = None, num_processors = 8):
    if path_to_initial_conditions is not None:
        #copy initial conditions to the simulation output directory and run the simulation there
        curr_dir = os.getcwd()
        print(curr_dir)
        os.chdir(path_to_simulation_output)
        os.system("cp "+path_to_initial_conditions+" ./")
        start_time = time.time()
        os.system("mpirun -np "+str(num_processors)+" ./enzo.exe "+path_to_initial_conditions+" | tee output.txt >/dev/null 2>&1") #The last bit after output.txt is to suppress all debug output in the notebook
        end_time = time.time()
        os.system("echo 'Simulation took "+str(end_time-start_time)+" seconds' | tee -a output.txt")
        os.chdir(curr_dir)
        print("Simulation took "+str(end_time-start_time)+" seconds")
    else:
        if restart_datadump is None:
            print("provide either path to initial conditions or restart datadump")
            return 1    
        #go to the simulation output directory and run the simulation there
        curr_dir = os.getcwd()
        os.chdir(path_to_simulation_output)
        start_time = time.time()
        os.system("mpirun -np "+str(num_processors)+" ./enzo.exe -r "+restart_datadump+" | tee output.txt >/dev/null 2>&1")
        end_time = time.time()
        os.system("echo 'Simulation took "+str(end_time-start_time)+" seconds' | tee -a output.txt")
        os.chdir(curr_dir)
        print("Simulation took "+str(end_time-start_time)+" seconds")

def simulation_visualize(plot_dir, PlotType, path_to_data, coordinate, dataset_to_plot, number_of_frames,cbar_range = None, zoom_level = 1):
    #import data
    if not os.path.exists(plot_dir+PlotType):
        os.makedirs(plot_dir+PlotType)

    for frame_number in range(0,number_of_frames):
        frame_str = str(frame_number).zfill(4)
        data = yt.load(path_to_data+"/Data/DD"+frame_str+"/DD"+frame_str)
        all_data = data.all_data()
        plot = yt.ProjectionPlot(data, coordinate, dataset_to_plot, fontsize = 10)
        plot.set_cmap(dataset_to_plot, "dusk")
        plot.set_background_color(dataset_to_plot, color="black")
        plot.zoom(zoom_level)
        plot.annotate_timestamp(corner="upper_left", redshift=True, draw_inset_box=True)
        plot.annotate_scale(corner="upper_right")
        if cbar_range != None:
            plot.set_zlim(dataset_to_plot[1],cbar_range[0],cbar_range[1])
        plot.save(plot_dir+PlotType+"/DD"+frame_str+".png")
    
    animator(plot_dir+PlotType,PlotType)

def simulation_comparison(Path_to_sim_1, path_to_sim_2, observation_time, ALL_FRAMES, path_to_output_plots):
    frame_num = str(np.where(ALL_FRAMES==observation_time)[0][0]).zfill(4)
    data_1 = yt.load(Path_to_sim_1+"/Data/DD"+frame_num+"/DD"+frame_num)
    data_2 = yt.load(path_to_sim_2+"/Data/DD"+frame_num+"/DD"+frame_num)
    p1 = yt.ProjectionPlot(data_1, 'z', ('gas', 'density'), fontsize = 10)
    p1.set_zlim('density',1e-2,1e4)
    p1.annotate_timestamp(corner="upper_left", draw_inset_box=True)
    p1.annotate_scale(corner="upper_right")
    p1.set_cmap(('gas', 'density'), "dusk")
    p2 = yt.ProjectionPlot(data_2, 'z', ('gas', 'density'), fontsize = 10)
    p2.set_zlim('density',1e-2,1e4)
    p2.annotate_timestamp(corner="upper_left", draw_inset_box=True)
    p2.annotate_scale(corner="upper_right")
    p2.set_cmap(('gas', 'density'), "dusk")
    fig = plt.figure()
    grid = AxesGrid(fig,(0.075, 0.075, 0.85, 0.85), nrows_ncols=(1, 2), axes_pad=1.0, label_mode="1", share_all=True, cbar_location="right", cbar_mode="each", cbar_size="3%", cbar_pad="0%")
    i = 0
    for p in [p1,p2]:
        plot = p.plots[('gas', 'density')]
        plot.figure = fig
        plot.axes = grid[i].axes
        plot.cax = grid.cbar_axes[i]
        p.render()
        i+=1
    plt.show()
    plt.savefig(path_to_output_plots+'Comparison_DD'+str(frame_num)+'.png')
    plt.close()

def get_params(line_arr):
    pointer = []
    for i in range(len(line_arr)):
        comp_str = line_arr[i].split()
        if comp_str[0] == 'Grid':
            gridnum = int(comp_str[2])
        if comp_str[0] == 'GridDimension':
            griddim = [int(comp_str[2]), int(comp_str[3]), int(comp_str[4])]
        if comp_str[0] == 'GridLeftEdge':
            gridle = [float(comp_str[2]), float(comp_str[3]), float(comp_str[4])]
        if comp_str[0] == 'GridRightEdge':
            gridre = [float(comp_str[2]), float(comp_str[3]), float(comp_str[4])]
        if comp_str[0] == 'BaryonFileName':
            fname = comp_str[2]
        if comp_str[0] == 'Pointer:':
            pointer.append(int(comp_str[-1]))
    return gridnum, {'GridDimension': griddim, 'GridLeftEdge': gridle, 'GridRightEdge': gridre, 'BaryonFileName': fname, 'Pointers':pointer}
def read_hierarchy_file(hr_filename):
    Grid_dict = {}
    running_line_arr = []
    for line in hr_filename.readlines():
        if line == '\n' or None:
            if running_line_arr==[]:
                continue
            else:
                #add the grid to the dictionary
                gridnum, temp_dic = get_params(running_line_arr)
                Grid_dict[gridnum] = temp_dic
                running_line_arr = []
        else:
            running_line_arr.append(line)
    gridnum, temp_dic = get_params(running_line_arr)
    Grid_dict[gridnum] = temp_dic
    return Grid_dict

def edit_enzo_param_file(current_time, new_time, ANALYSIS_RUN_INITIAL_CONDITIONS, ANALYSIS_RUN, ALL_FRAMES):
    if current_time == 0:
        fpath = ANALYSIS_RUN_INITIAL_CONDITIONS
    else:
        frame_num = str(np.where(ALL_FRAMES==current_time)[0][0]).zfill(4)
        fpath = ANALYSIS_RUN +"/Data/DD"+frame_num+"/DD"+frame_num
    #Find StopTime and set it to new time
    #Create temp file
    fh, abs_path = mkstemp()
    with fdopen(fh,'w') as new_param_file:
        with open(fpath) as old_param_file:
            for line in old_param_file:
                line_arr = line.split()
                if len(line_arr)>0:
                    if line_arr[0] == 'StopTime':
                        new_param_file.write('StopTime = '+str(new_time)+' \n')
                        print('Time changed')
                    else:
                        new_param_file.write(line)
    #Copy the file permissions from the old file to the new file
    copymode(fpath, abs_path)
    #Remove original file
    remove(fpath)
    #Move new file
    move(abs_path, fpath)
    print('Parameter File updated')