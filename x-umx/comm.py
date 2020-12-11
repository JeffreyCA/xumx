import nnabla as nn
from nnabla.logger import logger


def create_float_context(ctx):
    from nnabla.ext_utils import get_extension_context
    ctx_float = get_extension_context(ctx.backend[0].split(':')[
                                      0], device_id=ctx.device_id)
    return ctx_float


class CommunicatorWrapper(object):
    def __init__(self, ctx):
        try:
            import nnabla.communicators as C
            comm = C.MultiProcessDataParallelCommunicator(ctx)
            comm.init()
            self.n_procs = comm.size
            self.rank = comm.rank
            self.comm = comm
        except Exception as e:
            print(e)
            print('No communicator found. Running with a single process. If you run this with MPI processes,'
                  ' all processes will perform totally same.')
            self.n_procs = 1
            self.rank = 0
            self.comm = None

        ctx.device_id = str(int(ctx.device_id) + int(self.rank))
        self.ctx = ctx
        self.ctx_float = create_float_context(ctx)

        logger.info("[Communicator] Using gpu_id = {} as rank = {}".format(
            self.ctx.device_id, self.rank))

    def all_reduce(self, params, division, inplace):
        if self.n_procs == 1:
            # skip all reduce since no processes have to be all-reduced
            return
        self.comm.all_reduce(params, division=division, inplace=inplace)

    def all_reduced_solver_update(self, solver, division=False, inplace=True):
        if self.n_procs > 1:
            params = [
                x.grad for x in solver.get_parameters().values()]
            self.all_reduce(params, division=division, inplace=inplace)

        solver.update()

    def all_reduced_solver_update_all(self, *solvers, division=False, inplace=True):
        for solver in solvers:
            self.all_reduced_solver_update(
                solver, division=division, inplace=inplace)

    def get_all_reduce_callback(self, packing_size=2 << 20):
        callback = None
        if self.n_procs > 1:
            params = [x.grad for x in nn.get_parameters().values()]
            callback = self.comm.all_reduce_callback(
                params, packing_size)
        return callback
