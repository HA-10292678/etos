#!/usr/bin/env python3

import sys
import time
from multiprocessing import *
from multiprocessing.managers import *
import numpy as np

def make_server_manager(port, authkey):
    """ Create a manager for the server, listening on the given port.
        Return a manager object with get_job_q and get_result_q methods.
    """
    job_q = Queue()
    result_q = Queue()

    # This is based on the examples in the official docs of multiprocessing.
    # get_{job|result}_q return synchronized proxies for the actual Queue
    # objects.
    class JobQueueManager(BaseManager):pass

    JobQueueManager.register('get_job_q', callable=lambda: job_q)
    JobQueueManager.register('get_result_q', callable=lambda: result_q)

    manager = JobQueueManager(address=('', port), authkey=authkey)
    manager.start()
    print ('Server started at port %s' % port)
    return manager

def runserver():
    # Start a shared manager server and access its queues
    manager = make_server_manager(6842, b"heslo")
    shared_job_q = manager.get_job_q()
    shared_result_q = manager.get_result_q()

    tasks = [dict(cars=50, stations=s, shoppingProbability=sp) 
               for s in range(1,51,1)for sp in np.arange(0.1, 1.1, 0.1)]
    numTasks=len(tasks)
    for task in tasks:
        shared_job_q.put(task)

    # Wait until all results are ready in shared_result_q
    f = open(sys.argv[1], "wt")
    numresults = 0
    print(numTasks)
    while numresults < numTasks:
        req,result,id=shared_result_q.get()
        print(req, id, file=sys.stderr)
        print(req["stations"],req["shoppingProbability"]," ".join(str(x) for x in result), file=f)	
        f.flush()
        numresults += 1

    # Sleep a bit before shutting down the server - to give clients time to
    # realize the job queue is empty and exit in an orderly way.
    time.sleep(2)
    manager.shutdown()

if __name__ == '__main__':
    runserver()

