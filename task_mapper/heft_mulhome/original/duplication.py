"""
----------------------------- part1: calculate duplication ----------------------------
The condition under which duplication can improve the throughput: 
possible new bottlenecks introduced in the system are less than the old one. 


Possible new bottlenecks include:

1. Copy tasks (which transfer data using bottleneck link) from src node to idle node. Don't copy all src node tasks.
   The new execution time sum of those copied tasks on the idle node cannot exceed the bottleneck time.
2. Find all nodes who has a parent task of any of the copied tasks. Since we use virtual links, 
   the links related to a new node are all idle, thus we just need to make sure 
   the new file transfer time on each link is less than the bottleneck.
3. Transfer time from new node to dst node is less than bottleneck.

----------------------------- part2: duplicate ----------------------------------------

In file cal_duplication, we choose a node and a set of tasks to duplicate on this node
This file takes the node name and tasks as input, does task graph and mapping change

- What this program does:
    1. Create K new tasks (tasks that transfer data through btnk link), map them on the selected node
    2. Add the K tasks as new child for all the parent tasks
    3. Remove the parent-child relations between tasks that communicate through btnk link
    
- Prerequisites knowledge:
    1. The mapper pod is exposed as a service where an instance of flask is running in container.
       The flask can be queried through kube proxy and return assignment, which is a hashmap like
       {"task0": "node2", "task1": "node1", "task2": "node1", "task3": "node1"}
    2. File auto_deploy_system reads configuration and node file, passes them to mapper, gets "dag" and "schedule", then CIRCE
    3. File k8s_circe_scheduler.py creates all CIRCE pods (services, deployments, replicasets). Each pod is injected
       with a env variable called CHILD_NODES, which is a pod where the child tasks run. It task node.txt and configuration.txt from 
       CIRCE home container, which are copied from code folder
    4. Each CIRCE instance has fs monitor for its input folder, wait for number of files then start processing; also fs monitor for 
       output folder, where it scp files to child input folder. Children are unaware of parents

- How to do it:
    We have to change both tasks and mapping, but CIRCE is hard-coded so that it iterates through DAG and creates a pod for each task
    For duplication, we'll create another pod which runs exactly the same task. The DAG updated by mappers can't modify the original 
    configuration file that CIRCE takes input from. In order to make minimum changes, we pass the new DAG, together with the 'assignment'
    to CIRCE through flask and kube service. For new tasks, we have to use new names, but refer to old tasks.

    Maintain all the data (task list, comp matrix etc) in the heft_dup file.

"""

"""
    this class has two main functions, namely "get_dup_node" and "duplicate"
    all the data-structures are passed into these functions by reference from file heft_dup
    this class doesn't maintain any instance level data-structures
"""
import numpy as np
import heft_dup as hd

