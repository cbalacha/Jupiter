# Bunch of import statements
import os
import shutil
from PIL import Image
# import numpy as np
#KRishna
from multiprocessing import Process, Manager
from flask import Flask, request
import configparser
import urllib
import logging
import time
import multiprocessing
from multiprocessing import Process, Manager
#Krishna

"""
Task for master encoder node.
1) Takes as input multiple image files and creates a collage image file. It is ideal to have 9 different inputs to create one collage image. 
2) Sends the image files to ResNet or Collage task folders downstream.
"""
### create a collage image and write to a file

#KRishna
app = Flask(__name__)
global logging
logging.basicConfig(level = logging.DEBUG)
### NOTETOQUYNH: Need to set the below
### store class node tasks ip/port, store class node paths




store_class_tasks_paths_dict = {}
### May be need to use job ids to tackle issues coming from queuing/slowdowns
global manager, tasks_to_images_dict
manager = Manager()
tasks_to_images_dict = manager.dict()

INI_PATH = 'jupiter_config.ini'
config = configparser.ConfigParser()
config.read(INI_PATH)

global FLASK_DOCKER, FLASK_SVC, num_retries, ssh_port, username, password
FLASK_DOCKER = int(config['PORT']['FLASK_DOCKER'])
FLASK_SVC   = int(config['PORT']['FLASK_SVC'])
num_retries = int(config['OTHER']['SSH_RETRY_NUM'])
ssh_port    = int(config['PORT']['SSH_SVC'])
username    = config['AUTH']['USERNAME']
password    = config['AUTH']['PASSWORD']

global all_nodes, all_nodes_ips, map_nodes_ip, master_node_port
all_nodes = os.environ["ALL_NODES"].split(":")
all_nodes_ips = os.environ["ALL_NODES_IPS"].split(":") 
logging.debug(all_nodes)
map_nodes_ip = dict(zip(all_nodes, all_nodes_ips))
store_class_list = ['storeclass1','storeclass2']

store_class_tasks_dict = {}
store_class_tasks_dict[555] = "storeclass1"
store_class_tasks_dict[779] = "storeclass2"
store_class_tasks_dict[270] = "storeclass3"
store_class_tasks_dict[276] = "storeclass4"
store_class_tasks_dict[278] = "storeclass5"
store_class_tasks_dict[283] = "storeclass6"
store_class_tasks_dict[288] = "storeclass7"
store_class_tasks_dict[291] = "storeclass8"
store_class_tasks_dict[292] = "storeclass9"
store_class_tasks_dict[295] = "storeclass10"
store_class_tasks_dict[298] = "storeclass11"
store_class_tasks_dict[340] = "storeclass12"
store_class_tasks_dict[341] = "storeclass13"
store_class_tasks_dict[344] = "storeclass14"
store_class_tasks_dict[345] = "storeclass15"
store_class_tasks_dict[346] = "storeclass16"
store_class_tasks_dict[348] = "storeclass17"
store_class_tasks_dict[352] = "storeclass18"
store_class_tasks_dict[354] = "storeclass19"
store_class_tasks_dict[360] = "storeclass20"





def transfer_data_scp(ID,user,pword,source, destination):
    """Transfer data using SCP
    
    Args:
        ID (str): destination ID
        user (str): username
        pword (str): password
        source (str): source file path
        destination (str): destination file path
    """
    #Keep retrying in case the containers are still building/booting up on
    #the child nodes.
    retry = 0
    ts = -1
    while retry < num_retries:
        try:
            logging.debug(map_nodes_ip)
            nodeIP = map_nodes_ip[ID]
            logging.debug(nodeIP)
            cmd = "sshpass -p %s scp -P %s -o StrictHostKeyChecking=no -r %s %s@%s:%s" % (pword, ssh_port, source, user, nodeIP, destination)
            logging.debug(cmd)
            os.system(cmd)
            logging.debug('data transfer complete\n')
            break
        except Exception as e:
            logging.debug('SSH Connection refused or File transfer failed, will retry in 2 seconds')
            logging.debug(e)
            time.sleep(2)
            retry += 1
    if retry == num_retries:
        s = "{:<10} {:<10} {:<10} {:<10} \n".format(node_name,transfer_type,source,ts)
        runtime_sender_log.write(s)
        runtime_sender_log.flush()

