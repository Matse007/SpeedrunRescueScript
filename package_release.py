import yaml
import subprocess
import pathlib
import shutil
import platform
import argparse
import PyInstaller.__main__

def main():
    with open("build_options.yml", "r") as f:
        options = yaml.safe_load(f)

    print("Building executable!")
    PyInstaller.__main__.run(["speedrunrescue.py", "-D", "--noconfirm"])

    release_name = options["release_name"]
    release_dirname = f"release_working/{release_name}"
    print(f"Creating release at {release_dirname}!")
    release_dirpath = pathlib.Path(release_dirname)
    if release_dirpath.is_dir():
        shutil.rmtree(release_dirpath)

    print("Copying over files!")
    shutil.copytree("release_info", release_dirpath)
    shutil.copytree("dist/speedrunrescue", f"{release_dirname}/bin")

    print("Creating zip archive!")
    sevenz_filename = options["sevenz_filename"]
    
    subprocess.run((sevenz_filename, "a", f"release_working/SpeedrunRescueScript_{release_name}.zip", f"./{release_dirname}/*", "-tzip", "-mx=9", "-mfb=258", "-mpass=3", "-mmt=off"), check=True)

if __name__ == "__main__":
    main()
