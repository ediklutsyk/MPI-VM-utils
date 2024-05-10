import subprocess
import argparse
import os


def compile_file(file_path):
    # Check if the file exists
    if not os.path.exists(file_path):
        print("Error: File not found.")
        return
    subprocess.run(f"multipass transfer {file_path} manager:cloud", shell=True)
    full_file_name = os.path.basename(file_path)
    file_name = os.path.splitext(full_file_name)[0]
    print(f"File {full_file_name} transferred to manager.")
    # Compile file on the manager node
    subprocess.run(
        f"multipass exec manager -- mpicc -o /home/ubuntu/cloud/{file_name} /home/ubuntu/cloud/{full_file_name}",
        shell=True)


def run_mpi_program(file_name, num_threads):
    # Check if the compiled file exists
    if not subprocess.run(f"multipass exec manager -- test -f /home/ubuntu/cloud/{file_name}", shell=True).returncode == 0:
        print("Error: Compiled file not found on manager machine.")
        return

    # Construct the mpiexec command
    mpi_command = f"mpiexec -hostfile /home/ubuntu/cloud/mpi_hosts"
    if num_threads != -1:
        mpi_command += f" -n {num_threads}"

    # Run MPI program with mpiexec
    subprocess.run(f"multipass exec manager -- {mpi_command} /home/ubuntu/cloud/{file_name}", shell=True)


def main():
    parser = argparse.ArgumentParser(description='Run MPI cluster')
    parser.add_argument('--c', '-c', metavar='path_to_file.c', type=str, help='Path to the C file to compile')
    parser.add_argument('--r', '-r', metavar='file_name', type=str, help='Name of the compiled file to run')
    parser.add_argument('--n', '-n', type=int, default=-1,
                        help='Number of threads to run the MPI program with (optional)')
    args = parser.parse_args()

    if args.c:
        compile_file(args.c)
        print("File compiled successfully.")
    elif args.r:
        run_mpi_program(args.r, args.n)
    else:
        print("Please provide either --c or --r option.")


if __name__ == "__main__":
    main()
