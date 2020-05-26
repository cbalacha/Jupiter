__author__ = "Quynh Nguyen and Bhaskar Krishnamachari"
__copyright__ = "Copyright (c) 2019, Autonomous Networks Research Group. All rights reserved."
__license__ = "GPL"
__version__ = "3.0"

import sys
sys.path.append("../")
import time
import os
from os import path
from multiprocessing import Process
from write_pricing_circe_service_specs import *
from write_pricing_circe_specs import *
import yaml
from kubernetes import client, config
from pprint import *
import jupiter_config
from utilities import *

import sys, json
sys.path.append("../")
import logging
from pathlib import Path

from k8s_sink_scheduler import *
from k8s_stream_scheduler import *

logging.basicConfig(level = logging.DEBUG)


def write_file(filename,message):
    with open(filename,'a') as f:
        f.write(message)


def check_status_circe_controller(dag,app_name):
    """
    This function logging.debugs out all the tasks that are not running.
    If all the tasks are running: return ``True``; else return ``False``.
    """

    jupiter_config.set_globals()

    sys.path.append(jupiter_config.CIRCE_PATH)
    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE


    # We have defined the namespace for deployments in jupiter_config

    # Get proper handles or pointers to the k8-python tool to call different functions.
    v1_delete_options = client.V1DeleteOptions()
    core_v1_api = client.CoreV1Api()

    result = True
    for key, value in dag.items():
        # First check if there is a deployment existing with
        # the name = key in the respective namespac    # Check if there is a replicaset running by using the label app={key}
        # The label of kubernets are used to identify replicaset associate to each task
        label = "app="+ app_name+'-' + key

        resp = None

        resp = core_v1_api.list_namespaced_pod(namespace, label_selector = label)
        # if a pod is running just delete it
        if resp.items:
            a=resp.items[0]
            if a.status.phase != "Running":
                logging.debug("Pod Not Running %s", key)
                result = False

            # logging.debug("Pod Deleted. status='%s'" % str(del_resp_2.status))

    if result:
        logging.debug("All the task controllers GOOOOO!!")
    else:
        logging.debug("Wait before trying again!!!!")

    return result

def check_status_circe_computing(app_name):
    """
    This function logging.debugs out all the tasks that are not running.
    If all the tasks are running: return ``True``; else return ``False``.
    """

    jupiter_config.set_globals()

    path1 = jupiter_config.HERE + 'nodes.txt'
    nodes, homes = utilities.k8s_get_nodes_worker(path1)

    sys.path.append(jupiter_config.CIRCE_PATH)
    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE


    # We have defined the namespace for deployments in jupiter_config

    # Get proper handles or pointers to the k8-python tool to call different functions.
    k8s_apps_v1 = client.AppsV1Api()
    v1_delete_options = client.V1DeleteOptions()
    core_v1_api = client.CoreV1Api()

    result = True
    for key in nodes:
        # First check if there is a deployment existing with
        # the name = key in the respective namespac    # Check if there is a replicaset running by using the label app={key}
        # The label of kubernets are used to identify replicaset associate to each task
        label = "app=" + app_name+'-'+ key 

        resp = None

        resp = core_v1_api.list_namespaced_pod(namespace, label_selector = label)
        # if a pod is running just delete it
        if resp.items:
            a=resp.items[0]
            if a.status.phase != "Running":
                logging.debug("Pod Not Running %s", key)
                result = False

            # logging.debug("Pod Deleted. status='%s'" % str(del_resp_2.status))

    if result:
        logging.debug("All the computing nodes GOOOOO!!")
    else:
        logging.debug("Wait before trying again!!!!")

    return result

