"""Launch a jupyter notebook on SLURM.

After launching, the cmd-line (MacOS + Linux) option for port forwaring will be printed.
Execute the port forwarding and then open the given http adress.

If you're finished, shut down the jupyter server by using the "quit" option in the notebook overview.
"""

import argparse
import secrets

import subprocess
import time
import warnings
import getpass

parser = argparse.ArgumentParser(description='Launch a jupyter notebook on the CML cluster')
# Central:
parser.add_argument('--conda', default='/cmlscratch/jonas0/miniconda3/envs/dl', type=str, help='Path to conda env')
parser.add_argument('--qos', default='default', type=str, help='QOS, choose default, medium, high, very_high, scav')
parser.add_argument('--gpus', default='1', type=int, help='Requested GPUs PER job')
parser.add_argument('--mem', default='32', type=int, help='Requested memory PER job')
parser.add_argument('--timelimit', default=8, type=int, help='Requested hour limit PER job')
args = parser.parse_args()

args.conda = args.conda.rstrip('/')
# Usage warnings:
if args.mem > 385:
    raise ValueError('Maximal node memory exceeded.')
if args.gpus > 8:
    raise ValueError('Maximal node GPU number exceeded.')
if args.qos == 'high' and args.gpus > 4:
    warnings.warn('QOS only allows for 4 GPUs, GPU request has been reduced to 4.')
    args.gpus = 4
if args.qos == 'medium' and args.gpus > 2:
    warnings.warn('QOS only allows for 2 GPUs, GPU request has been reduced to 2.')
    args.gpus = 2
if args.qos == 'default' and args.gpus > 1:
    warnings.warn('QOS only allows for 1 GPU, GPU request has been reduced to 1.')
    args.gpus = 1
if args.mem / args.gpus > 48:
    warnings.warn('You are oversubscribing to memory. '
                  'This might leave some GPUs idle as total node memory is consumed.')
if args.qos == 'high' and args.timelimit > 48:
    warnings.warn('QOS only allows for 48 hours. Timelimit request has been reduced to 48.')
    args.gpus = 4

username = getpass.getuser()
token = secrets.token_urlsafe(10)
authkey = secrets.token_urlsafe(5)



# 4) Construct the sbatch launch file
if args.qos == 'scav':
    cml_account = 'scavenger'
elif args.qos in ['high', 'very_high']:
    cml_account = 'tomg'
else:
    cml_account = 'cml'

SBATCH_PROTOTYPE = \
    f"""#!/bin/bash

# Lines that begin with #SBATCH specify commands to be used by SLURM for scheduling
#SBATCH --job-name=jupyter
#SBATCH --time={args.timelimit}:00:00
#SBATCH --account={cml_account}
#SBATCH --qos={args.qos if args.qos != "scav" else "scavenger"}
#SBATCH --gres=gpu:{args.gpus}
#SBATCH --cpus-per-task={min(args.gpus * 4, 32)}
#SBATCH --partition={"dpart" if args.qos != "scav" else "scavenger"}
#SBATCH --mem={args.mem}gb

#SBATCH --output .notebook_{authkey}.log

source {"/".join(args.conda.split("/")[:-2])}/etc/profile.d/conda.sh
conda activate {args.conda}

export JUPYTER_PORT=$(shuf -i 2000-65000 -n 1)
export HOSTNAME=`/bin/hostname -s`

printf "
Run this command for the ssh connection:
ssh -N -f -L localhost:${{JUPYTER_PORT}}:${{HOSTNAME}}:${{JUPYTER_PORT}} {username}@cmlsub00.umiacs.umd.edu

and open the following web adress in your local browser:
http://localhost:${{JUPYTER_PORT}}/?token={token}
" >> .notebook_{authkey}.log


jupyter notebook --no-browser --port=${{JUPYTER_PORT}} --ip ${{HOSTNAME}} --NotebookApp.token={token}

"""
# Write launch commands to file
with open(f".cml_launch_{authkey}.temp.sh", "w") as file:
    file.write(SBATCH_PROTOTYPE)


# 5) Launch

# Execute file with sbatch
output_status = subprocess.run(["/usr/bin/sbatch", f".cml_launch_{authkey}.temp.sh"], capture_output=True)
process_id = output_stats.stdout.split('Submitted batch job ')[1].split('\n')[0]
print(f'Subprocess queued with id {process_id}...')
time.sleep(1)
subprocess.run(["/usr/bin/squeue", "-u jonas0 -l"])

# 6) Print login info from logfile
with open(f'.notebook_{authkey}.log') as file:
    for line in file:
        print(line, end="")