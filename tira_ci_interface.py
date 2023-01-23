#!/usr/bin/env python3
# https://github.com/tira-io/tira/blob/main/application/src/tira/templates/tira/git_task_repository_gitlab_ci.yml
import urllib.request
import argparse
import subprocess, platform
from glob import glob
from os.path import exists
import os
import shutil
from pathlib import Path
import json
import sys
from django.conf import settings
from datetime import datetime as dt
from gitlab_integration import persist_tira_metadata_for_job
from git import Repo
import string
from github import Github
from subprocess import check_output

from tira.git_integration.gitlab_integration import merge_to_main_failsave
from tira.git_integration.gitlab_integration import delete_branch_of_repository; 


EXECUTED_ON_GITHUB = False

class TiraCiInterface:
    pass

    def persist_tira_metadata_for_job_intern(run_dir, run_id, job_name):
        pass

    def execute(self, step):
        """
        Executes one of three provisioning steps, that are:
        Provisioning I:
            Prepares the local environment by branching and cloning the
            shared task’s repository and copying the test data into the local environ-
            ment (all operations are trusted).
        Provisioning II:
            Persists the run files and logs. Copies the test truth to the
            local environment for the evaluation step (all operations are trusted).
        Provisioning III:
            Persists evaluation results and logs and merges the branch
            for this software execution into the main branch (all operations are trusted)

        Parameters
        ----------
        args: str
        Arguments that specify the provisioning step to execute.
        

        Return
        ----------
        -
        """
        # implementet in this class

        if(step == 1): self.provisioning1_prepare_environment()
        elif(step == 2): self.provisioning2_persist_software_result()
        elif(step == 3): self.provisioning3_persist_evaluation_result()
        else:   
            print("Error: Step '" + str(step) + "' doesn't exist")

        return
        
    def provisioning1_prepare_environment(self):
        """
        Prepares the local environment by identifing the job to execute and 
        tests that the runner ist trustworthy (only if requiered)
        This step loads the data and sets all environment variables so that
        the user software can run in the next step.

        Parameters
        ----------
        -
        
        Return
        ----------
        -
        """
        # tira-test-runner-is-trustworthy.sh
        URLs=[  "google.com", 
                "github.com", 
                "gitlab.com", 
                "webis.de",
                "1.1.1.1"       # IP in case only the DNS is unavailable
                ]

        def _ping(host):
            """
            Returns True if host (str) responds to a ping request.
            Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
            """
            # Option for the number of packets as a function of
            param = '-n' if platform.system().lower()=='windows' else '-c'

            # Building the command. Ex: "ping -c 1 google.com"
            command = ['ping', param, '1', host]

            output = subprocess.run(command, capture_output=True, text=True)
            # since on Windows this function will still return True if you get a Destination Host unreachable error:
            if "host unreachable" in output.stderr or "host unreachable" in output.stdout:
                return False
            return output.returncode

        # test connection
        for url in URLs:
            if _ping(url) == 0: 
                print("The runner has access to the internet. I abort the run.")
                exit(1)

        #
        # tira-specify-task-to-run.py: input dataset paths anpassen für github (direkt im Repo liegend)
        #
        def find_job_to_execute():
            ret = list(glob('*/*/*/job-to-execute.txt'))
            return None if len(ret) == 0 else ret[0]

        def config(job_file):
            ret = {}
            with open(job_file, 'r') as f:
                for l in f:
                    l = l.split('=')
                    if len(l) == 2:
                        ret[l[0].strip()] = l[1].strip()
            
            return ret

        def identify_environment_variables(job_file):
            if job_file is None or not exists(job_file) or not Path(job_file).is_file():
                return ['TIRA_IMAGE_TO_EXECUTE=ubuntu:16.04']
            

            if(EXECUTED_ON_GITHUB):
                job_dir = os.getenv('GITHUB_WORKSPACE') # TODO: add import of ENV Var: GITHUB_WORKSPACE  at docker run step

            else:
                job_dir = job_file.split('/job-to-execute')[0]
                #tira_dataset_id = job_dir.split('/')[-3]
                #tira_vm_id = job_dir.split('/')[-2]
                #tira_run_id = job_dir.split('/')[-1]

            tira_dataset_id = config(job_file)['TIRA_DATASET_ID']
            tira_vm_id = config(job_file)['TIRA_VM_ID']
            tira_run_id = config(job_file)['TIRA_RUN_ID']
            
            # TODO: add TIRA_DATASET_PATH=..... to job-to-execute file.txt
            input_data_storage_path = config(job_file)['TIRA_DATASET_PATH']

            input_dataset = config(job_file)['TIRA_DATASET_TYPE'] + '-datasets/' + config(job_file)['TIRA_TASK_ID'] + '/' + tira_dataset_id + '/'
            #absolute_input_dataset = '/mnt/ceph/tira/data/datasets/' + input_dataset
            absolute_input_dataset = input_data_storage_path + input_dataset
            #input_dataset_truth = '/mnt/ceph/tira/data/datasets/' + config(job_file)['TIRA_DATASET_TYPE'] + '-datasets-truth/' + config(job_file)['TIRA_TASK_ID'] + '/' + tira_dataset_id + '/'
            input_dataset_truth_data = config(job_file)['TIRA_DATASET_TYPE'] + '-datasets-truth/' + config(job_file)['TIRA_TASK_ID'] + '/' + tira_dataset_id + '/'
            input_dataset_truth = input_data_storage_path + input_dataset_truth_data
            

            ret = [
                'TIRA_INPUT_RUN=' + absolute_input_dataset,
                'TIRA_DATASET_ID=' + tira_dataset_id,
                'TIRA_INPUT_DATASET=' + input_dataset,
                'inputDataset=' + input_dataset,
                'outputDir=' + job_dir + '/output',
                'TIRA_EVALUATION_GROUND_TRUTH=' + input_dataset_truth,
                'TIRA_EVALUATION_GROUND_TRUTH_DATA=' + input_dataset_truth_data,
                'TIRA_VM_ID=' + tira_vm_id,
                'TIRA_RUN_ID=' + tira_run_id,
                'TIRA_OUTPUT_DIR=' + job_dir + '/output',
                'TIRA_JOB_FILE=' + job_file,
            ]
            
            with open(job_file, 'r') as f:
                for l in f:
                    if '=' in l:
                        ret += [l.strip()]
            
            for i in ['TIRA_TASK_ID', 'TIRA_IMAGE_TO_EXECUTE', 'TIRA_COMMAND_TO_EXECUTE']:
                if len([j for j in ret if i in j]) != 1:
                    raise ValueError('I expected the variable "' + i + '" to be defined by the job, but it is missing.')

            if exists(absolute_input_dataset) and not exists(input_dataset):
                print(f'Copy input data from {absolute_input_dataset} to {os.path.abspath(Path(input_dataset) / "..")}', file=sys.stderr)
                shutil.copytree(absolute_input_dataset, os.path.abspath(Path(input_dataset)))
            else:
                print(f'Absolute input dataset {absolute_input_dataset} exists: {exists(absolute_input_dataset)}', file=sys.stderr)
                print(f'Relative input dataset {input_dataset} exists: {exists(input_dataset)}', file=sys.stderr)
            
            if not exists(input_dataset):
                print(f'Make input-directory: "{input_dataset}"', file=sys.stderr)
                Path(input_dataset).mkdir(parents=True, exist_ok=True)
            
            json.dump({'keep': True}, open(input_dataset + '/.keep', 'w'))
            
            return ret

        job_to_execute = find_job_to_execute()
        for i in identify_environment_variables(job_to_execute):
            print(i.strip())


        # zusätzlich von dem hochgeladenen File eingelesenes Argument: verzeichnisse für input/output (bei Gitlab Implementation bisher: CEPH)
        # job-to-execute.txt
        pass

    def provisioning2_persist_software_result(self):
        """ TODO Dane
        Persists the run files and logs at:
          - their final location(persistent) 
          - and makes them available for the evaluation container.
            Copies the test truth to the local environment for 
            the evaluation step.

        Parameters
        ----------
        args: str
        

        Return
        ----------
        -
        """
        # https://github.com/tira-io/tira/blob/main/pipelines/src/python/tira-persist-software-result.py

        def fail_if_environment_variables_are_missing():
            for v in ['TIRA_DATASET_ID', 'TIRA_VM_ID', 'TIRA_RUN_ID', 'TIRA_OUTPUT_DIR', 'TIRA_TASK_ID']:
                if v not in os.environ:
                    raise ValueError('I expect that the environment variable "' + v + '" is set, but it was absent.')

        def run_output_dir():
            return settings.TIRA_ROOT / 'data' / 'runs' / os.environ['TIRA_DATASET_ID'] / os.environ['TIRA_VM_ID'] / os.environ['TIRA_RUN_ID'] / 'output'

        def eval_dir(eval_id):
            return Path(os.environ['TIRA_OUTPUT_DIR']) / '..' / '..' / eval_id
            
        def final_eval_dir(eval_id):
            return settings.TIRA_ROOT / 'data' / 'runs' / os.environ['TIRA_DATASET_ID'] / os.environ['TIRA_VM_ID'] / eval_id

        def copy_resources():
            if exists(str(run_output_dir())):
                print(str(run_output_dir()) + " exists already. I do not overwrite.")
                return

            src = str(os.environ['TIRA_OUTPUT_DIR'])
            target = run_output_dir()
            target_without_output = str(os.path.abspath(target / '..'))
            
            if not exists(src):
                print(f'Make src-directory: "{src}"')
                Path(src).mkdir(parents=True, exist_ok=True)
            
            print(f'Make target directory: "{target_without_output}"')
            Path(target_without_output).mkdir(parents=True, exist_ok=True)
            
            print('The output dir exists: ' + str(exists(str(run_output_dir()))))
            
            shutil.copytree(src, str(target))
            self.persist_tira_metadata_for_job_intern(target_without_output, os.environ['TIRA_RUN_ID'], 'run-user-software')

        def config(job_file):
            ret = {}
            with open(job_file, 'r') as f:
                for l in f:
                    l = l.split('=')
                    if len(l) == 2:
                        ret[l[0].strip()] = l[1].strip()
            
            return ret

        def extract_evaluation_commands():
            if 'TIRA_JOB_FILE' in os.environ:
                c = config(os.environ['TIRA_JOB_FILE'])
                return {'TIRA_EVALUATION_IMAGE_TO_EXECUTE': c['TIRA_EVALUATION_IMAGE_TO_EXECUTE'], 'TIRA_EVALUATION_COMMAND_TO_EXECUTE': c['TIRA_EVALUATION_COMMAND_TO_EXECUTE'], 'TIRA_EVALUATION_SOFTWARE_ID': os.environ['TIRA_EVALUATION_SOFTWARE_ID']}
                
            if 'TIRA_EVALUATION_COMMAND_TO_EXECUTE' in os.environ and 'TIRA_EVALUATOR_TRANSACTION_ID' in os.environ and 'TIRA_EVALUATION_IMAGE_TO_EXECUTE' in os.environ:
                return {'TIRA_EVALUATION_IMAGE_TO_EXECUTE': os.environ['TIRA_EVALUATION_IMAGE_TO_EXECUTE'], 'TIRA_EVALUATION_COMMAND_TO_EXECUTE': os.environ['TIRA_EVALUATION_COMMAND_TO_EXECUTE'], 'TIRA_EVALUATION_SOFTWARE_ID': os.environ['TIRA_EVALUATION_SOFTWARE_ID']}

            return {'TIRA_EVALUATION_IMAGE_TO_EXECUTE': 'ubuntu:16.04', 'TIRA_EVALUATION_COMMAND_TO_EXECUTE': 'echo "No evaluation specified..."', 'TIRA_EVALUATION_SOFTWARE_ID': '-1'}

        def copy_to_local(absolute_src, relative_target):
            if exists(absolute_src) and not exists(relative_target):
                print(f'Copy ground data from {absolute_src} to {os.path.abspath(Path(relative_target))}')
                shutil.copytree(absolute_src, os.path.abspath(Path(relative_target)))
            
            if not exists(relative_target):
                print(f'Make empty ground directory: "{relative_target}"')
                Path(relative_target).mkdir(parents=True, exist_ok=True)
            
            json.dump({'keep': True}, open(relative_target + '/.keep', 'w'))

        def identify_environment_variables():
            eval_id = dt.now().strftime('%Y-%m-%d-%H-%M-%S')
            ret = set()
            for (k,v) in os.environ.items() :
                if k.lower().startswith('tira') and k.upper() not in ['TIRA_EVALUATION_INPUT_DIR', 'TIRA_EVALUATION_OUTPUT_DIR', 'TIRA_FINAL_EVALUATION_OUTPUT_DIR', 'TIRA_EVALUATION_IMAGE_TO_EXECUTE', 'TIRA_EVALUATION_COMMAND_TO_EXECUTE', 'TIRA_EVALUATION_SOFTWARE_ID']:
                    ret.add((k + '=' + v).strip())

            absolute_input_dataset = os.environ['TIRA_EVALUATION_GROUND_TRUTH']
            #input_dataset = absolute_input_dataset.split('/mnt/ceph/tira/data/datasets/')[1]
            input_dataset = os.environ['TIRA_EVALUATION_GROUND_TRUTH_DATA']
            copy_to_local(absolute_input_dataset, input_dataset)
            copy_to_local(str(run_output_dir()), 'local-copy-of-input-run')
            
            evaluator = extract_evaluation_commands()
            ret.add('TIRA_EVALUATION_INPUT_DIR=local-copy-of-input-run')
            ret.add('inputRun=local-copy-of-input-run')
            ret.add('TIRA_EVALUATION_OUTPUT_DIR=' + str(eval_dir(eval_id) / 'output'))
            ret.add('TIRA_FINAL_EVALUATION_OUTPUT_DIR=' + str(final_eval_dir(eval_id)))
            ret.add('inputDataset=' + input_dataset)
            ret.add('outputDir=' + str(eval_dir(eval_id) / 'output'))
            ret.add('TIRA_EVALUATION_IMAGE_TO_EXECUTE=' + evaluator['TIRA_EVALUATION_IMAGE_TO_EXECUTE'])
            ret.add('TIRA_EVALUATION_COMMAND_TO_EXECUTE=' + evaluator['TIRA_EVALUATION_COMMAND_TO_EXECUTE'])
            ret.add('TIRA_EVALUATION_SOFTWARE_ID=' + evaluator['TIRA_EVALUATION_SOFTWARE_ID'])

            return sorted(list(ret))

        if __name__ == '__main__':
            fail_if_environment_variables_are_missing()
            copy_resources()

            with open('task.env', 'w') as f:
                for l in identify_environment_variables():
                    f.write(l.strip() + '\n')

        pass

    def provisioning3_persist_evaluation_result(self):
        """ TODO Niklas
        Persists evaluation results and logs at their final location(persistent).
        Makes an GRPC Call to tell TIRA that this run ist finished and makes a
        final cleanup by:
        - merging this branch for this software execution into the main branch 
        - and deleting the branch afterwards.
        

        Parameters
        ----------
        args: str
        

        Return
        ----------
        -
        """
        # https://github.com/tira-io/tira/blob/main/pipelines/src/bash/tira-persist-evaluation-result.sh
        # abhängigkeit zu Gitlab entfernen, indem löschen des branches nicht über
        # gitlab api, sondern per git vorgenommen wird?

        #SRC_DIR=${TIRA_EVALUATION_OUTPUT_DIR} #Umgebungsvar holen
        src_dir = os.getenv('TIRA_EVALUATION_OUTPUT_DIR')

        #DIR_TO_CHANGE=$(echo ${TIRA_OUTPUT_DIR}| awk -F '/output' '{print $1}')
        dir_to_change = os.getenv('TIRA_OUTPUT_DIR').split('/output')[1]
        tira_final_evaluation_output_dir = os.getenv('TIRA_FINAL_EVALUATION_OUTPUT_DIR')
        target_file = os.getenv('TARGET_FILE')
        


        #if [ -f "${DIR_TO_CHANGE}/job-to-execute.txt" ]; then
        if os.path.isfile(dir_to_change + "/job-to-execute.txt"):

            f = open("/etc/tira-git-credentials/GITCREDENTIALUSERNAME", "r")
            username = f.read()
            f.close()

            f = open("/etc/tira-git-credentials/GITCREDENTIALPASSWORD", "r")
            password = f.read()
            f.close()

            #git remote set-url origin "https://$(cat /etc/tira-git-credentials/GITCREDENTIALUSERNAME):$(cat /etc/tira-git-credentials/GITCREDENTIALPASSWORD)@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git"
            repo = Repo( "https://" + username + ":" + password +"@" + os.getenv('CI_SERVER_HOST') + "/" + os.getenv('CI_PROJECT_PATH')+ ".git")

            #git remote get-url origin

            #git config user.email "tira-automation@tira.io"
            #git config user.name "TIRA Automation"
            repo.config_writer().set_value("user", "name", "TIRA Automation").release()
            repo.config_writer().set_value("user", "email", "tira-automation@tira.io").release()

            #TARGET_FILE="${DIR_TO_CHANGE}/job-executed-on-$(date +'%Y-%m-%d-%I-%M-%S').txt"
            target_file = dir_to_change + "/job-executed-on-" + dt.datetime.now().strftime("%Y-%m-%d-%I-%M-%S") + ".txt"

            #echo "mv ${DIR_TO_CHANGE}/job-to-execute.txt ${TARGET_FILE}"
            print("shutil.move(" + dir_to_change + "/job-to-execute.txt, " + target_file +")")
            #mv ${DIR_TO_CHANGE}/job-to-execute.txt ${TARGET_FILE}
            shutil.move(dir_to_change + "/job-to-execute.txt", target_file)

            #git rm ${DIR_TO_CHANGE}/job-to-execute.txt
            repo.index.remove(dir_to_change + "/job-to-execute.txt",working_tree = True) #Without the working_tree argument the file is left in the working tree even though it is not in the repository.
            #git add ${TARGET_FILE}
            repo.index.add(target_file)
            #git commit -m "TIRA-Automation: software was executed and evaluated." || echo "No changes to commit"
            succ = repo.index.commit("TIRA-Automation: software was executed and evaluated.")
            if not succ:
                print("No changes to commit")

            #git push -o ci.skip origin HEAD:$CI_COMMIT_BRANCH
            ci_commit_branch = os.getenv("CI_COMMIT_BRANCH")
            repo.git.push("origin", "HEAD:"+ci_commit_branch , "-o ", "ci.skip")            

            #python3 -c 'from tira.git_integration.gitlab_integration import merge_to_main_failsave; merge_to_main_failsave()'
            merge_to_main_failsave()    

        else:
            #echo "The file ${DIR_TO_CHANGE}/job-to-execute.txt does not exist, I cant change it."
            print("The file " + dir_to_change + "/job-to-execute.txt does not exist, I cant change it.")

        #if [ -f "${TIRA_FINAL_EVALUATION_OUTPUT_DIR}" ]; then
        if os.path.exists(tira_final_evaluation_output_dir):
            #echo "${TIRA_FINAL_EVALUATION_OUTPUT_DIR} exists already. Exit."
            print(tira_final_evaluation_output_dir + " exists already. Exit.")
            #exit 0
            exit(0)

        # TODO: Warum ist das doppelt?
        #if [ -d "${TIRA_FINAL_EVALUATION_OUTPUT_DIR}" ]; then
        #    echo "${TIRA_FINAL_EVALUATION_OUTPUT_DIR} exists already. Exit."
        #    exit 0
        #fi

        #mkdir -p "${SRC_DIR}"
        os.mkdir(src_dir)
        #su tira
        os.system("su tira")
        #mkdir -p "${TIRA_FINAL_EVALUATION_OUTPUT_DIR}"
        os.mkdir(tira_final_evaluation_output_dir)

        #echo "cp -r ${SRC_DIR} ${TIRA_FINAL_EVALUATION_OUTPUT_DIR}"
        print("shutil.copytree("+ src_dir + ", " + tira_final_evaluation_output_dir + ")")
        #cp -r ${SRC_DIR} ${TIRA_FINAL_EVALUATION_OUTPUT_DIR}
        shutil.copytree(src_dir, tira_final_evaluation_output_dir)

        #EVAL_RUN_ID=$(echo $TIRA_FINAL_EVALUATION_OUTPUT_DIR| awk -F '/' '{print ($NF)}')
        eval_run_id = os.getenv("TIRA_FINAL_EVALUATION_OUTPUT_DIR").split('/')[-1]

        #python3 -c "from tira.git_integration.gitlab_integration import persist_tira_metadata_for_job; persist_tira_metadata_for_job('${TIRA_FINAL_EVALUATION_OUTPUT_DIR}', '${EVAL_RUN_ID}', 'evaluate-software-result')"
        self.persist_tira_metadata_for_job_intern(tira_final_evaluation_output_dir, eval_run_id, 'evaluate-software-result')

        #su root
        os.system("su root")
        #echo "chown directories"
        print("chown directories")
        #chown -R tira:tira ${TIRA_FINAL_EVALUATION_OUTPUT_DIR}
        shutil.chown(tira_final_evaluation_output_dir, "tira", "tira")
        #chown -R tira:tira ${TIRA_FINAL_EVALUATION_OUTPUT_DIR}/../${TIRA_RUN_ID}
        shutil.chown(Path(tira_final_evaluation_output_dir) / '..' / os.environ['TIRA_RUN_ID'], "tira", "tira")

        #echo "python3 /tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id ${TIRA_VM_ID} --dataset_id ${TIRA_DATASET_ID} --run_id ${TIRA_RUN_ID} --transaction_id 1 --task confirm-run-execute"
        print("/tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id " + os.getenv('TIRA_VM_ID')+ "--dataset_id " + os.getenv('TIRA_DATASET_ID') + "--run_id " + os.getenv('TIRA_RUN_ID') + "--transaction_id 1 --task confirm-run-execute")
        #python3 /tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id ${TIRA_VM_ID} --dataset_id ${TIRA_DATASET_ID} --run_id ${TIRA_RUN_ID} --transaction_id 1 --task confirm-run-execute
        os.system("/tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id "+os.getenv('TIRA_VM_ID')+" --dataset_id "+os.getenv('TIRA_DATASET_ID')+" --run_id "+os.getenv('TIRA_RUN_ID')+" --transaction_id 1 --task confirm-run-execute")


        #echo "python3 /tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id ${TIRA_VM_ID} --dataset_id ${TIRA_DATASET_ID} --run_id ${EVAL_RUN_ID} --transaction_id  ${TIRA_EVALUATOR_TRANSACTION_ID} --task confirm-run-eval"
        print("/tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id "+ os.getenv('TIRA_VM_ID') + " --dataset_id " + os.getenv('TIRA_DATASET_ID') + "--run_id " + eval_run_id + "--transaction_id " + os.getenv('TIRA_EVALUATOR_TRANSACTION_ID') + "--task confirm-run-eval")
        #python3 /tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id ${TIRA_VM_ID} --dataset_id ${TIRA_DATASET_ID} --run_id ${EVAL_RUN_ID} --transaction_id  ${TIRA_EVALUATOR_TRANSACTION_ID} --task confirm-run-eval
        os.system("/tira/application/src/tira/git_integration/grpc_wrapper.py --input_run_vm_id "+ os.getenv('TIRA_VM_ID') + " --dataset_id "+ os.getenv('TIRA_DATASET_ID')+" --run_id "+ eval_run_id+" --transaction_id "+ os.getenv('TIRA_EVALUATOR_TRANSACTION_ID')+" --task confirm-run-eval")

        #env|grep 'TIRA' >> task.env
        _file = open('task.env', 'a')
        for k, v in os.environ.items():
            if "TIRA" in k:
                _file.write(f'{k}={v}')
        f.close()

        #python3 -c 'from tira.git_integration.gitlab_integration import delete_branch_of_repository; delete_branch_of_repository()'
        delete_branch_of_repository()




