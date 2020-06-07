import numpy as np
import time
import os
import cv2
import requests
import json
import configparser
from pathlib import Path
from os import listdir
import logging

logging.basicConfig(level = logging.DEBUG)
taskname = Path(__file__).stem
classnum = taskname.split('lccenc')[1]
classlist = ['fireengine', 'schoolbus', 'whitewolf', 'hyena', 'kitfox', 'persiancat', 'leopard', 'lion', 'tiger', 'americanblackbear', 'mongoose', 'zebra', 'hog', 'hippopotamus', 'ox', 'waterbuffalo', 'ram', 'impala', 'arabiancamel', 'otter']
classname = classlist[int(classnum)-1]

INI_PATH = 'jupiter_config.ini'
config = configparser.ConfigParser()
config.read(INI_PATH)

global FLASK_DOCKER, FLASK_SVC
FLASK_DOCKER = int(config['PORT']['FLASK_DOCKER'])
FLASK_SVC   = int(config['PORT']['FLASK_SVC'])
FLAG_PART2 = int(config['OTHER']['FLAG_PART2'])

global global_info_ip


def gen_Lagrange_coeffs(alpha_s,beta_s):
    U = np.zeros((len(alpha_s), len(beta_s)))
    for i in range(len(alpha_s)):
        for j in range(len(beta_s)):
            cur_beta = beta_s[j];
            den = np.prod([cur_beta - o   for o in beta_s if cur_beta != o])
            num = np.prod([alpha_s[i] - o for o in beta_s if cur_beta != o])
            U[i][j] = num/den 
    return U


def LCC_encoding(X,N,M):
    w,l = X[0].shape
    n_beta = M
    beta_s, alpha_s = range(1,1+n_beta), range(1+n_beta,N+1+n_beta)

    U = gen_Lagrange_coeffs(alpha_s,beta_s)
    X_LCC = []
    for i in range(N):
        X_zero = np.zeros(X[0].shape)
        for j in range(M):
            X_zero = X_zero + U[i][j]*X[j]
        X_LCC.append(X_zero)
    return X_LCC



def task(filelist, pathin, pathout):    
    filelist = [filelist] if isinstance(filelist, str) else filelist  
    logging.debug(filelist)

    fileid = [x.split('.')[0].split('_')[-1].split('img')[0] for x in filelist]
    logging.debug(fileid)
    filesuffix = classname+'-'+'-'.join(fileid)
    logging.debug(filesuffix)

    #snapshot_time = filelist[0].partition('_')[2].partition('.')[0]  #store the data&time info 
    
    hdr = {
            'Content-Type': 'application/json',
            'Authorization': None #not using HTTP secure
                                }
    # message for requesting job_id
    # payload = {'event': 'request id'}
    payload = {'class_image': int(classnum)}
    # address of flask server for class1 is 0.0.0.0:5000 and "post-id" is for requesting id
    try:
        # url = "http://0.0.0.0:5000/post-id"
        global_info_ip = os.environ['GLOBAL_IP']
        url = "http://%s:%s/post-id"%(global_info_ip,str(FLASK_SVC))
        print(url)
        # request job_id

        response = requests.post(url, headers = hdr, data = json.dumps(payload))
        job_id = response.json()
        print(job_id)
    except Exception as e:
        print('Possibly running on the execution profiler')
        print(e)
        job_id = 2

    # Parameters
    # L = 10 # Number of images in a data-batch
    L = 2 # Number of images in a data-batch
    M = 2 # Number of data-batches
    N = 3 # Number of workers (encoded data-batches)
    
    # Dimension of resized image
    width = 400
    height = 400
    dim = (width, height)
    
    if FLAG_PART2: #Coding Version
        #Read M batches
        Image_Batch = []
        count_file = 0
        for j in range(M):
            count = 0
            while count < L:
                print(os.path.join(pathin, filelist[count_file]))
                img = cv2.imread(os.path.join(pathin, filelist[count_file])) 
                if img is not None:
                # resize image
                    img = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
                    img = np.float64(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)) 
                    img -= img.mean()
                    img /= img.std()
                    img_w ,img_l = img.shape
                    img = img.reshape(1,img_w*img_l)
                    if count == 0:
                       Images = img
                    else:
                       Images = np.concatenate((Images,img), axis=0)  
                    count+=1
                count_file+=1
            Image_Batch.append(Images)

        # Encode M data batches to N encoded data
        En_Image_Batch = LCC_encoding(Image_Batch,N,M)

        out_list = []

        # Save each encoded data-batch i to a csv 
        for i in range(N):
            #destination = os.path.join(pathout,'lccenc'+classnum+'_score'+classnum+chr(i+97)+'_'+'job'+str(job_id)+'.csv')
            destination = os.path.join(pathout,'lccenc'+classnum+'_score'+classnum+chr(i+97)+'_'+'job'+str(job_id)+'_'+filesuffix+'.csv')
            print(destination)
            np.savetxt(destination, En_Image_Batch[i], delimiter=',')
            out_list.append(destination)
        return out_list
    
    else: # Uncoding version
        #Read M batches
        Image_Batch = []
        count_file = 0
        for j in range(N):
            count = 0
            while count < L:
                img = cv2.imread(os.path.join(pathin, filelist[count_file])) 
                if img is not None:
                # resize image
                    img = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
                    img = np.float64(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)) 
                    img -= img.mean()
                    img /= img.std()
                    img_w ,img_l = img.shape
                    img = img.reshape(1,img_w*img_l)
                    if count == 0:
                       Images = img
                    else:
                       Images = np.concatenate((Images,img), axis=0)  
                    count+=1
                count_file+=1
            Image_Batch.append(Images)

        En_Image_Batch = LCC_encoding(Image_Batch,N,N)

        out_list = []

        # Save each encoded data-batch i to a csv 
        for i in range(N):
            destination = os.path.join(pathout,'lccenc'+classnum+'_score'+classnum+chr(i+97)+'_'+'job'+str(job_id)+'_'+filesuffix+'.csv')
            np.savetxt(destination, En_Image_Batch[i], delimiter=',')
            out_list.append(destination)
        return out_list

        
def main():
    outpath = os.path.join(os.path.dirname(__file__), 'sample_input/')
    c = 'storeclass%s'%(classnum)
    filelists = [f for f in listdir(outpath) if f.startswith(c)]
    filelist = filelists[0:4] #4 files
    outfile = task(filelist, outpath, outpath)
    return outfile
    