# if __name__ == '__main__':
def k8s_pricing_circe_scheduler(dag_info, temp_info, profiler_ips, execution_ips, app_name):
    """
    This script deploys CIRCE in the system. 
    
    Args:
        dag_info : DAG info and mapping
        temp_info : schedule information
        profiler_ips : IPs of network profilers
        execution_ips : IP of execution profilers 
        app_name (str): application name
    """
    jupiter_config.set_globals()
    
    sys.path.append(jupiter_config.CIRCE_PATH)

    global configs, taskmap, path1

    path1 = jupiter_config.HERE + 'nodes.txt'
    nodes, homes = utilities.k8s_get_nodes_worker(path1)


    #get DAG and home machine info
    first_task = dag_info[0]
    dag = dag_info[1]
    hosts = temp_info[2] 


    logging.debug('Starting to deploy pricing CIRCE')
    if jupiter_config.BOKEH == 3:
        latency_file = utilities.prepare_stat_path(nodes, homes, dag)
        start_time = time.time()
        if jupiter_config.PRICING == 1:
            msg = 'PRICEpush deploystart %f \n'%(start_time)
        elif jupiter_config.PRICING == 2:
            msg = 'PRICEevent deploystart %f \n'%(start_time)
        write_file(latency_file, msg)

    configs = json.load(open(jupiter_config.APP_PATH+ 'scripts/config.json'))
    taskmap = configs["taskname_map"]
    executionmap = configs["exec_profiler"]


    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    
    """
        We have defined the namespace for deployments in jupiter_config
    """
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE
    
    """
        Get proper handles or pointers to the k8-python tool to call different functions.
    """
    api = client.CoreV1Api()
    k8s_apps_v1 = client.AppsV1Api()
    service_ips = {}; #list of all service IPs including home and task controllers
    computing_service_ips = {}
    all_profiler_ips = ''
    all_profiler_nodes = ''
    

    logging.debug('-------- First create the home node service')
    """
        First create the home node's service.
    """

    for key in homes:
        all_profiler_ips = all_profiler_ips + ':'+ profiler_ips[key]
        all_profiler_nodes = all_profiler_nodes +':'+ key
        home_name =app_name+"-"+key
        home_body = write_pricing_circe_service_specs(name = home_name)
        ser_resp = api.create_namespaced_service(namespace, home_body)
        logging.debug("Home service created. status = '%s'" % str(ser_resp.status))

        try:
            resp = api.read_namespaced_service(home_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        service_ips[key] = resp.spec.cluster_ip

    # given that there is only one home
    service_ips_sinks = k8s_sink_scheduler(app_name,service_ips['home'])
    logging.debug('Data sinks')
    logging.debug(service_ips_sinks)
    all_sinks = ' '.join(service_ips_sinks.keys())
    all_sinks_ips = ' '.join(service_ips_sinks.values())

    """
        Iterate through the list of tasks and run the related k8 deployment, replicaset, pod, and service on the respective node.
        You can always check if a service/pod/deployment is running after running this script via kubectl command.
        E.g., 
            kubectl get svc -n "namespace name"
            kubectl get deployement -n "namespace name"
            kubectl get replicaset -n "namespace name"
            kubectl get pod -n "namespace name"
    """ 

    logging.debug('-------- Create task controllers service')
    """
        Create task controllers' service (all the tasks)
    """
   
    for key, value in dag.items():

        task = key
        """
            Generate the yaml description of the required service for each task
        """
        pod_name = app_name+"-"+task

        body = write_pricing_circe_service_specs(name = pod_name)

        # Call the Kubernetes API to create the service
        ser_resp = api.create_namespaced_service(namespace, body)
        logging.debug("Service created. status = '%s'" % str(ser_resp.status))
    
        try:
            resp = api.read_namespaced_service(pod_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        # logging.debug resp.spec.cluster_ip
        service_ips[task] = resp.spec.cluster_ip
    
    
    all_node_ips = ':'.join(service_ips.values())
    all_node = ':'.join(service_ips.keys())

    logging.debug('-------- Create computing nodes service')

    """
        Create computing nodes' service
    """

    for node in nodes:
 
        """
            Generate the yaml description of the required service for each computing node
        """

        
        pod_name = app_name+"-"+node
        body = write_pricing_circe_service_specs(name = pod_name)

        # Call the Kubernetes API to create the service
        ser_resp = api.create_namespaced_service(namespace, body)
        logging.debug("Service created. status = '%s'" % str(ser_resp.status))
    
        try:
            resp = api.read_namespaced_service(pod_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        # logging.debug resp.spec.cluster_ip
        computing_service_ips[node] = resp.spec.cluster_ip
        all_profiler_ips = all_profiler_ips + ':' + profiler_ips[node]
        all_profiler_nodes = all_profiler_nodes + ':' + node

    all_computing_ips = ':'.join(computing_service_ips.values())
    all_computing_nodes = ':'.join(computing_service_ips.keys())


    """
    Start circe
    """

    logging.debug('---------  Start computing nodes')
    """
        Start computing nodes
    """

    home_nodes = {}
    for key in homes:
        home_nodes[key] = service_ips[key]

    home_nodes_str = ' '.join('{0}:{1}'.format(key, val) for key, val in sorted(home_nodes.items()))

    logging.debug(nodes)
    for i in nodes:

        
        """
            We check whether the node is a home / master.
            We do not run the controller on the master.
        """

        """
            Generate the yaml description of the required deployment for WAVE workers
        """
        pod_name = app_name+"-"+i
        dep = write_circe_computing_specs(name = pod_name, label =  pod_name, image = jupiter_config.WORKER_COMPUTE_IMAGE,
                                         host = nodes[i][0], all_node = all_node,
                                         node_name = i,
                                         all_node_ips = all_node_ips,
                                         all_computing_nodes = all_computing_nodes,
                                         all_computing_ips = all_computing_ips,
                                         self_ip = computing_service_ips[i],
                                         profiler_ip = profiler_ips[i],
                                         all_profiler_ips = all_profiler_ips,
                                         all_profiler_nodes = all_profiler_nodes,
                                         execution_home_ip = execution_ips['home'],
                                         home_node_ip = home_nodes_str,
                                         child = jupiter_config.HOME_CHILD)
        # # Call the Kubernetes API to create the deployment
        resp = k8s_apps_v1.create_namespaced_deployment(body = dep, namespace = namespace)
        logging.debug("Deployment created. status ='%s'" % str(resp.status))


    while 1:
        if check_status_circe_computing(app_name):
            break
        time.sleep(30)
    
    logging.debug('--------- Start task controllers')
    """
        Start task controllers (DAG)
    """

    for key, value in dag.items():

        task = key
        nexthosts = ''
        next_svc = ''

        """
            We inject the host info for the child task via an environment variable valled CHILD_NODES to each pod/deployment.
            We perform it by concatenating the child-hosts via delimeter ':'
            For example if the child nodes are k8node1 and k8node2, we will set CHILD_NODES=k8node1:k8node2
            Note that the k8node1 and k8node2 in the example are the unique node ids of the kubernets cluster nodes.
        """

        inputnum = str(value[0])
        flag = str(value[1])

        for i in range(2, len(value)):
            if i != 2:
                nexthosts = nexthosts + ':'
            nexthosts = nexthosts + str(hosts.get(value[i])[0])

        for i in range(2, len(value)): 
            if i != 2:
                next_svc = next_svc + ':'
            next_svc = next_svc + str(service_ips.get(value[i]))

        pod_name = app_name+"-"+task

        if taskmap[key][1] and executionmap[key]: #DAG
            logging.debug('--------- Start task controllers DAG')
            dep = write_circe_controller_specs(flag = str(flag), inputnum = str(inputnum), name = pod_name, label = pod_name, node_name = hosts.get(task)[1],
                image = jupiter_config.WORKER_CONTROLLER_IMAGE, child = nexthosts, 
                child_ips = next_svc, host = hosts.get(task)[1], dir = '{}',
                home_node_ip = home_nodes_str,
                node_id = dag_info[2][task], own_ip = service_ips[key],
                task_name = task,
                app_name = app_name,
                app_option = jupiter_config.APP_OPTION,
                all_node = all_node,
                all_node_ips = all_node_ips,
                first_task = jupiter_config.HOME_CHILD,
                all_computing_nodes = all_computing_nodes,
                all_computing_ips = all_computing_ips)
        elif taskmap[key][1] and not executionmap[key]: #nonDAG controllers:
            logging.debug('--------- Start task controllers nonDAG')
            #Generate the yaml description of the required deployment for each task
            dep = write_circe_nondag_specs(flag = str(flag), inputnum = str(inputnum), name = pod_name, label = pod_name, node_name = hosts.get(task)[1],
                image = jupiter_config.NONDAG_CONTROLLER_IMAGE, child = nexthosts, task_name=task,
                child_ips = next_svc, host = hosts.get(task)[1], dir = '{}',
                home_node_ip = home_nodes_str,
                own_ip = service_ips[task],
                all_node = all_node,
                all_node_ips = all_node_ips,
                all_computing_nodes = all_computing_nodes,
                all_computing_ips = all_computing_ips,
                node_id = dag_info[2][key])
        else:
            logging.debug('--------- Start nonDAG workers')
            dep = write_circe_specs_non_dag_tasks(flag = str(flag), inputnum = str(inputnum), name = pod_name, label = pod_name,node_name = task,
                image = jupiter_config.NONDAG_WORKER_IMAGE, child = nexthosts,
                host = hosts.get(task)[1],
                child_ips = next_svc,
                task_name = task,
                home_node_ip = home_nodes_str,
                own_ip = service_ips[key],
                all_node = all_node,
                all_node_ips = all_node_ips,
                all_computing_nodes = all_computing_nodes,
                all_computing_ips = all_computing_ips,
                node_id = dag_info[2][key])

        resp = k8s_apps_v1.create_namespaced_deployment(body = dep, namespace = namespace)
        logging.debug("Deployment created. status = '%s'" % str(resp.status))



    while 1:
        if check_status_circe_controller(dag, app_name):
            break
        time.sleep(30)

    logging.debug('-------- Start home node')

    for key in homes:
        home_name =app_name+"-" + key
        home_dep = write_circe_home_specs(name=home_name, image = jupiter_config.PRICING_HOME_IMAGE, 
                                    label=home_name,
                                    host = jupiter_config.HOME_NODE, 
                                    child = jupiter_config.HOME_CHILD,
                                    child_ips = service_ips.get(jupiter_config.HOME_CHILD), 
                                    all_computing_nodes = all_computing_nodes,
                                    all_computing_ips = all_computing_ips,
                                    all_node = all_node,
                                    all_node_ips = all_node_ips,
                                    profiler_ip= profiler_ips[key],
                                    all_profiler_ips = all_profiler_ips,
                                    all_profiler_nodes = all_profiler_nodes,
                                    appname = app_name,
                                    appoption = jupiter_config.APP_OPTION,
                                    dir = '{}')
        
        resp = k8s_apps_v1.create_namespaced_deployment(body = home_dep, namespace = namespace)
        logging.debug("Home deployment created. status = '%s'" % str(resp.status))

    logging.debug('Starting to teardown pricing CIRCE')
    if jupiter_config.BOKEH == 3:
        latency_file = utilities.prepare_stat_path(nodes, homes, dag)
        end_time = time.time()
        if jupiter_config.PRICING == 1:
            msg = 'PRICEpush deployend %f \n'%(end_time)
        elif jupiter_config.PRICING == 2:
            msg = 'PRICEevent deployend %f \n'%(end_time)
        write_file(latency_file, msg)

def k8s_integrated_pricing_circe_scheduler(dag_info ,profiler_ips, execution_ips, app_name):
    """
    This script deploys CIRCE in the system. 
    
    Args:
        dag_info : DAG info and mapping
        profiler_ips : IPs of network profilers
        execution_ips : IP of execution profilers 
        app_name (str): application name
    """
    jupiter_config.set_globals()
    
    sys.path.append(jupiter_config.CIRCE_PATH)

    global configs, taskmap, path1

    path1 = jupiter_config.HERE + 'nodes.txt'
    nodes, homes = utilities.k8s_get_nodes_worker(path1)

    #get DAG and home machine info
    first_task = dag_info[0]
    dag = dag_info[1]

    logging.debug('Starting to deploy integrated CIRCE')
    if jupiter_config.BOKEH == 3:
        latency_file = utilities.prepare_stat_path(nodes, homes, dag)
        start_time = time.time()
        msg = 'PRICEintegrated deploystart %f \n'%(start_time)
        write_file(latency_file, msg)

    configs = json.load(open(jupiter_config.APP_PATH+ 'scripts/config.json'))
    taskmap = configs["taskname_map"]
    executionmap = configs["exec_profiler"]


    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    
    """
        We have defined the namespace for deployments in jupiter_config
    """
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE
    
    """
        Get proper handles or pointers to the k8-python tool to call different functions.
    """
    api = client.CoreV1Api()
    k8s_apps_v1 = client.AppsV1Api()

    service_ips = {}; #list of all service IPs including home and task controllers
    computing_service_ips = {}
    all_profiler_ips = ''
    all_profiler_nodes = ''
    

    logging.debug('-------- First create the home node service')
    """
        First create the home node's service.
    """

    for key in homes:
        all_profiler_ips = all_profiler_ips + ':'+ profiler_ips[key]
        all_profiler_nodes = all_profiler_nodes +':'+ key
        home_name =app_name+"-"+key
        home_body = write_pricing_circe_service_specs(name = home_name)
        ser_resp = api.create_namespaced_service(namespace, home_body)
        logging.debug("Home service created. status = '%s'" % str(ser_resp.status))

        try:
            resp = api.read_namespaced_service(home_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        service_ips[key] = resp.spec.cluster_ip

    """
        Iterate through the list of tasks and run the related k8 deployment, replicaset, pod, and service on the respective node.
        You can always check if a service/pod/deployment is running after running this script via kubectl command.
        E.g., 
            kubectl get svc -n "namespace name"
            kubectl get deployement -n "namespace name"
            kubectl get replicaset -n "namespace name"
            kubectl get pod -n "namespace name"
    """ 
    logging.debug('-------- Create computing nodes service')

    """
        Create computing nodes' service
    """

    for node in nodes:
 
        """
            Generate the yaml description of the required service for each computing node
        """

        
        pod_name = app_name+"-"+node
        body = write_pricing_circe_service_specs(name = pod_name)

        # Call the Kubernetes API to create the service
        ser_resp = api.create_namespaced_service(namespace, body)
        logging.debug("Service created. status = '%s'" % str(ser_resp.status))
    
        try:
            resp = api.read_namespaced_service(pod_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        # logging.debug resp.spec.cluster_ip
        computing_service_ips[node] = resp.spec.cluster_ip
        all_profiler_ips = all_profiler_ips + ':' + profiler_ips[node]
        all_profiler_nodes = all_profiler_nodes + ':' + node

    all_computing_ips = ':'.join(computing_service_ips.values())
    all_computing_nodes = ':'.join(computing_service_ips.keys())

    """
    Start circe
    """

    logging.debug('---------  Start computing nodes')
    """
        Start computing nodes
    """

    home_nodes = {}
    for key in homes:
        home_nodes[key] = service_ips[key]

    home_nodes_str = ' '.join('{0}:{1}'.format(key, val) for key, val in sorted(home_nodes.items()))

    for i in nodes:        
        """
            We check whether the node is a home / master.
            We do not run the controller on the master.
        """

        """
            Generate the yaml description of the required deployment for WAVE workers
        """
        pod_name = app_name+"-"+i
        dep = write_integrated_circe_computing_specs(name = pod_name, label =  pod_name, image = jupiter_config.WORKER_COMPUTE_IMAGE,
                                         host = nodes[i][0], node_name = i,
                                         appname = app_name,
                                         appoption = jupiter_config.APP_OPTION,
                                         all_computing_nodes = all_computing_nodes,
                                         all_computing_ips = all_computing_ips,
                                         self_ip = computing_service_ips[i],
                                         profiler_ip = profiler_ips[i],
                                         all_profiler_ips = all_profiler_ips,
                                         all_profiler_nodes = all_profiler_nodes,
                                         execution_home_ip = execution_ips['home'],
                                         home_node_ip = home_nodes_str,
                                         child = jupiter_config.HOME_CHILD)
        # # Call the Kubernetes API to create the deployment
        resp = k8s_apps_v1.create_namespaced_deployment(body = dep, namespace = namespace)
        logging.debug("Deployment created. status ='%s'" % str(resp.status))


    while 1:
        if check_status_circe_computing(app_name):
            break
        time.sleep(30)

    logging.debug('-------- Start home node')

    for key in homes:
        home_name =app_name+"-" + key
        home_dep = write_integrated_circe_home_specs(name=home_name,label=home_name, image = jupiter_config.PRICING_HOME_IMAGE, 
                                    host = jupiter_config.HOME_NODE, 
                                    child = jupiter_config.HOME_CHILD,
                                    child_ips = service_ips.get(jupiter_config.HOME_CHILD), 
                                    all_computing_nodes = all_computing_nodes,
                                    all_computing_ips = all_computing_ips,
                                    appname = app_name,
                                    appoption = jupiter_config.APP_OPTION,
                                    home_node_ip = home_nodes_str,
                                    profiler_ip= profiler_ips[key],
                                    all_profiler_ips = all_profiler_ips,
                                    all_profiler_nodes = all_profiler_nodes,
                                    dir = '{}')
        resp = k8s_apps_v1.create_namespaced_deployment(body = home_dep, namespace = namespace)
        logging.debug("Home deployment created. status = '%s'" % str(resp.status))

    pprint(service_ips)

    logging.debug('Successfully deploy integrated Pricing CIRCE')
    if jupiter_config.BOKEH == 3:
        end_time = time.time()
        msg = 'PRICEintegrated deployend %f \n'%(end_time)
        write_file(latency_file,msg)
        deploy_time = end_time - start_time
        logging.debug('Time to deploy WAVE '+ str(deploy_time))


def check_status_circe_controllers_decoupled(app_name):
    """Verify if all the WAVE home and workers have been deployed and UP in the system.
    """
    jupiter_config.set_globals()


    """
        This loads the node lists in use
    """
    path1 = jupiter_config.HERE + 'nodes.txt'
    nodes, homes = utilities.k8s_get_nodes_worker(path1)
    pprint(nodes)

    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE


    # We have defined the namespace for deployments in jupiter_config

    # Get proper handles or pointers to the k8-python tool to call different functions.
    v1_delete_options = client.V1DeleteOptions()
    core_v1_api = client.CoreV1Api()

    result = True
    for key in nodes:

        label = "app=%s_wave_"%(app_name)
        label = label + key
        resp = None

        resp = core_v1_api.list_namespaced_pod(namespace, label_selector = label)
        # if a pod is running just delete it
        if resp.items:
            a=resp.items[0]
            if a.status.phase != "Running":
                logging.debug("Pod Not Running", key)
                result = False

    if result:
        logging.debug("All systems GOOOOO!!")
    else:
        logging.debug("Wait before trying again!!!!")

    return result

def check_status_circe_compute_decoupled(app_name):
    """
    This function logging.debugs out all the tasks that are not running.
    If all the tasks are running: return ``True``; else return ``False``.
    """

    jupiter_config.set_globals()

    path1 = jupiter_config.HERE + 'nodes.txt'
    nodes, homes = utilities.k8s_get_nodes_worker(path1)

    sys.path.append(jupiter_config.CIRCE_PATH)
    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE


    # We have defined the namespace for deployments in jupiter_config

    # Get proper handles or pointers to the k8-python tool to call different functions.
    v1_delete_options = client.V1DeleteOptions()
    core_v1_api = client.CoreV1Api()

    result = True
    for key in nodes:
        # First check if there is a deployment existing with
        # the name = key in the respective namespac    # Check if there is a replicaset running by using the label app={key}
        # The label of kubernets are used to identify replicaset associate to each task
        label = "app=" + app_name+'-'+ key 

        resp = None

        resp = core_v1_api.list_namespaced_pod(namespace, label_selector = label)
        # if a pod is running just delete it
        if resp.items:
            a=resp.items[0]
            if a.status.phase != "Running":
                logging.debug("Pod Not Running %s", key)
                result = False

            # logging.debug("Pod Deleted. status='%s'" % str(del_resp_2.status))

    if result:
        logging.debug("All the computing nodes GOOOOO!!")
    else:
        logging.debug("Wait before trying again!!!!")

    return result




def k8s_decoupled_pricing_controller_scheduler(dag_info, profiler_ips, app_name, compute_service_ips, start_time):
    """
        Deploy WAVE in the system. 
    """
    jupiter_config.set_globals()

    """
        This loads the node list
    """
    all_profiler_ips = ''
    all_profiler_nodes = ''
    all_resources_nodes = ''
    all_resources_ips = ''
    nexthost_ips = ''
    nexthost_names = ''
    path2 = jupiter_config.HERE + 'nodes.txt'
    # nodes, homes = utilities.k8s_get_nodes_worker(path2)
    nodes, homes,datasources,datasinks = k8s_get_all_elements(path2)

    #get DAG and home machine info
    first_task = dag_info[0]
    dag = dag_info[1]

    logging.debug('-------- Add datasources profiler ips')
    for ds in datasources:
        all_profiler_nodes = all_profiler_nodes + ':' + ds
        all_profiler_ips = all_profiler_ips + ':' +   profiler_ips[ds] 


    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """    
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    
    """
        We have defined the namespace for deployments in jupiter_config
    """
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE
    
    """
        Get proper handles or pointers to the k8-python tool to call different functions.
    """
    api = client.CoreV1Api()
    k8s_apps_v1 = client.AppsV1Api()

    service_ips = {}; 

    """
        Loop through the list of nodes and run all WAVE related k8 deployment, replicaset, pods, and service.
        You can always check if a service/pod/deployment is running after running this script via kubectl command.
        E.g., 
            kubectl get svc -n "namespace name"
            kubectl get deployement -n "namespace name"
            kubectl get replicaset -n "namespace name"
            kubectl get pod -n "namespace name"
    """   
    home_name = app_name+'-controllerhome'
    home_label = app_name+'-controllerhome'
    home_body = write_decoupled_pricing_circe_service_specs(name = home_name, label = home_label)
    ser_resp = api.create_namespaced_service(namespace, home_body)
    logging.debug("Home service created. status = '%s'" % str(ser_resp.status))

    try:
        resp = api.read_namespaced_service(home_name, namespace)
    except ApiException as e:
        logging.debug("Exception Occurred")
    
    service_ips['home'] = resp.spec.cluster_ip
    home_ip = service_ips['home']

    all_profiler_nodes = all_profiler_nodes + ':' + 'home'
    all_profiler_ips = all_profiler_ips + ':' + profiler_ips['home']
    all_resources_nodes = all_resources_nodes + ':' + 'home'
    all_resources_ips = all_resources_ips + ':' + profiler_ips['home']


    logging.debug('Create controller services for the following nodes')
    logging.debug(nodes)

    for i in nodes:

        """
            Generate the yaml description of the required service for each task
        """
        all_profiler_nodes = all_profiler_nodes + ':' + i
        all_profiler_ips = all_profiler_ips + ':' + profiler_ips[i]
        all_resources_nodes = all_resources_nodes + ':' + i
        all_resources_ips = all_resources_ips + ':' + profiler_ips[i]
        if i != 'home':
            pod_name = app_name+'-controller'+i
            pod_label = app_name+'-controller'+i
            body = write_decoupled_pricing_circe_service_specs(name = pod_name, label = pod_label)

            # Call the Kubernetes API to create the service
    
            try:
                ser_resp = api.create_namespaced_service(namespace, body)
                logging.debug("Service created. status = '%s'" % str(ser_resp.status))
                logging.debug(i)
                resp = api.read_namespaced_service(pod_name, namespace)
            except ApiException as e:
                logging.debug("Exception Occurred")

            # logging.debug resp.spec.cluster_ip
            service_ips[i] = resp.spec.cluster_ip
            nexthost_ips = nexthost_ips + ':' + service_ips[i]
            nexthost_names = nexthost_names + ':' + i
            

    logging.debug('All provided network profilers for the decoupled pricing circe module')
    logging.debug(all_profiler_ips)
    logging.debug(all_profiler_nodes)

    home_profiler_ips = {}
    for key in homes:
        home_profiler_ips[key] = profiler_ips[key]

    home_profiler_str = ' '.join('{0}:{1}'.format(key, val) for key, val in sorted(home_profiler_ips.items()))

    for i in nodes:

        # logging.debug nodes[i][0]
        
        """
            We check whether the node is a home / master.
            We do not run the controller on the master.
        """
        if i != 'home':

            """
                Generate the yaml description of the required deployment for WAVE workers
            """
            pod_name = app_name+'-controller'+i
            label_name = app_name+'-controller'+i
            dep = write_decoupled_pricing_controller_worker_specs(name = pod_name, label = label_name, image = jupiter_config.WORKER_CONTROLLER_IMAGE,
                                             host = nodes[i][0], all_node = nexthost_names,
                                             all_node_ips = nexthost_ips,
                                             self_name=i,
                                             home_ip = home_ip,
                                             home_name = home_name,
                                             serv_ip = service_ips[i],
                                             profiler_ip = profiler_ips[i],
                                             child = jupiter_config.HOME_CHILD,
                                             all_profiler_ips = all_profiler_ips,
                                             all_profiler_nodes = all_profiler_nodes,
                                             home_profiler_ip = home_profiler_str,
                                             all_resources_nodes = all_resources_nodes,
                                             all_resources_ips = all_resources_ips)
            # # pprint(dep)
            # # Call the Kubernetes API to create the deployment
            resp = k8s_apps_v1.create_namespaced_deployment(body = dep, namespace = namespace)
            logging.debug("Deployment created. status ='%s'" % str(resp.status))
            


    # have to somehow make sure that the worker nodes are on and working by this time
    
    while 1:
        if check_status_circe_controllers_decoupled(app_name):
            break
        time.sleep(30)

    home_name = app_name+'-controllerhome'
    label_name = app_name+'-controllerhome'



    home_dep = write_decoupled_pricing_controller_home_specs(name = home_name, label = label_name,
                                image = jupiter_config.PRICING_HOME_CONTROLLER, 
                                host = jupiter_config.HOME_NODE, all_node = nexthost_names,
                                             all_node_ips = nexthost_ips,
                                             self_name = 'home',
                                             home_ip = home_ip,
                                             home_name = home_name,
                                             serv_ip = service_ips['home'],
                                             profiler_ip = profiler_ips['home'],
                                             all_profiler_nodes = all_profiler_nodes,
                                             all_profiler_ips = all_profiler_ips,
                                             home_profiler_ip = home_profiler_str,
                                             compute_home_ip = compute_service_ips['home'],
                                             child = jupiter_config.HOME_CHILD,
                                             app_name = app_name,
                                             app_option =jupiter_config.APP_OPTION,
                                             all_resources_nodes = all_resources_nodes,
                                             all_resources_ips = all_resources_ips)
    resp = k8s_apps_v1.create_namespaced_deployment(body = home_dep, namespace = namespace)
    logging.debug("Home deployment created. status = '%s'" % str(resp.status))

    logging.debug('Successfully deploy CIRCE dispatcher')
    if jupiter_config.BOKEH == 3:
        latency_file = utilities.prepare_stat_path(nodes, homes, dag)
        end_time = time.time()
        msg = 'CIRCE decoupled deployend %f \n'%(end_time)
        write_file(latency_file, msg)
        deploy_time = end_time - start_time
        logging.debug('Time to deploy CIRCE '+ str(deploy_time))

def k8s_decoupled_pricing_compute_scheduler(dag_info, profiler_ips, execution_ips, app_name):
    """
    This script deploys CIRCE in the system. 
    
    Args:
        dag_info : DAG info and mapping
        profiler_ips : IPs of network profilers
        execution_ips : IP of execution profilers 
        app_name (str): application name
    """
    jupiter_config.set_globals()
    
    sys.path.append(jupiter_config.CIRCE_PATH)

    global configs, taskmap, path1

    path1 = jupiter_config.HERE + 'nodes.txt'
    # nodes, homes = utilities.k8s_get_nodes_worker(path1)
    nodes, homes,datasources,datasinks = k8s_get_all_elements(path1)

    #get DAG and home machine info
    first_task = dag_info[0]
    dag = dag_info[1]

    logging.debug('Starting to deploy decoupled CIRCE dispatcher')
    start_time = time.time()
    if jupiter_config.BOKEH == 3:
        latency_file = utilities.prepare_stat_path(nodes, homes, dag)
        msg = 'CIRCE decoupled deploystart %f \n'%(start_time)
        write_file(latency_file, msg)


    configs = json.load(open(jupiter_config.APP_PATH+ 'scripts/config.json'))
    taskmap = configs["taskname_map"]
    executionmap = configs["exec_profiler"]


    """
        This loads the kubernetes instance configuration.
        In our case this is stored in admin.conf.
        You should set the config file path in the jupiter_config.py file.
    """
    config.load_kube_config(config_file = jupiter_config.KUBECONFIG_PATH)
    
    """
        We have defined the namespace for deployments in jupiter_config
    """
    namespace = jupiter_config.DEPLOYMENT_NAMESPACE
    
    """
        Get proper handles or pointers to the k8-python tool to call different functions.
    """
    api = client.CoreV1Api()
    k8s_apps_v1 = client.AppsV1Api()

    
    service_ips = {}; #list of all service IPs including home and task controllers
    computing_service_ips = {}
    all_profiler_ips = ''
    all_profiler_nodes = ''

    logging.debug('-------- Add datasources profiler ips')
    for ds in datasources:
        all_profiler_nodes = all_profiler_nodes + ':' + ds
        all_profiler_ips = all_profiler_ips + ':' +   profiler_ips[ds]  

    logging.debug('-------- First create the home node service')
    """
        First create the home node's service.
    """

    for key in homes:
        all_profiler_ips = all_profiler_ips + ':'+ profiler_ips[key]
        all_profiler_nodes = all_profiler_nodes +':'+ key
        home_name =app_name+"-"+key
        home_body = write_decoupled_pricing_circe_compute_service_specs(name = home_name)
        ser_resp = api.create_namespaced_service(namespace, home_body)
        logging.debug("Home service created. status = '%s'" % str(ser_resp.status))

        try:
            resp = api.read_namespaced_service(home_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        service_ips[key] = resp.spec.cluster_ip

    """
        Iterate through the list of tasks and run the related k8 deployment, replicaset, pod, and service on the respective node.
        You can always check if a service/pod/deployment is running after running this script via kubectl command.
        E.g., 
            kubectl get svc -n "namespace name"
            kubectl get deployement -n "namespace name"
            kubectl get replicaset -n "namespace name"
            kubectl get pod -n "namespace name"
    """ 
    logging.debug('-------- Create computing nodes service')

    """
        Create computing nodes' service
    """

    for node in nodes:
 
        """
            Generate the yaml description of the required service for each computing node
        """

        
        pod_name = app_name+"-"+node
        body = write_decoupled_pricing_circe_compute_service_specs(name = pod_name)

        # Call the Kubernetes API to create the service
        ser_resp = api.create_namespaced_service(namespace, body)
        logging.debug("Service created. status = '%s'" % str(ser_resp.status))
    
        try:
            resp = api.read_namespaced_service(pod_name, namespace)
        except ApiException as e:
            logging.debug("Exception Occurred")

        computing_service_ips[node] = resp.spec.cluster_ip
        all_profiler_ips = all_profiler_ips + ':' + profiler_ips[node]
        all_profiler_nodes = all_profiler_nodes + ':' + node

    all_computing_ips = ':'.join(computing_service_ips.values())
    all_computing_nodes = ':'.join(computing_service_ips.keys())

    logging.debug('Checking network profilers')
    logging.debug(all_profiler_nodes)
    logging.debug(all_profiler_ips)



    """
    Start circe
    """

    logging.debug('---------  Start computing nodes')
    """
        Start computing nodes
    """

    home_nodes = {}
    for key in homes:
        home_nodes[key] = service_ips[key]

    home_nodes_str = ' '.join('{0}:{1}'.format(key, val) for key, val in sorted(home_nodes.items()))

    for i in nodes:
        
        """
            We check whether the node is a home / master.
            We do not run the controller on the master.
        """

        """
            Generate the yaml description of the required deployment for WAVE workers
        """
        pod_name = app_name+"-"+i
        dep = write_decoupled_circe_compute_worker_specs(name = pod_name, label =  pod_name, image = jupiter_config.WORKER_COMPUTE_IMAGE,
                                         host = nodes[i][0], node_name = i,
                                         # all_node = all_node,
                                         # all_node_ips = all_node_ips,
                                         all_computing_nodes = all_computing_nodes,
                                         all_computing_ips = all_computing_ips,
                                         self_ip = computing_service_ips[i],
                                         profiler_ip = profiler_ips[i],
                                         all_profiler_ips = all_profiler_ips,
                                         all_profiler_nodes = all_profiler_nodes,
                                         execution_home_ip = execution_ips['home'],
                                         home_node_ip = home_nodes_str,
                                         child = jupiter_config.HOME_CHILD)
        #pprint(dep)
        # # Call the Kubernetes API to create the deployment
        resp = k8s_apps_v1.create_namespaced_deployment(body = dep, namespace = namespace)
        logging.debug("Deployment created. status ='%s'" % str(resp.status))


    while 1:
        if check_status_circe_compute_decoupled(app_name):
            break
        time.sleep(30)

    logging.debug('-------- Start home node')

    for key in homes:
        home_name =app_name+"-" + key
        home_dep = write_decoupled_circe_compute_home_specs(name=home_name,label=home_name, image = jupiter_config.PRICING_HOME_COMPUTE, 
                                    host = jupiter_config.HOME_NODE, 
                                    child = jupiter_config.HOME_CHILD,
                                    child_ips = service_ips.get(jupiter_config.HOME_CHILD), 
                                    all_computing_nodes = all_computing_nodes,
                                    all_computing_ips = all_computing_ips,
                                    appname = app_name,
                                    appoption = jupiter_config.APP_OPTION,
                                    home_node_ip = home_nodes_str,
                                    profiler_ip= profiler_ips[key],
                                    all_profiler_ips = all_profiler_ips,
                                    all_profiler_nodes = all_profiler_nodes,
                                    dir = '{}')
        resp = k8s_apps_v1.create_namespaced_deployment(body = home_dep, namespace = namespace)
        logging.debug("Home deployment created. status = '%s'" % str(resp.status))

    pprint(service_ips)

    return service_ips, start_time

def k8s_decoupled_pricing_circe_scheduler(dag_info , profiler_ips, execution_ips,app_name):
    compute_service_ips, start_time = k8s_decoupled_pricing_compute_scheduler(dag_info , profiler_ips, execution_ips, app_name)
    k8s_decoupled_pricing_controller_scheduler(dag_info, profiler_ips, app_name, compute_service_ips, start_time)
    