class TiraGitlabCiInterface(TiraCiInterface):

    def persist_tira_metadata_for_job_intern(run_dir, run_id, job_name):
        persist_tira_metadata_for_job(run_dir, run_id, job_name)
        return


class TiraGithubCiInterface(TiraCiInterface):

    def read_creds(name):
        return open('/etc/tira-git-credentials/' + name).read().strip()

    def github_client(self):
        self.git_token = self.read_creds('GITCREDENTIALPRIVATETOKEN')
        return Github(login_or_token = self.git_token, base_url = ('https://' + os.environ['CI_SERVER_HOST']))

        ## so war es für gitlab --> annahme wir wollen nicht alles was am Token hängt sondern nur das aus der base_url ??
        ## return gitlab.Gitlab('https://' + os.environ['CI_SERVER_HOST'], private_token=self.read_creds('GITCREDENTIALPRIVATETOKEN'))

    def persist_tira_metadata_for_job_intern(self, run_dir, run_id, job_name):
        with open(os.path.join(run_dir, 'run.prototext'), 'w') as f:
            f.write(self.run_prototext(run_id, job_name))

        with open(os.path.join(run_dir, 'file-list.txt'), 'wb') as f:
            file_list = check_output(['tree', '-ahv', os.path.join(run_dir, 'output')])
            f.write(file_list)

        with open(os.path.join(run_dir, 'stdout.txt'), 'w') as f:
            f.write(self.job_trace(job_name) + '\n')

        with open(os.path.join(run_dir, 'stderr.txt'), 'w') as f:
            f.write('################################################################\n# Executed Command\n################################################################\n'+  self.job_command(job_name) + '\n################################################################\n')

        with open(os.path.join(run_dir, 'size.txt'), 'wb') as f:
            f.write(check_output(['bash', '-c', '(du -sb "' + run_dir + '" && du -hs "' +  run_dir + '") | cut -f1']))
            f.write(check_output(['bash', '-c', 'find "' + os.path.join(run_dir, 'output') + '" -type f -exec cat {} + | wc -l']))
            f.write(check_output(['bash', '-c', 'find "' + os.path.join(run_dir, 'output') + '" -type f | wc -l']))
            f.write(check_output(['bash', '-c', 'find "' + os.path.join(run_dir, 'output') + '" -type d | wc -l']))

    def run_prototext(run_id, job_name):
        inputRun = os.environ['TIRA_RUN_ID'] if ('evaluate-software-result' == job_name) else 'none'
        software_id = os.environ['TIRA_SOFTWARE_ID'] if ('run-user-software' == job_name) else os.environ['TIRA_EVALUATION_SOFTWARE_ID']

    def job_trace(self, name):
        return self.clean_job_output(self.get_job(name).trace().decode('UTF-8'))

    def clean_job_output(self, ret):
        ret = ''.join(filter(lambda x: x in string.printable, ret.strip()))
        if '$ eval "${TIRA_COMMAND_TO_EXECUTE}"[0;m' in ret:
            return self.clean_job_suffix(ret.split('$ eval "${TIRA_COMMAND_TO_EXECUTE}"[0;m')[1])
        elif '$ eval "${TIRA_EVALUATION_COMMAND_TO_EXECUTE}"[0;m' in ret:
            return self.clean_job_suffix(ret.split('$ eval "${TIRA_EVALUATION_COMMAND_TO_EXECUTE}"[0;m')[1])
        else:
            raise ValueError('The format of the output seems to be changed...\n\n' + ret)

    def clean_job_suffix(ret):
        if "[32;1m$ env|grep 'TIRA' > task.env" in ret:
            ret = ret.split("[32;1m$ env|grep 'TIRA' > task.env")[0]
        if "section_end:" in ret:
            ret = ret.split("section_end:")[0]

        return ret.strip()

    def get_job(self, name):
        gl = self.github_client()
        repos = gl.get_user().get_repos()
        for r in repos:
            if r.id == int(os.environ['CI_PROJECT_ID']):
                wf = r.get_workflow(int(os.environ['CI_PIPELINE_ID']))

        try:
            wf
        except NameError:
            raise ValueError('I could not find the workflow.')
        else:
            runs = wf.get_runs()
            for run in runs:
                if run.name == name:
                    return run

        raise ValueError('I could not find the job trace.')

    def job_command(self, name):
        return self.clean_job_command(self.get_job(name).trace().decode('UTF-8'))

    def clean_job_command(ret):
        ret = ''.join(filter(lambda x: x in string.printable, ret.strip()))

    pass


if __name__ == "__main__": 

    # TODO: execute this Script in Github Workflow with ENV Var: THIS_IS_EXECUTED_ON_GITHUB=True
    # check if this Script is executed in a Github Workflow or a GitLab CI
    if(os.getenv('THIS_IS_EXECUTED_ON_GITHUB', default=False)):
        EXECUTED_ON_GITHUB = True

    # Create the parser
    parser = argparse.ArgumentParser(description='provisions the environment')
    # Add arguments

    # argument 'step': which phase is currently being called in the workflow/where we are located
    parser.add_argument('--step', type=int, required=True, help='provisioning step to execute')

    # Parse the arguments
    args = parser.parse_args()

    # start the interface
    if(EXECUTED_ON_GITHUB):
        tira_ci_interface = TiraGithubCiInterface()
        tira_ci_interface.execute(step=args.step)
    else:
        tira_ci_interface = TiraGitlabCiInterface()
        tira_ci_interface.execute(step=args.step)
