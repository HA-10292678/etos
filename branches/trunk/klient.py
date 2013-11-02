#!/usr/bin/env python3

import sys
import multiprocessing
from multiprocessing.managers import BaseManager
from Etos import *
import Pause
import ECarModel
import socket

registerModule(ECarModel)
registerModule(Pause)


def taskF(job_q, result_q):
    while(True):
        sim = Simulation()
        request=job_q.get()
        sim.disableLog()
        sim.setParameters(**request)
        sim.start("XML/e-car-inwest2.xml#transaction[@id='starter']") 
        ip = sys.argv[2]
        result_q.put( (request, (sim.charged_f.sum / sim.charged_h.sum, sim.batteryOut[1.0]), ip))
        print("request", request)
        
def mp_simulate(shared_job_q, shared_result_q, nprocs):
    """ Split the work with jobs in shared_job_q and results in
        shared_result_q into several processes. Launch each process with
        factorizer_worker as the worker function, and wait until all are
        finished.
    """
    procs = []
    for i in range(nprocs):
        p = multiprocessing.Process(
                target=taskF,
                args=(shared_job_q, shared_result_q))
        procs.append(p)
        p.start()

    for p in procs:
        p.join()

def make_client_manager(ip, port, authkey):
    """ Create a manager for a client. This manager connects to a server on the
        given address and exposes the get_job_q and get_result_q methods for
        accessing the shared queues from the server.
        Return a manager object.
    """
    class ServerQueueManager(BaseManager):
        pass

    ServerQueueManager.register('get_job_q')
    ServerQueueManager.register('get_result_q')

    manager = ServerQueueManager(address=(ip, port), authkey=authkey)
    manager.connect()

    print ('Client connected to %s:%s' % (ip, port))
    return manager

def runclient():
    manager = make_client_manager(sys.argv[1], 6842, b"heslo")
    job_q = manager.get_job_q()
    result_q = manager.get_result_q()
    mp_simulate(job_q, result_q, 4)
    
if __name__ == '__main__':    
    runclient()
