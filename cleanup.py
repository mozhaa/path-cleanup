import argparse
import subprocess
import sys
import os
from functools import partial
from pathlib import Path
from typing import Callable, List, Tuple

try:
    from termcolor import colored
except ModuleNotFoundError:

    def colored(text: str, color: str) -> str:
        return text


def marked(text: str, marker: str) -> str:
    return f"{marker} {text}"


def color_path(text: str, status: str) -> str:
    if status == "good":
        return colored(marked(text, " "), "green")
    if status == "empty":
        return colored(marked(text, "."), "yellow")
    if status == "nonexisting":
        return colored(marked(text, "X"), "red")
    if status == "duplicate":
        return colored(marked(text, "+"), "cyan")
    return colored(marked(text, "?"), "blue")


if sys.platform == "win32":

    def get_path_and_setter(scope: str) -> List[Tuple[List[str], Callable[[List[str]], Tuple[bool, str]]]]:
        def get(target: str) -> List[str]:
            return subprocess.getoutput(
                ["powershell", "-Command", f"[Environment]::GetEnvironmentVariable('Path','{target}')"],
                encoding="utf-8",
            ).split(";")

        def set_paths(path: List[str], target: str) -> Tuple[bool, str]:
            output = subprocess.getoutput(
                [
                    "powershell",
                    "-Command",
                    f"[Environment]::SetEnvironmentVariable('Path','{';'.join(path)}','{target}')",
                ],
                encoding="utf-8"
            )
            success = not ("exception" in output.lower())
            return success, output

        result = []
        if scope == "system" or scope == "all":
            result.append((get("Machine"), partial(set_paths, target="Machine")))
        if scope == "user" or scope == "all":
            result.append((get("User"), partial(set_paths, target="User")))
        return result

else:
    raise OSError(f"This script is only for Windows (your OS is '{sys.platform}')")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Path CleanUp",
        description="Script for cleaning dead folders from PATH environment variable on Windows",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-D",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="which folders to delete from PATH\n"
        " 0 - don't delete anything (default option)\n"
        " 1 - delete non-existing folders\n"
        " 2 - delete non-existing and duplicate folders\n"
        " 3 - delete non-existing, duplicate and empty folders",
    )
    parser.add_argument("-y", action="store_true", help="skip confirmation when deleting")
    parser.add_argument(
        "-s",
        "--scope",
        type=str,
        choices=["user", "system", "all"],
        default="all",
        help="which PATH variables to modify\n"
        " user   - user-specific\n"
        " system - system-wide\n"
        " all    - both of these",
    )
    args = parser.parse_args()

    paths_and_setters = []
    paths_to_delete = []
    for paths, set_paths in get_path_and_setter(args.scope):
        result_paths = []
        result_paths_resolved = []
        for p in paths:
            path = Path(os.path.expanduser(os.path.expandvars(p))).resolve()
            if not path.exists() or p == "":
                print(color_path(p, "nonexisting"))
                if args.D < 1:
                    result_paths.append(p)
                    result_paths_resolved.append(str(path))
                else:
                    paths_to_delete.append(p)
            elif str(path) in result_paths_resolved:
                print(color_path(p, "duplicate"))
                if args.D < 2:
                    result_paths.append(p)
                    result_paths_resolved.append(str(path))
                else:
                    paths_to_delete.append(p)
            elif len(list(path.glob("*"))) == 0:
                print(color_path(p, "empty"))
                if args.D < 3:
                    result_paths.append(p)
                    result_paths_resolved.append(str(path))
                else:
                    paths_to_delete.append(p)
            else:
                print(color_path(p, "good"))
                result_paths.append(p)
                result_paths_resolved.append(str(path))
        paths_and_setters.append((result_paths, set_paths))

    print()
    if args.D > 0:
        if len(paths_to_delete) == 0:
            print("Nothing to delete")
        else:
            print("Paths to be deleted:", *paths_to_delete, sep="\n")
            if args.y:
                confirmation = "y"
            else:
                confirmation = input("\nType y/Y to accept changes, or n/N to abort: ")

            if confirmation in ["y", "Y"]:
                for paths, set_paths in paths_and_setters:
                    success, output = set_paths(paths)
                    if not success:
                        print(output)
                        raise RuntimeError("Failed to update PATH, see output above")
                print("Successfully updated PATH")
            elif confirmation in ["n", "N"]:
                print("Aborted")
            else:
                print(f"Aborted (unrecognized option - '{confirmation}')")
