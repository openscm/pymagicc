import re
import subprocess

try:
    subprocess.run(
        "git update-index -q --refresh".split(" ")
    )
    subprocess.check_call(
        "git diff-index --quiet HEAD -- README.md".split(" ")
    )
except subprocess.CalledProcessError:
    print("README.md was edited. Please commit first.")
    import sys
    sys.exit()

regex = re.compile(r"## API([.\n]+)## License", re.MULTILINE)

out = subprocess.check_output(["pydocmd", "simple", "pymagicc+"])

with open("README.md", "r") as f:
    content = f.read()

updated  = re.sub(
    regex,
    ("## API\n\n" +
     out.decode("UTF-8").replace("h2", "h4").replace("h1", "h3") +
     "## License"),
    content
)

with open("README.md", "w") as f:
    f.write(updated)
