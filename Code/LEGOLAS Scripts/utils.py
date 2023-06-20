import paramiko # for interacting over ssh

default_pi_username = "pi"
default_pi_password = "raspberry"

def find_server_pid(ssh):
    find_server_cmd = "ps aux | grep rpyc_classic"
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(find_server_cmd)
    pid = None
    try:
        """
        pi        5930  1.5  2.2  90384 18540 ?        Sl   10:05   0:28 python3 /home/pi/git/rpyc-master/bin/rpyc_classic.py --host 0.0.0.0
        pi        6380  0.0  0.0   7348   484 pts/0    S+   10:35   0:00 grep --color=au
        """        

        line = ssh_stdout.readlines()[0]
        pid = line.split()[1]
    except:
        print(line)
        print("rpyc server is not initiated.")
    return pid

def restart_server(
    host, 
    port=22, 
    username=default_pi_username, 
    password=default_pi_password):

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, port=port, allow_agent=False)    #CO20230620 - adding allow_agent=False

    find_server_cmd = "ps aux | grep rpyc_classic"
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(find_server_cmd)

    pid = find_server_pid(ssh)
    if pid is not None:
        print(f"kill server at PID:{pid}")
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(f"kill {pid}")
    else:
        print("no need to kill rpyc server")

    print(f"restarting the rpyc server at host: {host}")
    try:
        start_rpyc_cmd = "bash /home/pi/auto_rpyc_server.sh"
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(start_rpyc_cmd)
        print("rpyc server start successfully")
    except Exception as e:
        print("Unable to start the rpyc server.", e)
    # print(ssh_stdin,ssh_stdout,ssh_stderr)