class Duplication:
'''
    def __init__(self, links, processors, tasks, comp_cost, data, quaratic_profile, btnk_id):
        self.links = links
        self.processors = processors
        self.btnk_id = btnk_id
        self.tasks = tasks
        self.comp_cost = comp_cost
        self.data = data
        self.quaratic_profile = quaratic_profile
'''
    def get_dup_node(self, links, processors, tasks, comp_cost, data, quaratic_profile, btnk_id):
        """
        input: links and nodes, and the bottleneck link to bypass
        calculate a hashmap of candidate nodes and the max value of incurred resource takeup time
        output: best candidate node
        """
        btnk_link = self.get_link_by_id(links, btnk_id)
        btnk_time = btnk_link.time_line[-1].end
        src_proc = self.get_proc_by_id(processors, btnk_id.split('_')[0])
        dst_proc = self.get_proc_by_id(processors, btnk_id.split('_')[1])
        
        # hashmap { task number (index in the tasks list) -> processor id }
        task_to_proc = self.get_procs_by_tasks(processors)
        
        # get tasks in src proc that transfer file to dst proc
        # get tasks in dst proc that receive file from src node
        task_ids_to_dup = []
        task_ids_to_recv = []
        for linkdur in btnk_link:
            task_ids_to_dup.append(linkdur.start_task_num)
            task_ids_to_recv.append(linkdur.end_task_num)
        
        # find all parents of the to-be-duplicated tasks
        parent_tasks = set()
        for parent in tasks:
            for task_id in task_ids_to_dup:
                if self.data[parent.number][task_id] > 0:
                    parent_tasks.add(parent)
        
        # a list of file sizes to transfer from idle node to dst node
        # these are fixed on two nodes      
        files_to_dst = [] 
        # node id -> list of file sizes to transfer to idle node
        # fixed destination node but multiple source nodes
        files_from_src = {} 
        for tid_scr in task_ids_to_dup:
            for tid_dst in task_ids_to_recv:
                if self.data[tid_src][tid_dst] > 0:
                    files_to_dst.append(self.data[tid_src][tid_dst])
        for tid_scr in parent_tasks:
            for tid_dst in task_ids_to_dup:
                if self.data[tid_src][tid_dst] > 0:
                    src_proc = task_to_proc[tid_src]
                    if not src_proc in files_from_src:
                        files_from_src[src_proc] = []
                    files_from_src[src_proc].append(self.data[tid_src][tid_dst])
        
        # hashmap {idle node id to duplicate : max new time incurred}. New incurred times:
        # 1. all parent nodes to idle node link usage
        # 2. idle node computation
        # 3. idle node to destination node transfer
        procid_to_max_time = {}
        for proc in self.processors:
            if len(proc.time_line) != 0:
                continue
            else: # this is an idle node
                # get sum of computation time
                comp_time = 0
                for task_id in task_ids_to_dup:
                    comp_time = comp_time + comp_cost[task_id][proc.number]
                
                # get the max of all link transfer time
                # new node to destination node
                time_to_dst = 0.0
                for file_size in files_to_dst:
                    time_to_dst += self.cal_comm_quadratic(file_size, self.quaratic_profile[proc.number][dst_proc.number])
                        
                # all source nodes to new node
                time_from_src = []
                for key in files_from_src:
                    cur_time = 0.0
                    for file_size in files_from_src[key]:
                        cur_time += self.cal_comm_quadratic(file_size, self.quaratic_profile[key.number][proc.number])
                    time_from_src.append(cur_time)
                
                new_btnk_proc = max(time_from_src)
                new_btnk_proc = max(new_btnk_proc, time_to_dst)
                new_btnk_proc = max(new_btnk_proc, comp_time)
                
                procid_to_max_time[proc.number] = new_btnk_proc
        
        min_btnk = time.time()
        node = -1
        for key in procid_to_max_time:
            if procid_to_max_time[key] < min_btnk:
                min_btnk = procid_to_max_time[key]
                node = key
            
        if min_btnk >= btnk_time: # no point for duplication
            return (-1, time.time())
        return (node, min_btnk, task_ids_to_dup, task_ids_to_recv, list(parent_tasks))
    
    # all these params are passed by reference, thus changing them would change original ones too
    def duplicate(self, links, processors, tasks, comp_cost, data, quaratic_profile, btnk_id, new_node,
                  min_btnk, task_ids_to_dup, task_ids_to_recv, parent_tasks, task_names):
        """
        what to do in actual duplicate;
        1. update takeup times of related nodes and links, comp matrix etc
        2. read the configuration task file, override it with updated task graph
            2.1 name (create) duplicated tasks, add children
            2.2 remove children of original tasks
            2.3 add children to parent source tasks
        """
        tasks_to_dup = tasks[i for i in task_ids_to_dup]
        tasts_to_recv = tasks[i for i in task_ids_to_recv]
        
        # create tasks
        for task in tasks_to_dup:
            dup_task = hd.Task()

        config_file = 'configuration.txt'
        f = open(config_file, "r")
        # a list of strings (adjlist lines)
        graph = []
        while(1):
            line = f.readline().rstrip('\n')
            if len(line) == 0:
                break
            graph.append(line)
        print("------------------- adjList in last graph --------------------------")
        print(graph)
        
        # parent task ID from parent nodes -> child 
    
    def get_link_by_id(self, links, link_id):
        for link in links:
            if link.id == link_id:
                return link
    
    def get_proc_by_id(self, processors, proc_id):
        for proc in processors:
            if proc.number == proc_id:
                return proc
                
    def get_procs_by_tasks(self, processors):
        task_to_proc = {}
        for proc in processors:
            if len(proc.time_line) == 0:
                continue
            else:
                for duration in proc.time_line:
                    task_to_proc[duration.task_num] = proc.number
        return task_to_proc
            
    def cal_comm_quadratic(self, file_size, quaratic_profile):
        return (np.square(file_size)*quaratic_profile[0] + file_size*quaratic_profile[1] + quaratic_profile[2])
        
            