def recv_missing_from_decoder_task():
    """
    Receive information on slow/missing resnet tasks from the decoder task
    Forward the images to corresonding destination storage nodes
    Raises:
        Exception: failed processing in Flask
    """
    global store_class_tasks_node_port_dict
    global tasks_to_images_dict
    try:
        missing_resnet_tasks_str = request.args.get('missing_resnet_tasks')
        class_predictions_str = request.args.get('class_predictions')
        missing_resnet_tasks = missing_resnet_tasks_str.split(" ")
        class_predictions = class_predictions_str.split(" ")
        logging.debug('Receive missing from decoder task:')
        for task,item in zip(missing_resnet_tasks, class_predictions):
            source_path = tasks_to_images_dict[int(task)]
            logging.debug(source_path)
            file_name = 'master_'+source_path.split('/')[3]
            logging.debug('Transfer the file')
            destination_path = os.path.join('/centralized_scheduler/input',file_name)
            logging.debug(destination_path)
            try:
                next_store_class = store_class_tasks_dict[int(item)]
                logging.debug(next_store_class)
                transfer_data_scp(next_store_class,username,password,source_path, destination_path)
            except Exception as e:
                logging.debug('The predicted item is not available in the stored class')
    except Exception as e:
        logging.debug("Bad reception or failed processing in Flask for receiving slow resnet tasks information from decoder task")
        logging.debug(e)
        return "not ok"
    return "ok"
app.add_url_rule('/recv_missing_from_decoder_task', 'recv_missing_from_decoder_task', recv_missing_from_decoder_task)

def helper_update_tasks_to_images_dict(task_num, f, pathin):
    ### Reusing the input files to the master node. NOT creating a local copy of input files.
    global tasks_to_images_dict
    # logging.debug('Update tasks to image dict')
    # logging.debug(task_num)
    source = os.path.join(pathin, f)
    tasks_to_images_dict[task_num] = source 
    # logging.debug(tasks_to_images_dict)
    return tasks_to_images_dict

class MonitorRecv(multiprocessing.Process):
    def __init__(self):
        multiprocessing.Process.__init__(self)

    def run(self):
        """
        Start Flask server
        """
        logging.debug("Flask server started")
        app.run(host='0.0.0.0', port=FLASK_DOCKER)
        global tasks_to_images_dict
        print(tasks_to_images_dict)

#KRishna

def create_collage(input_list, collage_spatial, single_spatial, single_spatial_full, w):
    collage = Image.new('RGB', (single_spatial*w,single_spatial*w))
    collage_resized = Image.new('RGB', (collage_spatial, collage_spatial))
    ### Crop boundaries. Square shaped.
    left_crop = (single_spatial_full - single_spatial)/2
    top_crop = (single_spatial_full - single_spatial)/2
    right_crop = (single_spatial_full + single_spatial)/2
    bottom_crop = (single_spatial_full + single_spatial)/2
    for j in range(w):
        for i in range(w):
            ### NOTE: Logic for creation of collage can be modified depending on latency requirements.
            ### open -> resize -> crop
            idx = j * w + i 
            im = Image.open(input_list[idx]).resize((single_spatial_full,single_spatial_full), Image.ANTIALIAS).crop((left_crop, top_crop, right_crop, bottom_crop))
            ### insert into collage. append label.
            collage.paste(im, (int(i*single_spatial), int(j*single_spatial)))
    #collage = np.asarray(collage)
    #collage = np.transpose(collage,(2,0,1))
    #collage /= 255.0
    ### write to file 
    collage_name = "collage.JPEG"
    collage_resized = collage.resize((collage_spatial, collage_spatial), Image.ANTIALIAS)
    collage_resized.save(collage_name)
    print('New collage file is created!')
    print(collage_name)
    return collage_name


