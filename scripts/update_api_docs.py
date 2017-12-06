import subprocess

out = subprocess.check_output(["pydocmd", "simple", "pymagicc+"])

print("\n" + out.decode("UTF-8").replace("h2", "h4").replace("h1", "h3"))
