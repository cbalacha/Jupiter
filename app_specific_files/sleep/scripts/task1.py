import os
import time
import sys

def task(input_files, pathin, pathout):


    filelist=[]
    filelist.append(input_files)

    # single input file
    time.sleep(50)
    output_files = input_files.split('_')[0] + "_task1"
    cmd = "dd bs=1024 count=8192 </dev/urandom >%s/%s" % (pathout, output_files)
    os.system(cmd)
    return [os.path.join(pathout, output_files)]



def main():
    filelist= 'input0'
    outpath = os.path.join(os.path.dirname(__file__), "generated_files/")
    outfile = task(filelist, outpath, outpath)
    return outfile

if __name__ == '__main__':

    #Suppose the file structure is erick/detection_app/camera1_input/camera1_20190222.jpeg
    filelist= 'input0'
    task(filelist, '../sample_input', '.')