def task(filelist, pathin, pathout):
    
    global tasks_to_images_dict


    logging.debug('Start the flask server: ')
    web_server = MonitorRecv()
    web_server.start()

    out_list = []# output file list. Ordered as => [collage_file, image1, image2, ...., image9]
    ### send to collage task
    ### Collage image is arranged as a rectangular grid of shape w x w 
    filelist = [filelist] if isinstance(filelist, str) else filelist  
    w = 3 
    num_images = w * w
    collage_spatial = 416
    single_spatial = 224
    single_spatial_full = 256
    input_list = []
    ### List of images that are used to create a collage image
    
    for i in range(num_images):
        ### Number of files in file list can be less than the number of images needed (9)
        file_idx = int(i % len(filelist))
        input_list.append(os.path.join(pathin, filelist[file_idx]))
        # KRishna
        tasks_to_images_dict = helper_update_tasks_to_images_dict(i, filelist[file_idx], pathin)
        #KRishna
    # print('Task to images dict')
    # print(tasks_to_images_dict)
    # print('Input list')
    # print(input_list)
    
    collage_file = create_collage(input_list, collage_spatial, single_spatial, single_spatial_full, w)
    
    shutil.copyfile(collage_file, os.path.join(pathout,"master_"+collage_file))
    print('Receive collage file:')
    ### send to collage task
    outlist = [os.path.join(pathout,"master_"+collage_file)]
    # print(outlist)
    ### send to resnet tasks
    print('Receive resnet files: ')
    for i, f in enumerate(filelist):
        idx  = i%num_images
        shutil.copyfile(os.path.join(pathin,f), os.path.join(pathout,"master_resnet"+str(idx)+'_'+f))	
        outlist.append(os.path.join(pathout,"master_resnet"+str(idx)+'_'+f))
        # print(outlist)
    return outlist

def main():
    classlist = ['fireengine', 'schoolbus', 'whitewolf', 'hyena', 'kitfox', 'persiancat', 'leopard', 'lion', 'tiger', 'americanblackbear', 'mongoose', 'zebra', 'hog', 'hippopotamus', 'ox', 'waterbuffalo', 'ram', 'impala', 'arabiancamel', 'otter']
    num = 27
    filelist = []
    for i in classlist:
        for j in range(1,num+1):
            filename = i+'_'+str(j)+'.JPEG'
            filelist.append(filename)
    # filelist = ['n03345487_10.JPEG','n03345487_108.JPEG', 'n03345487_133.JPEG','n03345487_135.JPEG','n03345487_136.JPEG','n04146614_16038.JPEG','n03345487_18.JPEG','n03345487_40.JPEG','n03345487_78.JPEG','n04146614_1.JPEG','n04146614_39.JPEG','n04146614_152.JPEG','n04146614_209.JPEG','n04146614_263.JPEG','n04146614_318.JPEG','n03345487_206.JPEG','n03345487_243.JPEG','n03345487_284.JPEG','n04146614_25.JPEG','n04146614_53.JPEG','n04146614_158.JPEG','n04146614_231.JPEG','n04146614_284.JPEG','n03345487_144.JPEG','n03345487_208.JPEG','n03345487_245.JPEG',
    #    'n03345487_311.JPEG','n04146614_27.JPEG','n04146614_69.JPEG','n04146614_186.JPEG','n04146614_232.JPEG','n04146614_295.JPEG','n03345487_163.JPEG','n03345487_209.JPEG','n03345487_267.JPEG','n03345487_317.JPEG','n04146614_30.JPEG','n04146614_79.JPEG','n04146614_187.JPEG','n04146614_237.JPEG','n04146614_309.JPEG','n03345487_192.JPEG','n03345487_210.JPEG','n03345487_279.JPEG','n03345487_328.JPEG','n04146614_36.JPEG','n04146614_84.JPEG','n04146614_199.JPEG','n04146614_245.JPEG','n04146614_312.JPEG','n03345487_205.JPEG','n03345487_241.JPEG','n03345487_282.JPEG','n03345487_334.JPEG',
    #    'n03345487_351.JPEG','n03345487_360.JPEG','n03345487_386.JPEG','n03345487_410.JPEG','n03345487_417.JPEG','n04146614_330.JPEG','n04146614_363.JPEG','n04146614_377.JPEG','n04146614_387.JPEG']
    outpath = os.path.join(os.path.dirname(__file__), 'sample_input/')
    outfile = task(filelist, outpath, outpath)
    return outfile

