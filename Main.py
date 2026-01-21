from start_up import *
from trap_hmi import *
from capturing import *
from end import *
from package_whl_installer import install_packages

if __name__ == "__main__":
    start_up("log")
    install_packages("log")
    open_trap_hmi("log")
    capturing("log")
    trap_shutdown("log",60)