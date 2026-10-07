from pathlib import Path
import subprocess
import sys
import unittest


repoDir = Path(__file__).resolve().parents[1]
programPath = repoDir / "evalPriority2Select.py"
exampleDir = repoDir / "examples"


class ExampleOutputTest(unittest.TestCase):
    def runCase(self, priorityName, expectedName):
        commandList = [
            sys.executable,
            "-S",
            str(programPath),
            "--tableE",
            str(exampleDir / "evalTable.md"),
            "--tableP",
            str(exampleDir / priorityName),
        ]
        completedProcess = subprocess.run(
            commandList,
            cwd=repoDir,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(completedProcess.returncode, 0)
        self.assertEqual(completedProcess.stderr, "")

        expectedText = (exampleDir / expectedName).read_text(encoding="utf-8")
        self.assertEqual(completedProcess.stdout, expectedText)

    def testExampleA(self):
        self.runCase("priorityA.md", "OselTreeA.md")

    def testExampleB(self):
        self.runCase("priorityB.md", "OselTreeB.md")


if __name__ == "__main__":
    unittest.main()
