import subprocess
import argparse
import json
import logging
import time

logging.basicConfig(level=logging.INFO, format='-- %(message)s --')


def launch_vms(size, cpu, ram):
    logging.info(f"Launching {size} VMs with {cpu} CPUs and {ram}MB RAM each")
    for i in range(size):
        start_time = time.time()  # Record start time
        vm_name = "manager" if i == 0 else f"worker{i}"
        subprocess.run(f"multipass launch -n {vm_name} --cpus {cpu} --memory {ram}M --cloud-init cloud-init.yaml",
                       shell=True)
        elapsed_time = (time.time() - start_time)
        logging.info(f"VM {vm_name} launched successfully. Time taken: {elapsed_time:.2f} seconds")


def get_vm_ips():
    logging.info("Get information about all launched VMs using multipass list")
    result = subprocess.run("multipass list --format=json", capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        vm_info = json.loads(result.stdout)["list"]
        vm_info.sort(key=lambda vm: vm["name"])
        vm_ips = {vm["name"]: vm["ipv4"][0] for vm in vm_info if vm["state"] == "Running"}
        print(vm_ips)
        return vm_ips
    else:
        logging.error("Failed to get VM information.")


def update_etc_hosts(vm_ips):
    for name, ip in vm_ips.items():
        logging.info(f"Updating /etc/hosts on {name}")
        for other_name, other_ip in vm_ips.items():
            if name != other_name:
                subprocess.run(
                    f"multipass exec {name} -- sudo bash -c \"echo '{other_ip} {other_name}' >> /etc/hosts\"",
                    shell=True)
        logging.info(f"Updated /etc/hosts on {name}")


def generate_ssh_keys(size):
    # Generate SSH keys on each VM and store the public keys in a dictionary
    ssh_keys = {}
    for i in range(size):
        vm_name = f"manager" if i == 0 else f"worker{i}"
        logging.info(f"Generating SSH key pair on {vm_name}")
        subprocess.run(
            f"multipass exec {vm_name} -- ssh-keygen -q -t rsa -C {vm_name} -f /home/ubuntu/.ssh/id_rsa -N \"\"",
            shell=True)
        public_key = subprocess.run(f"multipass exec {vm_name} -- cat /home/ubuntu/.ssh/id_rsa.pub",
                                    capture_output=True, text=True, shell=True)
        ssh_keys[vm_name] = public_key.stdout.strip()
        logging.info(f"SSH key pair generated on {vm_name}")
    return ssh_keys


def setup_ssh_keys(ssh_keys):
    # Update authorized_keys on each VM with public keys from other nodes
    for vm_name, public_key in ssh_keys.items():
        logging.info(f"Setting up authorized keys on {vm_name}")
        for other_vm, other_key in ssh_keys.items():
            if vm_name != other_vm:
                subprocess.run(
                    f"multipass exec {vm_name} -- bash -c \"echo '{other_key}' >> /home/ubuntu/.ssh/authorized_keys\"",
                    shell=True)
                subprocess.run(
                    f"multipass exec {other_vm} -- ssh {vm_name} -q -o StrictHostKeyChecking=no echo $'#  {other_vm}'",
                    shell=True)
        logging.info(f"Finished setting up authorized keys for {vm_name}.")


def setup_nfs_server():
    logging.info("Setting up NFS server on manager")
    bash = "multipass exec manager"
    subprocess.run(f"{bash} -- mkdir /home/ubuntu/cloud", shell=True)
    exports_content = "/home/ubuntu/cloud *(rw,sync,no_root_squash,no_subtree_check)"
    subprocess.run(f"{bash} -- sudo bash -c \"echo '{exports_content}' >> /etc/exports\"", shell=True)
    subprocess.run(f"{bash} -- sudo exportfs -a", shell=True)
    subprocess.run(f"{bash} -- sudo service nfs-kernel-server restart", shell=True)


def setup_nfs_common(size):
    for i in range(1, size):
        logging.info(f"Setting up NFS common on worker{i}")
        bash = f"multipass exec worker{i}"
        subprocess.run(f"{bash} -- mkdir /home/ubuntu/cloud", shell=True)
        subprocess.run(f"{bash} -- sudo mount -t nfs manager:/home/ubuntu/cloud /home/ubuntu/cloud", shell=True)
        fstab_content = "manager:/home/ubuntu/cloud /home/ubuntu/cloud nfs"
        subprocess.run(f"{bash} -- sudo bash -c \"echo '{fstab_content}' >> /etc/fstab\"", shell=True)


def create_mpi_hosts(size):
    logging.info("Creating mpi_hosts file on manager")
    subprocess.run(f"multipass exec manager -- touch /home/ubuntu/cloud/mpi_hosts", shell=True)
    for i in range(size):
        vm_name = f"manager" if i == 0 else f"worker{i}"
        subprocess.run(f"multipass exec manager -- bash -c \"echo '{vm_name}' >> /home/ubuntu/cloud/mpi_hosts\"",
                       shell=True)
    logging.info("mpi_hosts file created on manager")


def main():
    parser = argparse.ArgumentParser(description='Setup VMs with NFS and OpenMPI')
    parser.add_argument('size', metavar="S", type=int, help='The size of the VM cluster to create')
    parser.add_argument('--cpu', type=int, default=1, help='Number of CPUs for each VM (default: 1)')
    parser.add_argument('--ram', type=int, default=1024, help='Amount of RAM in MB for each VM (default: 1024)')
    args = parser.parse_args()

    launch_vms(args.size, args.cpu, args.ram)
    vm_ips = get_vm_ips()
    update_etc_hosts(vm_ips)
    ssh_keys = generate_ssh_keys(args.size)
    setup_ssh_keys(ssh_keys)
    setup_nfs_server()
    setup_nfs_common(args.size)
    create_mpi_hosts(args.size)


if __name__ == "__main__":
    main()
