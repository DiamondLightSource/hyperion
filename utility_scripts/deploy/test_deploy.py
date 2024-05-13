import subprocess

cmd = "ssh qqh35939@i03-control"
process = subprocess.Popen(
    cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
stdout, stderr = process.communicate()
if process.returncode != 0:
    print(f"Error occurred: {stderr.decode()}")
else:
    print(f"Output: {stdout.decode()}")
