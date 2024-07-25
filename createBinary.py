import os
import PyInstaller.__main__
import shutil

env_path = os.environ['CONDA_PREFIX']
env_path = env_path.replace(chr(92), '/')

src_selenium_stealth = f"{env_path}/Lib/site-packages/selenium_stealth;selenium_stealth/"

PyInstaller.__main__.run(['autopay.py', '--noconfirm',
                          '--onefile', '--console',
                          '--add-data', src_selenium_stealth])